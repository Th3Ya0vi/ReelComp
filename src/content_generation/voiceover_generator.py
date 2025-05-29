"""
Voiceover Generator Module

Generates voiceovers from script text using various text-to-speech engines.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import re

import edge_tts
from loguru import logger

from src.utils.config_loader import Config
from src.utils.file_manager import FileManager

try:
    from elevenlabs import generate, save, set_api_key, voices
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logger.warning("ElevenLabs not available. Install with 'pip install elevenlabs' for premium voice synthesis.")


class VoiceoverGenerator:
    """
    Generates voiceovers from script text using various text-to-speech engines.
    """
    
    # Default English voices for Edge TTS
    DEFAULT_EDGE_VOICES = {
        "male": "en-US-ChristopherNeural",
        "female": "en-US-JennyNeural"
    }
    
    # Default language to voice mapping for Edge TTS
    LANGUAGE_TO_VOICE = {
        "en-US": {"male": "en-US-ChristopherNeural", "female": "en-US-JennyNeural"},
        "es-ES": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
        "fr-FR": {"male": "fr-FR-HenriNeural", "female": "fr-FR-DeniseNeural"},
        "de-DE": {"male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural"},
        "it-IT": {"male": "it-IT-DiegoNeural", "female": "it-IT-ElsaNeural"},
        "pt-PT": {"male": "pt-PT-DuarteNeural", "female": "pt-PT-RaquelNeural"},
        "ru-RU": {"male": "ru-RU-DmitryNeural", "female": "ru-RU-SvetlanaNeural"},
        "zh-CN": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
        "ja-JP": {"male": "ja-JP-KeitaNeural", "female": "ja-JP-NanamiNeural"},
        "ko-KR": {"male": "ko-KR-InJoonNeural", "female": "ko-KR-SunHiNeural"},
        "ar-AE": {"male": "ar-AE-HamdanNeural", "female": "ar-AE-FatimaNeural"},
        "hi-IN": {"male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural"},
        "pl-PL": {"male": "pl-PL-MarekNeural", "female": "pl-PL-ZofiaNeural"}
    }
    
    def __init__(self, config: Config, file_manager: Optional[FileManager] = None):
        """
        Initialize the voiceover generator with config.
        
        Args:
            config: Application configuration
            file_manager: File manager instance (optional)
        """
        self.config = config
        self.file_manager = file_manager
        
        # Initialize ElevenLabs if available and API key is provided
        if ELEVENLABS_AVAILABLE and self.config.ai.elevenlabs_api_key:
            set_api_key(self.config.ai.elevenlabs_api_key)
    
    async def generate_voiceover(
        self, 
        script: str, 
        output_path: Optional[str] = None,
        voice_gender: str = "male",
        language: Optional[str] = None
    ) -> str:
        """
        Generate a voiceover from script text.
        
        Args:
            script: Script text to synthesize
            output_path: Path to save the audio file (optional)
            voice_gender: Voice gender to use (male or female)
            language: Language code (defaults to config setting)
            
        Returns:
            Path to the generated audio file
        """
        # Use language from config if not specified
        if language is None:
            language = self.config.ai.language
        
        # Generate output path if not provided
        if output_path is None:
            if self.file_manager:
                output_path = self.file_manager.get_temp_path(extension="mp3")
            else:
                # Create a temporary directory if file manager not available
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, f"voiceover_{os.urandom(4).hex()}.mp3")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate voiceover based on provider
        if self.config.ai.voice_provider == "elevenlabs" and ELEVENLABS_AVAILABLE and self.config.ai.elevenlabs_api_key:
            logger.info(f"Generating ElevenLabs voiceover for language: {language}")
            return await self._generate_elevenlabs_voiceover(script, output_path, voice_gender, language)
        else:
            logger.info(f"Generating Edge TTS voiceover for language: {language}")
            return await self._generate_edge_tts_voiceover(script, output_path, voice_gender, language)
    
    async def _generate_edge_tts_voiceover(
        self, 
        script: str, 
        output_path: str,
        voice_gender: str = "male",
        language: str = "en-US"
    ) -> str:
        """
        Generate a voiceover using Edge TTS.
        
        Args:
            script: Script text to synthesize
            output_path: Path to save the audio file
            voice_gender: Voice gender to use (male or female)
            language: Language code
            
        Returns:
            Path to the generated audio file
        """
        try:
            # Get appropriate voice for language and gender
            voice = self._get_edge_tts_voice(language, voice_gender)
            
            # Normalize script for TTS (add punctuation if missing)
            script = self._normalize_script_for_tts(script)
            
            # Create communicate object
            communicate = edge_tts.Communicate(script, voice)
            
            # Create generator and save to file
            await communicate.save(output_path)
            
            logger.success(f"Generated Edge TTS voiceover: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating Edge TTS voiceover: {str(e)}")
            raise
    
    async def _generate_elevenlabs_voiceover(
        self, 
        script: str, 
        output_path: str,
        voice_gender: str = "male",
        language: str = "en-US"
    ) -> str:
        """
        Generate a voiceover using ElevenLabs.
        
        Args:
            script: Script text to synthesize
            output_path: Path to save the audio file
            voice_gender: Voice gender to use (male or female)
            language: Language code (note: ElevenLabs has limited language support)
            
        Returns:
            Path to the generated audio file
        """
        if not ELEVENLABS_AVAILABLE:
            logger.error("ElevenLabs not available. Using Edge TTS as fallback.")
            return await self._generate_edge_tts_voiceover(script, output_path, voice_gender, language)
        
        try:
            # Use specified voice ID or default to a standard voice
            voice_id = self.config.ai.elevenlabs_voice_id
            
            # Check if language is supported (ElevenLabs primarily supports English)
            if not language.startswith("en"):
                logger.warning(f"ElevenLabs may have limited support for {language}. Results may vary.")
            
            # Normalize script for TTS
            script = self._normalize_script_for_tts(script)
            
            # Generate audio
            audio = generate(
                text=script,
                voice=voice_id,
                model="eleven_monolingual_v1"
            )
            
            # Save to file
            save(audio, output_path)
            
            logger.success(f"Generated ElevenLabs voiceover: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating ElevenLabs voiceover: {str(e)}, falling back to Edge TTS")
            # Fallback to Edge TTS
            return await self._generate_edge_tts_voiceover(script, output_path, voice_gender, language)
    
    def _get_edge_tts_voice(self, language: str, gender: str = "male") -> str:
        """
        Get the appropriate Edge TTS voice for the specified language and gender.
        
        Args:
            language: Language code
            gender: Voice gender (male or female)
            
        Returns:
            Voice ID for Edge TTS
        """
        # Normalize gender
        gender = gender.lower()
        if gender not in ["male", "female"]:
            gender = "male"
        
        # Check if we have a mapping for this language
        if language in self.LANGUAGE_TO_VOICE:
            return self.LANGUAGE_TO_VOICE[language][gender]
        
        # Fallback to default English voice
        logger.warning(f"No voice mapping found for language {language}, falling back to English")
        return self.DEFAULT_EDGE_VOICES[gender]
    
    def _normalize_script_for_tts(self, script: str) -> str:
        """
        Normalize script text for TTS by removing script directions and ensuring proper punctuation.
        Also removes filler content and subscription-related phrases.
        
        Args:
            script: Original script text
            
        Returns:
            Normalized script text
        """
        # Remove script directions in parentheses and brackets
        script = re.sub(r'\([^)]*\)', '', script)
        script = re.sub(r'\[[^\]]*\]', '', script)
        
        # Remove common script directions and filler content
        unwanted_phrases = [
            'pause', 'emphasis', 'welcome to our video', 'music', 'sound effect', 
            'sfx', 'fade in', 'fade out', 'cut to', 'scene', 'title card',
            'welcome to', 'thanks for watching', "don't forget to", 'like and subscribe',
            'in this video', "let's dive into", "today we're going to", 'make sure to',
            'if you enjoyed', 'hit the like button', 'ring the notification bell',
            'without further ado', 'so without delay', "let's get started",
            'subscribe for more', 'hit subscribe', 'smash that like button',
            'turn on notifications', 'ring that notification bell'
        ]
        
        for phrase in unwanted_phrases:
            # Remove phrase with various punctuation endings
            script = re.sub(rf'\b{phrase}\b[^.!?]*[.!?]?', '', script, flags=re.IGNORECASE)
            # Also remove the phrase if it appears mid-sentence
            script = re.sub(rf'\b{phrase}\b', '', script, flags=re.IGNORECASE)
        
        # Remove common transitional filler phrases
        filler_transitions = [
            r'\b(so|now|next|well|alright|okay)\,?\s+',
            r'\b(you know|um|uh|like)\s+',
            r'\b(basically|essentially|actually)\s+',
            r'\blet me tell you\b',
            r'\byou see\b',
            r'\bas you can see\b'
        ]
        
        for pattern in filler_transitions:
            script = re.sub(pattern, ' ', script, flags=re.IGNORECASE)
        
        # Clean up any extra whitespace from removals
        script = re.sub(r'\s+', ' ', script).strip()
        
        # Remove empty sentences (just punctuation)
        script = re.sub(r'\s*[.!?]+\s*', '. ', script)
        script = re.sub(r'^\.\s*', '', script)  # Remove leading period
        
        # Add period at the end if missing punctuation
        if script and not script[-1] in ['.', '!', '?']:
            script += '.'
        
        # Final cleanup - remove any remaining double spaces
        script = re.sub(r'\s+', ' ', script).strip()
        
        return script
    
    async def generate_section_voiceovers(
        self, 
        sections: List[Dict[str, str]], 
        output_dir: Optional[str] = None,
        voice_gender: str = "male",
        language: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Generate separate voiceovers for each script section.
        
        Args:
            sections: List of section dictionaries, each with a 'content' key
            output_dir: Directory to save audio files (optional)
            voice_gender: Voice gender to use
            language: Language code
            
        Returns:
            List of section dictionaries with added 'audio_path' key
        """
        # Use language from config if not specified
        if language is None:
            language = self.config.ai.language
        
        # Generate output directory if not provided
        if output_dir is None:
            if self.file_manager:
                output_dir = os.path.join(self.file_manager.config.app.temp_dir, f"sections_{os.urandom(4).hex()}")
            else:
                output_dir = tempfile.mkdtemp()
        
        # Ensure directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize updated sections
        updated_sections = []
        
        # Process each section
        for i, section in enumerate(sections):
            if "content" not in section:
                logger.warning(f"Section {i} missing 'content' key, skipping")
                updated_sections.append(section)
                continue
            
            # Generate output path for this section
            section_path = os.path.join(output_dir, f"section_{i:03d}.mp3")
            
            # Generate voiceover
            audio_path = await self.generate_voiceover(
                script=section["content"],
                output_path=section_path,
                voice_gender=voice_gender,
                language=language
            )
            
            # Update section with audio path
            updated_section = section.copy()
            updated_section["audio_path"] = audio_path
            updated_sections.append(updated_section)
        
        return updated_sections


if __name__ == "__main__":
    # Simple test for the voiceover generator
    from src.utils.config_loader import ConfigLoader
    
    async def test_voiceover():
        config_loader = ConfigLoader()
        config = config_loader.get_config()
        
        generator = VoiceoverGenerator(config)
        
        test_script = "This is a test of the voiceover generator. It should create an audio file with this text."
        
        audio_path = await generator.generate_voiceover(
            script=test_script,
            output_path="test_voiceover.mp3"
        )
        
        print(f"Generated voiceover at: {audio_path}")
    
    # Run the test
    asyncio.run(test_voiceover()) 