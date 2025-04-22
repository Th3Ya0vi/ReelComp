"""
YouTube Shorts Generator module.

This module handles the creation of YouTube Shorts (vertical videos)
from TikTok videos or compilations, ensuring they meet the requirements for YouTube Shorts.
"""

import os
from typing import List, Optional
from datetime import datetime

from loguru import logger
from moviepy.editor import TextClip, VideoFileClip, CompositeVideoClip, concatenate_videoclips, ColorClip
from moviepy.video.fx.resize import resize

from src.utils.config_loader import Config
from src.utils.file_manager import FileManager
from src.video_collection.collector import VideoMetadata


class ShortsGenerator:
    """
    Handles the generation of YouTube Shorts from TikTok videos.
    
    YouTube Shorts have specific requirements:
    - 9:16 aspect ratio (vertical video)
    - Max duration of 60 seconds
    """
    
    MAX_SHORT_DURATION = 60.0  # YouTube Shorts must be 60s or less

    def __init__(self, config: Optional[Config] = None, file_manager: Optional[FileManager] = None):
        """
        Initialize the YouTube Shorts generator.
        
        Args:
            config: Application configuration
            file_manager: File manager instance
        """
        from src.utils.config_loader import ConfigLoader
        
        self.config = config or ConfigLoader().get_config()
        self.file_manager = file_manager or FileManager(self.config)
    
    def _clamp_duration(self, duration: float) -> float:
        """
        Clamp the duration to the maximum allowed for YouTube Shorts.
        """
        return min(duration, self.MAX_SHORT_DURATION)

    async def create_short_from_compilation(
        self,
        compilation_path: str,
        title: str = None,
        max_duration: float = 59.0,
        include_branding: bool = True
    ) -> Optional[str]:
        """
        Create a YouTube Short from a compilation video.
        
        Args:
            compilation_path: Path to the compilation video
            title: Title for the Short
            max_duration: Maximum duration for the Short in seconds
            include_branding: Whether to include branding on the Short
            
        Returns:
            Path to the created Short, or None if creation failed
        """
        try:
            # Ensure the compilation video exists
            if not os.path.exists(compilation_path):
                logger.error(f"Compilation video not found: {compilation_path}")
                return None
            
            logger.info(f"Creating YouTube Short from compilation video: {compilation_path}")
            
            # Generate output path for the Short
            timestamp = int(datetime.now().timestamp())
            if title:
                # Create safe filename from title
                safe_title = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in title)
                safe_title = safe_title.strip().replace(' ', '_')
                short_path = os.path.join(self.config.app.shorts_dir, f"short_{safe_title}_{timestamp}.mp4")
            else:
                short_path = os.path.join(self.config.app.shorts_dir, f"compilation_short_{timestamp}.mp4")
            
            # Load the compilation video
            with VideoFileClip(compilation_path) as clip:
                # Always clamp max_duration to 59.0s for Shorts
                max_duration = min(59.0, self._clamp_duration(max_duration))
                # Enforce Shorts duration limit
                if clip.duration > max_duration:
                    logger.warning(f"Shorts upload duration limit is 59s. Truncating {clip.duration:.1f}s to 59.0s.")
                    clip = clip.subclip(0, max_duration)
                
                # Ensure vertical format (9:16 aspect ratio)
                width, height = clip.size
                
                # If the video is horizontal, crop it to make it vertical
                if width > height:
                    # Calculate the new width to make it vertical (9:16 ratio)
                    new_width = int(height * 9 / 16)
                    # Crop from the center
                    x1 = max(0, int((width - new_width) / 2))
                    clip = clip.crop(x1=x1, y1=0, x2=x1+new_width, y2=height)
                    logger.info(f"Cropped horizontal video to vertical format: {new_width}x{height}")
                
                # Add branding if requested
                if include_branding:
                    clip = await self._add_branding_to_short(
                        clip=clip,
                        creator="TikTok Weekly Top",
                        title=title
                    )
                
                # Write the Short
                clip.write_videofile(
                    short_path,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=os.path.join(self.config.app.temp_dir, "temp_audio.m4a"),
                    remove_temp=True,
                    preset="ultrafast",  # Use "medium" or "slow" for final production
                    threads=4,
                    logger=None  # Suppress moviepy's verbose logging
                )
            
            logger.success(f"Created YouTube Short from compilation: {short_path}")
            return short_path
            
        except Exception as e:
            logger.error(f"Error creating Short from compilation: {str(e)}")
            return None
    
    async def create_shorts_from_videos(
        self,
        video_metadata_list: List[VideoMetadata],
        max_duration: float = 59.0,
        include_branding: bool = True
    ) -> List[str]:
        # Clamp max_duration to Shorts limit
        max_duration = self._clamp_duration(max_duration)
        """
        Create YouTube Shorts from a list of TikTok videos.
        
        Args:
            video_metadata_list: List of video metadata
            max_duration: Maximum duration for Shorts in seconds
            include_branding: Whether to include branding on the Shorts
            
        Returns:
            List of paths to the created Shorts
        """
        shorts_paths = []
        
        logger.info(f"Generating YouTube Shorts from {len(video_metadata_list)} videos")
        
        for video_metadata in video_metadata_list:
            try:
                # Ensure the video exists
                if not video_metadata.local_path or not os.path.exists(video_metadata.local_path):
                    logger.warning(f"Video file not found: {video_metadata.local_path}")
                    continue
                
                # Create short
                short_path = await self._create_short(
                    video_metadata=video_metadata,
                    max_duration=max_duration,
                    include_branding=include_branding
                )
                
                if short_path:
                    shorts_paths.append(short_path)
                    logger.success(f"Created YouTube Short: {short_path}")
                
            except Exception as e:
                logger.error(f"Error creating Short from {video_metadata.local_path}: {str(e)}")
        
        return shorts_paths
    
    async def _create_short(
        self,
        video_metadata: VideoMetadata,
        max_duration: float = 59.0,
        include_branding: bool = True
    ) -> Optional[str]:
        # Clamp max_duration to Shorts limit
        max_duration = self._clamp_duration(max_duration)
        """
        Create a YouTube Short from a TikTok video.
        
        Args:
            video_metadata: Video metadata
            max_duration: Maximum duration for Shorts in seconds
            include_branding: Whether to include branding on the Short
            
        Returns:
            Path to the created Short, or None if creation failed
        """
        try:
            # Generate output path
            short_path = self.file_manager.get_short_path(
                video_id=video_metadata.id,
                title=video_metadata.desc or video_metadata.author
            )
            
            # Load the video
            with VideoFileClip(video_metadata.local_path) as clip:
                # Trim video if needed
                if clip.duration > max_duration:
                    logger.info(f"Trimming video from {clip.duration:.1f}s to {max_duration:.1f}s")
                    clip = clip.subclip(0, max_duration)
                
                # Add branding if requested
                if include_branding:
                    clip = await self._add_branding_to_short(
                        clip=clip,
                        creator=video_metadata.author or "TikTok Creator"
                    )
                
                # Write the Short
                clip.write_videofile(
                    short_path,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=os.path.join(self.config.app.temp_dir, "temp_audio.m4a"),
                    remove_temp=True,
                    preset="ultrafast",  # Use "medium" or "slow" for final production
                    threads=4,
                    logger=None  # Suppress moviepy's verbose logging
                )
            
            return short_path
            
        except Exception as e:
            logger.error(f"Error creating Short: {str(e)}")
            return None
    
    async def _add_branding_to_short(
        self,
        clip: VideoFileClip,
        creator: str,
        title: str = None
    ) -> CompositeVideoClip:
        """
        Add branding overlay to a Short.
        
        Args:
            clip: Video clip
            creator: Original creator's handle
            title: Optional title to display on the video
            
        Returns:
            Video clip with branding
        """
        try:
            # Create branding elements
            width, height = clip.size
            fontsize = int(height * 0.035)  # Scale font size based on video height
            elements = [clip]
            
            # Credit to original creator at the top
            creator_text = TextClip(
                f"@{creator}",
                fontsize=fontsize,
                color="white",
                font="Arial-Bold",
                stroke_color="black",
                stroke_width=1
            )
            creator_text = creator_text.set_position(("center", height * 0.05)).set_duration(clip.duration)
            elements.append(creator_text)
            
            # Add "Watch full video" text as a prominent call-to-action that stays on screen the entire time
            # First, create a semi-transparent black background box - make it wider
            bg_width = int(width * 0.95)  # 95% of video width
            bg_height = int(height * 0.09)  # 9% of video height
            
            # Position the banner higher up from the bottom
            banner_y_position = height * 0.85 
            
            bg_clip = ColorClip(
                size=(bg_width, bg_height),
                color=(0, 0, 0)
            )
            bg_clip = bg_clip.set_opacity(0.7)  # Semi-transparent
            bg_clip = bg_clip.set_position(("center", banner_y_position - bg_height/2))
            bg_clip = bg_clip.set_duration(clip.duration)
            elements.append(bg_clip)
            
            # Create the text on top of the background - slightly smaller font
            watch_text = TextClip(
                "WATCH FULL VIDEO ON YOUTUBE",
                fontsize=int(fontsize * 1.0),  # Reduced from 1.2
                color="#FF0000",  # YouTube red
                font="Arial-Bold",
                stroke_color="white",
                stroke_width=2
            )
            
            # Position at the same height as the background
            watch_text = watch_text.set_position(("center", banner_y_position))
            watch_text = watch_text.set_duration(clip.duration)
            elements.append(watch_text)
            
            # Create composite
            branded_clip = CompositeVideoClip(elements)
            
            return branded_clip
            
        except Exception as e:
            logger.warning(f"Failed to add branding to Short: {str(e)}")
            return clip


