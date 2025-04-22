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
python -m src.main --auto-fetch --fetch-hashtag dance --fetch-count 15 --title "Best Dance TikToks" --upload

# Automatically fetch and create Shorts (only one Shorts video will be created)
python -m src.main --auto-fetch --shorts --title "Funny TikTok Shorts"
```

- `--auto-fetch`: Automatically collects new TikTok URLs if none are provided
- `--fetch-hashtag`: Hashtag to use for collection (default: funny)
- `--fetch-count`: Number of TikToks to fetch (default: 10)
- `--shorts`: (Recommended) Create a single Shorts video from the compilation (default if any Shorts flag is set)
- `--generate-shorts`, `--compilation-short`: [DEPRECATED] Use `--shorts` instead. These flags now behave identically and only create one Shorts video from the compilation.

**Note:** Whether you use auto-fetch or manual workflows, only one Shorts video is ever created, always based on your compilation. Multiple Shorts from individual videos are no longer supported.

### Complete Workflow (Manual)

```bash
# Collect videos and create compilation in one command
python -m src.url_collector.tiktok_scraper --count 10 --output tiktok_urls.txt --hashtag funny && python -m src.main --urls tiktok_urls.txt --title "Weekly Compilation" --upload
```

### YouTube Shorts (Manual)

```bash
# Create a YouTube Short from compilation
python -m src.main --urls tiktok_urls.txt --title "Funny Moments" --shorts
```

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
