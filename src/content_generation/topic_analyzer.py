"""
Topic Analyzer Module

Processes user-provided topics into searchable terms and generates content ideas.
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Union, Any

from loguru import logger
import openai
from openai import OpenAI

from src.utils.config_loader import Config


class TopicAnalyzer:
    """
    Analyzes topics to generate content ideas and search terms.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the topic analyzer with config.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.client = None
        
        # Initialize OpenAI client if API key is available
        if self.config.ai.openai_api_key:
            self.client = OpenAI(api_key=self.config.ai.openai_api_key)
        else:
            logger.warning("OpenAI API key not provided. Some functionality will be limited.")
    
    def _ensure_client(self) -> bool:
        """
        Ensure OpenAI client is initialized.
        
        Returns:
            True if client is available, False otherwise
        """
        if not self.client and self.config.ai.openai_api_key:
            try:
                self.client = OpenAI(api_key=self.config.ai.openai_api_key)
                return True
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {str(e)}")
                return False
        return bool(self.client)
    
    def analyze_topic(self, topic: str) -> Dict[str, Union[str, List[str]]]:
        """
        Analyze a topic to extract key terms and content ideas.
        
        Args:
            topic: User topic string
            
        Returns:
            Dictionary with topic information
        """
        # Basic analysis without OpenAI
        result = {
            "topic": topic,
            "search_terms": self._extract_search_terms(topic),
            "hashtags": self._extract_hashtags(topic),
            "content_ideas": [],
            "title_ideas": []
        }
        
        # Enhanced analysis with OpenAI if available
        if self._ensure_client():
            try:
                enhanced_result = self._analyze_with_openai(topic)
                
                # Update with enhanced data if available
                if enhanced_result:
                    if "search_terms" in enhanced_result and enhanced_result["search_terms"]:
                        result["search_terms"] = enhanced_result["search_terms"]
                    if "hashtags" in enhanced_result and enhanced_result["hashtags"]:
                        result["hashtags"] = enhanced_result["hashtags"]
                    if "content_ideas" in enhanced_result and enhanced_result["content_ideas"]:
                        result["content_ideas"] = enhanced_result["content_ideas"]
                    if "title_ideas" in enhanced_result and enhanced_result["title_ideas"]:
                        result["title_ideas"] = enhanced_result["title_ideas"]
                    if "hook_ideas" in enhanced_result and enhanced_result["hook_ideas"]:
                        result["hook_ideas"] = enhanced_result["hook_ideas"]
            except Exception as e:
                logger.error(f"Error in OpenAI analysis: {str(e)}")
        
        return result
    
    def _extract_search_terms(self, topic: str) -> List[str]:
        """
        Extract search terms from a topic without AI.
        
        Args:
            topic: User topic string
            
        Returns:
            List of search terms
        """
        # Simple tokenization and stopword removal
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'on', 'of', 'at', 'to'}
        
        # Clean the topic string
        clean_topic = re.sub(r'[^\w\s#]', ' ', topic.lower())
        
        # Extract terms
        terms = [term.strip() for term in clean_topic.split() if term.strip() and term not in stopwords]
        
        # Add the full topic as a term if it's not too long
        if len(topic) < 50 and topic not in terms:
            terms.append(topic)
        
        return terms
    
    def _extract_hashtags(self, topic: str) -> List[str]:
        """
        Extract hashtags from the topic or create relevant ones.
        
        Args:
            topic: User topic string
            
        Returns:
            List of hashtags
        """
        # Extract explicit hashtags first
        hashtags = re.findall(r'#(\w+)', topic)
        
        # If no explicit hashtags, create from the topic
        if not hashtags:
            # Remove punctuation and spaces
            clean_topic = re.sub(r'[^\w\s]', '', topic.lower())
            words = clean_topic.split()
            
            # Create hashtags from individual words
            for word in words:
                if len(word) > 3 and word not in ['with', 'that', 'this', 'from', 'there', 'these', 'those']:
                    hashtags.append(word)
        
        # Limit to 5 hashtags
        return hashtags[:5]
    
    def _analyze_with_openai(self, topic: str) -> Optional[Dict[str, List[str]]]:
        """
        Use OpenAI to analyze the topic and provide enhanced content ideas.
        
        Args:
            topic: User topic string
            
        Returns:
            Dictionary with enhanced topic analysis or None if failed
        """
        if not self._ensure_client():
            return None
        
        try:
            # Create system prompt
            system_prompt = """
            You are an expert content strategist for viral video content.
            Analyze the provided topic and return a structured JSON response with the following:
            
            1. search_terms: List of relevant search terms for finding content related to this topic
            2. hashtags: List of 5-10 relevant hashtags (without the # symbol)
            3. content_ideas: List of 5-10 specific content ideas related to the topic
            4. title_ideas: List of 5-10 catchy titles for videos about this topic
            5. hook_ideas: List of 3-5 attention-grabbing hooks for the first 5 seconds of a video
            
            Keep each item concise. Return the result as valid JSON with these exact keys.
            """
            
            user_prompt = f"Topic: {topic}"
            
            # Clean the model name if it has comments
            model_name = self.config.ai.openai_model
            if isinstance(model_name, str) and "#" in model_name:
                model_name = model_name.split("#")[0].strip()
                logger.debug(f"Cleaned model name for OpenAI API call: {model_name}")
            
            # Call OpenAI API
            # Remove temperature parameter to use default value (1.0)
            response = self.client.chat.completions.create(
                model=model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=1000
            )
            
            # Parse the response
            if response.choices and response.choices[0].message.content:
                result = json.loads(response.choices[0].message.content)
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error in OpenAI analysis: {str(e)}")
            return None
    
    def generate_tiktok_hashtags(self, topic: str, count: int = 5) -> List[str]:
        """
        Generate TikTok-specific hashtags for a topic.
        
        Args:
            topic: User topic string
            count: Number of hashtags to generate
            
        Returns:
            List of hashtags relevant for TikTok
        """
        basic_hashtags = self._extract_hashtags(topic)
        
        # Add viral/trending hashtags
        viral_hashtags = ["fyp", "foryou", "foryoupage", "viral", "trending"]
        
        # Combine topic-specific and viral hashtags
        combined_hashtags = basic_hashtags + [h for h in viral_hashtags if h not in basic_hashtags]
        
        # Limit to requested count
        return combined_hashtags[:count]
    
    def generate_content_brief(self, topic: str) -> Dict[str, Union[str, List[str]]]:
        """
        Generate a content brief for creating a video.
        
        Args:
            topic: User topic string
            
        Returns:
            Dictionary with content brief information
        """
        # Start with basic analysis
        analysis = self.analyze_topic(topic)
        
        # Create a structured brief
        brief = {
            "topic": topic,
            "title": self._generate_title(topic, analysis.get("title_ideas", [])),
            "search_terms": analysis.get("search_terms", []),
            "hashtags": analysis.get("hashtags", []),
            "content_structure": self._generate_structure(topic, analysis)
        }
        
        return brief
    
    def _generate_title(self, topic: str, title_ideas: List[str]) -> str:
        """
        Generate a catchy title for the video.
        
        Args:
            topic: User topic string
            title_ideas: List of title ideas
            
        Returns:
            Video title
        """
        if title_ideas:
            return title_ideas[0]
        
        # Fallback title generation
        return f"Amazing Facts About {topic.title()} | Must Watch!"
    
    def _generate_structure(self, topic: str, analysis: Dict[str, Union[str, List[str]]]) -> Dict[str, Union[str, List[str]]]:
        """
        Generate a content structure for the video.
        
        Args:
            topic: User topic string
            analysis: Topic analysis result
            
        Returns:
            Dictionary with content structure
        """
        if not self._ensure_client():
            # Basic structure without OpenAI
            return {
                "hook": f"Did you know these amazing facts about {topic}?",
                "sections": [
                    "Introduction to the topic",
                    "Main points or facts",
                    "Interesting details",
                    "Conclusion"
                ],
                "points": [
                    f"Point 1 about {topic}",
                    f"Point 2 about {topic}",
                    f"Point 3 about {topic}"
                ]
            }
        
        try:
            # Clean the model name if it has comments
            model_name = self.config.ai.openai_model
            if isinstance(model_name, str) and "#" in model_name:
                model_name = model_name.split("#")[0].strip()
                logger.debug(f"Cleaned model name for content structure generation: {model_name}")

            # Create system prompt
            system_prompt = """
            You are an expert scriptwriter for informative short-form videos.
            Create a video structure for the given topic with the following format:
            
            1. hook: An attention-grabbing first line for the video
            2. sections: 3-5 main sections for the video
            3. points: 3-7 key points or facts to cover
            4. narrative_style: Suggested tone/style (informative, humorous, dramatic, etc.)
            
            Return the result as valid JSON with these exact keys.
            """
            
            user_prompt = f"Topic: {topic}"
            
            # Include any content ideas in the prompt
            if "content_ideas" in analysis and analysis["content_ideas"]:
                content_ideas_str = "\n".join([f"- {idea}" for idea in analysis["content_ideas"][:3]])
                user_prompt += f"\n\nContent ideas:\n{content_ideas_str}"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=800
            )
            
            # Parse the response
            if response.choices and response.choices[0].message.content:
                structure = json.loads(response.choices[0].message.content)
                return structure
            
            # Fallback to basic structure
            return {
                "hook": f"Did you know these amazing facts about {topic}?",
                "sections": [
                    "Introduction to the topic",
                    "Main points or facts",
                    "Interesting details",
                    "Conclusion"
                ],
                "points": [
                    f"Point 1 about {topic}",
                    f"Point 2 about {topic}",
                    f"Point 3 about {topic}"
                ],
                "narrative_style": "informative"
            }
            
        except Exception as e:
            logger.error(f"Error generating content structure: {str(e)}")
            
            # Fallback to basic structure
            return {
                "hook": f"Did you know these amazing facts about {topic}?",
                "sections": [
                    "Introduction to the topic",
                    "Main points or facts",
                    "Interesting details",
                    "Conclusion"
                ],
                "points": [
                    f"Point 1 about {topic}",
                    f"Point 2 about {topic}",
                    f"Point 3 about {topic}"
                ],
                "narrative_style": "informative"
            } 