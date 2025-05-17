#!/usr/bin/env python3
"""
Test Script for Topic-Based Video Generation

This script demonstrates the use of the content_generation module to create videos
from any topic using AI-generated content.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Fix environment variables before importing the modules
os.environ["USE_POPUP_CAPTIONS"] = "true"

# Add the parent directory to sys.path to import the project modules
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.config_loader import ConfigLoader
from src.content_generation import (
    ContentVideoEngine, ContentShortEngine, 
    TopicAnalyzer, ScriptGenerator,
    VoiceoverGenerator, AssetCollector
)

async def generate_topic_video(
    topic: str, 
    duration: int = 60, 
    style: str = "informative",
    output_format: str = "standard",  # standard, short, tiktok
    language: str = "en-US"
):
    """Generate a video based on the given topic."""
    
    print(f"Generating {style} {output_format} video about: {topic}")
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.get_config("config.json")
    
    # Fix any problematic settings
    config.ai.use_popup_captions = True
    
    # Initialize content engine based on format
    if output_format == "standard":
        engine = ContentVideoEngine(config)
        video_info = await engine.create_content_video(
            topic=topic,
            duration=duration,
            style=style,
            include_voiceover=True,
            include_captions=True,
            language=language
        )
    elif output_format in ["short", "tiktok"]:
        engine = ContentShortEngine(config)
        if output_format == "short":
            video_info = await engine.create_shorts_video(
                topic=topic,
                include_voiceover=True,
                include_captions=True,
                language=language
            )
        else:  # tiktok
            video_info = await engine.create_tiktok_video(
                topic=topic,
                include_voiceover=True,
                language=language
            )
    
    print(f"Video generation complete!")
    print(f"Title: {video_info['title']}")
    print(f"Video path: {video_info['video_path']}")
    print(f"Duration: {duration} seconds")
    
    return video_info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a video from a topic using AI")
    parser.add_argument("topic", help="Topic to generate a video about")
    parser.add_argument("--duration", type=int, default=60, help="Target duration in seconds")
    parser.add_argument("--style", choices=["informative", "entertaining", "educational"], 
                        default="informative", help="Video style")
    parser.add_argument("--format", choices=["standard", "short", "tiktok"], 
                        default="standard", help="Video format")
    parser.add_argument("--language", default="en-US", help="Language code (e.g., en-US, es-ES)")
    
    args = parser.parse_args()
    
    asyncio.run(generate_topic_video(
        topic=args.topic,
        duration=args.duration,
        style=args.style,
        output_format=args.format,
        language=args.language
    )) 