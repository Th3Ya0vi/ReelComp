"""
Caption Generator Module

Generates timestamped captions from audio using speech recognition.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import whisper
from loguru import logger
from moviepy.editor import AudioFileClip, VideoFileClip

from src.utils.config_loader import Config
from src.utils.file_manager import FileManager


class CaptionGenerator:
    """
    Generates timestamped captions from audio for video content.
    Uses OpenAI Whisper for speech recognition.
    """
    
    def __init__(self, config: Config, file_manager: Optional[FileManager] = None):
        """
        Initialize the caption generator with config.
        
        Args:
            config: Application configuration
            file_manager: File manager instance (optional)
        """
        self.config = config
        self.file_manager = file_manager
        self._model = None
    
    @property
    def model(self):
        """Lazy-load the Whisper model when needed to save memory."""
        if self._model is None:
            # Use a smaller model by default for faster processing
            model_size = getattr(self.config.ai, "whisper_model_size", "base")
            
            # Clean up any comments in the model size
            if isinstance(model_size, str) and "#" in model_size:
                model_size = model_size.split("#")[0].strip()
                
            logger.info(f"Loading Whisper {model_size} model...")
            self._model = whisper.load_model(model_size)
        return self._model
    
    async def generate_captions(
        self, 
        audio_path: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Union[str, float]]]:
        """
        Generate timestamped captions from an audio file.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (optional, will be detected if not provided)
            
        Returns:
            List of caption segments with text and timestamps
        """
        try:
            logger.info(f"Generating captions for audio: {audio_path}")
            
            # Ensure audio path exists
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return []
            
            # Process with Whisper
            whisper_options = {}
            if language:
                # Normalize language code format for Whisper
                # Whisper expects lowercase, no country code (e.g. "en" not "en-US")
                base_language = language.split('-')[0].lower()
                whisper_options["language"] = base_language
                logger.debug(f"Using language '{base_language}' for speech recognition")
            
            result = self.model.transcribe(audio_path, **whisper_options)
            
            # Extract segments with timestamps
            segments = result.get("segments", [])
            
            # Format for our usage
            captions = []
            for segment in segments:
                # Clean text from script directions like (pause), [emphasis], etc.
                text = segment["text"].strip()
                text = self._clean_script_directions(text)
                
                # Skip empty segments after cleaning
                if not text:
                    continue
                
                captions.append({
                    "text": text,
                    "start": segment["start"],
                    "end": segment["end"]
                })
            
            logger.success(f"Generated {len(captions)} caption segments")
            return captions
            
        except Exception as e:
            logger.error(f"Error generating captions: {str(e)}")
            return []
    
    def _clean_script_directions(self, text: str) -> str:
        """
        Clean script directions and other unwanted elements from the caption text.
        
        Args:
            text: Raw caption text
            
        Returns:
            Cleaned caption text
        """
        import re
        
        # Remove text in parentheses like (pause), (laughs), etc.
        text = re.sub(r'\([^)]*\)', '', text)
        
        # Remove text in brackets like [emphasis], [music], etc.
        text = re.sub(r'\[[^\]]*\]', '', text)
        
        # Remove common script directions
        directions = ['pause', 'emphasis', 'music', 'sound effect', 'sfx', 'welcome to our video', 
                      'intro music', 'outro music', 'fade in', 'fade out', 'cut to']
        for direction in directions:
            text = re.sub(rf'\b{direction}\b', '', text, flags=re.IGNORECASE)
        
        # Remove duplicate words that may come from incorrect transcription
        words = text.split()
        if len(words) > 1:
            cleaned_words = [words[0]]
            for i in range(1, len(words)):
                if words[i].lower() != words[i-1].lower():
                    cleaned_words.append(words[i])
            text = ' '.join(cleaned_words)
        
        # Clean up extra spaces and punctuation
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'(\.|,|;|:|!|\?)\s*(\.|,|;|:|!|\?)', r'\1', text)  # Remove consecutive punctuation
        text = text.strip()
        
        return text
    
    async def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """
        Extract audio from a video file for captioning.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Path to the extracted audio file
        """
        try:
            # Generate output path
            if self.file_manager:
                audio_path = self.file_manager.get_temp_path(extension="mp3")
            else:
                temp_dir = tempfile.mkdtemp()
                audio_path = os.path.join(temp_dir, f"audio_{os.urandom(4).hex()}.mp3")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)
            
            # Extract audio
            video = VideoFileClip(video_path)
            audio = video.audio
            audio.write_audiofile(audio_path, logger=None)
            
            # Close clips
            audio.close()
            video.close()
            
            return audio_path
            
        except Exception as e:
            logger.error(f"Error extracting audio from video: {str(e)}")
            return None
    
    async def generate_captions_for_video(
        self, 
        video_path: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Union[str, float]]]:
        """
        Generate timestamped captions directly from a video file.
        
        Args:
            video_path: Path to the video file
            language: Language code (optional, will be detected if not provided)
            
        Returns:
            List of caption segments with text and timestamps
        """
        # Extract audio from video
        audio_path = await self.extract_audio_from_video(video_path)
        
        if not audio_path:
            return []
        
        try:
            # Get video duration for validation
            from moviepy.editor import VideoFileClip
            try:
                video = VideoFileClip(video_path)
                video_duration = video.duration
                video.close()
            except Exception:
                video_duration = None
            
            # Generate captions from the audio
            captions = await self.generate_captions(audio_path, language)
            
            # Validate and adjust captions if we have video duration
            if video_duration and captions:
                # Filter out captions that start after video ends
                captions = [c for c in captions if c["start"] < video_duration]
                
                # Adjust end times for captions that extend beyond video
                for caption in captions:
                    if caption["end"] > video_duration:
                        caption["end"] = video_duration
            
            # Clean up temporary audio file
            try:
                os.remove(audio_path)
            except Exception:
                pass
            
            return captions
            
        except Exception as e:
            logger.error(f"Error generating captions for video: {str(e)}")
            return []


# For testing
if __name__ == "__main__":
    import asyncio
    from src.utils.config_loader import ConfigLoader
    
    async def test_caption_generator():
        # Setup
        config_loader = ConfigLoader()
        config = config_loader.get_config()
        
        caption_generator = CaptionGenerator(config)
        
        # Test on a video with known speech
        test_video = "path_to_test_video.mp4"  # Replace with an actual test video path
        
        if os.path.exists(test_video):
            captions = await caption_generator.generate_captions_for_video(test_video)
            
            print(f"Generated {len(captions)} captions:")
            for i, caption in enumerate(captions[:5]):  # Print first 5 captions
                print(f"{i+1}. [{caption['start']:.2f} - {caption['end']:.2f}]: {caption['text']}")
        else:
            print(f"Test video not found: {test_video}")
    
    # Run the test
    asyncio.run(test_caption_generator()) 