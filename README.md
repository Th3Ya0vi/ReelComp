# ReelComp: TikTok Video Compilation Automation

Automate creating video compilations from tiktok content. Collect videos from TikTok, create compilations with smooth transitions, generate thumbnails, and upload directly to YouTube.

## ❤️ Sponsor This Project

If you find ReelComp useful, please consider sponsoring the project to support ongoing development and maintenance:

[![Sponsor me on GitHub](https://img.shields.io/badge/Sponsor-Th3Ya0vi-blue?logo=github&style=for-the-badge)](https://github.com/sponsors/Th3Ya0vi)

Your sponsorship helps keep this project active and improving!

## Installation

### Prerequisites
- Python 3.8+
- FFmpeg
- Playwright (for browser automation)

### Setup

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/reelcomp.git
cd reelcomp
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### Installing FFmpeg

- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt update && sudo apt install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

## Usage

### Collecting Videos (Manual)

```bash
python -m src.url_collector.tiktok_scraper --count 10 --output tiktok_urls.txt --hashtag funny
```

### Creating a Compilation (Manual)

```bash
python -m src.main --urls tiktok_urls.txt --title "Funny Compilation"
```

### 🚀 Fully Automated Compilation & Shorts (NEW)

You can now let ReelComp automatically fetch new TikTok URLs and create a compilation or Shorts in one step:

```bash
# Fetch 10 trending TikToks with hashtag 'funny' and create a compilation
python -m src.main --auto-fetch --title "Weekly Compilation" --upload

# Customize hashtag and number of videos
python -m src.main --auto-fetch --fetch-hashtag funny --fetch-count 15 --title "Funniest TiktTok Compilation" --upload

# Automatically fetch and create Shorts (only one Shorts video will be created)
python -m src.main --auto-fetch --shorts --title "Funny TikTok Shorts"

# Create a multi-clip Shorts with segments from multiple videos (NEW!)
python -m src.main --auto-fetch --multi-clip-shorts --title "Best Funny Moments" --upload-shorts
```

- `--auto-fetch`: Automatically collects new TikTok URLs if none are provided
- `--fetch-hashtag`: Hashtag to use for collection (default: funny)
- `--fetch-count`: Number of TikToks to fetch (default: 10)
- `--shorts`: Create a single Shorts video from the compilation (default if any Shorts flag is set)
- `--multi-clip-shorts`: Create a Shorts video with multiple clips from different videos (max 60s total)
- `--generate-shorts`, `--compilation-short`: [DEPRECATED] Use `--shorts` instead. These flags now behave identically and only create one Shorts video from the compilation.

**Note:** For standard shorts (with `--shorts`), only one Shorts video is created from the compilation. For multi-clip shorts (with `--multi-clip-shorts`), multiple video segments are combined into a single 60-second or less video.

### 🧠 AI-Powered Topic Videos (NEW!)

You can now generate videos on any topic using AI, without needing TikTok source content:

```bash
# Main command - Production use
# Create a standard video about a specific topic
python -m src.main --topic "Benefits of meditation" 

# Create a longer video with specific style
python -m src.main --topic "What is the Stock Market?" --topic-duration 180 --topic-style educational

# Create a YouTube Short about a topic
python -m src.main --topic "How to Buy Your First Stock" --topic-shorts

# Customize voice and language
python -m src.main --topic "French cuisine history" --language fr-FR --voice-gender female

# Upload directly to YouTube
python -m src.main --topic "The Difference Between Saving and Investing" --upload

# Test script - For quick testing and development
# Create a standard video about a specific topic
python scripts/test_topic_video.py "Benefits of meditation" --style informative --duration 120

# Create a YouTube Short about a topic
python scripts/test_topic_video.py "Quick cooking tips" --format short

# Create a TikTok-style video
python scripts/test_topic_video.py "Amazing science facts" --format tiktok

# Specify different language
python scripts/test_topic_video.py "History of Paris" --language fr-FR
```

**Features:**
- Generate professional scripts tailored to any topic with AI
- Create natural-sounding voiceovers in multiple languages
- Automatically source relevant images and videos from stock libraries
- Generate synchronized captions for better engagement
- Create TikTok-style pop-up captions that follow the audio
- Create optimized formats for YouTube standard, Shorts, and TikTok
- Support for multiple content styles (informative, entertaining, educational)

### AI Content Configuration

To use the AI features, you'll need to add API keys to your `.env` file:

```
# OpenAI API for script generation
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4-turbo  # or gpt-3.5-turbo for faster/cheaper generation

# Voice provider options
VOICE_PROVIDER=edge_tts  # Free Microsoft Edge TTS (default)
# VOICE_PROVIDER=elevenlabs  # Premium voice quality (requires API key)
ELEVENLABS_API_KEY=your_elevenlabs_api_key  # Only needed if using ElevenLabs

# Caption generation
WHISPER_MODEL_SIZE=base  # Options: tiny, base, small, medium, large
USE_POPUP_CAPTIONS=true  # Enable TikTok-style pop-up captions

# Visual assets
PEXELS_API_KEY=your_pexels_api_key  # For video/image sourcing
UNSPLASH_ACCESS_KEY=your_unsplash_access_key  # For image sourcing
PIXABAY_API_KEY=your_pixabay_api_key  # For video/image sourcing (required for background assets)
```

### Getting API Keys for Visual Assets

For the best results with background videos and images, you should add at least one of these API keys:

#### Pixabay API Key (Recommended)
1. Sign up for a free account at [Pixabay](https://pixabay.com/)
2. Go to https://pixabay.com/api/docs/ and get your API key
3. Add it to your config.json file or .env file as `PIXABAY_API_KEY`

#### Unsplash Access Key
1. Create a developer account at [Unsplash Developers](https://unsplash.com/developers)
2. Create a new application to get your access key
3. Add it to your config.json or .env file as `UNSPLASH_ACCESS_KEY`

#### Pexels API Key
1. Sign up for a free account at [Pexels](https://www.pexels.com/)
2. Apply for an API key at [Pexels API](https://www.pexels.com/api/)
3. Add it to your config.json or .env file as `PEXELS_API_KEY`

### DALL-E Fallback for Background Images and Videos

ReelComp now includes support for OpenAI's GPT Image model as a fallback when other asset sources (Pexels, Unsplash, Pixabay) fail. This ensures your videos always have high-quality backgrounds, even if the stock image APIs are unavailable.

To enable this feature:

1. Make sure your OpenAI API key is configured (same as for script generation)
2. The system will automatically fall back to GPT Image when other sources fail
3. You can test GPT Image generation with the included script:

```bash
# Generate GPT Image assets for specific terms
python scripts/generate_gpt_image_assets.py "nature landscape" "abstract pattern"

# Generate both images and video assets
python scripts/generate_gpt_image_assets.py "sunset beach" "mountain view" --videos

# Specify output directory and number of images per term
python scripts/generate_gpt_image_assets.py "city skyline" -o data/assets/custom -n 3
```

Note: GPT Image generation uses your OpenAI API credits. The system is designed to minimize API usage by only generating images when necessary and limiting the number of images per term.

### Complete Workflow (Manual)

```bash
# Collect videos and create compilation in one command
python -m src.url_collector.tiktok_scraper --count 20 --output tiktok_urls.txt --hashtag fail && python -m src.main --urls tiktok_urls.txt --title "The Best TikTok Shorts For April Fools' Day
" --upload
```

### YouTube Shorts (Manual)

```bash
# Create a standard YouTube Short from compilation
python -m src.main --urls tiktok_urls.txt --title "Funny Moments" --shorts

# Create a multi-clip YouTube Short with segments from different videos
python -m src.main --urls tiktok_urls.txt --title "Best Comedy Moments" --multi-clip-shorts
```

### Diagnosing Video Issues

If you encounter problems with specific videos, you can use the built-in diagnostic tools:

```bash
# Analyze a video file to check for compatibility
python -m src.main --diagnose-video data/videos/problematic_video.mp4

# Attempt to repair a problematic video
python -m src.main --diagnose-video data/videos/problematic_video.mp4 --repair-video

# Specify output path for repaired video
python -m src.main --diagnose-video data/videos/problematic_video.mp4 --repair-video --repair-output fixed_video.mp4
```

### Uploading Existing Videos

If you've already created a compilation or Shorts video, you can upload it directly to YouTube without going through the entire pipeline:

```bash
# Upload an existing video file directly to YouTube
python -m src.main --upload-existing-path "/path/to/your/video.mp4" --title "Your Video Title" --upload
```

This is useful when:
- You've previously created compilations but didn't upload them
- You've edited a video outside of ReelComp
- You want to re-upload a video with a different title/description

## 🕒 Automated Weekly Workflow

You can automate the entire process to run weekly (or on any schedule) using a shell script and cron.

### Example Shell Script

Create a file called `tiktok_weekly.sh`:

```bash
#!/bin/bash
# Example: Collect 10 funny TikToks and create/upload a compilation

python -m src.url_collector.tiktok_scraper --count 10 --output tiktok_urls.txt --hashtag funny
python -m src.main --urls tiktok_urls.txt --title "Weekly Funny Compilation" --upload
```

Make it executable:

```bash
chmod +x tiktok_weekly.sh
```

### Example Cron Job (macOS/Linux)

To run every Wednesday at 10:10 AM, add this to your crontab (`crontab -e`):

```
10 10 * * 3 /path/to/your/reelcomp/tiktok_weekly.sh >> /path/to/your/reelcomp/logs/cron.log 2>&1
```

**Note:**
- Do **not** include any real TikTok URLs or sensitive data in the repository.
- Users should create their own `tiktok_urls.txt` and customize the script for their needs.
- `tiktok_urls.txt` and `tiktok_weekly.sh` are already in `.gitignore` to prevent accidental commits of sensitive or user-specific data.

## Configuration

### Key Settings

```
# Basic Settings in .env file
APP_MAX_VIDEOS_PER_COMPILATION=15  # Maximum videos to include
APP_VIDEO_WIDTH=1080               # Output video width
APP_VIDEO_HEIGHT=1920              # Output video height
APP_TRANSITION_TYPE=random         # Transition between clips

# YouTube Settings
YOUTUBE_PRIVACY_STATUS=unlisted    # Video privacy (private, unlisted, public)
```

### Using a Config File

Create a file (e.g., `config.json`):
```json
{
  "app": {
    "max_videos_per_compilation": 10,
    "video_width": 1920,
    "video_height": 1080,
    "transition_type": "crossfade",
    "use_intro": true,
    "intro_path": "data/assets/my_intro.mp4"
  },
  "youtube": {
    "privacy_status": "unlisted"
  }
}
```

Then run:
```bash
python -m src.main --urls tiktok_urls.txt --config config.json
```

## Troubleshooting

### Common Issues

- **Videos Not Downloading**: Check network connection, TikTok might have updated site structure
- **YouTube Upload Fails**: Delete `credentials/youtube_token.json` and reauthenticate
- **Poor Video Quality**: Increase `bitrate` setting or resolution
- **FFmpeg Not Found**: Verify installation with `ffmpeg -version` and check PATH

### Multi-Clip Shorts Issues

- **"NoneType object has no attribute get_frame"**: This typically means one of your videos is corrupted or can't be read properly. Use our diagnostic tool to identify and fix problematic videos.

- **"No 'fps' attribute specified for function write_videofile"**: This error occurs when one or more video clips don't have a valid frames-per-second value. Use the diagnostic tool to check and repair your videos:

```bash
# Diagnose and check for missing FPS
python -m scripts.diagnose_video data/videos/problematic_video.mp4

# Repair a video with missing or invalid FPS
python -m scripts.diagnose_video data/videos/problematic_video.mp4 --repair
```

- **Empty or Black Output**: This can happen when all source videos fail validation. Try using different videos or repair corrupted ones.

- **Short Duration Output**: If your multi-clip short is much shorter than expected, this could indicate that most clips were rejected during processing. Check your videos using the diagnostic tool.

For more details on the multi-clip shorts feature, see [Multi-Clip Shorts Guide](docs/multi_clip_shorts.md).

## Project Structure

```
reelcomp/
├── src/                       # Source code
│   ├── main.py                # Main entry point
│   ├── url_collector/         # Video URL collection
│   ├── video_collection/      # Video downloading
│   ├── video_processing/      # Compilation creation
│   ├── youtube_uploader/      # YouTube integration
│   ├── thumbnail_generator/   # Thumbnail creation
│   ├── content_generation/    # AI content generation
│   └── utils/                 # Utility functions
├── data/                      # Data storage (created at runtime)
└── credentials/               # API credentials (empty in repo)
```

## Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes**
4. **Commit changes** (`git commit -m 'Add amazing feature'`)
5. **Push to branch** (`git push origin feature/amazing-feature`)
6. **Open a Pull Request**

Please follow these guidelines:
- Follow existing code style
- Add tests for new features
- Update documentation for significant changes
- Use descriptive commit messages

## Changelog

### v1.3.0 (2025-07-25)

- **AI Content Generation:** Create videos about any topic using AI, without needing TikTok source content.
- **Topic-Based Videos:** Generate informative, entertaining, or educational videos on any subject.
- **AI Script Generation:** Automatically create compelling scripts with OpenAI.
- **Voice Synthesis:** Add natural-sounding voiceovers in 13+ languages.
- **Asset Collection:** Automatically find and include relevant images and video footage.
- **Multi-Language Support:** Create content in multiple languages, including English, Spanish, French, German, Chinese, and more.
- **YouTube Shorts:** Generate short-form videos optimized for YouTube Shorts.
- **Improved CLI:** New command-line arguments for AI video generation workflow.
- **Documentation:** Added comprehensive documentation for the new AI content generation features.

### v1.2.0 (2025-06-10)

- **Multi-Clip Shorts Feature:** New `--multi-clip-shorts` flag creates a single Shorts video (max 60s) that includes multiple short segments from different TikTok videos.
- **Improved Shorts Variety:** Multi-clip shorts provide better viewer engagement by showing multiple entertaining clips in one video.
- **Smart Duration Management:** Automatically calculates optimal clip lengths to include as many videos as possible within the 60-second limit.
- **UX Improvements:** Each clip in multi-clip shorts preserves the creator attribution while maintaining smooth transitions.
- **Documentation:** Updated usage instructions for the new multi-clip shorts workflow.

### v1.1.0 (2025-04-22)

- **Direct Video Upload:** New `--upload-existing-path` flag allows you to upload any existing video file (Shorts or compilation) directly to YouTube, bypassing the TikTok/compilation pipeline. Prints the YouTube URL upon success.
- **Documentation:** Added usage instructions for direct video upload.
- **Auto-fetch TikTok URLs:** Use `--auto-fetch` to automatically collect trending TikTok URLs by hashtag.
- **Unified Shorts Creation:** Only one Shorts video is created, always based on the compilation. Per-video Shorts are no longer supported.
- **Improved CLI:** New `--shorts` flag (recommended) for Shorts creation. `--generate-shorts` and `--compilation-short` are deprecated and behave identically.
- **Updated Documentation:** README and CLI help updated for new workflows and options.
- **Bug fixes and usability improvements.**

### v1.0.0

- Initial release
- TikTok video collection by hashtag
- Compilation creation with transitions
- Thumbnail generation
- YouTube Shorts creation
- YouTube upload functionality

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for educational purposes only. Always respect platform terms of service and copyright laws. Ensure you have permission to use and redistribute content.
