#!/usr/bin/env python3
"""
GPT Image Asset Generator

This script demonstrates how to generate image and video assets using OpenAI's GPT Image model
to serve as backgrounds for ReelComp videos when other image sources fail.
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


def generate_gpt_image_assets(
    search_terms: List[str],
    output_dir: Optional[str] = None,
    num_images: int = 2,
    create_videos: bool = True
) -> None:
    """
    Generate GPT Image assets (images and videos) for specified search terms.
    
    Args:
        search_terms: Search terms to generate images for
        output_dir: Directory to save assets (optional)
        num_images: Number of images to generate per term
        create_videos: Whether to create video assets from images
    """
    # Load config
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Check if OpenAI API key is set
    if not config.ai.openai_api_key:
        logger.error("OpenAI API key not configured. Please set OPENAI_API_KEY in .env or config.json")
        return
    
    # Create asset collector
    asset_collector = AssetCollector(config)
    
    # Create output directory if not specified
    if not output_dir:
        import time
        output_dir = os.path.join("data", "assets", f"gpt_image_{int(time.time())}")
        os.makedirs(output_dir, exist_ok=True)
    
    # Generate assets for each search term
    for term in search_terms:
        logger.info(f"Generating GPT Image assets for term: {term}")
        
        # Generate images
        images = []
        for i in range(num_images):
            image_path = asset_collector._generate_dalle_image(term, output_dir)
            if image_path:
                images.append(image_path)
                logger.success(f"Generated image {i+1}/{num_images} for {term}")
        
        # Create video assets if requested
        if create_videos and images:
            logger.info(f"Creating video assets from GPT Image images for {term}")
            for image in images:
                # Create a 5-second video clip from the image
                video_path = asset_collector.generate_fallback_asset(
                    search_term=term,
                    duration=5.0,
                    output_dir=output_dir
                )
                logger.success(f"Created video asset: {video_path}")


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Generate GPT Image assets for ReelComp")
    parser.add_argument("terms", nargs="+", help="Search terms to generate assets for")
    parser.add_argument("--output", "-o", help="Output directory for assets")
    parser.add_argument("--num-images", "-n", type=int, default=2, help="Number of images per term")
    parser.add_argument("--videos", "-v", action="store_true", help="Generate video assets from images")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Generate assets
    generate_gpt_image_assets(
        search_terms=args.terms,
        output_dir=args.output,
        num_images=args.num_images,
        create_videos=args.videos
    )


if __name__ == "__main__":
    main() 