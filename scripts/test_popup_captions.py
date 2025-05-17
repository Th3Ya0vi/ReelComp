#!/usr/bin/env python3
"""
Test script for popup captions feature.

This script allows testing the pop-up captions feature on an existing video.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to the path to allow importing from src
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from src.content_generation.popup_captions import PopupCaptionStyler
from src.utils.config_loader import ConfigLoader
from src.utils.logger_config import setup_logger


async def main():
    """Run the popup captions test."""
    parser = argparse.ArgumentParser(description="Test Pop-up Captions on a Video")
    parser.add_argument("video_path", help="Path to the video file to add captions to")
    parser.add_argument("--output", "-o", help="Path to save the output video (optional)")
    parser.add_argument("--language", "-l", help="Language code for speech recognition (e.g., en-US)")
    parser.add_argument("--config", help="Path to custom config file")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logger()
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.get_config(args.config)
    
    # Ensure the video path exists
    if not os.path.exists(args.video_path):
        logger.error(f"Video file not found: {args.video_path}")
        return 1
    
    # Create popup caption styler
    popup_styler = PopupCaptionStyler(config)
    
    # Process video
    logger.info(f"Adding pop-up captions to video: {args.video_path}")
    
    output_path = await popup_styler.add_popup_captions_to_video(
        video_path=args.video_path,
        output_path=args.output,
        language=args.language
    )
    
    logger.success(f"Created video with pop-up captions: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 