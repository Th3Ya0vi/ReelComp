#!/usr/bin/env python3
"""
Test script for the asset collector with detailed logging.
"""
import os
import sys
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="DEBUG")

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.utils.config_loader import ConfigLoader
from src.content_generation.asset_collector import AssetCollector

def main():
    # Load config
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Create asset collector
    collector = AssetCollector(config)
    
    # Output directory for collected assets
    output_dir = os.path.join("data", "temp", "test_assets")
    os.makedirs(output_dir, exist_ok=True)
    
    # Print configuration
    logger.info(f"Using config from: {config_loader.env_file}")
    logger.info(f"Pixabay API key: {config.ai.pixabay_api_key[:5]}...{config.ai.pixabay_api_key[-4:]} (Length: {len(config.ai.pixabay_api_key)})")
    
    # Test collecting images
    search_term = "nature"
    logger.info(f"Testing image collection for search term: {search_term}")
    
    images = collector.collect_images(search_term, max_count=2, output_dir=output_dir)
    logger.info(f"Collected {len(images)} images: {images}")
    
    # Test collecting videos
    logger.info(f"Testing video collection for search term: {search_term}")
    videos = collector.collect_videos(search_term, max_count=1, output_dir=output_dir)
    logger.info(f"Collected {len(videos)} videos: {videos}")
    
    # Test with a different search term
    search_term = "finance"
    logger.info(f"Testing image collection for search term: {search_term}")
    
    images = collector.collect_images(search_term, max_count=2, output_dir=output_dir)
    logger.info(f"Collected {len(images)} images: {images}")

if __name__ == "__main__":
    main() 