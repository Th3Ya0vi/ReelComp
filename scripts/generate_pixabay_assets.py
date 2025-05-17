#!/usr/bin/env python3
"""
Pixabay Asset Generator

This script demonstrates how to generate image and video assets from Pixabay
to serve as backgrounds for ReelComp videos.
"""

import os
import sys
import argparse
from typing import List, Optional

# Add parent directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
from src.utils.config_loader import ConfigLoader
from src.content_generation.asset_collector import AssetCollector


def generate_pixabay_assets(
    search_terms: List[str],
    output_dir: Optional[str] = None,
    collect_videos: bool = True
) -> None:
    """
    Generate Pixabay assets (images and videos) for specified search terms.
    
    Args:
        search_terms: Search terms to search for
        output_dir: Directory to save assets (optional)
        collect_videos: Whether to collect video assets in addition to images
    """
    # Load config
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Check if Pixabay API key is set
    if not config.ai.pixabay_api_key:
        logger.error("Pixabay API key not configured. Please set PIXABAY_API_KEY in config.json")
        return
    
    # Create asset collector
    asset_collector = AssetCollector(config)
    
    # Create output directory if not specified
    if not output_dir:
        import time
        output_dir = os.path.join("data", "assets", f"pixabay_{int(time.time())}")
        os.makedirs(output_dir, exist_ok=True)
    
    # Generate assets for each search term
    for term in search_terms:
        logger.info(f"Collecting Pixabay assets for term: {term}")
        
        # Collect one image
        image_path = asset_collector._collect_pixabay_images(term, 1, output_dir)
        if image_path:
            logger.success(f"Collected image for {term}: {image_path}")
        
        # Collect one video if requested
        if collect_videos:
            video_path = asset_collector._collect_pixabay_videos(term, 1, output_dir)
            if video_path:
                logger.success(f"Collected video for {term}: {video_path}")


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Generate Pixabay assets for ReelComp")
    parser.add_argument("terms", nargs="+", help="Search terms to generate assets for")
    parser.add_argument("--output", "-o", help="Output directory for assets")
    parser.add_argument("--videos", "-v", action="store_true", help="Collect video assets", default=True)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Generate assets
    generate_pixabay_assets(
        search_terms=args.terms,
        output_dir=args.output,
        collect_videos=args.videos
    )


if __name__ == "__main__":
    main() 