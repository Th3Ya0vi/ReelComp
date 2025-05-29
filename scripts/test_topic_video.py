#!/usr/bin/env python3
"""
Test script for topic-based video generation with verbose logging.
"""
import os
import sys
import argparse
import logging
from loguru import logger

# Add parent directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.config_loader import ConfigLoader
from src.content_generation.content_engine import ContentVideoEngine
from src.utils.file_manager import FileManager

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Test topic video generation")
    parser.add_argument("topic", help="Topic to generate a video about")
    parser.add_argument("--duration", type=int, default=60, help="Video duration in seconds")
    parser.add_argument("--style", default="informative", 
                        choices=["informative", "entertaining", "educational"],
                        help="Content style")
    parser.add_argument("--format", default="standard",
                        choices=["standard", "short", "tiktok"],
                        help="Video format")
    parser.add_argument("--language", default="en-US", help="Language code")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
        logger.debug("Verbose logging enabled")
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Override config with command line arguments
    config.ai.language = args.language
    
    # Print configuration
    logger.info(f"Using topic: {args.topic}")
    logger.info(f"Duration: {args.duration} seconds")
    logger.info(f"Style: {args.style}")
    logger.info(f"Format: {args.format}")
    logger.info(f"Language: {args.language}")
    
    # Print API keys (partially redacted)
    openai_key = config.ai.openai_api_key
    if openai_key:
        logger.info(f"OpenAI API Key: {openai_key[:5]}...{openai_key[-4:]} (Length: {len(openai_key)})")
    else:
        logger.warning("OpenAI API Key not configured")
    
    pixabay_key = config.ai.pixabay_api_key
    if pixabay_key:
        logger.info(f"Pixabay API Key: {pixabay_key[:5]}...{pixabay_key[-4:]} (Length: {len(pixabay_key)})")
    else:
        logger.warning("Pixabay API Key not configured")
        
    # Create file manager
    file_manager = FileManager(config)
    
    # Create content engine
    content_engine = ContentVideoEngine(config, file_manager)
    
    # Generate video
    logger.info("Generating topic video...")
    
    try:
        if args.format == "standard":
            video_path = content_engine.create_content_video(
                args.topic, 
                duration=args.duration,
                style=args.style
            )
        elif args.format in ["short", "tiktok"]:
            from src.content_generation.content_engine import ContentShortEngine
            short_engine = ContentShortEngine(config, file_manager)
            video_path = short_engine.create_content_short(
                args.topic,
                style=args.style
            )
            
        logger.success(f"Video generated successfully: {video_path}")
    except Exception as e:
        logger.exception(f"Error generating video: {str(e)}")
    
if __name__ == "__main__":
    main() 