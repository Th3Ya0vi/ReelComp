#!/usr/bin/env python3
"""
Test script for the multi-clip shorts feature.
This script tests the creation of a shorts video with multiple clips from different videos.
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import List

# Add the parent directory to the path to import from src
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from moviepy.editor import VideoFileClip
from src.video_processing.shorts_generator import ShortsGenerator
from src.video_collection.collector import VideoMetadata
from src.utils.logger_config import setup_logger
from src.utils.config_loader import ConfigLoader


def verify_video_integrity(video_path: str) -> bool:
    """
    Verify that a video file is valid and can be read by moviepy.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        True if the video is valid, False otherwise
    """
    try:
        if not os.path.exists(video_path):
            logger.error(f"Video file does not exist: {video_path}")
            return False
            
        with VideoFileClip(video_path) as clip:
            if clip is None:
                logger.error(f"Failed to load video: {video_path}")
                return False
                
            if clip.duration <= 0:
                logger.error(f"Video has invalid duration: {video_path}")
                return False
                
            # Try to access the first frame
            try:
                clip.get_frame(0)
            except Exception as e:
                logger.error(f"Cannot read frames from video {video_path}: {str(e)}")
                return False
                
            # Try to access the audio if available
            if clip.audio is not None:
                try:
                    clip.audio.get_frame(0)
                except Exception as e:
                    logger.warning(f"Video has invalid audio: {video_path} - {str(e)}")
                    # We'll still return True here as invalid audio isn't a critical issue
                
            logger.success(f"Video file is valid: {video_path} (duration: {clip.duration:.1f}s, size: {clip.size})")
            return True
                
    except Exception as e:
        logger.error(f"Error validating video {video_path}: {str(e)}")
        return False


def copy_sample_videos(source_dir: str, target_dir: str, max_videos: int = 5) -> List[Path]:
    """
    Copy sample videos from the source directory to the target directory.
    
    Args:
        source_dir: Source directory containing videos
        target_dir: Target directory to copy videos to
        max_videos: Maximum number of videos to copy
        
    Returns:
        List of paths to the copied videos
    """
    source_path = Path(source_dir)
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Find all video files in the source directory
    video_files = list(source_path.glob("*.mp4"))
    if not video_files:
        logger.error(f"No video files found in {source_dir}")
        return []
        
    logger.info(f"Found {len(video_files)} video files in {source_dir}")
    
    # Limit the number of videos to copy
    video_files = video_files[:max_videos]
    
    # Copy the video files
    copied_files = []
    for video_file in video_files:
        target_file = target_path / video_file.name
        try:
            shutil.copy2(video_file, target_file)
            if verify_video_integrity(str(target_file)):
                copied_files.append(target_file)
            else:
                # Remove invalid videos
                target_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to copy {video_file}: {str(e)}")
    
    logger.info(f"Copied {len(copied_files)} valid video files to {target_dir}")
    return copied_files


async def test_multi_clip_shorts():
    """Test the multi-clip shorts generation feature."""
    # Setup logger
    setup_logger("DEBUG")
    
    # Initialize config
    config = ConfigLoader().get_config()
    
    # Initialize shorts generator
    shorts_generator = ShortsGenerator(config)
    
    # Create test metadata
    test_videos_dir = Path("data/test_videos")
    videos_dir = Path("data/videos")
    
    # Create directory if it doesn't exist
    test_videos_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if we have test videos
    video_files = list(test_videos_dir.glob("*.mp4"))
    
    # If no test videos, try to copy from data/videos
    if not video_files and videos_dir.exists():
        logger.info(f"No test videos found in {test_videos_dir}. Copying from {videos_dir}...")
        video_files = copy_sample_videos(videos_dir, test_videos_dir)
    
    if not video_files:
        logger.error("No test videos found. Please add some test videos to data/test_videos/")
        logger.info("You can download sample videos for testing or use videos from your data/videos/ directory")
        return False
    
    # Verify video files
    valid_video_files = []
    for video_file in video_files:
        if verify_video_integrity(str(video_file)):
            valid_video_files.append(video_file)
    
    if not valid_video_files:
        logger.error("No valid test videos found")
        return False
    
    # Create metadata for each test video
    video_metadata_list = []
    for i, video_file in enumerate(valid_video_files):
        metadata = VideoMetadata(
            id=f"test_video_{i}",
            url=f"https://www.tiktok.com/@test_user/video/test_video_{i}",
            author=f"test_user_{i}",
            desc=f"Test video {i}",
            local_path=str(video_file)
        )
        video_metadata_list.append(metadata)
    
    logger.info(f"Created metadata for {len(video_metadata_list)} valid test videos")
    
    # Create multi-clip short
    short_path = await shorts_generator.create_multi_clip_short(
        video_metadata_list=video_metadata_list,
        title="Test Multi-Clip Short",
        max_duration=59.0,
        max_clips=5,
        clip_duration=10.0,
        include_branding=True
    )
    
    if short_path and os.path.exists(short_path):
        # Verify the output video
        if verify_video_integrity(short_path):
            logger.success(f"Multi-clip Short created and verified successfully: {short_path}")
            return True
        else:
            logger.error(f"Multi-clip Short was created but is not valid: {short_path}")
            return False
    else:
        logger.error("Failed to create multi-clip Short")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_multi_clip_shorts())
    sys.exit(0 if success else 1) 