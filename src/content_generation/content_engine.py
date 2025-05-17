"""
Content Engine Module

Coordinates the entire process of generating a video from a topic.
"""

import asyncio
import os
import random
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger
from moviepy.editor import (AudioFileClip, CompositeVideoClip, ImageClip,
                           TextClip, VideoFileClip, concatenate_videoclips)

from src.content_generation.asset_collector import AssetCollector
from src.content_generation.script_generator import ScriptGenerator
from src.content_generation.topic_analyzer import TopicAnalyzer
from src.content_generation.voiceover_generator import VoiceoverGenerator
from src.utils.config_loader import Config
from src.utils.file_manager import FileManager
from src.video_processing.compiler import VideoCompiler


class ContentVideoEngine:
    """
    Coordinates the process of generating a video from a topic.
    """
    
    def __init__(self, config: Config, file_manager: Optional[FileManager] = None):
        """
        Initialize the content engine with config.
        
        Args:
            config: Application configuration
            file_manager: File manager instance (optional)
        """
        self.config = config
        self.file_manager = file_manager
        
        # Initialize components
        self.topic_analyzer = TopicAnalyzer(config)
        self.script_generator = ScriptGenerator(config)
        self.voiceover_generator = VoiceoverGenerator(config, file_manager)
        self.asset_collector = AssetCollector(config, file_manager)
        
        # Initialize dependent components
        if self.file_manager:
            self.video_compiler = VideoCompiler(config, file_manager)
    
    async def create_content_video(
        self, 
        topic: str, 
        duration: int = 60,
        style: str = "informative",
        voice_gender: str = "male",
        include_voiceover: bool = True,
        include_captions: bool = True,
        language: Optional[str] = None,
        output_path: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Union[str, Dict]]:
        """
        Create a complete video about a topic.
        
        Args:
            topic: Video topic
            duration: Target duration in seconds
            style: Video style (informative, entertaining, educational)
            voice_gender: Voice gender for voiceover
            include_voiceover: Whether to include voiceover
            include_captions: Whether to include captions
            language: Language code for content
            output_path: Path to save the output video (optional)
            title: Video title (optional)
            
        Returns:
            Dictionary with information about the created video
        """
        # Use language from config if not specified
        if language is None:
            language = self.config.ai.language
        
        # Generate output path if not provided
        if output_path is None:
            if self.file_manager:
                # Safe title for filename
                safe_title = title or topic
                safe_title = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in safe_title)
                safe_title = safe_title.strip().replace(' ', '_')
                
                output_path = self.file_manager.get_compilation_path(
                    prefix=f"topic_{safe_title}",
                    title=safe_title
                )
            else:
                # Create a temporary directory if file manager not available
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, f"topic_video_{int(time.time())}.mp4")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Step 1: Generate script
        logger.info(f"Generating script for topic: {topic}")
        script_data = self.script_generator.generate_script(topic, script_type=style, duration=duration)
        
        # Use provided title or generated title
        if title:
            script_data["title"] = title
        
        # Step 2: Generate voiceover if requested
        audio_path = None
        if include_voiceover:
            logger.info("Generating voiceover")
            audio_path = await self.voiceover_generator.generate_voiceover(
                script=script_data["script"],
                voice_gender=voice_gender,
                language=language
            )
        
        # Step 3: Collect assets
        logger.info("Collecting assets")
        search_terms = script_data.get("search_terms", [topic])
        assets = self.asset_collector.collect_assets(
            search_terms=search_terms,
            num_images=min(5, duration // 10),  # Roughly 1 image per 10 seconds
            num_videos=min(3, duration // 20)   # Roughly 1 video per 20 seconds
        )
        
        # Step 4: Create video
        logger.info("Creating video")
        video_path = await self._create_video(
            script_data=script_data,
            assets=assets,
            audio_path=audio_path,
            include_captions=include_captions,
            output_path=output_path
        )
        
        # Return result
        return {
            "topic": topic,
            "title": script_data["title"],
            "script": script_data["script"],
            "video_path": video_path,
            "audio_path": audio_path,
            "assets": assets,
            "script_data": script_data
        }
    
    async def create_shorts_video(
        self, 
        topic: str, 
        voice_gender: str = "male",
        include_voiceover: bool = True,
        include_captions: bool = True,
        language: Optional[str] = None,
        output_path: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Union[str, Dict]]:
        """
        Create a Shorts/TikTok video about a topic.
        
        Args:
            topic: Video topic
            voice_gender: Voice gender for voiceover
            include_voiceover: Whether to include voiceover
            include_captions: Whether to include captions
            language: Language code for content
            output_path: Path to save the output video (optional)
            title: Video title (optional)
            
        Returns:
            Dictionary with information about the created video
        """
        # Shorts-specific parameters
        return await self.create_content_video(
            topic=topic,
            duration=30,  # Shorts should be 30-60 seconds
            style="entertaining",
            voice_gender=voice_gender,
            include_voiceover=include_voiceover,
            include_captions=include_captions,
            language=language,
            output_path=output_path,
            title=title
        )
    
    async def _create_video(
        self,
        script_data: Dict[str, Union[str, List, Dict]],
        assets: Dict[str, List[str]],
        audio_path: Optional[str] = None,
        include_captions: bool = True,
        output_path: Optional[str] = None
    ) -> str:
        """
        Create a video from script data and assets.
        
        Args:
            script_data: Script data dictionary
            assets: Dictionary with paths to assets
            audio_path: Path to audio file (optional)
            include_captions: Whether to include captions
            output_path: Path to save the output video (optional)
            
        Returns:
            Path to the created video
        """
        try:
            # Create output directory for temporary files
            temp_dir = tempfile.mkdtemp()
            
            # Load audio if available
            audio_clip = None
            audio_duration = 0
            if audio_path and os.path.exists(audio_path):
                audio_clip = AudioFileClip(audio_path)
                audio_duration = audio_clip.duration
            
            # Determine video duration
            target_duration = script_data.get("target_duration", 60)
            video_duration = audio_duration if audio_duration > 0 else target_duration
            
            # Create a sequence of clips based on script sections and visuals
            clips = []
            
            # Check if we have enough assets
            if not assets["videos"] and not assets["images"]:
                logger.warning("No assets available. Generating fallback assets.")
                
                # Generate fallback assets without trying image generation anymore
                # since it already failed earlier in the pipeline
                search_terms = script_data.get("search_terms", [script_data.get("title", "content")])
                assets = self.asset_collector.collect_fallback_assets(
                    search_terms=search_terms,
                    num_assets=min(5, len(search_terms)),
                    duration=video_duration,
                    output_dir=temp_dir,
                    skip_image_generation=True  # Skip image generation when using fallbacks
                )
                
                if not assets["videos"] and not assets["images"]:
                    logger.warning("Failed to generate fallback assets. Creating basic text-only video.")
                    # Create a basic text clip as last resort
                    text_clip = TextClip(
                        script_data["title"], 
                        fontsize=60, 
                        color='white', 
                        bg_color='black',
                        size=(self.config.app.video_width, self.config.app.video_height)
                    ).set_duration(video_duration)
                    
                    clips.append(text_clip)
            
            if not clips and assets["videos"] or assets["images"]:
                # Use assets to create video sequence
                # First, try to follow visual suggestions from script if available
                if "visuals" in script_data and script_data["visuals"]:
                    # Create clips from visual suggestions
                    for visual in script_data["visuals"]:
                        try:
                            # Get timing information
                            start_time = float(visual.get("timing", 0))
                            duration = float(visual.get("duration", 5))
                            
                            # Skip if beyond video duration
                            if start_time >= video_duration:
                                continue
                            
                            # Adjust duration if it would exceed video length
                            if start_time + duration > video_duration:
                                duration = video_duration - start_time
                            
                            # Select asset based on description
                            description = visual.get("description", "").lower()
                            
                            if "title" in description or "text" in description:
                                # Create text clip
                                text = visual.get("text", script_data["title"])
                                text_clip = (
                                    TextClip(
                                        text.upper(), 
                                        fontsize=60, 
                                        color='white',
                                        method='caption',
                                        bg_color='transparent',
                                        size=(self.config.app.video_width, self.config.app.video_height - 200)
                                    )
                                    .set_position(('center', 'center'))
                                    .set_start(start_time)
                                    .set_duration(duration)
                                )
                                clips.append(text_clip)
                                
                            elif "image" in description and assets["images"]:
                                # Use an image
                                image_path = random.choice(assets["images"])
                                image_clip = (
                                    ImageClip(image_path)
                                    .resize(height=self.config.app.video_height)
                                    .set_position(('center', 'center'))
                                    .set_start(start_time)
                                    .set_duration(duration)
                                )
                                clips.append(image_clip)
                                
                            elif assets["videos"]:
                                # Use a video
                                video_path = random.choice(assets["videos"])
                                video_clip = (
                                    VideoFileClip(video_path)
                                    .resize(height=self.config.app.video_height)
                                    .set_position(('center', 'center'))
                                    .set_start(start_time)
                                    .set_duration(duration)
                                )
                                clips.append(video_clip)
                        except Exception as e:
                            logger.error(f"Error creating clip for visual: {str(e)}")
                
                # If we don't have enough clips, add more
                if not clips or len(clips) < 3:
                    # Basic structure: intro, content, outro
                    segments = 3
                    segment_duration = video_duration / segments
                    
                    # Use videos first, then fall back to images
                    for i in range(segments):
                        segment_start = i * segment_duration
                        
                        if i == 0:
                            # Intro - title card
                            text_clip = (
                                TextClip(
                                    script_data["title"].upper(), 
                                    fontsize=60, 
                                    color='white',
                                    method='caption',
                                    size=(self.config.app.video_width, self.config.app.video_height - 200),
                                    bg_color='transparent'  # Ensure text has transparent background
                                )
                                .set_position(('center', 'center'))
                                .set_start(segment_start)
                                .set_duration(min(5, segment_duration))
                            )
                            clips.append(text_clip)
                            
                            # We no longer need segment-specific backgrounds as we'll use a full video background
                            pass
                        
                        elif i == segments - 1:
                            # Outro
                            text_clip = (
                                TextClip(
                                    "THANKS FOR WATCHING!", 
                                    fontsize=60, 
                                    color='white',
                                    method='caption',
                                    size=(self.config.app.video_width, self.config.app.video_height - 200),
                                    bg_color='transparent'  # Ensure text has transparent background
                                )
                                .set_position(('center', 'center'))
                                .set_start(segment_start)
                                .set_duration(min(5, segment_duration))
                            )
                            clips.append(text_clip)
                            
                            # We no longer need segment-specific backgrounds as we'll use a full video background
                            pass
                        
                        else:
                            # We now use a single full-duration background for the entire video
                            # Add any segment-specific text or overlays here if needed
                            pass
            
            # Create a full video background if we have videos
            if assets["videos"]:
                # Use a video for the entire background
                video_path = random.choice(assets["videos"])
                try:
                    background_video = (
                        VideoFileClip(video_path)
                        .resize(height=self.config.app.video_height)
                        .set_position(('center', 'center'))
                        .set_duration(video_duration)
                    )
                    clips.insert(0, background_video)
                except Exception as e:
                    logger.error(f"Error creating background video clip: {str(e)}")
                    # Fallback to black background
                    background_clip = ColorClip(
                        size=(self.config.app.video_width, self.config.app.video_height),
                        color=(0, 0, 0),
                        duration=video_duration
                    )
                    clips.insert(0, background_clip)
            # Use image if no video is available
            elif assets["images"]:
                image_path = random.choice(assets["images"])
                try:
                    background_image = (
                        ImageClip(image_path)
                        .resize(height=self.config.app.video_height)
                        .set_position(('center', 'center'))
                        .set_duration(video_duration)
                    )
                    clips.insert(0, background_image)
                except Exception as e:
                    logger.error(f"Error creating background image clip: {str(e)}")
                    # Fallback to black background
                    background_clip = ColorClip(
                        size=(self.config.app.video_width, self.config.app.video_height),
                        color=(0, 0, 0),
                        duration=video_duration
                    )
                    clips.insert(0, background_clip)
            # Fallback to black background if no assets
            else:
                background_clip = ColorClip(
                    size=(self.config.app.video_width, self.config.app.video_height),
                    color=(0, 0, 0),
                    duration=video_duration
                )
                clips.insert(0, background_clip)
            
            # Add captions if requested
            if include_captions and "script" in script_data:
                # Don't add full script caption at the bottom, we'll use popup captions instead
                # Store this in script_data to use when adding pop-up captions
                script_data["use_popup_captions"] = True
            
            # Create final composite
            final_clip = CompositeVideoClip(clips, size=(self.config.app.video_width, self.config.app.video_height))
            
            # Add audio if available
            if audio_clip:
                final_clip = final_clip.set_audio(audio_clip)
            
            # Write output video
            final_clip.write_videofile(
                output_path,
                fps=30,
                codec='libx264',
                audio_codec='aac',
                threads=4,
                preset='medium'
            )
            
            # Clean up
            try:
                for clip in clips:
                    clip.close()
                if audio_clip:
                    audio_clip.close()
                final_clip.close()
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Error during cleanup: {str(e)}")
            
            logger.success(f"Created video: {output_path}")
            
            # Add pop-up captions if requested
            if include_captions and script_data.get("use_popup_captions", False):
                try:
                    from src.content_generation.popup_captions import PopupCaptionStyler
                    
                    # Create popup caption styler
                    popup_styler = PopupCaptionStyler(self.config, self.file_manager)
                    
                    # Use audio path to generate captions based on speech
                    if audio_path and os.path.exists(audio_path):
                        # Generate captions from the audio file
                        logger.info("Adding pop-up style captions to video...")
                        
                        # Determine the output path for captioned video
                        captioned_output_path = output_path
                        temp_output_path = output_path + ".temp.mp4"
                        
                        # Rename the current output to a temp file
                        os.rename(output_path, temp_output_path)
                        
                        # Generate captions based on the audio
                        language = script_data.get("language", self.config.ai.language)
                        
                        # Add pop-up captions to the video
                        captioned_output_path = await popup_styler.add_popup_captions_to_video(
                            video_path=temp_output_path,
                            output_path=captioned_output_path,
                            language=language
                        )
                        
                        # Clean up the temp file if successful
                        if os.path.exists(captioned_output_path) and os.path.exists(temp_output_path):
                            os.remove(temp_output_path)
                        
                        logger.success(f"Added pop-up style captions to video: {captioned_output_path}")
                        return captioned_output_path
                except Exception as e:
                    logger.error(f"Error adding pop-up captions, using regular captions instead: {str(e)}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating video: {str(e)}")
            raise


class ContentShortEngine(ContentVideoEngine):
    """
    Specialized engine for creating short-form content.
    """
    
    async def create_tiktok_video(
        self,
        topic: str,
        voice_gender: str = "male",
        include_voiceover: bool = True,
        language: Optional[str] = None,
        output_path: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Union[str, Dict]]:
        """
        Create a TikTok-optimized video.
        
        Args:
            topic: Video topic
            voice_gender: Voice gender for voiceover
            include_voiceover: Whether to include voiceover
            language: Language code for content
            output_path: Path to save the output video (optional)
            title: Video title (optional)
            
        Returns:
            Dictionary with information about the created video
        """
        # TikTok-specific settings
        return await self.create_shorts_video(
            topic=topic,
            voice_gender=voice_gender,
            include_voiceover=include_voiceover,
            include_captions=True,  # Always include captions for TikTok
            language=language,
            output_path=output_path,
            title=title
        )


# Helper function needed for video creation
def ColorClip(size, color, duration):
    """Create a solid color clip."""
    from moviepy.editor import ColorClip as MoviePyColorClip
    return MoviePyColorClip(size, color=color, duration=duration)


if __name__ == "__main__":
    # Simple test for the content engine
    from src.utils.config_loader import ConfigLoader
    
    async def test_content_engine():
        config_loader = ConfigLoader()
        config = config_loader.get_config()
        
        engine = ContentVideoEngine(config)
        
        result = await engine.create_content_video(
            topic="The benefits of meditation",
            duration=30,
            style="informative",
            include_voiceover=True,
            include_captions=True
        )
        
        print(f"Created video at: {result['video_path']}")
    
    # Run the test
    asyncio.run(test_content_engine()) 