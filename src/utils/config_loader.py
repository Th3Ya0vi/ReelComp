"""
Configuration Loader Utility

Loads configuration from environment variables and JSON files, using Pydantic for validation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any, List

from dotenv import load_dotenv
from loguru import logger
from pydantic_settings import BaseSettings


class TikTokConfig(BaseSettings):
    """TikTok API configuration settings."""
    
    # TikTok authentication tokens
    ms_token: Optional[str] = None
    session_id: Optional[str] = None
    
    # Simplified TikTok configuration (no API credentials needed)
    
    class Config:
        env_prefix = "TIKTOK_"
        extra = "ignore"


class YoutubeConfig(BaseSettings):
    """YouTube API configuration settings."""
    
    # Basic YouTube settings
    default_category_id: str = "22"  # People & Blogs
    privacy_status: str = "private"
    client_secrets_path: str = "credentials/client_secret.json"
    token_path: str = "credentials/youtube_token.json"
    
    class Config:
        env_prefix = "YOUTUBE_"
        extra = "ignore"


class AIConfig(BaseSettings):
    """AI services configuration settings."""
    
    # OpenAI settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    
    # Voice synthesis settings
    voice_provider: str = "edge_tts"  # Options: edge_tts, elevenlabs
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # Default male voice
    
    # Language settings
    language: str = "en-US"  # Default language code
    supported_languages: List[str] = [
        "en-US", "es-ES", "fr-FR", "de-DE", "it-IT", 
        "pt-PT", "ru-RU", "zh-CN", "ja-JP", "ko-KR",
        "ar-AE", "hi-IN", "pl-PL"
    ]
    
    # Image/Video API keys
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None
    unsplash_access_key: Optional[str] = None
    
    # Whisper settings for speech recognition
    whisper_model_size: str = "base"  # Options: tiny, base, small, medium, large
    use_popup_captions: bool = True  # Use TikTok-style pop-up captions
    
    class Config:
        env_prefix = ""  # Removed AI_ prefix to use direct environment variable names
        extra = "ignore"
        
    @classmethod
    def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
        """
        Parse environment variables, handling string values with comments.
        """
        if field_name == "use_popup_captions" and isinstance(raw_val, str):
            if "#" in raw_val:
                # Remove comment from the boolean value
                raw_val = raw_val.split("#")[0].strip()
            
            # Convert to boolean
            if raw_val.lower() in ("true", "1", "yes", "y", "on"):
                return True
            elif raw_val.lower() in ("false", "0", "no", "n", "off"):
                return False
            # If it's not a recognized boolean value, use default
            return True
        
        if "#" in raw_val and isinstance(raw_val, str):
            # For other values with comments, remove the comment
            raw_val = raw_val.split("#")[0].strip()
        
        # For other fields, use the default parser
        return raw_val


class AppConfig(BaseSettings):
    """Application configuration settings."""
    
    debug: bool = False
    log_level: str = "INFO"
    base_dir: str = "data"
    temp_dir: str = "data/temp"
    download_dir: str = "data/downloaded_videos"
    compilation_dir: str = "data/compilations"
    thumbnail_dir: str = "data/thumbnails"
    shorts_dir: str = "data/shorts"  # Directory for YouTube Shorts
    log_dir: str = "logs"
    max_file_age_days: int = 7
    max_videos_per_compilation: int = 200
    min_videos_per_compilation: int = 3
    video_width: int = 1080
    video_height: int = 1920
    use_intro: bool = False
    intro_path: Optional[str] = None
    use_outro: bool = False
    outro_path: Optional[str] = None
    include_video_titles: bool = True
    transition_type: str = "random"
    thumbnail_width: int = 1280
    thumbnail_height: int = 720
    auto_upload: bool = False
    assets_dir: str = "data/assets"
    max_duration_per_clip: Optional[float] = None  # None means use full video length
    
    class Config:
        env_prefix = "APP_"
        extra = "ignore"


class Config:
    """Main configuration class combining all settings."""
    
    def __init__(self):
        """Initialize the Config object with default settings."""
        self.tiktok = TikTokConfig()
        self.youtube = YoutubeConfig()
        self.app = AppConfig()
        self.ai = AIConfig()


class ConfigLoader:
    """Loads and manages application configuration."""
    
    def __init__(self, env_file: Optional[str] = ".env"):
        """
        Initialize the configuration loader.
        
        Args:
            env_file: Path to .env file (optional)
        """
        self.env_file = env_file
        
        # Load environment variables from .env file if it exists and is not None
        if env_file is not None and os.path.exists(env_file):
            load_dotenv(dotenv_path=env_file)
            logger.debug(f"Loaded environment variables from {env_file}")
    
    def get_config(self, config_file: Optional[str] = None) -> Config:
        """
        Get application configuration from environment and optional config file.
        
        Args:
            config_file: Optional path to JSON configuration file
            
        Returns:
            Config object with all configuration settings
        """
        # Create config object
        config = Config()
        
        # Clean up any environment variables with comments
        self._clean_environment_variables()
        
        # Load from config file if provided and it exists
        if config_file is not None and os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                
                logger.info(f"Loaded configuration from {config_file}")
                
                # Update tiktok config
                if "tiktok" in file_config:
                    for key, value in file_config["tiktok"].items():
                        if hasattr(config.tiktok, key):
                            setattr(config.tiktok, key, value)
                
                # Update youtube config
                if "youtube" in file_config:
                    for key, value in file_config["youtube"].items():
                        if hasattr(config.youtube, key):
                            setattr(config.youtube, key, value)
                
                # Update app config
                if "app" in file_config:
                    for key, value in file_config["app"].items():
                        if hasattr(config.app, key):
                            setattr(config.app, key, value)
                
                # Update AI config
                if "ai" in file_config:
                    for key, value in file_config["ai"].items():
                        if hasattr(config.ai, key):
                            setattr(config.ai, key, value)
                            
            except Exception as e:
                logger.error(f"Error loading config file {config_file}: {str(e)}")
        
        return config
        
    def _clean_environment_variables(self):
        """
        Clean up environment variables, removing comments and converting string values to appropriate types.
        """
        for key, value in os.environ.items():
            if isinstance(value, str):
                # Remove comments from booleans
                if value.lower().startswith(('true', 'false')):
                    # Extract the actual boolean value
                    if '#' in value:
                        clean_value = value.split('#')[0].strip()
                        os.environ[key] = clean_value
                
                # Handle explicitly for use_popup_captions
                if key == 'USE_POPUP_CAPTIONS' and '#' in value:
                    clean_value = value.split('#')[0].strip()
                    os.environ[key] = clean_value


# Example usage
if __name__ == "__main__":
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Print configuration
    print(f"TikTok Config: {config.tiktok}")
    print(f"YouTube Config: {config.youtube}")
    print(f"App Config: {config.app}")
    print(f"AI Config: {config.ai}") 