"""
Pop-up Captions Module

Adds TikTok-style pop-up captions to videos based on timestamped transcriptions.
"""

import os
import re
import random
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from loguru import logger
from moviepy.editor import (
    CompositeVideoClip, TextClip, VideoClip, VideoFileClip, ColorClip
)

from src.content_generation.caption_generator import CaptionGenerator
from src.utils.config_loader import Config
from src.utils.file_manager import FileManager


class PopupCaptionStyler:
    """
    Creates TikTok-style pop-up captions for videos.
    """
    
    # Default font settings
    DEFAULT_STYLES = {
        "standard": {
            "font": "Arial-Bold",
            "fontsize": 60,
            "color": "white",
            "stroke_color": "black",
            "stroke_width": 1.5,
            "method": "caption",
        },
        "highlight": {
            "font": "Arial-Bold",
            "fontsize": 65,
            "color": "#FFDD33",
            "bg_color": "rgba(0,0,0,0.7)",
            "stroke_color": "black",
            "stroke_width": 1.5,
            "method": "caption",
            "align": "center",
        },
        "big": {
            "font": "Arial-Bold",
            "fontsize": 75,
            "color": "#FF5555",
            "stroke_color": "black",
            "stroke_width": 2,
            "method": "caption",
            "align": "center",
        },
        "accent": {
            "font": "Helvetica-Bold",
            "fontsize": 65,
            "color": "#5599FF",
            "bg_color": "rgba(0,0,0,0.6)",
            "stroke_color": "black",
            "stroke_width": 1.5,
            "method": "caption",
            "align": "center",
        },
        "emphasis": {
            "font": "Georgia-Bold",
            "fontsize": 65,
            "color": "#66DDAA",
            "bg_color": "rgba(0,0,0,0.6)",
            "stroke_color": "black",
            "stroke_width": 1.5,
            "method": "caption",
            "align": "center",
        }
    }
    
    # Animation styles for pop-up effects
    ANIMATION_STYLES = [
        "fade-in", "slide-up", "slide-left", "slide-right"
    ]
    
    # Available fonts that should work on most systems
    SYSTEM_FONTS = [
        "Arial-Bold", "Helvetica-Bold", "Georgia-Bold", 
        "Verdana-Bold", "Courier-Bold", "Times-Bold"
    ]

    def __init__(self, config: Config, file_manager: Optional[FileManager] = None):
        """
        Initialize the pop-up caption styler.
        
        Args:
            config: Application configuration
            file_manager: File manager instance (optional)
        """
        self.config = config
        self.file_manager = file_manager
        self.caption_generator = CaptionGenerator(config, file_manager)
    
    async def add_popup_captions_to_video(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        captions: Optional[List[Dict[str, Union[str, float]]]] = None,
        language: Optional[str] = None
    ) -> str:
        """
        Add pop-up captions to a video.
        
        Args:
            video_path: Path to the input video
            output_path: Path to save the output video (optional)
            captions: Pre-generated captions (optional, will generate if not provided)
            language: Language code for speech recognition (optional)
            
        Returns:
            Path to the output video with captions
        """
        try:
            # Generate output path if not provided
            if output_path is None:
                if self.file_manager:
                    output_path = self.file_manager.get_compilation_path(
                        prefix="captioned_video",
                        title=os.path.basename(video_path).split('.')[0]
                    )
                else:
                    dirname = os.path.dirname(video_path)
                    basename = os.path.basename(video_path)
                    name, ext = os.path.splitext(basename)
                    output_path = os.path.join(dirname, f"{name}_captioned{ext}")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Load video
            video = VideoFileClip(video_path)
            
            # Generate captions if not provided
            if not captions:
                logger.info("Generating captions for video...")
                captions = await self.caption_generator.generate_captions_for_video(video_path, language)
            
            if not captions:
                logger.warning("No captions generated. Returning original video.")
                video.write_videofile(output_path)
                video.close()
                return output_path
            
            # Add pop-up captions to video
            logger.info(f"Adding {len(captions)} pop-up captions to video...")
            
            try:
                captioned_video = self._add_popup_captions(video, captions)
                
                # Write output video
                captioned_video.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile=f"{output_path}.temp_audio.m4a",
                    remove_temp=True,
                    fps=30
                )
                
                # Clean up
                captioned_video.close()
                
                logger.success(f"Created video with pop-up captions: {output_path}")
            except Exception as e:
                logger.error(f"Error creating pop-up captions: {str(e)}")
                # Fallback to original video
                video.write_videofile(output_path)
            
            # Always close the video
            video.close()
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding pop-up captions to video: {str(e)}")
            # Attempt to return original video if processing fails
            try:
                if not os.path.exists(output_path) and os.path.exists(video_path):
                    import shutil
                    shutil.copy(video_path, output_path)
                    return output_path
            except Exception:
                pass
            return video_path
    
    def _add_popup_captions(
        self,
        video: VideoFileClip,
        captions: List[Dict[str, Union[str, float]]]
    ) -> CompositeVideoClip:
        """
        Add styled pop-up captions to a video.
        
        Args:
            video: VideoFileClip to add captions to
            captions: List of caption segments with text and timestamps
            
        Returns:
            CompositeVideoClip with captions added
        """
        # Calculate dimensions
        video_width = video.w
        video_height = video.h
        
        # Create caption clips
        caption_clips = []
        
        # Process the captions to identify repeated words that should be removed
        # like "how" appearing in every caption
        self._remove_repeated_filler_words(captions)
        
        # Ensure captions don't overlap in time (important for sync)
        self._adjust_caption_timings(captions)
        
        # Special handling for "Thanks for watching" - only include at the end
        has_thanks_for_watching = False
        ending_caption_index = None
        
        for i, caption in enumerate(captions):
            text = caption["text"]
            
            # Check if this is likely a "thanks for watching" segment
            if "thank" in text.lower() and "watch" in text.lower():
                has_thanks_for_watching = True
                ending_caption_index = i
        
        # Get the video duration for later checks
        video_duration = video.duration
        
        for i, caption in enumerate(captions):
            text = caption["text"]
            start_time = caption["start"]
            end_time = caption["end"]
            
            # Sanity check on times to ensure they're within video bounds
            if start_time >= video_duration:
                continue
                
            if end_time > video_duration:
                end_time = video_duration
                
            # Ensure minimum duration for readability
            if end_time - start_time < 0.8:
                end_time = min(start_time + 0.8, video_duration)
                
            # Skip very short segments (less than 0.3 seconds)
            if end_time - start_time < 0.3:
                continue
                
            # Skip "thanks for watching" if not at the end
            if has_thanks_for_watching and "thank" in text.lower() and "watch" in text.lower() and i != ending_caption_index:
                continue
                
            # Skip empty captions after cleaning
            if not text.strip():
                continue
            
            # Determine caption style and animation
            style_name = self._determine_caption_style(text, i)
            style = self.DEFAULT_STYLES[style_name].copy()
            animation_style = random.choice(self.ANIMATION_STYLES)
            
            # Create text clip
            txt_clip = self._create_text_clip(
                text, 
                style, 
                video_width, 
                video_height,
                animation_style,
                start_time, 
                end_time
            )
            
            # Skip if the text clip creation failed
            if txt_clip is None:
                continue
                
            # Add to list of caption clips
            caption_clips.append(txt_clip)
        
        # If we have no caption clips, return the original video
        if not caption_clips:
            return video
            
        # Combine with original video
        final_clip = CompositeVideoClip([video] + caption_clips, size=(video_width, video_height))
        
        return final_clip
    
    def _remove_repeated_filler_words(self, captions: List[Dict[str, Union[str, float]]]) -> None:
        """
        Remove repeated filler words from captions.
        Looks for words that appear in most or all captions and removes them.
        
        Args:
            captions: List of caption segments with text and timestamps
        """
        if not captions or len(captions) <= 2:
            return
            
        # Count words across all captions
        word_counts = {}
        total_captions = len(captions)
        
        # First, count words in each caption
        for caption in captions:
            text = caption["text"].lower()
            words = set(text.split())  # Use set to count each word once per caption
            
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Find words that appear in more than 70% of captions
        potential_fillers = []
        threshold = total_captions * 0.7
        
        for word, count in word_counts.items():
            if count >= threshold and len(word) > 1:  # Only consider words, not single characters
                potential_fillers.append(word)
        
        # Remove these words from captions
        if potential_fillers:
            logger.debug(f"Removing potential filler words: {potential_fillers}")
            
            for caption in captions:
                text = caption["text"]
                
                # Create regex to match whole words only
                for filler in potential_fillers:
                    text = re.sub(rf'\b{re.escape(filler)}\b', '', text, flags=re.IGNORECASE)
                
                # Clean up extra spaces
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Update caption
                caption["text"] = text
    
    def _adjust_caption_timings(self, captions: List[Dict[str, Union[str, float]]]) -> None:
        """
        Adjust caption timings to prevent overlap and ensure proper display.
        
        Args:
            captions: List of caption segments with text and timestamps
        """
        if not captions or len(captions) <= 1:
            return
            
        # Sort captions by start time to ensure proper processing
        captions.sort(key=lambda c: c["start"])
        
        # Adjust captions to prevent overlap
        for i in range(1, len(captions)):
            prev_caption = captions[i-1]
            curr_caption = captions[i]
            
            # Check for overlap
            if curr_caption["start"] < prev_caption["end"]:
                # Option 1: If very close, make previous caption end earlier
                if curr_caption["start"] > prev_caption["start"] + 0.3:
                    prev_caption["end"] = curr_caption["start"]
                # Option 2: If significant overlap, adjust both
                else:
                    mid_point = (prev_caption["end"] + curr_caption["start"]) / 2
                    prev_caption["end"] = mid_point
                    curr_caption["start"] = mid_point
    
    def _determine_caption_style(self, text: str, index: int) -> str:
        """
        Determine the style to use for a caption based on content and position.
        
        Args:
            text: Caption text
            index: Caption index
            
        Returns:
            Style name to use
        """
        # More varied style assignment
        word_count = len(text.split())
        
        # Short text gets highlight style
        if word_count <= 5:
            return "highlight"
        
        # Excited text gets big style
        if text.isupper() or text.endswith('!') or text.count('!') > 1:
            return "big"
        
        # Questions get accent style
        if text.endswith('?'):
            return "accent"
        
        # Cycle through different styles for variety
        if index % 5 == 0:
            return "highlight"
        elif index % 5 == 1:
            return "accent"
        elif index % 5 == 2:
            return "emphasis"
        elif index % 5 == 3:
            return "big"
        
        return "standard"
    
    def _create_text_clip(
        self,
        text: str,
        style: Dict[str, Union[str, int, float]],
        video_width: int,
        video_height: int,
        animation_style: str,
        start_time: float,
        end_time: float
    ) -> TextClip:
        """
        Create a styled text clip with animation effects.
        
        Args:
            text: Caption text
            style: Style dictionary
            video_width: Width of the video
            video_height: Height of the video
            animation_style: Animation style to apply
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            TextClip with animation
        """
        # Skip if text is empty after cleaning
        if not text.strip():
            return None
            
        # Calculate max width as a percentage of video width
        max_width = int(video_width * 0.85)  # Slightly narrower for better readability
        
        # Ensure font size is appropriate for mobile viewing
        fontsize = style.get("fontsize", 60)  # Default larger fontsize
        if video_height <= 1280:  # Adjust for smaller screens
            fontsize = max(40, int(fontsize * 0.85))  # Increased minimum size
        
        # Add a background for better readability
        bg_color = style.get("bg_color", "rgba(0,0,0,0.6)")  # Semi-transparent black background
        
        # Create text clip
        try:
            txt_clip = TextClip(
                text,
                font=style.get("font", "Arial-Bold"),  # Default to bold
                fontsize=fontsize,
                color=style.get("color", "white"),
                bg_color=bg_color,
                stroke_color=style.get("stroke_color", "black"),
                stroke_width=style.get("stroke_width", 1.5),
                method=style.get("method", "caption"),
                align=style.get("align", "center"),
                size=(max_width, None)
            )
        except Exception as e:
            logger.error(f"Error creating text clip: {str(e)}")
            return None
        
        # Center all captions for consistency
        position = ('center', video_height * 0.5)  # Center of screen for better visibility
        
        # Apply animation effect
        try:
            animated_clip = self._apply_animation(
                txt_clip, 
                animation_style, 
                position, 
                video_width, 
                video_height,
                start_time,
                end_time
            )
            return animated_clip
        except Exception as e:
            logger.error(f"Error applying animation: {str(e)}")
            # Fallback to simple positioning without animation
            return txt_clip.set_position(position).set_start(start_time).set_duration(end_time - start_time)
    
    def _apply_animation(
        self,
        txt_clip: TextClip,
        animation_style: str,
        position: Tuple[str, float],
        video_width: int,
        video_height: int,
        start_time: float,
        end_time: float
    ) -> TextClip:
        """
        Apply animation effect to a text clip.
        
        Args:
            txt_clip: Text clip to animate
            animation_style: Animation style to apply
            position: Final position of the text
            video_width: Width of the video
            video_height: Height of the video
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            Animated text clip
        """
        # Calculate duration and animate in/out times
        duration = end_time - start_time
        anim_in_duration = min(0.3, duration / 4)
        anim_out_duration = min(0.2, duration / 5)
        
        # Simple crossfade - most compatible across moviepy versions
        animated_txt = txt_clip.set_position(position).set_start(start_time).set_duration(duration)
        animated_txt = animated_txt.crossfadein(anim_in_duration).crossfadeout(anim_out_duration)
        
        return animated_txt


# For testing
if __name__ == "__main__":
    import asyncio
    from src.utils.config_loader import ConfigLoader
    
    async def test_popup_captions():
        # Setup
        config_loader = ConfigLoader()
        config = config_loader.get_config()
        
        popup_captions = PopupCaptionStyler(config)
        
        # Test on a video with known speech
        test_video = "path_to_test_video.mp4"  # Replace with an actual test video path
        
        if os.path.exists(test_video):
            output_path = await popup_captions.add_popup_captions_to_video(test_video)
            print(f"Created video with pop-up captions: {output_path}")
        else:
            print(f"Test video not found: {test_video}")
    
    # Run the test
    asyncio.run(test_popup_captions()) 