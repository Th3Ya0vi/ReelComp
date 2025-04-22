#!/usr/bin/env python3
"""
Main application entry point for TikTok Compilation Automation.

This module handles the command-line interface and orchestrates the pipeline
for collecting TikTok videos, compiling them, and optionally uploading to YouTube.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

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
            shorts_flag = generate_shorts or compilation_short
            short_path = None
            if shorts_flag:
                logger.info("Generating a single YouTube Shorts video from the compilation...")
                short_path = await self.shorts_generator.create_short_from_compilation(
                    compilation_path=compilation_path,
                    title=title,
                    max_duration=59.0,  # YouTube Shorts limit is 60 seconds
                    include_branding=True
                )
                if short_path:
                    shorts_paths.append(short_path)
                    logger.success(f"Generated YouTube Short from compilation: {short_path}")
                else:
                    logger.warning("Failed to generate YouTube Short from compilation")

            # 5. Upload to YouTube based on user choice
            # Default: upload compilation if neither flag is set
            if upload_to_youtube:
                if (upload_compilation or (not upload_compilation and not upload_shorts)) and compilation_path:
                    logger.info("Uploading compilation video to YouTube...")
                    await self.youtube_uploader.upload_video(
                        compilation_path,
                        title=title,
                        description=description,
                        thumbnail_path=thumbnail_path
                    )
                if upload_shorts and short_path:
                    logger.info("Uploading Shorts video to YouTube...")
                    await self.youtube_uploader.upload_video(
                        short_path,
                        title=f"Shorts: {title}" if title else None,
                        description=description,
                        thumbnail_path=thumbnail_path
                    )
            
            # 6. Update processed URLs database to mark successfully processed URLs
            if processed_urls:
                logger.info(f"Marking {len(processed_urls)} URLs as processed in the database")
                save_processed_urls(processed_urls, processed_db_file)
                logger.success("Updated processed URLs database")
            
            # 7. Clean up temporary files
            self.file_manager.cleanup_temp_files()
            
            return compilation_path, shorts_paths
        
        except Exception as e:
            logger.error(f"Error during pipeline execution: {e}")
            return None, []
        
        finally:
            # Ensure cleanup is performed even if an exception occurs
            self.file_manager.cleanup_temp_files()
def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="TikTok Compilation Automation")
    
    # Required arguments
    url_group = parser.add_mutually_exclusive_group(required=False)
    url_group.add_argument("--urls", "-u", help="Path to a text file containing TikTok URLs")
    url_group.add_argument("--url-list", "-l", nargs="+", help="List of TikTok URLs")
    parser.add_argument("--auto-fetch", action="store_true", help="Automatically fetch new TikTok URLs if none are provided.")
    parser.add_argument("--fetch-hashtag", default="funny", help="Hashtag to use when auto-fetching TikTok URLs (default: funny)")
    parser.add_argument("--fetch-count", type=int, default=10, help="Number of TikTok URLs to fetch when auto-fetching (default: 10)")
    
    # Optional arguments
    parser.add_argument("--config", "-c", help="Path to a configuration file")
    parser.add_argument("--title", "-t", help="Title for the compilation video")
    parser.add_argument("--description", "-d", help="Description for the compilation video")
    parser.add_argument("--upload", "-y", action="store_true", help="Upload the compilation to YouTube")
    parser.add_argument("--max-videos", "-m", type=int, 
                      help="Maximum number of videos to include in the compilation (default: 50)")
    
    # Shorts options
    # Only one Shorts video will be created, which is a short version of the compilation.
    shorts_group = parser.add_mutually_exclusive_group()
    shorts_group.add_argument("--generate-shorts", "-s", action="store_true", 
                       help="[DEPRECATED: see --shorts] Generate a YouTube Short from the compilation video (now default behavior)")
    shorts_group.add_argument("--compilation-short", "-cs", action="store_true",
                       help="[DEPRECATED: see --shorts] Generate a YouTube Short from the compilation video (now default behavior)")
    parser.add_argument("--shorts", action="store_true", help="Create a single Shorts video from the compilation (default if any Shorts flag is set)")
    
    upload_group = parser.add_mutually_exclusive_group()
    upload_group.add_argument("--upload-compilation", action="store_true", help="Upload the long-form compilation video to YouTube (default)")
    upload_group.add_argument("--upload-shorts", action="store_true", help="Upload the Shorts video (vertical, <=59s) to YouTube")
    upload_group.add_argument("--upload-both", action="store_true", help="Upload both the compilation and Shorts video to YouTube")
    parser.add_argument("--upload-existing-path", type=str, default=None, help="Path to an existing video file to upload directly to YouTube (bypasses TikTok/compilation pipeline)")

    parser.add_argument("--log-level", "-v", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       default="INFO",
                       help="Logging level")
    
    parser.add_argument("--processed-db", 
                       default="data/processed_urls.json",
                       help="Path to the processed URLs database file")
    
    return parser.parse_args()


async def main():
    """Main entry point for the application."""
    import importlib
    args = parse_args()
    
    # Setup logging
    setup_logger(args.log_level)
    
    # Direct upload of existing video file if specified
    if args.upload_existing_path:
        logger.info(f"Uploading existing video file: {args.upload_existing_path}")
        app = CompilationApp(args.config)
        if not app.youtube_uploader.authenticate():
            logger.error("YouTube authentication failed. Please check your credentials.")
            return 1
        video_id = app.youtube_uploader.upload_video(
            args.upload_existing_path,
            title=args.title,
            description=args.description,
            thumbnail_path=None
        )
        if video_id:
            logger.success(f"Uploaded existing video: {args.upload_existing_path}")
            logger.info(f"YouTube URL: https://www.youtube.com/watch?v={video_id}")
        else:
            logger.error("Upload failed.")
        return 0
    
    # If no URLs are provided and --auto-fetch is set (or nothing is provided), fetch URLs
    urls = args.url_list
    urls_file = args.urls
    should_auto_fetch = args.auto_fetch or (not urls and not urls_file)

    if should_auto_fetch:
        logger.info(f"Auto-fetching {args.fetch_count} TikTok URLs using hashtag #{args.fetch_hashtag}")
        # Dynamically import the scraper to avoid circular imports
        tiktok_scraper = importlib.import_module("src.url_collector.tiktok_scraper")
        output_file = "auto_fetched_urls.txt"
        fetched_urls = await tiktok_scraper.collect_tiktok_video_urls(
            args.fetch_count,
            output_file,
            args.fetch_hashtag,
            args.processed_db
        )
        urls_file = output_file
        logger.info(f"Fetched {len(fetched_urls)} URLs to {output_file}")

    # Initialize the application
    app = CompilationApp(args.config)

    # Run the pipeline
    compilation_path, shorts_paths = await app.run(
        urls_file=urls_file,
        urls=urls,
        title=args.title,
        description=args.description,
        upload_to_youtube=args.upload_compilation or args.upload_shorts or args.upload_both,
        upload_compilation=args.upload_compilation or args.upload_both,
        upload_shorts=args.upload_shorts or args.upload_both,
        generate_shorts=args.generate_shorts,
        compilation_short=args.compilation_short,
        max_videos=args.max_videos,
        processed_db_file=args.processed_db
    )
    
    if compilation_path:
        logger.info(f"Compilation pipeline completed successfully. Output: {compilation_path}")
        if shorts_paths:
            if args.compilation_short:
                logger.info(f"Generated YouTube Short from compilation: {shorts_paths[0]}")
            else:
                logger.info(f"Generated {len(shorts_paths)} YouTube Shorts from individual videos: {', '.join(shorts_paths)}")
        return 0
    else:
        logger.error("Compilation pipeline failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
