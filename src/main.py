#!/usr/bin/env python3
"""
Main application for ReelComp

This module serves as the main entry point for the TikTok Video Compilation Automation tool.
It coordinates the various components of the system and handles command-line arguments.
"""

import os
import sys
import asyncio
import argparse
import logging
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Fix environment variables before importing other modules
os.environ["USE_POPUP_CAPTIONS"] = "true"

from loguru import logger

from src.content_generation.content_engine import ContentShortEngine, ContentVideoEngine
from src.thumbnail_generator.generator import ThumbnailGenerator
from src.utils.config_loader import ConfigLoader
from src.utils.file_manager import FileManager
from src.utils.logger_config import setup_logger
from src.video_collection.collector import TikTokCollector, VideoMetadata
from src.video_processing.compiler import VideoCompiler
from src.video_processing.shorts_generator import ShortsGenerator
from src.youtube_uploader.uploader import YouTubeUploader
from src.url_collector.tiktok_scraper import save_processed_urls


class CompilationApp:
    """Main application class for TikTok video compilation automation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the application with required components.
        
        Args:
            config_path: Path to a configuration file
        """
        # Load configuration
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.get_config(config_path)
        
        # Initialize components
        self.file_manager = FileManager(self.config)
        self.tiktok_collector = TikTokCollector(self.config, self.file_manager)
        self.video_compiler = VideoCompiler(self.config, self.file_manager)
        self.thumbnail_generator = ThumbnailGenerator(self.config, self.file_manager)
        self.shorts_generator = ShortsGenerator(self.config, self.file_manager)
        self.youtube_uploader = YouTubeUploader(self.config, self.file_manager)
        
        # Initialize AI content generation components
        self.content_video_engine = ContentVideoEngine(self.config, self.file_manager)
        self.content_short_engine = ContentShortEngine(self.config, self.file_manager)
    
    @staticmethod
    async def _read_urls_from_file(file_path: str) -> List[str]:
        """
        Read TikTok URLs from a file.
        
        Args:
            file_path: Path to the file containing URLs
            
        Returns:
            List of URLs
        """
        try:
            with open(file_path, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            logger.info(f"Read {len(urls)} URLs from {file_path}")
            return urls
        except Exception as e:
            logger.error(f"Error reading URLs from {file_path}: {str(e)}")
            return []
    
    async def run(
        self,
        urls_file: Optional[str] = None,
        urls: Optional[List[str]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        upload_to_youtube: bool = False,
        upload_compilation: bool = False,
        upload_shorts: bool = False,
        generate_shorts: bool = False,
        compilation_short: bool = False,
        multi_clip_shorts: bool = False,
        max_videos: Optional[int] = None,
        processed_db_file: str = 'data/processed_urls.json'
    ) -> Tuple[Optional[str], List[str]]:
        """
        Run the TikTok compilation pipeline.
        
        Args:
            urls_file: Path to file containing TikTok URLs
            urls: List of TikTok URLs
            title: Title for the compilation video
            description: Description for the compilation video
            upload_to_youtube: Whether to upload the compilation to YouTube
            upload_compilation: Whether to upload the compilation video to YouTube
            upload_shorts: Whether to upload the Shorts video to YouTube
            generate_shorts: Whether to generate YouTube Shorts from individual videos
            compilation_short: Whether to generate a YouTube Short from the compilation
            multi_clip_shorts: Whether to create a Shorts video with multiple clips
            max_videos: Maximum number of videos to include in the compilation
            processed_db_file: Path to the processed URLs database file
            
        Returns:
            Tuple containing path to compilation video and list of paths to Shorts
        """
        try:
            # Get URLs from file if specified
            if urls_file:
                urls = await self._read_urls_from_file(urls_file)
            
            # Ensure we have URLs
            if not urls:
                logger.error("No TikTok URLs provided")
                return None, []
            
            # Track which URLs were successfully processed
            processed_urls = set()
            
            # 1. Download TikTok videos
            logger.info(f"Downloading {len(urls)} TikTok videos...")
            video_metadata_list = await self.tiktok_collector.download_videos(urls)
            
            if not video_metadata_list:
                logger.error("Failed to download any videos")
                return None, []
            
            # Track which URLs were successfully downloaded
            for metadata in video_metadata_list:
                if metadata.url:
                    processed_urls.add(metadata.url)
            
            logger.success(f"Successfully downloaded {len(video_metadata_list)} videos")
            
            # Generate title and description if not provided
            today = datetime.now().strftime("%B %d, %Y")
            if not title:
                title = f"TikTok Highlights | {today}"
            
            if not description:
                description = (
                    "🎬 Welcome to TikTok Weekly Top!\n\n"
                    "Dive into this week's best TikToks—handpicked viral hits, hilarious moments, and trending clips that everyone's talking about! No endless scrolling needed; we've got your weekly dose of TikTok right here.\n\n"
                    "🔥 New compilations uploaded weekly—Subscribe and turn notifications on!\n\n"
                    "Disclaimer: All videos featured belong to their original creators. Follow and support their amazing content on TikTok!\n\n"
                    "📧 Want your video featured? Submit your TikTok link in the comments below!\n\n"
                    "Tags: #TikTok #TikTokWeekly #TikTokCompilation #Trending #ViralVideos #WeeklyTop"
                )
            
            # 2. Compile videos
            logger.info("Creating compilation video...")
            compilation_path = await self.video_compiler.create_compilation(
                video_metadata_list,
                title=title,
                max_videos=max_videos
            )
            
            if not compilation_path or not os.path.exists(compilation_path):
                logger.error("Failed to create compilation video")
                return None, []
            
            logger.success(f"Compilation created: {compilation_path}")
            
            # 3. Generate thumbnail
            logger.info("Generating thumbnail...")
            thumbnail_path = await self.thumbnail_generator.create_thumbnail(
                video_metadata_list,
                compilation_path,
                title=title
            )
            
            if not thumbnail_path or not os.path.exists(thumbnail_path):
                logger.warning("Failed to create thumbnail, continuing without it")
                thumbnail_path = None
            else:
                logger.success(f"Thumbnail created: {thumbnail_path}")
            
            # 4. Generate YouTube Shorts
            shorts_paths = []

            # Always create only ONE Shorts video from the compilation if any Shorts flag is set
            shorts_flag = generate_shorts or compilation_short or upload_shorts
            short_path = None
            
            if shorts_flag:
                if multi_clip_shorts:
                    logger.info("Generating a multi-clip YouTube Shorts video...")
                    short_path = await self.shorts_generator.create_multi_clip_short(
                        video_metadata_list=video_metadata_list,
                        title=title,
                        max_duration=59.0,  # YouTube Shorts limit is 60 seconds
                        max_clips=8,        # Use up to 8 clips
                        clip_duration=7.0,  # Target ~7 seconds per clip
                        include_branding=True
                    )
                else:
                    logger.info("Generating a single YouTube Shorts video from the compilation...")
                    short_path = await self.shorts_generator.create_short_from_compilation(
                        compilation_path=compilation_path,
                        title=title
                    )
                
                if short_path and os.path.exists(short_path):
                    logger.success(f"YouTube Short created: {short_path}")
                    shorts_paths.append(short_path)
                else:
                    logger.error("Failed to create YouTube Short")
            
            # 5. Upload videos to YouTube if requested
            youtube_urls = {}
            
            if upload_to_youtube or upload_compilation:
                logger.info("Uploading compilation to YouTube...")
                youtube_url = await self.youtube_uploader.upload_video(
                    video_path=compilation_path,
                    title=title,
                    description=description,
                    thumbnail_path=thumbnail_path
                )
                
                if youtube_url:
                    logger.success(f"Compilation uploaded to YouTube: {youtube_url}")
                    youtube_urls["compilation"] = youtube_url
                else:
                    logger.error("Failed to upload compilation to YouTube")
            
            if upload_shorts and shorts_paths:
                logger.info("Uploading Shorts to YouTube...")
                
                for i, short_path in enumerate(shorts_paths):
                    short_title = f"{title} | Short #{i+1}" if len(shorts_paths) > 1 else f"{title} | Short"
                    
                    youtube_url = await self.youtube_uploader.upload_shorts(
                        video_path=short_path,
                        title=short_title,
                        description=f"Check out our full compilation: {youtube_urls.get('compilation', '')}\n\n{description}"
                    )
                    
                    if youtube_url:
                        logger.success(f"Short #{i+1} uploaded to YouTube: {youtube_url}")
                        youtube_urls[f"short_{i+1}"] = youtube_url
                    else:
                        logger.error(f"Failed to upload Short #{i+1} to YouTube")
            
            # 6. Save processed URLs to avoid reprocessing
            if processed_urls:
                save_processed_urls(processed_urls, processed_db_file)
                logger.info(f"Saved {len(processed_urls)} processed URLs to {processed_db_file}")
            
            return compilation_path, shorts_paths
            
        except Exception as e:
            logger.error(f"Error in compilation pipeline: {str(e)}")
            return None, []
    
    async def run_topic_video(
        self,
        topic: str,
        duration: int = 60,
        style: str = "informative",
        voice_gender: str = "male",
        include_voiceover: bool = True,
        include_captions: bool = True,
        language: Optional[str] = None,
        is_shorts: bool = False,
        title: Optional[str] = None,
        description: Optional[str] = None,
        upload_to_youtube: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Run the topic-based content generation pipeline.
        
        Args:
            topic: Video topic
            duration: Target duration in seconds
            style: Video style (informative, entertaining, educational)
            voice_gender: Voice gender for voiceover
            include_voiceover: Whether to include voiceover
            include_captions: Whether to include captions
            language: Language code for content
            is_shorts: Whether to create a Shorts video
            title: Title for the video
            description: Description for the video
            upload_to_youtube: Whether to upload the video to YouTube
            
        Returns:
            Tuple containing path to video and YouTube URL if uploaded
        """
        try:
            # Generate video
            logger.info(f"Generating {'Shorts' if is_shorts else 'content'} video for topic: {topic}")
            
            # Choose the appropriate engine
            engine = self.content_short_engine if is_shorts else self.content_video_engine
            
            # Set appropriate duration for Shorts
            if is_shorts and duration > 60:
                logger.warning(f"Duration {duration}s is too long for Shorts, limiting to 60s")
                duration = 60
            
            # Create the video
            if is_shorts:
                result = await engine.create_shorts_video(
                    topic=topic,
                    voice_gender=voice_gender,
                    include_voiceover=include_voiceover,
                    include_captions=include_captions,
                    language=language,
                    title=title
                )
            else:
                result = await engine.create_content_video(
                    topic=topic,
                    duration=duration,
                    style=style,
                    voice_gender=voice_gender,
                    include_voiceover=include_voiceover,
                    include_captions=include_captions,
                    language=language,
                    title=title
                )
            
            # Extract video path
            video_path = result.get("video_path")
            
            if not video_path or not os.path.exists(video_path):
                logger.error("Failed to generate video")
                return None, None
            
            # Use the title from the result
            final_title = result.get("title", title or topic)
            
            # Generate description if not provided
            if not description:
                description = (
                    f"🎬 Learn about {topic}!\n\n"
                    f"This video explores interesting facts and information about {topic}.\n\n"
                    "🔥 Subscribe for more content like this!\n\n"
                    f"Tags: #{topic.replace(' ', '')} #Educational #FactsAbout{topic.replace(' ', '')}"
                )
            
            # Generate thumbnail
            thumbnail_path = None
            try:
                logger.info("Generating thumbnail...")
                # Extract a frame from the video for thumbnail
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(video_path)
                frame = clip.get_frame(clip.duration * 0.25)  # Get a frame at 25% of the duration
                clip.close()
                
                # Save the frame as a thumbnail
                import cv2
                import numpy as np
                thumbnail_path = os.path.join(
                    self.config.app.thumbnail_dir,
                    f"topic_{os.path.basename(video_path).replace('.mp4', '.jpg')}"
                )
                cv2.imwrite(thumbnail_path, cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
                
                logger.success(f"Thumbnail created: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"Failed to create thumbnail: {str(e)}")
                thumbnail_path = None
            
            # Upload to YouTube if requested
            youtube_url = None
            if upload_to_youtube:
                logger.info(f"Uploading {'Shorts' if is_shorts else 'video'} to YouTube...")
                
                if is_shorts:
                    youtube_url = await self.youtube_uploader.upload_shorts(
                        video_path=video_path,
                        title=final_title,
                        description=description
                    )
                else:
                    youtube_url = await self.youtube_uploader.upload_video(
                        video_path=video_path,
                        title=final_title,
                        description=description,
                        thumbnail_path=thumbnail_path
                    )
                
                if youtube_url:
                    logger.success(f"{'Shorts' if is_shorts else 'Video'} uploaded to YouTube: {youtube_url}")
                else:
                    logger.error(f"Failed to upload {'Shorts' if is_shorts else 'video'} to YouTube")
            
            return video_path, youtube_url
            
        except Exception as e:
            logger.error(f"Error in topic video pipeline: {str(e)}")
            return None, None


def parse_args():
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="TikTok Video Compilation Tool")
    
    # Input source arguments
    input_group = parser.add_argument_group("Input Sources")
    input_group.add_argument("--urls", help="Path to file containing TikTok URLs")
    input_group.add_argument("--url-list", nargs="+", help="List of TikTok URLs")
    input_group.add_argument("--auto-fetch", action="store_true", help="Automatically fetch TikTok URLs")
    input_group.add_argument("--fetch-hashtag", default="funny", help="Hashtag to use when auto-fetching (default: funny)")
    input_group.add_argument("--fetch-count", type=int, default=10, help="Number of TikToks to fetch (default: 10)")
    
    # Compilation settings
    compilation_group = parser.add_argument_group("Compilation Settings")
    compilation_group.add_argument("--title", help="Title for the compilation video")
    compilation_group.add_argument("--max-videos", type=int, help="Maximum number of videos to include in compilation")
    
    # Shorts settings
    shorts_group = parser.add_argument_group("YouTube Shorts Settings")
    shorts_group.add_argument("--shorts", action="store_true", help="Create a YouTube Short from the compilation")
    shorts_group.add_argument("--generate-shorts", action="store_true", help="[DEPRECATED] Use --shorts instead")
    shorts_group.add_argument("--compilation-short", action="store_true", help="[DEPRECATED] Use --shorts instead")
    shorts_group.add_argument("--multi-clip-shorts", action="store_true", help="Create a multi-clip YouTube Short")
    
    # Upload settings
    upload_group = parser.add_argument_group("Upload Settings")
    upload_group.add_argument("--upload", action="store_true", help="Upload videos to YouTube")
    upload_group.add_argument("--upload-compilation", action="store_true", help="Upload compilation to YouTube")
    upload_group.add_argument("--upload-shorts", action="store_true", help="Upload Shorts to YouTube")
    upload_group.add_argument("--upload-existing-path", help="Upload an existing video file to YouTube")
    
    # Diagnostic tools
    diagnostic_group = parser.add_argument_group("Diagnostic Tools")
    diagnostic_group.add_argument("--diagnose-video", help="Analyze a video file for compatibility issues")
    diagnostic_group.add_argument("--repair-video", action="store_true", help="Attempt to repair a problematic video")
    diagnostic_group.add_argument("--repair-output", help="Output path for repaired video")
    
    # AI content generation
    ai_group = parser.add_argument_group("AI Content Generation")
    ai_group.add_argument("--topic", help="Generate video about specific topic")
    ai_group.add_argument("--topic-duration", type=int, default=60, help="Duration for topic video in seconds (default: 60)")
    ai_group.add_argument("--topic-style", choices=["informative", "entertaining", "educational"], default="informative",
                         help="Style of topic video (default: informative)")
    ai_group.add_argument("--topic-shorts", action="store_true", help="Create a YouTube Short for the topic")
    ai_group.add_argument("--voice-gender", choices=["male", "female"], default="male",
                         help="Voice gender for voiceover (default: male)")
    ai_group.add_argument("--no-voiceover", action="store_true", help="Disable voiceover in topic video")
    ai_group.add_argument("--no-captions", action="store_true", help="Disable captions in topic video")
    ai_group.add_argument("--language", help="Language code for content (default: from config)")
    
    # General settings
    general_group = parser.add_argument_group("General Settings")
    general_group.add_argument("--config", help="Path to configuration file")
    general_group.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    return parser.parse_args()


async def main():
    """Main entry point for the application."""
    # Parse command-line arguments
    args = parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logger(log_level)
    
    # Initialize application
    app = CompilationApp(config_path=args.config)
    
    # Process diagnostic requests first
    if args.diagnose_video:
        from src.video_processing.diagnostic import diagnose_video, repair_video
        
        # Diagnose the video
        logger.info(f"Diagnosing video file: {args.diagnose_video}")
        diagnosis = diagnose_video(args.diagnose_video)
        
        # Print diagnosis
        for key, value in diagnosis.items():
            logger.info(f"{key}: {value}")
        
        # Repair the video if requested
        if args.repair_video:
            repair_output = args.repair_output or f"repaired_{os.path.basename(args.diagnose_video)}"
            logger.info(f"Attempting to repair video: {args.diagnose_video} -> {repair_output}")
            
            success = repair_video(args.diagnose_video, repair_output)
            
            if success:
                logger.success(f"Video repaired successfully: {repair_output}")
            else:
                logger.error("Failed to repair video")
        
        return
    
    # Handle uploading existing video
    if args.upload_existing_path:
        if not os.path.exists(args.upload_existing_path):
            logger.error(f"Video file not found: {args.upload_existing_path}")
            return
        
        # Determine if it's a Shorts video based on dimensions
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(args.upload_existing_path)
        is_shorts = clip.size[0] < clip.size[1]  # Width < Height indicates vertical video (Shorts)
        clip.close()
        
        title = args.title or f"Video Upload | {datetime.now().strftime('%B %d, %Y')}"
        
        logger.info(f"Uploading existing {'Shorts' if is_shorts else 'video'}: {args.upload_existing_path}")
        
        # Upload the video
        if is_shorts:
            youtube_url = await app.youtube_uploader.upload_shorts(
                video_path=args.upload_existing_path,
                title=title
            )
        else:
            youtube_url = await app.youtube_uploader.upload_video(
                video_path=args.upload_existing_path,
                title=title
            )
        
        if youtube_url:
            logger.success(f"Video uploaded to YouTube: {youtube_url}")
        else:
            logger.error("Failed to upload video to YouTube")
        
        return
    
    # Handle topic-based content generation
    if args.topic:
        # Process topic-based content generation
        video_path, youtube_url = await app.run_topic_video(
            topic=args.topic,
            duration=args.topic_duration,
            style=args.topic_style,
            voice_gender=args.voice_gender,
            include_voiceover=not args.no_voiceover,
            include_captions=not args.no_captions,
            language=args.language,
            is_shorts=args.topic_shorts,
            title=args.title,
            upload_to_youtube=args.upload
        )
        
        if video_path:
            logger.success(f"Topic video created: {video_path}")
            if youtube_url:
                logger.success(f"Video uploaded to YouTube: {youtube_url}")
        
        return
    
    # Handle compilation-based workflow
    urls = []
    
    # Get URLs from file
    if args.urls:
        urls = await app._read_urls_from_file(args.urls)
    
    # Get URLs from command line
    elif args.url_list:
        urls = args.url_list
    
    # Auto-fetch URLs if requested and no URLs provided
    elif args.auto_fetch:
        from src.url_collector.tiktok_scraper import scrape_urls
        
        logger.info(f"Auto-fetching {args.fetch_count} TikTok URLs with hashtag '{args.fetch_hashtag}'...")
        
        urls = await scrape_urls(
            count=args.fetch_count,
            hashtag=args.fetch_hashtag,
            output_file="auto_fetched_urls.txt",
            save_screenshot=True
        )
        
        if not urls:
            logger.error("Failed to fetch any TikTok URLs")
            return
        
        logger.success(f"Fetched {len(urls)} TikTok URLs")
    
    # Ensure we have URLs
    if not urls:
        logger.error("No TikTok URLs provided. Use --urls, --url-list, or --auto-fetch")
        return
    
    # Normalize legacy flags
    shorts = args.shorts or args.generate_shorts or args.compilation_short
    
    # Run compilation pipeline
    compilation_path, shorts_paths = await app.run(
        urls=urls,
        title=args.title,
        upload_to_youtube=args.upload,
        upload_compilation=args.upload_compilation,
        upload_shorts=args.upload_shorts,
        generate_shorts=shorts,
        multi_clip_shorts=args.multi_clip_shorts,
        max_videos=args.max_videos
    )
    
    # Report results
    if compilation_path:
        logger.success(f"Pipeline completed successfully!")
        logger.info(f"Compilation video: {compilation_path}")
        
        if shorts_paths:
            for i, shorts_path in enumerate(shorts_paths):
                logger.info(f"Shorts video #{i+1}: {shorts_path}")
    else:
        logger.error("Pipeline failed")


if __name__ == "__main__":
    # Run the application
    asyncio.run(main())
