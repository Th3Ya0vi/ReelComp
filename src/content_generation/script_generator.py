"""
Script Generator Module

Generates video scripts for various content types based on user topics.
Focuses on direct, engaging content without filler words or subscription requests.
"""

import json
from typing import Dict, List, Optional, Union

from loguru import logger
from openai import OpenAI

from src.content_generation.topic_analyzer import TopicAnalyzer
from src.utils.config_loader import Config


class ScriptGenerator:
    """
    Generates video scripts based on topic analysis and content briefs.
    Focuses on direct, engaging content without filler words.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the script generator with config.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.topic_analyzer = TopicAnalyzer(config)
        self.client = None
        
        # Initialize OpenAI client if API key is available
        if self.config.ai.openai_api_key:
            self.client = OpenAI(api_key=self.config.ai.openai_api_key)
        else:
            logger.warning("OpenAI API key not provided. Script generation will be limited.")
    
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
    
    def generate_script(self, topic: str, script_type: str = "informative", duration: Optional[int] = None) -> Dict[str, Union[str, Dict]]:
        """
        Generate a complete video script.
        
        Args:
            topic: User topic string
            script_type: Type of script to generate (informative, entertaining, educational)
            duration: Suggested duration in seconds (optional, content will determine actual length)
            
        Returns:
            Dictionary with script information
        """
        # Analyze the topic first
        logger.info(f"Generating {script_type} script for topic: '{topic}'" + (f" (suggested duration: {duration}s)" if duration else ""))
        content_brief = self.topic_analyzer.generate_content_brief(topic)
        
        # Generate the script
        if self._ensure_client():
            try:
                script = self._generate_with_openai(topic, content_brief, script_type, duration)
                if script:
                    return script
            except Exception as e:
                logger.error(f"Error in OpenAI script generation: {str(e)}")
        
        # Fallback to basic script generation
        return self._generate_basic_script(topic, content_brief, script_type, duration)
    
    def _generate_with_openai(
        self, 
        topic: str, 
        content_brief: Dict[str, Union[str, List[str]]], 
        script_type: str,
        duration: Optional[int] = None
    ) -> Optional[Dict[str, Union[str, Dict]]]:
        """
        Generate a script using OpenAI with strict guidelines to avoid filler content.
        
        Args:
            topic: User topic string
            content_brief: Content brief from topic analyzer
            script_type: Type of script to generate
            duration: Target duration in seconds (optional, content will determine actual length)
            
        Returns:
            Dictionary with script information or None if failed
        """
        if not self._ensure_client():
            return None
        
        try:
            # Determine approach based on whether duration is specified
            if duration:
                # Duration-guided generation
                word_count = int((duration / 60) * 150)
                core_content_duration = duration - 10
                core_content_start = 5
                impact_start = core_content_start + core_content_duration
                
                structure_guidance = f"""
SCRIPT STRUCTURE:
1. HOOK (0-5 seconds): Most shocking/interesting fact about the topic
2. CORE CONTENT ({core_content_start}-{impact_start} seconds): Key information, insights, and details
3. IMPACT STATEMENT ({impact_start}-{duration} seconds): Most important takeaway

Target approximately {word_count} words total."""
            else:
                # Content-driven generation (no duration constraints)
                structure_guidance = """
SCRIPT STRUCTURE:
Let the content determine the natural length. Include:
1. HOOK: Most shocking/interesting fact about the topic
2. CORE CONTENT: All essential information, insights, and details needed to fully cover the topic
3. IMPACT STATEMENT: Most important takeaway

Use as many words as needed to thoroughly cover the topic with value-packed content."""
            
            # Clean the model name if it has comments
            model_name = self.config.ai.openai_model
            if isinstance(model_name, str) and "#" in model_name:
                model_name = model_name.split("#")[0].strip()
                logger.debug(f"Cleaned model name for OpenAI script generation: {model_name}")
            
            # Create system prompt focused on direct, engaging content
            duration_text = f"{duration}-second" if duration else "comprehensive"
            system_prompt = f"""You are an expert content creator who makes ultra-engaging {script_type} videos that dive straight into valuable content.

