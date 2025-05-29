#!/usr/bin/env python3
"""
Test script to validate improved AI video script generation.
Tests that scripts no longer contain filler content or subscription requests.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.config_loader import ConfigLoader
from src.content_generation.script_generator import ScriptGenerator
from src.content_generation.voiceover_generator import VoiceoverGenerator


def test_script_content_quality(script_text: str, topic: str) -> dict:
    """
    Test the quality of generated script content.
    
    Args:
        script_text: Generated script text
        topic: Original topic
        
    Returns:
        Dictionary with test results
    """
    results = {
        "passes": True,
        "issues": [],
        "word_count": len(script_text.split()),
        "script_length": len(script_text)
    }
    
    # Test for unwanted filler content
    filler_phrases = [
        "welcome to", "thanks for watching", "don't forget to", "like and subscribe",
        "in this video", "let's dive into", "today we're going to", "make sure to",
        "if you enjoyed", "hit the like button", "ring the notification bell",
        "without further ado", "so without delay", "let's get started",
        "subscribe for more", "hit subscribe", "smash that like button"
    ]
    
    script_lower = script_text.lower()
    found_filler = []
    
    for phrase in filler_phrases:
        if phrase in script_lower:
            found_filler.append(phrase)
            results["passes"] = False
    
    if found_filler:
        results["issues"].append(f"Contains filler phrases: {', '.join(found_filler)}")
    
    # Test for direct content start
    if script_text.lower().startswith(("welcome", "hello", "hi there", "good morning")):
        results["issues"].append("Script starts with greeting instead of direct content")
        results["passes"] = False
    
    # Test for subscription requests
    subscription_terms = ["subscribe", "like", "notification", "bell", "comment below"]
    subscription_found = []
    
    for term in subscription_terms:
        if term in script_lower:
            subscription_found.append(term)
    
    if subscription_found:
        results["issues"].append(f"Contains subscription-related terms: {', '.join(subscription_found)}")
        results["passes"] = False
    
    # Test for minimum content density (words per second for 60s video should be ~150 words)
    if results["word_count"] < 100:
        results["issues"].append(f"Content seems too short: only {results['word_count']} words")
        results["passes"] = False
    
    # Test for topic relevance
    if topic.lower() not in script_lower:
        results["issues"].append("Script doesn't seem to mention the main topic")
        results["passes"] = False
    
    return results


async def test_script_generation():
    """Test the script generation functionality."""
    print("🧪 Testing Improved AI Video Script Generation")
    print("=" * 60)
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    # Initialize generators
    script_generator = ScriptGenerator(config)
    voiceover_generator = VoiceoverGenerator(config)
    
    # Test topics
    test_topics = [
        "artificial intelligence in healthcare",
        "climate change solutions",
        "cryptocurrency basics",
        "healthy meal prep tips",
        "space exploration"
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for topic in test_topics:
        print(f"\n📝 Testing topic: '{topic}'")
        print("-" * 40)
        
        try:
            # Generate script
            script_data = script_generator.generate_script(
                topic=topic,
                script_type="informative",
                duration=60
            )
            
            script_text = script_data.get("script", "")
            title = script_data.get("title", "")
            
            print(f"Generated title: {title}")
            print(f"Script preview: {script_text[:100]}...")
            
            # Test script quality
            test_results = test_script_content_quality(script_text, topic)
            total_tests += 1
            
            if test_results["passes"]:
                print("✅ PASSED: Script meets quality standards")
                passed_tests += 1
            else:
                print("❌ FAILED: Script has quality issues:")
                for issue in test_results["issues"]:
                    print(f"   - {issue}")
            
            print(f"Word count: {test_results['word_count']}")
            
            # Test TTS normalization
            normalized_script = voiceover_generator._normalize_script_for_tts(script_text)
            if normalized_script != script_text:
                print(f"TTS normalization cleaned: {len(script_text) - len(normalized_script)} characters")
            
        except Exception as e:
            print(f"❌ ERROR generating script: {str(e)}")
            total_tests += 1
    
    print(f"\n🎯 Test Summary")
    print("=" * 30)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Script generation improvements are working.")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} tests failed. Review the issues above.")


async def test_voiceover_cleaning():
    """Test the voiceover text cleaning functionality."""
    print("\n🎤 Testing Voiceover Text Cleaning")
    print("=" * 40)
    
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    voiceover_generator = VoiceoverGenerator(config)
    
    # Test cases with various filler content
    test_cases = [
        "Welcome to our channel! Today we're going to discuss AI.",
        "Thanks for watching! Don't forget to like and subscribe.",
        "In this video, let's dive into the basics of machine learning.",
        "So, basically, you know, artificial intelligence is, um, really important.",
        "Make sure to hit that notification bell for more content like this!"
    ]
    
    for i, test_script in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_script}")
        cleaned = voiceover_generator._normalize_script_for_tts(test_script)
        print(f"Cleaned: {cleaned}")
        
        if cleaned != test_script:
            print("✅ Content was cleaned")
        else:
            print("⚠️  No cleaning applied")


if __name__ == "__main__":
    print("🚀 Starting AI Video Generation Tests")
    print("=" * 60)
    
    # Run async tests
    asyncio.run(test_script_generation())
    asyncio.run(test_voiceover_cleaning())
    
    print(f"\n✨ Testing complete!") 