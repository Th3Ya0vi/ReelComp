"""
Test script that creates a new test video with all the fixes applied
"""

import asyncio
import os
import uuid
from pathlib import Path
import textwrap

from src.content_generation.content_engine import ContentVideoEngine
from src.content_generation.popup_captions import PopupCaptionStyler
from src.content_generation.voiceover_generator import VoiceoverGenerator
from src.utils.config_loader import Config, AIConfig, AppConfig
from loguru import logger
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip, TextClip


class TestConfig(Config):
    """Test config that overrides problematic settings"""
    
    def __init__(self):
        """Initialize with overridden settings"""
        # Create AI config with explicit values
        self.ai = AIConfig(
            openai_api_key=os.environ.get("openai_api_key"),
            openai_model="gpt-4",
            voice_provider="edge_tts",
            language="en-US",
            whisper_model_size="base",
            use_popup_captions=True  # Explicitly set as Python boolean
        )
        
        # Create app config
        self.app = AppConfig(
            video_width=1080,
            video_height=1920
        )


async def test_simple_video_with_captions():
    """Create a simpler test video with synchronized captions"""
    
    # Create test config
    config = TestConfig()
    
    # Create required components
    voiceover_gen = VoiceoverGenerator(config)
    caption_styler = PopupCaptionStyler(config)
    
    # Output path
    output_dir = "data/compilations"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a simple script for testing
    test_script = textwrap.dedent("""
    Welcome to our video about options trading.
    
    Options trading offers several benefits for investors.
    
    First, you can make money whether the market goes up or down.
    
    Second, options require less financial commitment than buying stocks directly.
    
    Finally, options can help protect your existing investments against market changes.
    
    Thanks for watching and good luck with your investments!
    """).strip()
    
    # Generate voiceover
    audio_path = await voiceover_gen.generate_voiceover(
        script=test_script,
        output_path=os.path.join(output_dir, f"test_audio_{uuid.uuid4().hex[:8]}.mp3")
    )
    
    # Create a simple black background video
    audio_clip = AudioFileClip(audio_path)
    audio_duration = audio_clip.duration
    
    bg_clip = ColorClip(
        size=(config.app.video_width, config.app.video_height),
        color=(0, 0, 0),
        duration=audio_duration
    )
    
    # Set audio for background clip
    bg_clip = bg_clip.set_audio(audio_clip)
    
    # Create a temporary video file
    temp_video_path = os.path.join(output_dir, f"temp_video_{uuid.uuid4().hex[:8]}.mp4")
    
    # Write the video file
    bg_clip.write_videofile(
        temp_video_path,
        fps=30,
        codec='libx264',
        audio_codec='aac'
    )
    
    # Now add captions to the video
    output_path = os.path.join(output_dir, f"fixed_test_{uuid.uuid4().hex[:8]}.mp4")
    
    try:
        # Add popup captions
        logger.info(f"Adding captions to video: {temp_video_path}")
        result = await caption_styler.add_popup_captions_to_video(
            video_path=temp_video_path,
            output_path=output_path
        )
        
        logger.success(f"Created test video with captions: {result}")
        
        # Clean up temp file
        try:
            os.remove(temp_video_path)
        except:
            pass
    except Exception as e:
        logger.error(f"Error adding captions: {str(e)}")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_simple_video_with_captions()) 