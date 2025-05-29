"""
Asset Collector Module

Collects relevant images and video footage for content creation.
"""

import os
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union
import urllib.request
import urllib.parse
import json
import random
import base64

from loguru import logger
import requests
import numpy as np
from moviepy.editor import ColorClip, TextClip, CompositeVideoClip

from src.utils.config_loader import Config
from src.utils.file_manager import FileManager

try:
    from pexels_api import API
    PEXELS_AVAILABLE = True
except ImportError:
    PEXELS_AVAILABLE = False
    logger.warning("Pexels API not available. Install with 'pip install pexels-api' for improved asset sourcing.")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available. Install with 'pip install openai' for AI image generation.")


class AssetCollector:
    """
    Collects relevant images and video footage from various sources.
    """
    
    def __init__(self, config: Config, file_manager: Optional[FileManager] = None):
        """
        Initialize the asset collector with config.
        
        Args:
            config: Application configuration
            file_manager: File manager instance (optional)
        """
        self.config = config
        self.file_manager = file_manager
        self.pexels_client = None
        
        # Initialize Pexels client if available and API key is provided
        if PEXELS_AVAILABLE and self.config.ai.pexels_api_key:
            self.pexels_client = API(self.config.ai.pexels_api_key)

        # Initialize OpenAI client if available and API key is provided
        self.openai_client = None
        if OPENAI_AVAILABLE and self.config.ai.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=self.config.ai.openai_api_key)
            logger.debug("OpenAI client initialized")
    
    def _ensure_output_directory(self, directory: Optional[str] = None) -> str:
        """
        Ensure the output directory exists.
        
        Args:
            directory: Directory path (optional)
            
        Returns:
            Path to the output directory
        """
        if directory is None:
            if self.file_manager:
                # Use the asset directory from file manager
                directory = os.path.join(self.config.app.assets_dir, f"collected_{int(time.time())}")
            else:
                # Create a directory in the current working directory
                directory = os.path.join(os.getcwd(), "data", "assets", f"collected_{int(time.time())}")
        
        # Ensure the directory exists
        os.makedirs(directory, exist_ok=True)
        
        return directory
    
    def collect_assets(
        self, 
        search_terms: List[str], 
        num_images: int = 5, 
        num_videos: int = 3,
        output_dir: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Collect assets for video creation.
        
        Args:
            search_terms: List of search terms
            num_images: Number of images to collect per search term
            num_videos: Number of videos to collect per search term
            output_dir: Directory to save assets
            
        Returns:
            Dictionary with collected assets
        """
        # Make sure we have a valid output directory
        output_dir = self._ensure_output_directory(output_dir)
        
        # Initialize results
        results = {
            "images": [],
            "videos": []
        }
        
        # Create a set of fallback/generic search terms for backgrounds if the specific ones fail
        fallback_terms = ["background", "abstract", "texture", "gradient", "nature", "landscape", "colors"]
        
        # First try with specific search terms
        logger.info(f"Collecting assets for search terms: {search_terms}")
        
        # Collect images
        for search_term in search_terms:
            if len(results["images"]) >= num_images:
                break
                
            # Collect images for this search term
            images = self.collect_images(search_term, max_count=num_images - len(results["images"]), output_dir=output_dir)
            results["images"].extend(images)
            
            # If we still need more images, continue to next search term
            if len(results["images"]) < num_images:
                logger.debug(f"Collected {len(images)} images for '{search_term}', need {num_images - len(results['images'])} more")
            else:
                logger.debug(f"Collected enough images ({len(results['images'])})")
                break
        
        # If we still need images, try fallback terms
        if len(results["images"]) < num_images:
            logger.warning(f"Only found {len(results['images'])}/{num_images} images with specific search terms. Using generic background terms.")
            
            for term in fallback_terms:
                if len(results["images"]) >= num_images:
                    break
                    
                # Collect images for this fallback term
                images = self.collect_images(term, max_count=num_images - len(results["images"]), output_dir=output_dir)
                results["images"].extend(images)
                
                if images:
                    logger.info(f"Added {len(images)} generic background images using term '{term}'")
        
        # Collect videos
        for search_term in search_terms:
            if len(results["videos"]) >= num_videos:
                break
                
            # Collect videos for this search term
            videos = self.collect_videos(search_term, max_count=num_videos - len(results["videos"]), output_dir=output_dir)
            results["videos"].extend(videos)
            
            # If we still need more videos, continue to next search term
            if len(results["videos"]) < num_videos:
                logger.debug(f"Collected {len(videos)} videos for '{search_term}', need {num_videos - len(results['videos'])} more")
            else:
                logger.debug(f"Collected enough videos ({len(results['videos'])})")
                break
                
        # If we still need videos, try fallback terms
        if len(results["videos"]) < num_videos:
            logger.warning(f"Only found {len(results['videos'])}/{num_videos} videos with specific search terms. Using generic background terms.")
            
            for term in fallback_terms:
                if len(results["videos"]) >= num_videos:
                    break
                    
                # Collect videos for this fallback term
                videos = self.collect_videos(term, max_count=num_videos - len(results["videos"]), output_dir=output_dir)
                results["videos"].extend(videos)
                
                if videos:
                    logger.info(f"Added {len(videos)} generic background videos using term '{term}'")
        
        # Log results
        logger.info(f"Asset collection complete. Found {len(results['images'])} images and {len(results['videos'])} videos.")
        
        return results
    
    def collect_images(self, search_term: str, max_count: int = 5, output_dir: Optional[str] = None) -> List[str]:
        """
        Collect images based on a search term.
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images (optional)
            
        Returns:
            List of paths to collected images
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Try Pixabay first as the primary source
        if self.config.ai.pixabay_api_key:
            try:
                logger.debug(f"Searching Pixabay for images with term: {search_term}")
                image_paths = self._collect_pixabay_images(search_term, max_count, output_dir)
                
                if image_paths:
                    return image_paths
                    
                logger.warning(f"No images found on Pixabay for: {search_term}")
            except Exception as e:
                logger.error(f"Error collecting Pixabay images: {str(e)}")
        
        # Try Pexels as second option if available
        if PEXELS_AVAILABLE and self.pexels_client:
            try:
                logger.debug(f"Searching Pexels for images with term: {search_term}")
                image_paths = self._collect_pexels_images(search_term, max_count, output_dir)
                
                if image_paths:
                    return image_paths
                    
                logger.warning(f"No images found on Pexels for: {search_term}")
            except Exception as e:
                logger.error(f"Error collecting Pexels images: {str(e)}")
        
        # Fallback to unsplash as last option
        try:
            logger.debug(f"Searching Unsplash for images with term: {search_term}")
            image_paths = self._collect_unsplash_images(search_term, max_count, output_dir)
            
            if image_paths:
                return image_paths
                
            logger.warning(f"No images found on Unsplash for: {search_term}")
        except Exception as e:
            logger.error(f"Error collecting Unsplash images: {str(e)}")
        
        # No longer using GPT Image generation
        logger.info(f"Using only Pixabay and other standard sources for images")
        
        # If all else fails, return empty list
        logger.warning(f"Failed to collect any images for: {search_term}")
        return []
    
    def collect_videos(self, search_term: str, max_count: int = 3, output_dir: Optional[str] = None) -> List[str]:
        """
        Collect videos based on a search term.
        
        Args:
            search_term: Search term
            max_count: Maximum number of videos to collect
            output_dir: Directory to save videos (optional)
            
        Returns:
            List of paths to collected videos
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Try Pixabay first as the primary source for videos
        try:
            logger.debug(f"Searching Pixabay for videos with term: {search_term}")
            video_paths = self._collect_pixabay_videos(search_term, max_count, output_dir)
            
            if video_paths:
                return video_paths
                
            logger.warning(f"No videos found on Pixabay for: {search_term}")
        except Exception as e:
            logger.error(f"Error collecting Pixabay videos: {str(e)}")
        
        # Fallback to Pexels if available
        if PEXELS_AVAILABLE and self.pexels_client:
            try:
                logger.debug(f"Searching Pexels for videos with term: {search_term}")
                video_paths = self._collect_pexels_videos(search_term, max_count, output_dir)
                
                if video_paths:
                    return video_paths
                    
                logger.warning(f"No videos found on Pexels for: {search_term}")
            except Exception as e:
                logger.error(f"Error collecting Pexels videos: {str(e)}")
        
        # If all else fails, return empty list
        logger.warning(f"Failed to collect any videos for: {search_term}")
        return []
    
    def _collect_pexels_images(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect images from Pexels.
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images
            
        Returns:
            List of paths to collected images
        """
        if not PEXELS_AVAILABLE or not self.pexels_client:
            return []
        
        try:
            # Search for photos
            self.pexels_client.search(search_term, page=1, results_per_page=max_count)
            
            # Get photos
            photos = self.pexels_client.get_entries()
            
            # Check if we have results
            if not photos:
                return []
            
            # Download images
            image_paths = []
            
            for photo in photos[:max_count]:
                try:
                    # Generate filename
                    filename = f"pexels_{photo.id}_{uuid.uuid4().hex[:8]}.jpg"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Download the image
                    urllib.request.urlretrieve(photo.original, output_path)
                    
                    # Add to result
                    image_paths.append(output_path)
                    logger.debug(f"Downloaded Pexels image: {output_path}")
                    
                except Exception as e:
                    logger.error(f"Error downloading Pexels image: {str(e)}")
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error searching Pexels: {str(e)}")
            return []
    
    def _collect_pexels_videos(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect videos from Pexels.
        
        Args:
            search_term: Search term
            max_count: Maximum number of videos to collect
            output_dir: Directory to save videos
            
        Returns:
            List of paths to collected videos
        """
        if not PEXELS_AVAILABLE or not self.pexels_client:
            return []
        
        try:
            # Construct direct API request since the pexels-api package only supports photos
            headers = {
                "Authorization": self.config.ai.pexels_api_key
            }
            
            # Search for videos
            response = requests.get(
                f"https://api.pexels.com/videos/search?query={urllib.parse.quote(search_term)}&per_page={max_count}",
                headers=headers
            )
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Error searching Pexels videos: {response.status_code} {response.text}")
                return []
            
            # Parse response
            data = response.json()
            
            # Check if we have results
            if "videos" not in data or not data["videos"]:
                return []
            
            # Download videos
            video_paths = []
            
            for video in data["videos"][:max_count]:
                try:
                    # Find the best quality video file (prefer SD for size)
                    video_file = None
                    for file in video["video_files"]:
                        if file["quality"] == "sd" and file["file_type"] == "video/mp4":
                            video_file = file
                            break
                    
                    # If no SD, take the first mp4
                    if not video_file:
                        for file in video["video_files"]:
                            if file["file_type"] == "video/mp4":
                                video_file = file
                                break
                    
                    # Skip if no suitable file found
                    if not video_file:
                        logger.warning(f"No suitable video file found in Pexels video {video['id']}")
                        continue
                    
                    # Generate filename
                    filename = f"pexels_video_{video['id']}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Download the video
                    urllib.request.urlretrieve(video_file["link"], output_path)
                    
                    # Add to result
                    video_paths.append(output_path)
                    logger.debug(f"Downloaded Pexels video: {output_path}")
                    
                except Exception as e:
                    logger.error(f"Error downloading Pexels video: {str(e)}")
            
            return video_paths
            
        except Exception as e:
            logger.error(f"Error searching Pexels videos: {str(e)}")
            return []
    
    def _collect_unsplash_images(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect images from Unsplash (using public API, rate-limited).
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images
            
        Returns:
            List of paths to collected images
        """
        try:
            # Set up headers for a more browser-like request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Download images
            image_paths = []
            max_retries = 3
            
            # We need to make multiple requests for multiple images
            for i in range(min(max_count, 5)):  # Limit to 5 to avoid rate limiting
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        # Generate filename
                        filename = f"unsplash_{search_term.replace(' ', '_')}_{i}_{uuid.uuid4().hex[:8]}.jpg"
                        output_path = os.path.join(output_dir, filename)
                        
                        # Get a new random image with different query param to avoid caching
                        query_with_random = f"{search_term}&random={uuid.uuid4().hex[:8]}"
                        image_url = f"https://source.unsplash.com/random?{urllib.parse.quote(query_with_random)}"
                        
                        logger.debug(f"Fetching Unsplash image from: {image_url}")
                        
                        # Use session to maintain cookies
                        session = requests.Session()
                        response = session.get(image_url, headers=headers, timeout=10, allow_redirects=True)
                        
                        if response.status_code == 200:
                            # Save the image
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            
                            # Add to result
                            image_paths.append(output_path)
                            logger.debug(f"Downloaded Unsplash image: {output_path}")
                            success = True
                        else:
                            logger.warning(f"Error fetching Unsplash image (attempt {retry_count+1}): {response.status_code}")
                            retry_count += 1
                            time.sleep(2)  # Longer sleep between retries
                        
                    except Exception as e:
                        logger.error(f"Error downloading Unsplash image (attempt {retry_count+1}): {str(e)}")
                        retry_count += 1
                        time.sleep(2)
                    
                # Sleep between different images regardless of success
                time.sleep(2)
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error searching Unsplash: {str(e)}")
            return []
    
    def _collect_pixabay_videos(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect videos from Pixabay using their official API.
        
        Args:
            search_term: Search term
            max_count: Maximum number of videos to collect
            output_dir: Directory to save videos
            
        Returns:
            List of paths to collected videos
        """
        # Check if API key is available
        if not self.config.ai.pixabay_api_key:
            logger.warning("Pixabay API key not configured. Add it to your config.json file.")
            return []
        
        # Clean the API key (strip whitespace and check for issues)
        pixabay_api_key = self.config.ai.pixabay_api_key
        # Remove comments if present (e.g., "key # comment")
        if "#" in pixabay_api_key:
            pixabay_api_key = pixabay_api_key.split("#")[0].strip()
            logger.debug(f"Removed comment from Pixabay API key")
        
        pixabay_api_key = pixabay_api_key.strip()
        logger.debug(f"Using Pixabay API key: {pixabay_api_key[:5]}...{pixabay_api_key[-4:]} (Length: {len(pixabay_api_key)})")
        
        # Check for empty or invalid search terms
        if not search_term or len(search_term.strip()) == 0:
            logger.warning("Empty search term provided for Pixabay video search")
            return []
        
        # Clean and process the search term
        # Replace problematic characters and limit length
        clean_term = search_term.strip()
        clean_term = clean_term[:100]  # Limit length
        
        try:
            # Construct API URL for video search
            api_url = "https://pixabay.com/api/videos/"
            params = {
                "key": pixabay_api_key,
                "q": clean_term,
                "per_page": max(3, min(max_count, 200)),  # Ensure value is between 3-200
                "safesearch": "true",  # Ensure safe content
                "video_type": "all"    # Include all video types
            }
            
            logger.debug(f"Making Pixabay video API request for term: '{clean_term}'")
            logger.debug(f"Request URL: {api_url}")
            logger.debug(f"Request params: {params}")
            
            # Make API request
            response = requests.get(api_url, params=params)
            
            # Check response
            if response.status_code != 200:
                error_info = ""
                try:
                    error_info = response.text[:200]  # Get first 200 chars of error message
                except:
                    pass
                
                logger.error(f"Error searching Pixabay videos API: {response.status_code}, Details: {error_info}")
                
                if response.status_code == 400:
                    logger.error(f"Bad request to Pixabay video API. This may be due to invalid search terms or parameters. Search term: '{clean_term}'")
                elif response.status_code == 429:
                    logger.error("Rate limit exceeded for Pixabay API")
                
                return []
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Pixabay video API response: {str(e)}")
                return []
            
            # Check if we have results
            if "hits" not in data or not data["hits"]:
                logger.warning(f"No videos found on Pixabay API for: {clean_term}")
                return []
            
            # Log the number of results found
            logger.info(f"Found {len(data['hits'])} videos on Pixabay for '{clean_term}'")
            
            # Download videos
            video_paths = []
            
            for video_data in data["hits"][:max_count]:
                try:
                    video_id = video_data["id"]
                    
                    # Generate filename
                    filename = f"pixabay_video_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Get the best quality video URL that doesn't exceed our target dimensions
                    # Prioritize in this order: medium, small, large, tiny
                    video_url = None
                    target_width = self.config.app.video_width
                    target_height = self.config.app.video_height
                    
                    # Choose the best video size based on our target dimensions
                    if "videos" in video_data:
                        video_formats = video_data["videos"]
                        
                        # Try medium size first (1920x1080 or 1280x720)
                        if "medium" in video_formats and video_formats["medium"]["url"]:
                            video_url = video_formats["medium"]["url"]
                        
                        # If medium doesn't exist or target dimensions are smaller, try small (1280x720 or 960x540)
                        elif "small" in video_formats and video_formats["small"]["url"]:
                            video_url = video_formats["small"]["url"]
                        
                        # Try large if available (typically 3840x2160)
                        elif "large" in video_formats and video_formats["large"]["url"]:
                            video_url = video_formats["large"]["url"]
                        
                        # Last resort: tiny size (960x540 or 640x360)
                        elif "tiny" in video_formats and video_formats["tiny"]["url"]:
                            video_url = video_formats["tiny"]["url"]
                    
                    if not video_url:
                        logger.warning(f"No suitable video URL found for Pixabay video {video_id}")
                        continue
                    
                    # Download the video
                    logger.debug(f"Downloading Pixabay video from {video_url}")
                    
                    # Use requests with proper headers instead of urllib
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Referer": "https://pixabay.com/"
                    }
                    
                    video_response = requests.get(video_url, headers=headers, stream=True)
                    
                    if video_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in video_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Add to result
                        video_paths.append(output_path)
                        logger.debug(f"Downloaded Pixabay video: {output_path}")
                    else:
                        logger.error(f"Error downloading Pixabay video {video_id}: HTTP {video_response.status_code}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error downloading Pixabay video {video_id}: {str(e)}")
            
            return video_paths
            
        except Exception as e:
            logger.error(f"Error searching Pixabay API: {str(e)}")
            return []
    
    def _collect_pixabay_images(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect images from Pixabay using their official API.
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images
            
        Returns:
            List of paths to collected images
        """
        # Check if API key is available
        if not self.config.ai.pixabay_api_key:
            logger.warning("Pixabay API key not configured. Add it to your config.json file.")
            return []
        
        # Clean the API key (strip whitespace and check for issues)
        pixabay_api_key = self.config.ai.pixabay_api_key
        # Remove comments if present (e.g., "key # comment")
        if "#" in pixabay_api_key:
            pixabay_api_key = pixabay_api_key.split("#")[0].strip()
            logger.debug(f"Removed comment from Pixabay API key")
        
        pixabay_api_key = pixabay_api_key.strip()
        logger.debug(f"Using Pixabay API key: {pixabay_api_key[:5]}...{pixabay_api_key[-4:]} (Length: {len(pixabay_api_key)})")
        
        # Check for empty or invalid search terms
        if not search_term or len(search_term.strip()) == 0:
            logger.warning("Empty search term provided for Pixabay image search")
            return []
        
        # Clean and process the search term
        # Replace problematic characters and limit length
        clean_term = search_term.strip()
        clean_term = clean_term[:100]
        
        try:
            # Construct API URL for image search
            api_url = "https://pixabay.com/api/"
            
            # Properly encode parameters individually
            params = {
                "key": pixabay_api_key,
                "q": clean_term,
                "per_page": max(3, min(max_count, 200)),  # Ensure value is between 3-200
                "safesearch": "true",  # Ensure safe content
                "image_type": "all"    # Include all image types
            }
            
            logger.debug(f"Making Pixabay API request for term: '{clean_term}'")
            logger.debug(f"Request URL: {api_url}")
            logger.debug(f"Request params: {params}")
            
            # Make API request with explicit encoding
            response = requests.get(api_url, params=params)
            
            # Check response
            if response.status_code != 200:
                error_info = ""
                try:
                    error_info = response.text[:200]  # Get first 200 chars of error message
                except:
                    pass
                
                logger.error(f"Error searching Pixabay images API: {response.status_code}, Details: {error_info}")
                
                if response.status_code == 400:
                    logger.error(f"Bad request to Pixabay API. This may be due to invalid search terms or parameters. Search term: '{clean_term}'")
                elif response.status_code == 429:
                    logger.error("Rate limit exceeded for Pixabay API")
                
                return []
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Pixabay API response: {str(e)}")
                return []
            
            # Check if we have results
            if "hits" not in data or not data["hits"]:
                logger.warning(f"No images found on Pixabay API for: {clean_term}")
                return []
            
            # Log the number of results found
            logger.info(f"Found {len(data['hits'])} images on Pixabay for '{clean_term}'")
            
            # Download images
            image_paths = []
            
            for image_data in data["hits"][:max_count]:
                try:
                    image_id = image_data["id"]
                    
                    # Generate filename
                    filename = f"pixabay_image_{image_id}_{uuid.uuid4().hex[:8]}.jpg"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Get the best quality image URL for our needs
                    # Use largeImageURL for high quality
                    image_url = image_data.get("largeImageURL", image_data.get("webformatURL"))
                    
                    if not image_url:
                        logger.warning(f"No suitable image URL found for Pixabay image {image_id}")
                        continue
                    
                    # Download the image
                    logger.debug(f"Downloading Pixabay image from {image_url}")
                    
                    # Use requests with proper headers instead of urllib
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Referer": "https://pixabay.com/"
                    }
                    
                    image_response = requests.get(image_url, headers=headers, stream=True)
                    
                    if image_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in image_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Add to result
                        image_paths.append(output_path)
                        logger.debug(f"Downloaded Pixabay image: {output_path}")
                    else:
                        logger.error(f"Error downloading Pixabay image {image_id}: HTTP {image_response.status_code}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error downloading Pixabay image {image_id}: {str(e)}")
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error searching Pixabay API for images: {str(e)}")
            return []
    
    def get_stock_soundtrack(self, mood: str, duration: int, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Get a stock soundtrack based on mood.
        
        Args:
            mood: Mood of the soundtrack (e.g., upbeat, calm, dramatic)
            duration: Desired duration in seconds
            output_dir: Directory to save soundtrack (optional)
            
        Returns:
            Path to the soundtrack file or None if not found
        """
        # Not implemented yet - would require a source of royalty-free music
        logger.warning("Stock soundtrack feature not implemented yet")
        return None
    
    def generate_fallback_asset(
        self, 
        search_term: str, 
        duration: float = 5.0, 
        width: int = 1080, 
        height: int = 1920,
        output_dir: Optional[str] = None,
        skip_image_generation: bool = False
    ) -> str:
        """
        Generate a fallback asset when no images or videos are available.
        Creates a video with random colored background.
        
        Args:
            search_term: Search term to use in the text
            duration: Duration of the video in seconds
            width: Width of the video
            height: Height of the video
            output_dir: Directory to save the output file
            skip_image_generation: Skip trying to generate an image with OpenAI
            
        Returns:
            Path to the generated asset
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # No longer using OpenAI image generation, going directly to color background
        logger.info(f"Using color background for fallback asset: {search_term}")
        
        # If GPT Image failed or is not available, use original method
        # Generate a random color (but not too dark)
        color = (
            random.randint(30, 200),
            random.randint(30, 200),
            random.randint(30, 200)
        )
        
        # Create a color clip
        color_clip = ColorClip(
            size=(width, height),
            color=color,
            duration=duration
        )
        
        # No text clips needed
        
        # Use just the color clip without text overlays
        final_clip = CompositeVideoClip([color_clip])
        
        # Generate output path
        filename = f"fallback_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        # Write to file
        final_clip.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio=False,
            logger=None
        )
        
        # Close clips
        final_clip.close()
        
        logger.info(f"Generated fallback asset: {output_path}")
        return output_path
    
    def collect_fallback_assets(
        self,
        search_terms: List[str],
        num_assets: int = 3,
        duration: float = 5.0,
        output_dir: Optional[str] = None,
        skip_image_generation: bool = False
    ) -> Dict[str, List[str]]:
        """
        Generate fallback assets when API-based collection fails.
        
        Args:
            search_terms: List of search terms
            num_assets: Number of assets to generate
            duration: Duration of each asset in seconds
            output_dir: Directory to save assets
            skip_image_generation: Skip trying to generate images with OpenAI
            
        Returns:
            Dictionary with paths to generated assets
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Initialize result
        result = {
            "images": [],
            "videos": []
        }
        
        # No longer using OpenAI image generation, always skip
        logger.info("Using only color backgrounds for fallback assets")
        image_generation_failed = True  # Always skip image generation
        
        # Generate just one additional asset if needed (to limit total assets)
        if len(result["videos"]) == 0:
            # No assets yet, generate one from the first search term
            if search_terms:
                term = search_terms[0]
                try:
                    # Generate a fallback video asset
                    video_path = self.generate_fallback_asset(
                        search_term=term,
                        duration=duration,
                        width=self.config.app.video_width,
                        height=self.config.app.video_height,
                        output_dir=output_dir,
                        skip_image_generation=image_generation_failed
                    )
                    
                    if video_path:
                        result["videos"].append(video_path)
                    
                except Exception as e:
                    logger.error(f"Error generating fallback asset for {term}: {str(e)}")
        
        logger.success(f"Generated {len(result['videos'])} fallback assets")
        return result

    def _generate_ai_image(self, search_term: str, output_dir: str) -> Optional[str]:
        """
        Generate an image using OpenAI's image-1 model with fallbacks.
        
        Args:
            search_term: Description for the image to generate
            output_dir: Directory to save the generated image
            
        Returns:
            Path to the generated image or None if generation fails
        """
        if not OPENAI_AVAILABLE or not self.openai_client or not self.config.ai.openai_api_key:
            logger.warning("OpenAI not available for image generation")
            return None
        
        # Process the search term for better results
        # For financial terms, use specific imagery that works better
        financial_keywords = ["money", "saving", "budget", "finance", "invest", "financial", 
                               "wealth", "dollar", "cash", "bank", "economy"]
        
        is_financial_topic = any(keyword in search_term.lower() for keyword in financial_keywords)
        
        if is_financial_topic:
            # Use specific imagery for financial topics
            enhanced_prompts = [
                f"Stylized illustration representing {search_term}, with coins, graphs, and subtle imagery",
                f"Abstract visual metaphor of {search_term}, with graphs, charts, and financial concepts",
                f"Creative visualization of {search_term}, showing coins, wallet, and savings graphics"
            ]
        else:
            # Generic enhancement for non-financial topics
            enhanced_prompts = [
                f"High quality, visually appealing image of {search_term}, suitable as a background for a social media video",
                f"Creative illustration representing the concept of {search_term}",
                f"Stylized digital artwork depicting {search_term} for social media content"
            ]
        
        # Randomly select a prompt
        enhanced_prompt = random.choice(enhanced_prompts)
        logger.debug(f"Using AI image prompt: {enhanced_prompt}")
        
        # Use the image-1 model as specified
        models_to_try = [
            {"model": "gpt-image-1", "size": "1024x1024", "quality": "high"},  # Primary model with valid quality value
            {"model": "dall-e-2", "size": "1024x1024"},  # Fallback to older model if needed
        ]
        
        for model_config in models_to_try:
            try:
                logger.info(f"Generating image with {model_config['model']} for: {search_term}")
                
                # Prepare parameters based on the model
                generate_params = {
                    "model": model_config["model"],
                    "prompt": enhanced_prompt,
                    "size": model_config["size"],
                    "n": 1,
                }
                
                # Add quality parameter for models that support it
                if "quality" in model_config:
                    generate_params["quality"] = model_config["quality"]
                
                # Generate the image
                response = self.openai_client.images.generate(**generate_params)
                
                # Enhanced response logging
                logger.info(f"Got response from {model_config['model']}")
                logger.debug(f"Response type: {type(response)}")
                logger.debug(f"Response dir: {dir(response)}")
                logger.debug(f"Response full: {response}")
                
                # Try to access response.model and other attributes for better debugging
                try:
                    if hasattr(response, 'model'):
                        logger.debug(f"Response model: {response.model}")
                    if hasattr(response, 'created'):
                        logger.debug(f"Response created timestamp: {response.created}")
                    if hasattr(response, 'data') and response.data:
                        logger.debug(f"Response data length: {len(response.data)}")
                except Exception as attr_error:
                    logger.debug(f"Error accessing response attributes: {str(attr_error)}")
                
                # Check for valid data
                if not hasattr(response, 'data') or not response.data or len(response.data) == 0:
                    logger.warning(f"{model_config['model']} response contains no image data")
                    continue
                
                # Get image URL - with improved logging for gpt-image-1
                data_item = response.data[0]
                logger.debug(f"Data item type: {type(data_item)}")
                logger.debug(f"Data item representation: {repr(data_item)}")
                
                # Log all attributes and values if possible
                try:
                    if hasattr(data_item, '__dict__'):
                        for attr_name in dir(data_item):
                            if not attr_name.startswith('_'):
                                try:
                                    attr_value = getattr(data_item, attr_name)
                                    if not callable(attr_value):
                                        logger.debug(f"Data item attribute '{attr_name}' = {attr_value}")
                                except Exception:
                                    pass
                except Exception as attr_error:
                    logger.debug(f"Error inspecting data item attributes: {str(attr_error)}")
                
                # Debug the full data item to understand its structure
                logger.debug(f"Response data item structure: {dir(data_item)}")
                
                # More comprehensive check for various response structures
                image_url = None
                
                # Check for direct URL attribute (standard for DALL-E models)
                if hasattr(data_item, 'url') and data_item.url:
                    image_url = data_item.url
                    logger.debug(f"Found direct URL: {image_url}")
                
                # Check for revised URL attribute (might be used by gpt-image-1)
                elif hasattr(data_item, 'revised_prompt') and hasattr(data_item, 'url') and data_item.url:
                    image_url = data_item.url
                    logger.debug(f"Found URL with revised prompt: {image_url}")
                
                # Check for base64 encoded images
                elif hasattr(data_item, 'b64_json') and data_item.b64_json:
                    logger.info("Found base64 encoded image")
                    b64_data = data_item.b64_json
                    # Generate filename and save path
                    filename = f"{model_config['model']}_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Decode and save base64 image
                    try:
                        with open(output_path, "wb") as image_file:
                            image_file.write(base64.b64decode(b64_data))
                        logger.success(f"Saved base64 image to {output_path}")
                        return output_path
                    except Exception as decode_error:
                        logger.error(f"Error saving base64 image: {str(decode_error)}")
                        continue
                
                # Try accessing as a dictionary for non-standard responses
                elif hasattr(data_item, '__getitem__'):
                    try:
                        # Try common key patterns
                        for key in ['url', 'image_url', 'image_path']:
                            if key in data_item:
                                image_url = data_item[key]
                                logger.debug(f"Found URL using key '{key}': {image_url}")
                                break
                    except (TypeError, KeyError):
                        pass
                
                # If no URL found by direct methods, log detailed response and try to extract from string representation
                if not image_url:
                    logger.warning(f"{model_config['model']} direct URL extraction failed, trying string parsing")
                    logger.debug(f"Data item content: {data_item}")
                    
                    # Try to extract URL from string representation as last resort
                    try:
                        str_repr = str(data_item)
                        if 'http://' in str_repr or 'https://' in str_repr:
                            import re
                            url_matches = re.findall(r'https?://[^\s"\']+', str_repr)
                            if url_matches:
                                image_url = url_matches[0]
                                logger.debug(f"Found URL via regex: {image_url}")
                    except Exception as string_error:
                        logger.error(f"Error extracting URL from string: {str(string_error)}")
                
                # Final check if we have a valid URL
                if not image_url:
                    logger.warning(f"{model_config['model']} response missing URL or b64_json property")
                    continue
                    
                # For URL-based responses, verify we have a non-empty URL    
                if not image_url:
                    logger.warning(f"{model_config['model']} returned empty image URL")
                    continue
                
                logger.debug(f"Image URL obtained from {model_config['model']}: {image_url}")
                
                # Generate filename
                filename = f"{model_config['model']}_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
                output_path = os.path.join(output_dir, filename)
                
                # Download the image
                try:
                    # Use requests instead of urllib for better error handling
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    image_response = requests.get(image_url, headers=headers, timeout=10)
                    
                    if image_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(image_response.content)
                        logger.debug(f"Image successfully downloaded to {output_path}")
                        logger.success(f"Generated image with {model_config['model']}: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Failed to download image from {model_config['model']}: HTTP {image_response.status_code}")
                except Exception as download_error:
                    logger.error(f"Failed to download image from {model_config['model']}: {str(download_error)}")
                    continue
                
            except Exception as model_error:
                logger.error(f"Error with {model_config['model']}: {str(model_error)}")
                continue
        
        # If we got here, all models failed
        logger.error("All image generation models failed")
        return None


if __name__ == "__main__":
    # Simple test for the asset collector
    from src.utils.config_loader import ConfigLoader
    
    def test_asset_collector():
        config_loader = ConfigLoader()
        config = config_loader.get_config()
        
        collector = AssetCollector(config)
        
        search_terms = ["nature", "mountains", "sunset"]
        
        assets = collector.collect_assets(
            search_terms=search_terms,
            num_images=3,
            num_videos=2,
            output_dir="test_assets"
        )
        
        print(f"Collected assets: {assets}")
    
    # Run the test
    test_asset_collector() 