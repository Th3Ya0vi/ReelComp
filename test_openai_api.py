#!/usr/bin/env python3
"""
Test script to check OpenAI API integration.
"""
import os
from openai import OpenAI
from src.utils.config_loader import ConfigLoader

# Load configuration
config_loader = ConfigLoader()
config = config_loader.get_config()

# Get OpenAI API key and model
openai_api_key = config.ai.openai_api_key
openai_model = config.ai.openai_model

# Clean the model name if it has comments
if isinstance(openai_model, str) and "#" in openai_model:
    openai_model = openai_model.split("#")[0].strip()
    print(f"Cleaned model name to: {openai_model}")

print(f"Using OpenAI model: {openai_model}")
print(f"API key: {openai_api_key[:5]}...{openai_api_key[-4:]}")

# Test OpenAI API call
try:
    client = OpenAI(api_key=openai_api_key)
    
    # List available models
    print("\nListing available OpenAI models:")
    models_response = client.models.list()
    
    # Print model IDs
    print("Available models:")
    for model in models_response.data:
        print(f"- {model.id}")
    
    # Test the specified model
    print(f"\nTesting model: {openai_model}")
    response = client.chat.completions.create(
        model=openai_model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, can you hear me?"}
        ],
        max_tokens=100
    )
    
    print(f"Response from OpenAI: {response.choices[0].message.content}")
    print("OpenAI API test successful!")
    
except Exception as e:
    print(f"Error: {str(e)}")
    print("\nThis error suggests there's an issue with your OpenAI configuration.")
    
    if "invalid model" in str(e).lower() or "invalid model ID" in str(e).lower():
        print("\nPossible solutions:")
        print("1. Update your model name in config.json to a valid model")
        print("2. Check if your API key has access to the requested model")
        print("3. Try using a different model like 'gpt-4-turbo' or 'gpt-3.5-turbo'") 