Create a {duration_text} video script about "{topic}" that delivers maximum value from the first word to the last.

STRICT CONTENT RULES:
- Start immediately with the most interesting/valuable information
- NO greetings, introductions, or "welcome" statements
- NO "in this video we'll discuss" or similar phrases
- NO "let's dive into" or transitional filler
- NO subscription requests, likes, or engagement calls
- NO "thanks for watching" or sign-offs
- NO "don't forget to" statements
- Each sentence must provide direct value or information
- Use short, impactful sentences (8-12 words max)
- Focus on facts, insights, and actionable information
- Make every word count - remove all unnecessary words
- Cover the topic thoroughly - don't rush or cut corners

{structure_guidance}

Return a JSON object with this exact structure:"""
            
            # Build the JSON template separately
            if duration:
                json_template = """{
    "title": "Direct, value-focused title (5-8 words)",
    "script": "Complete script text that flows naturally from start to finish with zero filler content",
    "story_beats": [
        {
            "description": "Opening hook - most interesting fact",
            "content": "First 5 seconds content",
            "duration": 5
        },
        {
            "description": "Core information delivery",
            "content": "Main content section",
            "duration": """ + str(core_content_duration) + """
        },
        {
            "description": "Key takeaway or impact",
            "content": "Final insight or conclusion",
            "duration": 5
        }
    ],
    "search_terms": ["relevant", "keywords", "for", "visuals"],
    "visuals": [
        {
            "description": "Specific visual that supports the content",
            "timing": 0,
            "duration": 10
        }
    ]
}"""
            else:
                json_template = """{
    "title": "Direct, value-focused title (5-8 words)",
    "script": "Complete script text that flows naturally from start to finish with zero filler content",
    "story_beats": [
        {
            "description": "Opening hook - most interesting fact",
            "content": "Content for the opening hook"
        },
        {
            "description": "Core information delivery",
            "content": "Main content section with all essential information"
        },
        {
            "description": "Key takeaway or impact",
            "content": "Final insight or conclusion"
        }
    ],
    "search_terms": ["relevant", "keywords", "for", "visuals"],
    "visuals": [
        {
            "description": "Specific visual that supports the content"
        }
    ],
    "estimated_duration": "Estimated duration in seconds based on content length"
}"""
            
            system_prompt += "\n\n" + json_template
            
            # Create user prompt with content brief information
            user_prompt = f"""Create a {script_type} script about: {topic}

CRITICAL REQUIREMENTS:
- Start with the most valuable information immediately
- Every sentence must provide direct value
- NO filler words, greetings, or transitions
- NO subscription requests or engagement calls
- Use concrete facts and specific details
- Keep sentences short and impactful
- End with a powerful insight, not a sign-off

