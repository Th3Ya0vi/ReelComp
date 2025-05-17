"""
Test script to apply caption fixes to a video
"""

import asyncio
import os
from pathlib import Path

from src.content_generation.popup_captions import PopupCaptionStyler
from src.utils.config_loader import ConfigLoader
from loguru import logger


async def test_fixed_captions():
    """Test the fixed captions on a sample video"""
    
    # Set up configuration
    config = ConfigLoader().get_config()
    
    # Create caption styler
    styler = PopupCaptionStyler(config)
    
    # Source video path (either use the problematic one or a sample)
    source_video = "data/compilations/topic_How_to_make_option_call_How_to_make_option_call_1747455618.mp4"
    if not os.path.exists(source_video):
        # Try to find a sample video
        sample_dir = Path("data/sample_videos")
        if sample_dir.exists():
            samples = list(sample_dir.glob("*.mp4"))
            if samples:
                source_video = str(samples[0])
            else:
                logger.error("No sample videos found")
                return
        else:
            logger.error("No source video available")
            return
        
    # Output path
    output_path = "data/compilations/fixed_captions_test.mp4"
    
    # Process the video
    logger.info(f"Processing video: {source_video}")
    logger.info(f"Output will be saved to: {output_path}")
    
    try:
        result = await styler.add_popup_captions_to_video(
            video_path=source_video,
            output_path=output_path
        )
        
        logger.success(f"Processed video successfully: {result}")
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_fixed_captions()) 