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
    
    async def create_multi_clip_short(
        self,
        video_metadata_list: List[VideoMetadata],
        title: str = None,
        max_duration: float = 59.0,
        max_clips: int = 8,
        clip_duration: float = 7.0,
        include_branding: bool = True
    ) -> Optional[str]:
        """
        Create a YouTube Short composed of multiple clips from different videos.
        This ensures we have multiple clips in the Short while staying under the 60 second limit.
        
        Args:
            video_metadata_list: List of video metadata to use for clips
            title: Title for the Short
            max_duration: Maximum total duration for the Short in seconds (must be <= 60s)
            max_clips: Maximum number of clips to include
            clip_duration: Target duration for each clip in seconds
            include_branding: Whether to include branding on the Short
            
        Returns:
            Path to the created multi-clip Short, or None if creation failed
        """
        try:
            if not video_metadata_list:
                logger.error("No videos provided for multi-clip Short")
                return None
                
            # Clamp max_duration to ensure we stay under YouTube Shorts limit
            max_duration = min(59.0, self._clamp_duration(max_duration))
            
            logger.info(f"Creating multi-clip YouTube Short from {len(video_metadata_list)} videos")
            
            # Generate output path for the Short
            timestamp = int(datetime.now().timestamp())
            if title:
                # Create safe filename from title
                safe_title = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in title)
                safe_title = safe_title.strip().replace(' ', '_')
                short_path = os.path.join(self.config.app.shorts_dir, f"multi_short_{safe_title}_{timestamp}.mp4")
            else:
                short_path = os.path.join(self.config.app.shorts_dir, f"multi_clip_short_{timestamp}.mp4")
            
            # Filter out videos that don't exist
            valid_videos = []
            for vm in video_metadata_list:
                if not vm.local_path:
                    logger.warning(f"Skipping video with no local path: {vm.id}")
                    continue
                    
                if not os.path.exists(vm.local_path):
                    logger.warning(f"Skipping video with non-existent path: {vm.local_path}")
                    continue
                    
                # Try to open the video file to verify it's valid
                try:
                    with VideoFileClip(vm.local_path) as test_clip:
                        # Check if the clip can be loaded and has frames
                        if test_clip.duration <= 0:
                            logger.warning(f"Skipping video with invalid duration: {vm.local_path}")
                            continue
                            
                        # Try to access a frame to verify the clip is valid
                        try:
                            test_clip.get_frame(0)
                            valid_videos.append(vm)
                            logger.debug(f"Verified valid video: {vm.local_path} (duration: {test_clip.duration:.1f}s)")
                        except Exception as e:
                            logger.warning(f"Skipping video that can't be read: {vm.local_path} - {str(e)}")
                            continue
                except Exception as e:
                    logger.warning(f"Failed to load video {vm.local_path}: {str(e)}")
                    continue
            
            if not valid_videos:
                logger.error("No valid videos found for multi-clip Short")
                return None
                
            # Limit number of clips to process
            selected_videos = valid_videos[:max_clips]
            logger.info(f"Selected {len(selected_videos)} valid videos for processing")
            
            # Calculate how many seconds per clip to stay under max_duration
            total_clips = min(len(selected_videos), max_clips)
            seconds_per_clip = min(clip_duration, max_duration / total_clips)
            
            logger.info(f"Using {total_clips} clips with {seconds_per_clip:.1f}s per clip")
            
            # List to store all clips
            final_clips = []
            current_duration = 0
            
            # Process each video
            for i, metadata in enumerate(selected_videos):
                try:
                    # Skip if we've reached max duration
                    if current_duration >= max_duration:
                        break
                        
                    # Calculate how much time we have left
                    remaining_duration = max_duration - current_duration
                    
                    # If we don't have enough time for a full clip, adjust duration
                    clip_time = min(seconds_per_clip, remaining_duration)
                    if clip_time < 1.0:  # Skip if less than 1 second available
                        continue
                    
                    logger.info(f"Processing clip {i+1}/{len(selected_videos)}: {metadata.id}")
                    
                    # Load the video
                    clip = None
                    try:
                        clip = VideoFileClip(metadata.local_path)
                        
                        # Verify clip loaded correctly
                        if clip is None or clip.duration <= 0:
                            logger.warning(f"Skipping video with invalid duration: {metadata.local_path}")
                            continue
                            
                        # Try to access a frame to verify
                        try:
                            clip.get_frame(0)
                        except Exception as e:
                            logger.warning(f"Skipping video that can't be read: {metadata.local_path} - {str(e)}")
                            if clip:
                                clip.close()
                            continue
                                
                        # Select a section from the video
                        selected_clip = None
                        if clip.duration <= clip_time:
                            # Use the entire clip if it's short enough
                            selected_clip = clip.copy()
                        else:
                            # Try to use a section from the middle for more interesting content
                            # Avoid the first and last few seconds where intro/outro might be
                            start_time = min(2.0, clip.duration * 0.2)
                            usable_duration = clip.duration - start_time - 1.0
                            if usable_duration <= 0:
                                start_time = 0
                                usable_duration = clip.duration
                                
                            segment_duration = min(clip_time, usable_duration)
                            selected_clip = clip.subclip(start_time, start_time + segment_duration)
                        
                        # Verify subclip worked
                        if selected_clip is None:
                            logger.warning(f"Failed to create subclip from {metadata.local_path}")
                            clip.close()
                            continue
                        
                        # Ensure vertical format (9:16 aspect ratio)
                        width, height = selected_clip.size
                        
                        # If the video is horizontal, crop it to make it vertical
                        if width > height:
                            # Calculate the new width to make it vertical (9:16 ratio)
                            new_width = int(height * 9 / 16)
                            # Crop from the center
                            x1 = max(0, int((width - new_width) / 2))
                            try:
                                selected_clip = selected_clip.crop(x1=x1, y1=0, x2=x1+new_width, y2=height)
                            except Exception as e:
                                logger.warning(f"Failed to crop clip: {str(e)}")
                                selected_clip.close()
                                clip.close()
                                continue
                        
                        # Add creator name/branding if requested
                        if include_branding:
                            try:
                                branded_clip = await self._add_branding_to_short(
                                    clip=selected_clip,
                                    creator=metadata.author or "TikTok Creator",
                                    title=metadata.desc
                                )
                                
                                if branded_clip is None:
                                    logger.warning(f"Failed to add branding to clip from {metadata.local_path}")
                                    selected_clip.close()
                                    clip.close()
                                    continue
                                    
                                selected_clip = branded_clip
                            except Exception as e:
                                logger.warning(f"Error adding branding: {str(e)}, continuing with unbranded clip")
                                # Continue with unbranded clip rather than failing
                        
                        # Store processed clip
                        final_clips.append(selected_clip)
                        current_duration += selected_clip.duration
                        logger.info(f"Added clip from {metadata.id} (duration: {selected_clip.duration:.1f}s, " 
                                    f"total: {current_duration:.1f}s/{max_duration:.1f}s)")
                                    
                        # Close the original clip as we've made a copy
                        clip.close()
                        
                    except Exception as e:
                        logger.error(f"Error processing clip {metadata.id}: {str(e)}")
                        if clip:
                            try:
                                clip.close()
                            except:
                                pass
                        continue
                
                except Exception as e:
                    logger.error(f"Error processing clip {metadata.id}: {str(e)}")
                    continue
            
            # Check if we have any clips
            if not final_clips:
                logger.error("No valid clips were created for multi-clip Short")
                return None
                
            # Add title slide at the beginning if needed
            if title:
                try:
                    # Create vertical title slide (9:16 aspect ratio)
                    title_width = 1080
                    title_height = 1920
                    
                    # Create title text
                    txt_clip = TextClip(
                        title,
                        fontsize=70,
                        color="white",
                        font="Arial",
                        bg_color="black",
                        align="center",
                        size=(title_width - 100, None)  # Leave some margin
                    )
                    txt_clip = txt_clip.set_position("center")
                    
                    # Create a background
                    bg_clip = ColorClip(
                        size=(title_width, title_height),
                        color=(0, 0, 0)
                    )
                    
                    # Set duration for the title (shorter for shorts)
                    title_duration = min(2.0, max_duration * 0.1)
                    txt_clip = txt_clip.set_duration(title_duration)
                    bg_clip = bg_clip.set_duration(title_duration)
                    
                    # Combine text and background
                    title_clip = CompositeVideoClip([bg_clip, txt_clip])
                    final_clips.insert(0, title_clip)
                    current_duration += title_duration
                    
                    logger.info(f"Added title slide with duration {title_duration:.1f}s")
                except Exception as e:
                    logger.warning(f"Failed to create title slide: {str(e)}")
                    # Continue without title slide rather than failing
            
            # Final check on total duration
            if current_duration > max_duration:
                logger.warning(f"Total duration {current_duration:.1f}s exceeds limit of {max_duration:.1f}s")
                while final_clips and current_duration > max_duration:
                    # Remove clips from the end until we're under the limit
                    removed_clip = final_clips.pop()
                    current_duration -= removed_clip.duration
                    logger.info(f"Removed clip to meet duration limit (new total: {current_duration:.1f}s)")
            
            if not final_clips:
                logger.error("No clips left after duration adjustments")
                return None
                
            # Double-check all clips for validity
            valid_final_clips = []
            DEFAULT_FPS = 30.0  # Default to 30fps if no fps detected
            used_fps = DEFAULT_FPS
            
            for i, clip in enumerate(final_clips):
                try:
                    # Verify clip is valid and has frames
                    clip.get_frame(0)
                    
                    # Check if the clip has a valid fps, if not set a default
                    if not hasattr(clip, 'fps') or clip.fps is None or clip.fps <= 0:
                        logger.warning(f"Clip {i} has no valid fps, setting to {DEFAULT_FPS}")
                        clip.fps = DEFAULT_FPS
                    else:
                        # Keep track of a valid fps we've found (prefer the first clip's fps)
                        if used_fps == DEFAULT_FPS:
                            used_fps = clip.fps
                            
                    valid_final_clips.append(clip)
                except Exception as e:
                    logger.warning(f"Removing invalid clip at position {i}: {str(e)}")
                    try:
                        clip.close()
                    except:
                        pass
            
            if not valid_final_clips:
                logger.error("No valid clips left for final video")
                return None
                
            # Ensure all clips have the same fps to avoid problems during concatenation
            for clip in valid_final_clips:
                if clip.fps != used_fps:
                    logger.info(f"Adjusting clip fps from {clip.fps} to {used_fps}")
                    clip.fps = used_fps
                
            # Concatenate all clips
            logger.info(f"Concatenating {len(valid_final_clips)} video clips (total duration: {current_duration:.1f}s) with fps={used_fps}")
            
            try:
                final_short = concatenate_videoclips(valid_final_clips, method="chain")
                
                # Ensure the final clip has a valid fps
                if not hasattr(final_short, 'fps') or final_short.fps is None or final_short.fps <= 0:
                    logger.warning(f"Final clip has no valid fps, setting to {used_fps}")
                    final_short.fps = used_fps
                
                # Write the final Short with explicit fps parameter
                final_short.write_videofile(
                    short_path,
                    fps=used_fps,  # Explicitly provide fps parameter
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=os.path.join(self.config.app.temp_dir, "temp_audio.m4a"),
                    remove_temp=True,
                    preset="ultrafast",  # Use "medium" or "slow" for final production
                    threads=4,
                    logger=None  # Suppress moviepy's verbose logging
                )
                
                # Close all clips to free resources
                for clip in valid_final_clips:
                    try:
                        clip.close()
                    except:
                        pass
                    
                logger.success(f"Created multi-clip YouTube Short: {short_path} (duration: {current_duration:.1f}s)")
                return short_path
            except Exception as e:
                logger.error(f"Error during final video creation: {str(e)}")
                # Close all clips if concatenation failed
                for clip in valid_final_clips:
                    try:
                        clip.close()
                    except:
                        pass
                return None
            
        except Exception as e:
            logger.error(f"Error creating multi-clip Short: {str(e)}")
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
    ) -> Optional[CompositeVideoClip]:
        """
        Add branding overlay to a Short.
        
        Args:
            clip: Video clip
            creator: Original creator's handle
            title: Optional title to display on the video
            
        Returns:
            Video clip with branding or None if branding failed
        """
        try:
            # Verify clip is valid
            if clip is None:
                logger.error("Cannot add branding to None clip")
                return None
                
            # Try to access a frame to verify the clip is valid
            try:
                clip.get_frame(0)
            except Exception as e:
                logger.error(f"Cannot add branding to invalid clip: {str(e)}")
                return None
                
            # Store the original clip's fps for later use
            original_fps = getattr(clip, 'fps', None)
            if original_fps is None or original_fps <= 0:
                original_fps = 30.0  # Default to 30fps if not available
                logger.warning(f"Clip has no valid fps, using default: {original_fps}")
                clip.fps = original_fps
                
            # Create branding elements
            width, height = clip.size
            fontsize = int(height * 0.035)  # Scale font size based on video height
            elements = [clip]
            
            # Credit to original creator at the top
            try:
                # Clean up creator string
                if creator:
                    creator = str(creator).strip()
                    if not creator.startswith('@') and not creator.startswith('#'):
                        creator = f"@{creator}"
                else:
                    creator = "@TikTokCreator"
                    
                creator_text = TextClip(
                    creator,
                    fontsize=fontsize,
                    color="white",
                    font="Arial-Bold",
                    stroke_color="black",
                    stroke_width=1
                )
                creator_text = creator_text.set_position(("center", height * 0.05)).set_duration(clip.duration)
                elements.append(creator_text)
            except Exception as e:
                logger.warning(f"Failed to create creator text: {str(e)}")
                # Continue without creator text rather than failing
            
            # Add "Watch full video" text as a prominent call-to-action
            try:
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
            except Exception as e:
                logger.warning(f"Failed to create call-to-action banner: {str(e)}")
                # Continue without banner rather than failing completely
            
            # Create composite
            try:
                branded_clip = CompositeVideoClip(elements)
                
                # Ensure the composite clip has the same fps as the original
                branded_clip.fps = original_fps
                
                return branded_clip
            except Exception as e:
                logger.error(f"Failed to create composite clip: {str(e)}")
                # If we can't create the composite, return the original clip
                return clip
            
        except Exception as e:
            logger.warning(f"Failed to add branding to Short: {str(e)}")
            # Return original clip if branding fails
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