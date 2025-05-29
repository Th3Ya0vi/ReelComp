#!/usr/bin/env python3
import os
import json
import requests
from src.utils.config_loader import ConfigLoader

# Load config
config_loader = ConfigLoader()
config = config_loader.get_config("config.json")

# Get the Pixabay API key
pixabay_api_key = config.ai.pixabay_api_key
print(f"Pixabay API key from config: {pixabay_api_key}")
print(f"API key length: {len(pixabay_api_key) if pixabay_api_key else 'N/A'}")
print(f"API key character by character:")
if pixabay_api_key:
    for i, char in enumerate(pixabay_api_key):
        print(f"  Char {i}: '{char}' (ASCII: {ord(char)})")

# Check for leading/trailing whitespace
if pixabay_api_key and (pixabay_api_key != pixabay_api_key.strip()):
    print("WARNING: API key contains leading or trailing whitespace!")
    print(f"Original: '{pixabay_api_key}'")
    print(f"Stripped: '{pixabay_api_key.strip()}'")
    
    # Use the stripped version
    pixabay_api_key = pixabay_api_key.strip()
    print("Using stripped API key for test")

# Try a direct API call
api_url = "https://pixabay.com/api/"
params = {
    "key": pixabay_api_key,
    "q": "test",
    "per_page": 3
}

print("\nMaking direct API call to Pixabay...")
response = requests.get(api_url, params=params)
print(f"Status Code: {response.status_code}")
print(f"Response Text: {response.text[:200]}...")  # Print first 200 chars

# Try an API call with manually entered key
hardcoded_key = "9387924-f3e6d8e0cef5b651425289e7c"
params2 = {
    "key": hardcoded_key,
    "q": "test",
    "per_page": 3
}

print("\nMaking API call with hardcoded key...")
response2 = requests.get(api_url, params=params2)
print(f"Status Code: {response2.status_code}")
print(f"Response Text: {response2.text[:200]}...") 