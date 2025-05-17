"""
YouTube Uploader Module

Handles authentication with YouTube API and uploading of compilation videos with metadata.
"""

import os
import time
from typing import Dict, List, Optional, Tuple

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from loguru import logger

from src.utils.file_manager import FileManager
from src.video_collection.collector import VideoMetadata


class YouTubeUploader:
    """Handles authentication and uploading to YouTube."""
    
    # OAuth2 scopes needed for YouTube uploads
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload", 
              "https://www.googleapis.com/auth/youtube"]
    
    def __init__(self, config, file_manager: Optional[FileManager] = None):
        """
        Initialize the YouTube uploader.
        
        Args:
            config: Application configuration containing YouTube settings
            file_manager: Optional file manager instance
        """
        self.config = config
        self.youtube_config = config.youtube
        self.file_manager = file_manager or FileManager()
        self.youtube = None
        
        # Create tokens directory if it doesn't exist
        os.makedirs(os.path.dirname(self.youtube_config.token_path), exist_ok=True)
    
    async def authenticate(self) -> bool:
        """
        Authenticate with the YouTube API.
        
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            credentials = None
            
            # Check if token file exists
            import json
            # Persistent YouTube OAuth: only prompt if no valid token or refresh fails
            if os.path.exists(self.youtube_config.token_path):
                logger.info("Loading credentials from token file")
                try:
                    with open(self.youtube_config.token_path, 'r') as token_file:
                        info = json.load(token_file)
                    credentials = Credentials.from_authorized_user_info(
                        info=info,
                        scopes=self.SCOPES
                    )
                except Exception as e:
                    logger.warning(f"Error loading credentials: {str(e)}")
            
            # If credentials are not valid, run the flow
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    try:
                        logger.info("Refreshing expired credentials")
                        from google.auth.transport.requests import Request
                        credentials.refresh(Request())
                        # Save refreshed credentials
                        with open(self.youtube_config.token_path, 'w') as token:
                            token.write(credentials.to_json())
                        logger.info("Refreshed and saved credentials.")
                    except Exception as e:
                        logger.error(f"Error refreshing credentials: {str(e)}")
                        credentials = None
                
                if not credentials:
                    logger.info("Getting new credentials")
                    try:
                        # Load client secrets
                        if not os.path.exists(self.youtube_config.client_secrets_path):
                            logger.error(f"Client secrets file not found: {self.youtube_config.client_secrets_path}")
                            return False
                        
                        # Run the OAuth flow
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.youtube_config.client_secrets_path, 
                            self.SCOPES
                        )
                        # This is not an awaitable method - running it normally
                        credentials = flow.run_local_server(port=0)
                        
                        # Save the credentials for future use
                        with open(self.youtube_config.token_path, 'w') as token:
                            import json
                            token.write(credentials.to_json())
                        logger.info(f"Credentials saved to {self.youtube_config.token_path}")
                    except Exception as e:
                        logger.error(f"Authentication error: {str(e)}")
                        return False
            
            # Build the YouTube API client
            self.youtube = build("youtube", "v3", credentials=credentials)
            logger.success("Successfully authenticated with YouTube API")
            return True
            
        except Exception as e:
            logger.error(f"Error in YouTube authentication: {str(e)}")
            return False
    
    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        category_id: str = "22",  # "People & Blogs" category
        privacy_status: str = "private",
        thumbnail_path: Optional[str] = None,
        notify_subscribers: bool = False
    ) -> Optional[str]:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags for the video
            category_id: YouTube category ID (default: "22" for "People & Blogs")
            privacy_status: Privacy status (options: "private", "public", "unlisted")
            thumbnail_path: Optional path to a thumbnail image
            notify_subscribers: Whether to notify subscribers
            
        Returns:
            YouTube video ID if upload was successful, None otherwise
        """
        if not self.youtube:
            logger.error("YouTube API client not initialized. Call authenticate() first.")
            return None
        
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
        
        try:
            # Prepare metadata for the video
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags or [],
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False
                }
            }
            
            # Prepare the media file
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True
            )
            
            logger.info(f"Starting upload of '{title}' to YouTube")
            
            # Create the insert request
            insert_request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Upload the video with progress tracking
            video_id = await self._upload_with_progress(insert_request)
            
            if not video_id:
                logger.error("Upload failed or was interrupted")
                return None
            
            logger.success(f"Video uploaded successfully with ID: {video_id}")
            
            # Set thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info("Setting custom thumbnail")
                self._set_thumbnail(video_id, thumbnail_path)
            
            # Get the video URL
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"Video URL: {video_url}")
            
            return video_id
            
        except HttpError as e:
            logger.error(f"HTTP error during upload: {e.resp.status} {e.content}")
            return None
        except Exception as e:
            logger.error(f"Error during video upload: {str(e)}")
            return None
    
    async def _upload_with_progress(self, insert_request) -> Optional[str]:
        """
        Execute the upload request with progress tracking.
        
        Args:
            insert_request: YouTube API insert request
            
        Returns:
            Video ID if successful, None otherwise
        """
        response = None
        error = None
        retry = 0
        retry_status_codes = [500, 502, 503, 504]
        
        while response is None:
            try:
                logger.info("Uploading file...")
                status, response = insert_request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")
            except HttpError as e:
                if e.resp.status in retry_status_codes:
                    error = f"A retriable HTTP error {e.resp.status} occurred: {e.content}"
                    retry += 1
                    if retry > 5:
                        logger.error(f"Maximum retries exceeded: {error}")
                        return None
                    logger.warning(f"{error}. Retrying...")
                    time.sleep(5 * retry)
                else:
                    logger.error(f"Non-retriable HTTP error: {e.resp.status} {e.content}")
                    return None
            except Exception as e:
                logger.error(f"Unexpected error during upload: {str(e)}")
                return None
        
        if response:
            return response.get('id')
        
        return None
    
    def _set_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """
        Set a custom thumbnail for a video.
        
        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to the thumbnail image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Setting thumbnail for video {video_id}")
            
            # Create a media upload request for the thumbnail
            media = MediaFileUpload(
                thumbnail_path,
                mimetype='image/jpeg',
                resumable=True
            )
            
            # Set the thumbnail
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()
            
            logger.success("Thumbnail set successfully")
            return True
            
        except HttpError as e:
            logger.error(f"HTTP error setting thumbnail: {e.resp.status} {e.content}")
            return False
        except Exception as e:
            logger.error(f"Error setting thumbnail: {str(e)}")
            return False
    
    def create_playlist(
        self, 
        title: str, 
        description: str = "", 
        privacy_status: str = "private"
    ) -> Optional[str]:
        """
        Create a new YouTube playlist.
        
        Args:
            title: Playlist title
            description: Playlist description
            privacy_status: Privacy status (options: "private", "public", "unlisted")
            
        Returns:
            Playlist ID if successful, None otherwise
        """
        if not self.youtube:
            logger.error("YouTube API client not initialized. Call authenticate() first.")
            return None
        
        try:
            logger.info(f"Creating playlist: {title}")
            
            # Create the playlist
            result = self.youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": description
                    },
                    "status": {
                        "privacyStatus": privacy_status
                    }
                }
            ).execute()
            
            playlist_id = result["id"]
            logger.success(f"Playlist created with ID: {playlist_id}")
            
            return playlist_id
            
        except HttpError as e:
            logger.error(f"HTTP error creating playlist: {e.resp.status} {e.content}")
            return None
        except Exception as e:
            logger.error(f"Error creating playlist: {str(e)}")
            return None
    
    def add_to_playlist(self, playlist_id: str, video_id: str) -> bool:
        """
        Add a video to a playlist.
        
        Args:
            playlist_id: YouTube playlist ID
            video_id: YouTube video ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.youtube:
            logger.error("YouTube API client not initialized. Call authenticate() first.")
            return False
        
        try:
            logger.info(f"Adding video {video_id} to playlist {playlist_id}")
            
            # Add the video to the playlist
            self.youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            
            logger.success("Video added to playlist successfully")
            return True
            
        except HttpError as e:
            logger.error(f"HTTP error adding to playlist: {e.resp.status} {e.content}")
            return False
        except Exception as e:
            logger.error(f"Error adding to playlist: {str(e)}")
            return False


# Example usage
if __name__ == "__main__":
    import asyncio
    from src.utils.config_loader import ConfigLoader
    from src.utils.logger_config import setup_logger
    
    # Setup logger
    setup_logger()
    
    async def main():
        # Load config
        config = ConfigLoader().get_config()
        
        # Create uploader
        uploader = YouTubeUploader(config)
        
        # Authenticate
        if await uploader.authenticate():
            # Example video upload
            video_id = await uploader.upload_video(
                video_path="path/to/your/video.mp4",
                title="Test Upload from TikTok Compilation Tool",
                description="This is a test upload from the TikTok Compilation Automation tool.",
                tags=["test", "tiktok", "compilation"],
                privacy_status="private"  # Use private for testing
            )
            
            if video_id:
                print(f"Upload successful! Video ID: {video_id}")
                
                # Create and add to playlist (optional)
                playlist_id = uploader.create_playlist(
                    title="TikTok Compilations",
                    description="Automated TikTok compilations"
                )
                
                if playlist_id:
                    uploader.add_to_playlist(playlist_id, video_id)
        else:
            print("Authentication failed.")
    
    # Run the async main function
    asyncio.run(main()) 