if __name__ == "__main__":
    """Test the ShortsGenerator class."""
    import asyncio
    from src.utils.logger_config import setup_logger
    
    # Setup logging
    setup_logger("DEBUG")
    
    # Example video metadata
    test_metadata = VideoMetadata(
        id="test_video_id",
        author="test_user",
        desc="Test video",
        create_time=int(datetime.now().timestamp()),
        duration=30.0,
        height=1920,
        width=1080,
        cover="https://example.com/cover.jpg",
        download_url="https://example.com/video.mp4",
        play_url="https://example.com/video.mp4",
        music_author="test_music_author",
        music_title="test_music_title",
        url="https://www.tiktok.com/@user/video/test_video_id",
        local_path="data/downloaded_videos/test_video.mp4"
    )
    
    async def test_shorts_generator():
        # Initialize shorts generator
        shorts_generator = ShortsGenerator()
        
        # Test creating Short from individual video
        short_path = await shorts_generator._create_short(
            video_metadata=test_metadata,
            max_duration=59.0,
            include_branding=True
        )
        
        if short_path:
            logger.success(f"Created Short from individual video: {short_path}")
        else:
            logger.error("Failed to create Short from individual video")
            
        # Test creating Short from compilation
        compilation_path = "data/compilations/compilation_example.mp4"
        if os.path.exists(compilation_path):
            comp_short_path = await shorts_generator.create_short_from_compilation(
                compilation_path=compilation_path,
                title="Weekly Highlights",
                max_duration=59.0,
                include_branding=True
            )
            
            if comp_short_path:
                logger.success(f"Created Short from compilation: {comp_short_path}")
            else:
                logger.error("Failed to create Short from compilation")
    
    # Run test
    asyncio.run(test_shorts_generator()) 