Content Focus:"""
            
            if "content_structure" in content_brief:
                structure = content_brief["content_structure"]
                
                if "hook" in structure:
                    user_prompt += f"\n\nPOWERFUL OPENING: {structure['hook']}"
                
                if "points" in structure:
                    # Convert points into direct information
                    key_info = " ".join([f"{point}." for point in structure["points"]])
                    user_prompt += f"\n\nKEY INFORMATION TO INCLUDE: {key_info}"
                
                if "narrative_style" in structure:
                    user_prompt += f"\n\nTONE: {structure['narrative_style'].upper()} but always direct and value-focused"
            
            user_prompt += "\n\nRemember: No filler content, just pure value from word one!"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2000
            )
            
            # Parse the response
            if response.choices and response.choices[0].message.content:
                script_data = json.loads(response.choices[0].message.content)
                
                # Add metadata
                script_data["topic"] = topic
                script_data["type"] = script_type
                script_data["target_duration"] = duration
                
                # Estimate duration if not provided
                if not duration and "script" in script_data:
                    # Estimate based on word count (approx. 150 words per minute)
                    word_count = len(script_data["script"].split())
                    estimated_duration = max(30, int((word_count / 150) * 60))  # Minimum 30 seconds
                    script_data["estimated_duration"] = estimated_duration
                    script_data["target_duration"] = estimated_duration
                
                # Add hashtags
                if "hashtags" in content_brief:
                    script_data["hashtags"] = content_brief["hashtags"]
                
                # Validate script for filler content
                script_text = script_data.get("script", "")
                if self._contains_filler_content(script_text):
                    logger.warning("Generated script contains filler content, cleaning...")
                    script_data["script"] = self._clean_filler_content(script_text)
                
                return script_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error in OpenAI script generation: {str(e)}")
            return None
    
    def _contains_filler_content(self, script: str) -> bool:
        """
        Check if script contains common filler content.
        
        Args:
            script: Script text to check
            
        Returns:
            True if filler content is detected
        """
        filler_phrases = [
            "welcome to", "thanks for watching", "don't forget to", "like and subscribe",
            "in this video", "let's dive into", "today we're going to", "make sure to",
            "if you enjoyed", "hit the like button", "ring the notification bell",
            "without further ado", "so without delay", "let's get started"
        ]
        
        script_lower = script.lower()
        return any(phrase in script_lower for phrase in filler_phrases)
    
    def _clean_filler_content(self, script: str) -> str:
        """
        Remove filler content from script.
        
        Args:
            script: Original script text
            
        Returns:
            Cleaned script text
        """
        import re
        
        # Remove common filler phrases
        filler_patterns = [
            r'welcome to[^.!?]*[.!?]',
            r'thanks for watching[^.!?]*[.!?]',
            r"don't forget to[^.!?]*[.!?]",
            r'like and subscribe[^.!?]*[.!?]',
            r'in this video[^.!?]*[.!?]',
            r"let's dive into[^.!?]*[.!?]",
            r"today we're going to[^.!?]*[.!?]",
            r'make sure to[^.!?]*[.!?]',
            r'if you enjoyed[^.!?]*[.!?]',
            r'hit the like button[^.!?]*[.!?]',
            r'ring the notification bell[^.!?]*[.!?]',
            r'without further ado[^.!?]*[.!?]',
            r'so without delay[^.!?]*[.!?]',
            r"let's get started[^.!?]*[.!?]"
        ]
        
        cleaned_script = script
        for pattern in filler_patterns:
            cleaned_script = re.sub(pattern, '', cleaned_script, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned_script = re.sub(r'\s+', ' ', cleaned_script).strip()
        
        return cleaned_script
    
    def _generate_basic_script(
        self, 
        topic: str, 
        content_brief: Dict[str, Union[str, List[str]]], 
        script_type: str,
        duration: Optional[int] = None
    ) -> Dict[str, Union[str, Dict]]:
        """
        Generate a basic script without OpenAI, focusing on direct content delivery.
        
        Args:
            topic: User topic string
            content_brief: Content brief from topic analyzer
            script_type: Type of script to generate
            duration: Target duration in seconds (optional, content will determine actual length)
            
        Returns:
            Dictionary with script information
        """
        # Extract information from content brief
        title = content_brief.get("title", f"Essential Facts About {topic.title()}")
        structure = content_brief.get("content_structure", {})
        hook = structure.get("hook", f"Here's what you need to know about {topic}.")
        
        # Use points from content brief if available
        brief_points = structure.get("points", [
            f"Key insight about {topic}",
            f"Important fact about {topic}",
            f"Critical information about {topic}"
        ])
        
        # Calculate timing based on whether duration is specified
        if duration:
            # Fixed duration approach
            hook_duration = 5
            main_duration = duration - 10
            conclusion_duration = 5
        else:
            # Content-driven approach - let content determine timing
            hook_duration = None
            main_duration = None
            conclusion_duration = None
        
        # Create hook - start with most engaging fact
        if not self._contains_filler_content(hook):
            hook_content = hook
        else:
            if brief_points:
                hook_content = brief_points[0]
            else:
                hook_content = f"{topic} has surprising characteristics that most people don't know about."
        
        # Create main content - combine points into flowing narrative
        main_content = ""
        for i, point in enumerate(brief_points):
            if i == 0:
                main_content += f"{point}. "
            else:
                main_content += f"Additionally, {point.lower()}. "
        
        # Add more comprehensive content if no duration constraint
        if not duration and "content_structure" in content_brief:
            structure = content_brief["content_structure"]
            if "sections" in structure:
                # Add more detailed sections
                for section in structure["sections"]:
                    if section.lower() not in ["introduction", "conclusion"]:
                        main_content += f"Regarding {section.lower()}, this aspect of {topic} reveals important insights. "
        
        # Create conclusion with key takeaway
        conclusion_content = f"Understanding {topic} provides valuable insights for anyone interested in this field."
        if brief_points:
            conclusion_content = f"The most important thing to remember about {topic} is {brief_points[-1].lower()}."
        
        # Combine all sections
        full_script = f"{hook_content} {main_content} {conclusion_content}"
        
        # Estimate duration based on content
        word_count = len(full_script.split())
        estimated_duration = max(30, int((word_count / 150) * 60))  # Minimum 30 seconds
        
        # Create story beats
        if duration:
            story_beats = [
                {
                    "description": "Opening hook with key insight",
                    "content": hook_content,
                    "duration": hook_duration
                },
                {
                    "description": "Core information delivery",
                    "content": main_content,
                    "duration": main_duration
                },
                {
                    "description": "Key takeaway",
                    "content": conclusion_content,
                    "duration": conclusion_duration
                }
            ]
        else:
            story_beats = [
                {
                    "description": "Opening hook with key insight",
                    "content": hook_content
                },
                {
                    "description": "Core information delivery",
                    "content": main_content
                },
                {
                    "description": "Key takeaway",
                    "content": conclusion_content
                }
            ]
        
        # Generate visual suggestions based on content
        if duration:
            visuals = [
                {
                    "description": f"Visual representation of {topic}",
                    "timing": 0,
                    "duration": 10
                },
                {
                    "description": f"Detailed view of {topic} characteristics",
                    "timing": 10,
                    "duration": 15
                },
                {
                    "description": f"Comparison or example related to {topic}",
                    "timing": 25,
                    "duration": 10
                }
            ]
        else:
            visuals = [
                {
                    "description": f"Visual representation of {topic}"
                },
                {
                    "description": f"Detailed view of {topic} characteristics"
                },
                {
                    "description": f"Comparison or example related to {topic}"
                }
            ]
        
        # Return the script data
        result = {
            "topic": topic,
            "title": title,
            "script": full_script,
            "story_beats": story_beats,
            "search_terms": content_brief.get("search_terms", [topic]),
            "hashtags": content_brief.get("hashtags", []),
            "visuals": visuals,
            "type": script_type,
            "estimated_duration": estimated_duration
        }
        
        if duration:
            result["target_duration"] = duration
        else:
            result["target_duration"] = estimated_duration
            
        return result
    
    def generate_shorts_script(self, topic: str, duration: Optional[int] = 45) -> Dict[str, Union[str, Dict]]:
        """
        Generate a script specifically for YouTube Shorts or TikTok.
        
        Args:
            topic: User topic string
            duration: Suggested duration for shorts (default 45s, but content can determine actual length)
            
        Returns:
            Dictionary with script information
        """
        # Shorts typically benefit from suggested duration but content can still determine final length
        return self.generate_script(topic, script_type="entertaining", duration=duration)
    
    def generate_educational_script(self, topic: str, duration: int = 120) -> Dict[str, Union[str, Dict]]:
        """
        Generate an educational script.
        
        Args:
            topic: User topic string
            duration: Target duration in seconds
            
        Returns:
            Dictionary with script information
        """
        return self.generate_script(topic, script_type="educational", duration=duration) 