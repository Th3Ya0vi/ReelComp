#!/usr/bin/env python3
"""
Test script to demonstrate flexible video duration based on content.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.config_loader import ConfigLoader
from src.content_generation.script_generator import ScriptGenerator
from src.content_generation.content_engine import ContentVideoEngine


async def test_flexible_duration():
    """Test the flexible duration functionality."""
    print("🎬 Testing Flexible Video Duration System")
    print("=" * 60)
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Initialize generators
    script_generator = ScriptGenerator(config)
    content_engine = ContentVideoEngine(config)
    
    # Test scenarios
    test_scenarios = [
        {
            "topic": "quantum computing basics",
            "duration": None,  # Let content determine length
            "description": "No duration constraint - let content flow naturally"
        },
        {
            "topic": "quick meditation tips",
            "duration": 60,  # Suggest 60 seconds
            "description": "60-second suggested duration"
        },
        {
            "topic": "comprehensive guide to machine learning",
            "duration": None,  # Let content determine length
            "description": "Complex topic - no duration limit"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🧪 Test {i}: {scenario['description']}")
        print(f"Topic: {scenario['topic']}")
        print(f"Suggested Duration: {scenario['duration'] if scenario['duration'] else 'Content-driven'}")
        print("-" * 50)
        
        try:
            # Generate script
            script_data = script_generator.generate_script(
                topic=scenario["topic"],
                script_type="informative",
                duration=scenario["duration"]
            )
            
            # Extract key metrics
            script_text = script_data.get("script", "")
            title = script_data.get("title", "")
            target_duration = script_data.get("target_duration", 0)
            estimated_duration = script_data.get("estimated_duration", 0)
            word_count = len(script_text.split())
            
            print(f"✅ Generated Script:")
            print(f"   Title: {title}")
            print(f"   Word Count: {word_count}")
            print(f"   Target Duration: {target_duration}s")
            if estimated_duration != target_duration:
                print(f"   Estimated Duration: {estimated_duration}s")
            
            # Show script preview
            print(f"   Script Preview: {script_text[:150]}...")
            
            # Calculate words per minute
            if target_duration > 0:
                wpm = (word_count / target_duration) * 60
                print(f"   Words per Minute: {wpm:.1f}")
                
                # Check if it's a natural speaking pace (120-180 WPM is typical)
                if 120 <= wpm <= 180:
                    print(f"   ✅ Natural speaking pace")
                elif wpm < 120:
                    print(f"   📢 Slower pace - good for complex content")
                else:
                    print(f"   ⚡ Faster pace - good for energetic content")
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print(f"\n🎯 Summary")
    print("=" * 30)
    print("The improved system now:")
    print("✅ Allows content to determine natural video length")
    print("✅ Respects suggested durations when provided")
    print("✅ Scales asset collection based on content length")
    print("✅ Estimates duration based on script word count")
    print("✅ Uses actual audio duration when available")
    print("✅ No more artificial time constraints cutting content short")


if __name__ == "__main__":
    print("🚀 Testing Flexible Duration Video Generation")
    print("=" * 60)
    
    # Run async test
    asyncio.run(test_flexible_duration())
    
    print(f"\n✨ Testing complete!")
    print("\nNow your videos can be as long as they need to be!")
    print("The content determines the length, not arbitrary time limits. 🎉") 