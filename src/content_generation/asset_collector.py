"""
Asset Collector Module

Collects relevant images and video footage for content creation.
"""

import os
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union
import urllib.request
import urllib.parse
import json
import random
import base64

from loguru import logger
import requests
import numpy as np
from moviepy.editor import ColorClip, TextClip, CompositeVideoClip

from src.utils.config_loader import Config
from src.utils.file_manager import FileManager

try:
    from pexels_api import API
    PEXELS_AVAILABLE = True
except ImportError:
    PEXELS_AVAILABLE = False
    logger.warning("Pexels API not available. Install with 'pip install pexels-api' for improved asset sourcing.")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available. Install with 'pip install openai' for AI image generation.")


class AssetCollector:
    """
    Collects relevant images and video footage from various sources.
    """
    
    def __init__(self, config: Config, file_manager: Optional[FileManager] = None):
        """
        Initialize the asset collector with config.
        
        Args:
            config: Application configuration
            file_manager: File manager instance (optional)
        """
        self.config = config
        self.file_manager = file_manager
        self.pexels_client = None
        
        # Initialize Pexels client if available and API key is provided
        if PEXELS_AVAILABLE and self.config.ai.pexels_api_key:
            self.pexels_client = API(self.config.ai.pexels_api_key)

        # Initialize OpenAI client if available and API key is provided
        self.openai_client = None
        if OPENAI_AVAILABLE and self.config.ai.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=self.config.ai.openai_api_key)
            logger.debug("OpenAI client initialized")
    
    def _ensure_output_directory(self, directory: Optional[str] = None) -> str:
        """
        Ensure the output directory exists.
        
        Args:
            directory: Directory path (optional)
            
        Returns:
            Path to the output directory
        """
        if directory is None:
            if self.file_manager:
                # Use the asset directory from file manager
                directory = os.path.join(self.config.app.assets_dir, f"collected_{int(time.time())}")
            else:
                # Create a directory in the current working directory
                directory = os.path.join(os.getcwd(), "data", "assets", f"collected_{int(time.time())}")
        
        # Ensure the directory exists
        os.makedirs(directory, exist_ok=True)
        
        return directory
    
    def collect_assets(
        self, 
        search_terms: List[str], 
        num_images: int = 5, 
        num_videos: int = 3,
        output_dir: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Collect assets (images and videos) based on search terms.
        
        Args:
            search_terms: List of search terms
            num_images: Number of images to collect
            num_videos: Number of videos to collect
            output_dir: Directory to save assets (optional)
            
        Returns:
            Dictionary with paths to collected assets
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        logger.info(f"Collecting assets for search terms: {search_terms}")
        
        # Initialize result
        result = {
            "images": [],
            "videos": []
        }
        
        # Special handling for financial rules like the 50/30/20 rule
        full_topic = " ".join(search_terms).lower()
        financial_pattern_detected = False
        
        if any(term.isdigit() for term in search_terms) and any(kw in full_topic for kw in ["method", "rule", "budget", "saving", "money"]):
            # This looks like a financial rule that includes numbers
            logger.info("Detected a financial rule or method with numbers")
            financial_pattern_detected = True
            
            # Add specific financial search terms for better results
            financial_terms = [
                "personal finance concept",
                "money management illustration",
                "budget planning graphic",
                "financial advice chart",
                "saving money illustration"
            ]
            
            enhanced_search_terms = financial_terms
            # Still include the full topic if it's not just numbers
            if not full_topic.replace(" ", "").isdigit() and len(full_topic.strip()) > 5:
                enhanced_search_terms.append(full_topic)
        else:
            # Enhance single-word terms that might cause API issues
            enhanced_search_terms = []
            for term in search_terms:
                # Skip very short terms or numbers on their own
                if len(term) <= 2 or term.isdigit():
                    continue
                
                # For single words, add descriptive context
                if len(term.split()) == 1 and not term.isdigit():
                    enhanced_term = f"{term} concept"
                    enhanced_search_terms.append(enhanced_term)
                else:
                    enhanced_search_terms.append(term)
            
            # If we filtered out all terms, use the original list
            if not enhanced_search_terms and search_terms:
                # Add one combined term that includes multiple single terms
                combined_term = " ".join([term for term in search_terms if term and len(term) > 1])
                if combined_term:
                    enhanced_search_terms = [combined_term]
                else:
                    enhanced_search_terms = search_terms
            
            # Always include the full topic as one search term if it's not just digits
            if not full_topic.isdigit() and full_topic not in enhanced_search_terms:
                enhanced_search_terms.append(full_topic)
        
        logger.debug(f"Enhanced search terms: {enhanced_search_terms}")
        
        # Choose appropriate visual terms based on detected content type
        if financial_pattern_detected:
            # Use more finance-related visual backgrounds for videos
            visual_terms = [
                "financial graph animation", 
                "money background", 
                "business chart background",
                "financial success background", 
                "money management video"
            ]
        else:
            # Use standard abstract/nature terms for videos
            visual_terms = [
                "abstract background", "nature scenery", "colorful pattern", 
                "flowing water", "ocean waves", "forest canopy", "clouds timelapse", 
                "geometric shapes", "particle effects", "light bokeh"
            ]
        
        random.shuffle(visual_terms)
        visual_terms = visual_terms[:3]  # Use a subset of terms
        
        # Process each search term for images (can keep topic-related)
        for term in enhanced_search_terms:
            logger.debug(f"Searching for images with term: {term}")
            
            # Collect images
            images = self.collect_images(term, max_count=num_images // len(enhanced_search_terms) + 1, output_dir=output_dir)
            result["images"].extend(images)
        
        # Process visual terms for videos (abstract/nature regardless of topic)
        for term in visual_terms:
            logger.debug(f"Searching for videos with visual term: {term}")
            
            # Collect videos
            videos = self.collect_videos(term, max_count=num_videos // len(visual_terms) + 1, output_dir=output_dir)
            result["videos"].extend(videos)
        
        # Limit results to requested numbers
        result["images"] = result["images"][:num_images]
        result["videos"] = result["videos"][:num_videos]
        
        # If we didn't get enough videos, try with more visual terms as fallback
        if len(result["videos"]) < num_videos:
            logger.debug("Not enough videos found with visual terms, trying more abstract terms")
            
            if financial_pattern_detected:
                more_visual_terms = [
                    "financial success", "money growth animation", 
                    "savings growth", "budget planning", "finance background"
                ]
            else:
                more_visual_terms = [
                    "abstract motion", "slow motion", "gradient background", 
                    "ambient visuals", "relaxing scenery", "underwater scene"
                ]
            
            random.shuffle(more_visual_terms)
            
            for term in more_visual_terms:
                videos = self.collect_videos(term, max_count=num_videos - len(result["videos"]), output_dir=output_dir)
                result["videos"].extend(videos)
                if len(result["videos"]) >= num_videos:
                    break
            
            # Limit videos again
            result["videos"] = result["videos"][:num_videos]
        
        logger.success(f"Collected {len(result['images'])} images and {len(result['videos'])} videos")
        
        return result
    
    def collect_images(self, search_term: str, max_count: int = 5, output_dir: Optional[str] = None) -> List[str]:
        """
        Collect images based on a search term.
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images (optional)
            
        Returns:
            List of paths to collected images
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Try Pexels first if available
        if PEXELS_AVAILABLE and self.pexels_client:
            try:
                logger.debug(f"Searching Pexels for images with term: {search_term}")
                image_paths = self._collect_pexels_images(search_term, max_count, output_dir)
                
                if image_paths:
                    return image_paths
                    
                logger.warning(f"No images found on Pexels for: {search_term}")
            except Exception as e:
                logger.error(f"Error collecting Pexels images: {str(e)}")
        
        # Try Pixabay if API key is available
        if self.config.ai.pixabay_api_key:
            try:
                logger.debug(f"Searching Pixabay for images with term: {search_term}")
                image_paths = self._collect_pixabay_images(search_term, max_count, output_dir)
                
                if image_paths:
                    return image_paths
                    
                logger.warning(f"No images found on Pixabay for: {search_term}")
            except Exception as e:
                logger.error(f"Error collecting Pixabay images: {str(e)}")
        
        # Fallback to unsplash
        try:
            logger.debug(f"Searching Unsplash for images with term: {search_term}")
            image_paths = self._collect_unsplash_images(search_term, max_count, output_dir)
            
            if image_paths:
                return image_paths
                
            logger.warning(f"No images found on Unsplash for: {search_term}")
        except Exception as e:
            logger.error(f"Error collecting Unsplash images: {str(e)}")
        
        # Try GPT Image as a last resort
        if OPENAI_AVAILABLE and self.openai_client and self.config.ai.openai_api_key:
            try:
                logger.info(f"Attempting to generate images with GPT Image for: {search_term}")
                
                image_paths = []
                for i in range(min(2, max_count)):  # Generate up to 2 images to avoid excessive API usage
                    gpt_image = self._generate_dalle_image(search_term, output_dir)
                    if gpt_image:
                        image_paths.append(gpt_image)
                        # Small delay to avoid rate limits
                        time.sleep(1)
                
                if image_paths:
                    return image_paths
                    
                logger.warning(f"Failed to generate GPT Image images for: {search_term}")
            except Exception as e:
                logger.error(f"Error generating GPT Image images: {str(e)}")
        
        # If all else fails, return empty list
        logger.warning(f"Failed to collect any images for: {search_term}")
        return []
    
    def collect_videos(self, search_term: str, max_count: int = 3, output_dir: Optional[str] = None) -> List[str]:
        """
        Collect videos based on a search term.
        
        Args:
            search_term: Search term
            max_count: Maximum number of videos to collect
            output_dir: Directory to save videos (optional)
            
        Returns:
            List of paths to collected videos
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Try Pexels first if available
        if PEXELS_AVAILABLE and self.pexels_client:
            try:
                logger.debug(f"Searching Pexels for videos with term: {search_term}")
                video_paths = self._collect_pexels_videos(search_term, max_count, output_dir)
                
                if video_paths:
                    return video_paths
                    
                logger.warning(f"No videos found on Pexels for: {search_term}")
            except Exception as e:
                logger.error(f"Error collecting Pexels videos: {str(e)}")
        
        # Fallback to Pixabay
        try:
            logger.debug(f"Searching Pixabay for videos with term: {search_term}")
            video_paths = self._collect_pixabay_videos(search_term, max_count, output_dir)
            
            if video_paths:
                return video_paths
                
            logger.warning(f"No videos found on Pixabay for: {search_term}")
        except Exception as e:
            logger.error(f"Error collecting Pixabay videos: {str(e)}")
        
        # If all else fails, return empty list
        logger.warning(f"Failed to collect any videos for: {search_term}")
        return []
    
    def _collect_pexels_images(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect images from Pexels.
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images
            
        Returns:
            List of paths to collected images
        """
        if not PEXELS_AVAILABLE or not self.pexels_client:
            return []
        
        try:
            # Search for photos
            self.pexels_client.search(search_term, page=1, results_per_page=max_count)
            
            # Get photos
            photos = self.pexels_client.get_entries()
            
            # Check if we have results
            if not photos:
                return []
            
            # Download images
            image_paths = []
            
            for photo in photos[:max_count]:
                try:
                    # Generate filename
                    filename = f"pexels_{photo.id}_{uuid.uuid4().hex[:8]}.jpg"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Download the image
                    urllib.request.urlretrieve(photo.original, output_path)
                    
                    # Add to result
                    image_paths.append(output_path)
                    logger.debug(f"Downloaded Pexels image: {output_path}")
                    
                except Exception as e:
                    logger.error(f"Error downloading Pexels image: {str(e)}")
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error searching Pexels: {str(e)}")
            return []
    
    def _collect_pexels_videos(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect videos from Pexels.
        
        Args:
            search_term: Search term
            max_count: Maximum number of videos to collect
            output_dir: Directory to save videos
            
        Returns:
            List of paths to collected videos
        """
        if not PEXELS_AVAILABLE or not self.pexels_client:
            return []
        
        try:
            # Construct direct API request since the pexels-api package only supports photos
            headers = {
                "Authorization": self.config.ai.pexels_api_key
            }
            
            # Search for videos
            response = requests.get(
                f"https://api.pexels.com/videos/search?query={urllib.parse.quote(search_term)}&per_page={max_count}",
                headers=headers
            )
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Error searching Pexels videos: {response.status_code} {response.text}")
                return []
            
            # Parse response
            data = response.json()
            
            # Check if we have results
            if "videos" not in data or not data["videos"]:
                return []
            
            # Download videos
            video_paths = []
            
            for video in data["videos"][:max_count]:
                try:
                    # Find the best quality video file (prefer SD for size)
                    video_file = None
                    for file in video["video_files"]:
                        if file["quality"] == "sd" and file["file_type"] == "video/mp4":
                            video_file = file
                            break
                    
                    # If no SD, take the first mp4
                    if not video_file:
                        for file in video["video_files"]:
                            if file["file_type"] == "video/mp4":
                                video_file = file
                                break
                    
                    # Skip if no suitable file found
                    if not video_file:
                        logger.warning(f"No suitable video file found in Pexels video {video['id']}")
                        continue
                    
                    # Generate filename
                    filename = f"pexels_video_{video['id']}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Download the video
                    urllib.request.urlretrieve(video_file["link"], output_path)
                    
                    # Add to result
                    video_paths.append(output_path)
                    logger.debug(f"Downloaded Pexels video: {output_path}")
                    
                except Exception as e:
                    logger.error(f"Error downloading Pexels video: {str(e)}")
            
            return video_paths
            
        except Exception as e:
            logger.error(f"Error searching Pexels videos: {str(e)}")
            return []
    
    def _collect_unsplash_images(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect images from Unsplash (using public API, rate-limited).
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images
            
        Returns:
            List of paths to collected images
        """
        try:
            # Set up headers for a more browser-like request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Download images
            image_paths = []
            max_retries = 3
            
            # We need to make multiple requests for multiple images
            for i in range(min(max_count, 5)):  # Limit to 5 to avoid rate limiting
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        # Generate filename
                        filename = f"unsplash_{search_term.replace(' ', '_')}_{i}_{uuid.uuid4().hex[:8]}.jpg"
                        output_path = os.path.join(output_dir, filename)
                        
                        # Get a new random image with different query param to avoid caching
                        query_with_random = f"{search_term}&random={uuid.uuid4().hex[:8]}"
                        image_url = f"https://source.unsplash.com/random?{urllib.parse.quote(query_with_random)}"
                        
                        logger.debug(f"Fetching Unsplash image from: {image_url}")
                        
                        # Use session to maintain cookies
                        session = requests.Session()
                        response = session.get(image_url, headers=headers, timeout=10, allow_redirects=True)
                        
                        if response.status_code == 200:
                            # Save the image
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            
                            # Add to result
                            image_paths.append(output_path)
                            logger.debug(f"Downloaded Unsplash image: {output_path}")
                            success = True
                        else:
                            logger.warning(f"Error fetching Unsplash image (attempt {retry_count+1}): {response.status_code}")
                            retry_count += 1
                            time.sleep(2)  # Longer sleep between retries
                        
                    except Exception as e:
                        logger.error(f"Error downloading Unsplash image (attempt {retry_count+1}): {str(e)}")
                        retry_count += 1
                        time.sleep(2)
                    
                # Sleep between different images regardless of success
                time.sleep(2)
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error searching Unsplash: {str(e)}")
            return []
    
    def _collect_pixabay_videos(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect videos from Pixabay using their official API.
        
        Args:
            search_term: Search term
            max_count: Maximum number of videos to collect
            output_dir: Directory to save videos
            
        Returns:
            List of paths to collected videos
        """
        # Check if API key is available
        if not self.config.ai.pixabay_api_key:
            logger.warning("Pixabay API key not configured. Add it to your config.json file.")
            return []
        
        # Check for empty or invalid search terms
        if not search_term or len(search_term.strip()) == 0:
            logger.warning("Empty search term provided for Pixabay video search")
            return []
        
        # Clean and process the search term
        # Replace problematic characters and limit length
        clean_term = search_term.strip()
        clean_term = clean_term[:100]  # Limit length
        
        try:
            # Construct API URL for video search
            api_url = "https://pixabay.com/api/videos/"
            params = {
                "key": self.config.ai.pixabay_api_key,
                "q": clean_term,
                "per_page": min(max_count, 20),  # Limit to reasonable number
                "safesearch": "true",  # Ensure safe content
                "video_type": "all"    # Include all video types
            }
            
            logger.debug(f"Making Pixabay video API request for term: '{clean_term}'")
            
            # Make API request
            response = requests.get(api_url, params=params)
            
            # Check response
            if response.status_code != 200:
                error_info = ""
                try:
                    error_info = response.text[:200]  # Get first 200 chars of error message
                except:
                    pass
                
                logger.error(f"Error searching Pixabay videos API: {response.status_code}, Details: {error_info}")
                
                if response.status_code == 400:
                    logger.error(f"Bad request to Pixabay video API. This may be due to invalid search terms or parameters. Search term: '{clean_term}'")
                elif response.status_code == 429:
                    logger.error("Rate limit exceeded for Pixabay API")
                
                return []
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Pixabay video API response: {str(e)}")
                return []
            
            # Check if we have results
            if "hits" not in data or not data["hits"]:
                logger.warning(f"No videos found on Pixabay API for: {clean_term}")
                return []
            
            # Log the number of results found
            logger.info(f"Found {len(data['hits'])} videos on Pixabay for '{clean_term}'")
            
            # Download videos
            video_paths = []
            
            for video_data in data["hits"][:max_count]:
                try:
                    video_id = video_data["id"]
                    
                    # Generate filename
                    filename = f"pixabay_video_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Get the best quality video URL that doesn't exceed our target dimensions
                    # Prioritize in this order: medium, small, large, tiny
                    video_url = None
                    target_width = self.config.app.video_width
                    target_height = self.config.app.video_height
                    
                    # Choose the best video size based on our target dimensions
                    if "videos" in video_data:
                        video_formats = video_data["videos"]
                        
                        # Try medium size first (1920x1080 or 1280x720)
                        if "medium" in video_formats and video_formats["medium"]["url"]:
                            video_url = video_formats["medium"]["url"]
                        
                        # If medium doesn't exist or target dimensions are smaller, try small (1280x720 or 960x540)
                        elif "small" in video_formats and video_formats["small"]["url"]:
                            video_url = video_formats["small"]["url"]
                        
                        # Try large if available (typically 3840x2160)
                        elif "large" in video_formats and video_formats["large"]["url"]:
                            video_url = video_formats["large"]["url"]
                        
                        # Last resort: tiny size (960x540 or 640x360)
                        elif "tiny" in video_formats and video_formats["tiny"]["url"]:
                            video_url = video_formats["tiny"]["url"]
                    
                    if not video_url:
                        logger.warning(f"No suitable video URL found for Pixabay video {video_id}")
                        continue
                    
                    # Download the video
                    logger.debug(f"Downloading Pixabay video from {video_url}")
                    
                    # Use requests with proper headers instead of urllib
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Referer": "https://pixabay.com/"
                    }
                    
                    video_response = requests.get(video_url, headers=headers, stream=True)
                    
                    if video_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in video_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Add to result
                        video_paths.append(output_path)
                        logger.debug(f"Downloaded Pixabay video: {output_path}")
                    else:
                        logger.error(f"Error downloading Pixabay video {video_id}: HTTP {video_response.status_code}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error downloading Pixabay video {video_id}: {str(e)}")
            
            return video_paths
            
        except Exception as e:
            logger.error(f"Error searching Pixabay API: {str(e)}")
            return []
    
    def _collect_pixabay_images(self, search_term: str, max_count: int, output_dir: str) -> List[str]:
        """
        Collect images from Pixabay using their official API.
        
        Args:
            search_term: Search term
            max_count: Maximum number of images to collect
            output_dir: Directory to save images
            
        Returns:
            List of paths to collected images
        """
        # Check if API key is available
        if not self.config.ai.pixabay_api_key:
            logger.warning("Pixabay API key not configured. Add it to your config.json file.")
            return []
        
        # Check for empty or invalid search terms
        if not search_term or len(search_term.strip()) == 0:
            logger.warning("Empty search term provided for Pixabay image search")
            return []
        
        # Clean and process the search term
        # Replace problematic characters and limit length
        clean_term = search_term.strip()
        clean_term = clean_term[:100]  # Limit length
        
        try:
            # Construct API URL for image search
            api_url = "https://pixabay.com/api/"
            
            # Properly encode parameters individually
            params = {
                "key": self.config.ai.pixabay_api_key,
                "q": clean_term,
                "per_page": min(max_count, 20),  # Limit to reasonable number
                "safesearch": "true",  # Ensure safe content
                "image_type": "all"    # Include all image types
            }
            
            logger.debug(f"Making Pixabay API request for term: '{clean_term}'")
            
            # Make API request with explicit encoding
            response = requests.get(api_url, params=params)
            
            # Check response
            if response.status_code != 200:
                error_info = ""
                try:
                    error_info = response.text[:200]  # Get first 200 chars of error message
                except:
                    pass
                
                logger.error(f"Error searching Pixabay images API: {response.status_code}, Details: {error_info}")
                
                if response.status_code == 400:
                    logger.error(f"Bad request to Pixabay API. This may be due to invalid search terms or parameters. Search term: '{clean_term}'")
                elif response.status_code == 429:
                    logger.error("Rate limit exceeded for Pixabay API")
                
                return []
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Pixabay API response: {str(e)}")
                return []
            
            # Check if we have results
            if "hits" not in data or not data["hits"]:
                logger.warning(f"No images found on Pixabay API for: {clean_term}")
                return []
            
            # Log the number of results found
            logger.info(f"Found {len(data['hits'])} images on Pixabay for '{clean_term}'")
            
            # Download images
            image_paths = []
            
            for image_data in data["hits"][:max_count]:
                try:
                    image_id = image_data["id"]
                    
                    # Generate filename
                    filename = f"pixabay_image_{image_id}_{uuid.uuid4().hex[:8]}.jpg"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Get the best quality image URL for our needs
                    # Use largeImageURL for high quality
                    image_url = image_data.get("largeImageURL", image_data.get("webformatURL"))
                    
                    if not image_url:
                        logger.warning(f"No suitable image URL found for Pixabay image {image_id}")
                        continue
                    
                    # Download the image
                    logger.debug(f"Downloading Pixabay image from {image_url}")
                    
                    # Use requests with proper headers instead of urllib
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Referer": "https://pixabay.com/"
                    }
                    
                    image_response = requests.get(image_url, headers=headers, stream=True)
                    
                    if image_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in image_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Add to result
                        image_paths.append(output_path)
                        logger.debug(f"Downloaded Pixabay image: {output_path}")
                    else:
                        logger.error(f"Error downloading Pixabay image {image_id}: HTTP {image_response.status_code}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error downloading Pixabay image {image_id}: {str(e)}")
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error searching Pixabay API for images: {str(e)}")
            return []
    
    def get_stock_soundtrack(self, mood: str, duration: int, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Get a stock soundtrack based on mood.
        
        Args:
            mood: Mood of the soundtrack (e.g., upbeat, calm, dramatic)
            duration: Desired duration in seconds
            output_dir: Directory to save soundtrack (optional)
            
        Returns:
            Path to the soundtrack file or None if not found
        """
        # Not implemented yet - would require a source of royalty-free music
        logger.warning("Stock soundtrack feature not implemented yet")
        return None
    
    def generate_fallback_asset(
        self, 
        search_term: str, 
        duration: float = 5.0, 
        width: int = 1080, 
        height: int = 1920,
        output_dir: Optional[str] = None,
        skip_image_generation: bool = False
    ) -> str:
        """
        Generate a fallback asset when no images or videos are available.
        Creates a video with random colored background.
        
        Args:
            search_term: Search term to use in the text
            duration: Duration of the video in seconds
            width: Width of the video
            height: Height of the video
            output_dir: Directory to save the output file
            skip_image_generation: Skip trying to generate an image with OpenAI
            
        Returns:
            Path to the generated asset
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Try to create a video with OpenAI generated image as background (if not skipped)
        if not skip_image_generation and OPENAI_AVAILABLE and self.openai_client and self.config.ai.openai_api_key:
            try:
                # Try just once to generate an image
                logger.debug(f"Attempting to generate image for fallback asset: {search_term}")
                gpt_image = self._generate_dalle_image(search_term, output_dir)
                
                if gpt_image:
                    from PIL import Image
                    from moviepy.editor import ImageClip
                    
                    # Open and resize the image to maintain aspect ratio
                    img = Image.open(gpt_image)
                    img_width, img_height = img.size
                    
                    # Create image clip
                    image_clip = ImageClip(gpt_image)
                    
                    # Resize to fill the screen while maintaining aspect ratio
                    if img_width / img_height > width / height:  # Image is wider than video
                        image_clip = image_clip.resize(height=height)
                    else:  # Image is taller than video
                        image_clip = image_clip.resize(width=width)
                    
                    # Center the image
                    image_clip = image_clip.set_position(('center', 'center')).set_duration(duration)
                    
                    # No text clip with the search term anymore
                    
                    # Use just the image clip without text overlay
                    final_clip = CompositeVideoClip([image_clip])
                    
                    # Generate output path
                    filename = f"gpt_image_video_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Write to file
                    final_clip.write_videofile(
                        output_path,
                        fps=24,
                        codec='libx264',
                        audio=False,
                        logger=None
                    )
                    
                    # Close clips
                    final_clip.close()
                    
                    logger.info(f"Generated GPT Image based video asset: {output_path}")
                    return output_path
                
            except Exception as e:
                logger.error(f"Error creating GPT Image based video: {str(e)}")
                logger.info("Falling back to simple color background video")
        
        # If GPT Image failed or is not available, use original method
        # Generate a random color (but not too dark)
        color = (
            random.randint(30, 200),
            random.randint(30, 200),
            random.randint(30, 200)
        )
        
        # Create a color clip
        color_clip = ColorClip(
            size=(width, height),
            color=color,
            duration=duration
        )
        
        # No text clips needed
        
        # Use just the color clip without text overlays
        final_clip = CompositeVideoClip([color_clip])
        
        # Generate output path
        filename = f"fallback_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        # Write to file
        final_clip.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio=False,
            logger=None
        )
        
        # Close clips
        final_clip.close()
        
        logger.info(f"Generated fallback asset: {output_path}")
        return output_path
    
    def collect_fallback_assets(
        self,
        search_terms: List[str],
        num_assets: int = 3,
        duration: float = 5.0,
        output_dir: Optional[str] = None,
        skip_image_generation: bool = False
    ) -> Dict[str, List[str]]:
        """
        Generate fallback assets when API-based collection fails.
        
        Args:
            search_terms: List of search terms
            num_assets: Number of assets to generate
            duration: Duration of each asset in seconds
            output_dir: Directory to save assets
            skip_image_generation: Skip trying to generate images with OpenAI
            
        Returns:
            Dictionary with paths to generated assets
        """
        output_dir = self._ensure_output_directory(output_dir)
        
        # Initialize result
        result = {
            "images": [],
            "videos": []
        }
        
        # Try to generate at least one asset with image generation first if not skipped
        if not skip_image_generation and OPENAI_AVAILABLE and self.openai_client and self.config.ai.openai_api_key:
            try:
                # Try generating one asset with image
                term = search_terms[0] if search_terms else "background"
                logger.info(f"Attempting to generate first fallback asset with image for: {term}")
                
                video_path = self.generate_fallback_asset(
                    search_term=term,
                    duration=duration,
                    width=self.config.app.video_width,
                    height=self.config.app.video_height,
                    output_dir=output_dir,
                    skip_image_generation=False
                )
                
                if video_path:
                    result["videos"].append(video_path)
                    # If image generation was successful, continue with it for the rest
                    image_generation_failed = False
                else:
                    # If it failed, set flag to skip for the rest
                    image_generation_failed = True
                    logger.warning("Initial image generation failed, skipping for remaining assets")
            except Exception as e:
                logger.error(f"Error generating first fallback asset: {str(e)}")
                image_generation_failed = True
        else:
            # Skip image generation entirely
            image_generation_failed = True
        
        # Generate remaining assets, skipping image generation if it failed before
        for term in search_terms[1:num_assets] if (not skip_image_generation and result["videos"]) else search_terms[:num_assets]:
            try:
                # Generate a fallback video asset
                video_path = self.generate_fallback_asset(
                    search_term=term,
                    duration=duration,
                    width=self.config.app.video_width,
                    height=self.config.app.video_height,
                    output_dir=output_dir,
                    skip_image_generation=image_generation_failed
                )
                
                if video_path:
                    result["videos"].append(video_path)
                
            except Exception as e:
                logger.error(f"Error generating fallback asset for {term}: {str(e)}")
        
        logger.success(f"Generated {len(result['videos'])} fallback assets")
        return result

    def _generate_dalle_image(self, search_term: str, output_dir: str) -> Optional[str]:
        """
        Generate an image using OpenAI's image generation models with multiple fallbacks.
        
        Args:
            search_term: Description for the image to generate
            output_dir: Directory to save the generated image
            
        Returns:
            Path to the generated image or None if generation fails
        """
        if not OPENAI_AVAILABLE or not self.openai_client or not self.config.ai.openai_api_key:
            logger.warning("OpenAI not available for image generation")
            return None
        
        # Process the search term for better results
        # For financial terms, use specific imagery that works better
        financial_keywords = ["money", "saving", "budget", "finance", "invest", "financial", 
                               "wealth", "dollar", "cash", "bank", "economy"]
        
        is_financial_topic = any(keyword in search_term.lower() for keyword in financial_keywords)
        
        if is_financial_topic:
            # Use specific imagery for financial topics
            enhanced_prompts = [
                f"Stylized illustration representing {search_term}, with coins, graphs, and subtle imagery",
                f"Abstract visual metaphor of {search_term}, with graphs, charts, and financial concepts",
                f"Creative visualization of {search_term}, showing coins, wallet, and savings graphics"
            ]
        else:
            # Generic enhancement for non-financial topics
            enhanced_prompts = [
                f"High quality, visually appealing image of {search_term}, suitable as a background for a social media video",
                f"Creative illustration representing the concept of {search_term}",
                f"Stylized digital artwork depicting {search_term} for social media content"
            ]
        
        # Randomly select a prompt
        enhanced_prompt = random.choice(enhanced_prompts)
        logger.debug(f"Using DALL-E prompt: {enhanced_prompt}")
        
        # Prepare a list of models to try in fallback order
        models_to_try = [
            {"model": "dall-e-2", "size": "1024x1024"},  # Most reliable older model
            {"model": "dall-e-3", "size": "1024x1024", "quality": "standard"},  # Newer model
        ]
        
        for model_config in models_to_try:
            try:
                logger.info(f"Generating image with {model_config['model']} for: {search_term}")
                
                # Prepare parameters based on the model
                generate_params = {
                    "model": model_config["model"],
                    "prompt": enhanced_prompt,
                    "size": model_config["size"],
                    "n": 1,
                }
                
                # Add quality parameter for models that support it
                if "quality" in model_config:
                    generate_params["quality"] = model_config["quality"]
                
                # Generate the image
                response = self.openai_client.images.generate(**generate_params)
                
                # Log response summary
                logger.debug(f"Response from {model_config['model']}: {response}")
                
                # Check for valid data
                if not hasattr(response, 'data') or not response.data or len(response.data) == 0:
                    logger.warning(f"{model_config['model']} response contains no image data")
                    continue
                
                # Get image URL
                data_item = response.data[0]
                
                # Check for different response structures
                if hasattr(data_item, 'url'):
                    image_url = data_item.url
                elif hasattr(data_item, 'b64_json'):
                    # Handle base64 encoded images
                    logger.info("Found base64 encoded image")
                    b64_data = data_item.b64_json
                    # Generate filename and save path
                    filename = f"{model_config['model']}_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
                    output_path = os.path.join(output_dir, filename)
                    
                    # Decode and save base64 image
                    try:
                        with open(output_path, "wb") as image_file:
                            image_file.write(base64.b64decode(b64_data))
                        logger.success(f"Saved base64 image to {output_path}")
                        return output_path
                    except Exception as decode_error:
                        logger.error(f"Error saving base64 image: {str(decode_error)}")
                        continue
                else:
                    logger.warning(f"{model_config['model']} response missing URL or b64_json property")
                    continue
                
                # For URL-based responses
                if not image_url:
                    logger.warning(f"{model_config['model']} returned empty image URL")
                    continue
                
                logger.debug(f"Image URL obtained from {model_config['model']}: {image_url}")
                
                # Generate filename
                filename = f"{model_config['model']}_{search_term.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
                output_path = os.path.join(output_dir, filename)
                
                # Download the image
                try:
                    # Use requests instead of urllib for better error handling
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    image_response = requests.get(image_url, headers=headers, timeout=10)
                    
                    if image_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(image_response.content)
                        logger.debug(f"Image successfully downloaded to {output_path}")
                        logger.success(f"Generated image with {model_config['model']}: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Failed to download image from {model_config['model']}: HTTP {image_response.status_code}")
                except Exception as download_error:
                    logger.error(f"Failed to download image from {model_config['model']}: {str(download_error)}")
                    continue
                
            except Exception as model_error:
                logger.error(f"Error with {model_config['model']}: {str(model_error)}")
                continue
        
        # If we got here, all models failed
        logger.error("All image generation models failed")
        return None


if __name__ == "__main__":
    # Simple test for the asset collector
    from src.utils.config_loader import ConfigLoader
    
    def test_asset_collector():
        config_loader = ConfigLoader()
        config = config_loader.get_config()
        
        collector = AssetCollector(config)
        
        search_terms = ["nature", "mountains", "sunset"]
        
        assets = collector.collect_assets(
            search_terms=search_terms,
            num_images=3,
            num_videos=2,
            output_dir="test_assets"
        )
        
        print(f"Collected assets: {assets}")
    
    # Run the test
    test_asset_collector() 