#!/usr/bin/env python3
"""
Test script for FPS handling in video processing.
This script tests the ability to handle videos with missing FPS attributes.
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path

# Add the parent directory to the path to import from src
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
import ffmpeg
from moviepy.editor import VideoFileClip, ColorClip
from src.video_processing.shorts_generator import ShortsGenerator
from src.video_collection.collector import VideoMetadata
from src.utils.logger_config import setup_logger
from src.utils.config_loader import ConfigLoader


def create_test_video_without_fps():
    """
    Create a test video without FPS metadata for testing.
    
    Returns:
        Path to the test video file
    """
    try:
        # Create a directory for temporary test videos
        test_dir = Path("data/test_videos")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a temporary video file
        temp_file = test_dir / "test_video_no_fps.mp4"
        
        # Create a simple color clip without specifying FPS
        # Note: Even though we don't set fps here, moviepy will use a default
        # to write the file, but we'll manipulate it afterward
        clip = ColorClip(size=(640, 480), color=(255, 0, 0), duration=5)
        
        # Write the clip to the file with a specified fps
        clip.write_videofile(
            str(temp_file),
            fps=24,
            codec="libx264",
            audio=False,
            logger=None
        )
        
        logger.info(f"Created test video: {temp_file}")
        
        # Now try loading the clip and check its fps
        with VideoFileClip(str(temp_file)) as loaded_clip:
            if hasattr(loaded_clip, 'fps') and loaded_clip.fps is not None:
                logger.info(f"Test video has fps: {loaded_clip.fps}")
                
                # Now we need to create a version without FPS metadata
                # This requires using ffmpeg directly to manipulate the metadata
                temp_file_no_fps = test_dir / "test_video_no_fps_manipulated.mp4"
                
                # Use ffmpeg to copy the video without fps information
                # This is a bit tricky but we'll use a combination of options that
                # results in undefined fps in the output
                try:
                    (
                        ffmpeg
                        .input(str(temp_file))
                        .output(str(temp_file_no_fps), c='copy', vsync='0', **{'fpsmax': '0'})
                        .run(quiet=True, overwrite_output=True)
                    )
                    
                    logger.info(f"Created manipulated test video: {temp_file_no_fps}")
                    return str(temp_file_no_fps)
                except Exception as e:
                    logger.error(f"Failed to create manipulated test video: {e}")
                    return str(temp_file)
            else:
                logger.warning("Original test video already has no fps metadata")
                return str(temp_file)
                
    except Exception as e:
        logger.error(f"Error creating test video: {e}")
        return None


async def test_fps_handling():
    """Test handling of videos without fps attributes."""
    # Setup logger
    setup_logger("DEBUG")
    
    # Initialize config
    config = ConfigLoader().get_config()
    
    # Initialize shorts generator
    shorts_generator = ShortsGenerator(config)
    
    # Create a test video without FPS
    test_video_path = create_test_video_without_fps()
    if not test_video_path:
        logger.error("Failed to create test video")
        return False
    
    # Create metadata for the test video
    test_metadata = VideoMetadata(
        id="test_video_no_fps",
        url="https://www.tiktok.com/@test_user/video/test_video_no_fps",
        author="test_user",
        desc="Test video without FPS",
        local_path=test_video_path
    )
    
    # Create a multi-clip short using only this video
    # This should trigger FPS handling code
    short_path = await shorts_generator.create_multi_clip_short(
        video_metadata_list=[test_metadata],
        title="Test FPS Handling",
        max_duration=59.0,
        max_clips=1,
        clip_duration=5.0,
        include_branding=True
    )
    
    if short_path and os.path.exists(short_path):
        logger.success(f"Successfully created short with FPS handling: {short_path}")
        
        # Verify the output has valid FPS
        try:
            with VideoFileClip(short_path) as output_clip:
                if hasattr(output_clip, 'fps') and output_clip.fps is not None and output_clip.fps > 0:
                    logger.success(f"Output video has valid fps: {output_clip.fps}")
                    return True
                else:
                    logger.error("Output video still has no valid fps")
                    return False
        except Exception as e:
            logger.error(f"Error checking output video: {e}")
            return False
    else:
        logger.error("Failed to create short with FPS handling")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_fps_handling())
    sys.exit(0 if success else 1) 