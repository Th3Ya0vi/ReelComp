"""
Script Generator Module

Generates video scripts for various content types based on user topics.
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
    
    def generate_script(self, topic: str, script_type: str = "informative", duration: int = 60) -> Dict[str, Union[str, Dict]]:
        """
        Generate a complete video script.
        
        Args:
            topic: User topic string
            script_type: Type of script to generate (informative, entertaining, educational)
            duration: Target duration in seconds
            
        Returns:
            Dictionary with script information
        """
        # Analyze the topic first
        logger.info(f"Generating {script_type} script for topic: '{topic}' (duration: {duration}s)")
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
        duration: int
    ) -> Optional[Dict[str, Union[str, Dict]]]:
        """
        Generate a script using OpenAI.
        
        Args:
            topic: User topic string
            content_brief: Content brief from topic analyzer
            script_type: Type of script to generate
            duration: Target duration in seconds
            
        Returns:
            Dictionary with script information or None if failed
        """
        if not self._ensure_client():
            return None
        
        try:
            # Determine word count based on duration (approx. 150 words per minute)
            word_count = int((duration / 60) * 150)
            
            # Create system prompt
            system_prompt = f"""
            You are an expert script writer for {script_type} videos.
            Create a script for a {duration}-second video about "{topic}".
            The script should be approximately {word_count} words.
            
            Return a JSON object with the following structure:
            
            {{
                "title": "Catchy title for the video",
                "script": "Full script text with natural pauses and emphasis",
                "sections": [
                    {{
                        "name": "Section name",
                        "content": "Section text",
                        "duration": "Estimated duration in seconds"
                    }},
                    ...
                ],
                "search_terms": ["relevant", "search", "terms"],
                "visuals": [
                    {{
                        "description": "Description of visual element",
                        "timing": "When it should appear in seconds",
                        "duration": "How long it should display in seconds"
                    }},
                    ...
                ]
            }}
            
            Include 3-8 visual elements with specific timing suggestions.
            """
            
            # Create user prompt with content brief information
            user_prompt = f"Topic: {topic}\n\n"
            
            if "content_structure" in content_brief:
                structure = content_brief["content_structure"]
                
                if "hook" in structure:
                    user_prompt += f"Suggested hook: {structure['hook']}\n\n"
                
                if "sections" in structure:
                    sections_str = "\n".join([f"- {section}" for section in structure["sections"]])
                    user_prompt += f"Suggested sections:\n{sections_str}\n\n"
                
                if "points" in structure:
                    points_str = "\n".join([f"- {point}" for point in structure["points"]])
                    user_prompt += f"Key points to cover:\n{points_str}\n\n"
                
                if "narrative_style" in structure:
                    user_prompt += f"Narrative style: {structure['narrative_style']}\n\n"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.config.ai.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse the response
            if response.choices and response.choices[0].message.content:
                script_data = json.loads(response.choices[0].message.content)
                
                # Add metadata
                script_data["topic"] = topic
                script_data["type"] = script_type
                script_data["target_duration"] = duration
                
                # Add hashtags
                if "hashtags" in content_brief:
                    script_data["hashtags"] = content_brief["hashtags"]
                
                return script_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error in OpenAI script generation: {str(e)}")
            return None
    
    def _generate_basic_script(
        self, 
        topic: str, 
        content_brief: Dict[str, Union[str, List[str]]], 
        script_type: str,
        duration: int
    ) -> Dict[str, Union[str, Dict]]:
        """
        Generate a basic script without OpenAI.
        
        Args:
            topic: User topic string
            content_brief: Content brief from topic analyzer
            script_type: Type of script to generate
            duration: Target duration in seconds
            
        Returns:
            Dictionary with script information
        """
        # Extract information from content brief
        title = content_brief.get("title", f"Amazing Facts About {topic.title()}")
        structure = content_brief.get("content_structure", {})
        hook = structure.get("hook", f"Did you know these amazing facts about {topic}?")
        
        # Generate basic script sections
        sections = []
        
        # Use sections from content brief if available
        brief_sections = structure.get("sections", ["Introduction", "Main Content", "Conclusion"])
        brief_points = structure.get("points", [f"Fact about {topic}", f"Another fact about {topic}", f"Final fact about {topic}"])
        
        # Calculate section durations
        intro_duration = max(5, int(duration * 0.2))
        main_duration = int(duration * 0.6)
        conclusion_duration = max(5, duration - intro_duration - main_duration)
        
        # Create intro section
        sections.append({
            "name": brief_sections[0],
            "content": f"{hook} In this video, we'll explore some fascinating information about {topic}.",
            "duration": intro_duration
        })
        
        # Create main content sections
        points_per_section = max(1, len(brief_points) // (len(brief_sections) - 2 or 1))
        remaining_sections = brief_sections[1:-1]
        
        for i, section_name in enumerate(remaining_sections):
            start_idx = i * points_per_section
            end_idx = min(start_idx + points_per_section, len(brief_points))
            section_points = brief_points[start_idx:end_idx]
            
            section_content = f"{section_name} about {topic}. "
            section_content += " ".join(section_points)
            
            section_duration = main_duration // len(remaining_sections)
            
            sections.append({
                "name": section_name,
                "content": section_content,
                "duration": section_duration
            })
        
        # Create conclusion section
        sections.append({
            "name": brief_sections[-1],
            "content": f"Thanks for watching this video about {topic}! If you enjoyed it, please like and subscribe for more content like this.",
            "duration": conclusion_duration
        })
        
        # Combine sections into full script
        full_script = " ".join([section["content"] for section in sections])
        
        # Generate basic visual suggestions
        visuals = [
            {
                "description": f"Show title card with '{title}'",
                "timing": "0",
                "duration": "3"
            },
            {
                "description": f"Display relevant image of {topic}",
                "timing": str(intro_duration),
                "duration": "5"
            },
            {
                "description": "Show bullet points with key facts",
                "timing": str(intro_duration + 10),
                "duration": "10"
            },
            {
                "description": "End screen with call to action",
                "timing": str(duration - 5),
                "duration": "5"
            }
        ]
        
        # Return the script data
        return {
            "topic": topic,
            "title": title,
            "script": full_script,
            "sections": sections,
            "search_terms": content_brief.get("search_terms", [topic]),
            "hashtags": content_brief.get("hashtags", []),
            "visuals": visuals,
            "type": script_type,
            "target_duration": duration
        }
    
    def generate_shorts_script(self, topic: str) -> Dict[str, Union[str, Dict]]:
        """
        Generate a script specifically for YouTube Shorts or TikTok.
        
        Args:
            topic: User topic string
            
        Returns:
            Dictionary with script information
        """
        # Shorts have specific duration requirements
        return self.generate_script(topic, script_type="entertaining", duration=30)
    
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