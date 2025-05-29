import asyncio
import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright
import re

# --- CONFIGURABLE ---
TIKTOK_URL_TEMPLATE = "https://www.tiktok.com/tag/{hashtag}"
VIDEO_URL_PATTERN = re.compile(r"https://www.tiktok.com/@[\w.-]+/video/\d+")


def is_valid_tiktok_url(url):
    return bool(VIDEO_URL_PATTERN.match(url))


def load_existing_urls(output_file):
    if Path(output_file).exists():
        with open(output_file, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def load_processed_urls(processed_db_file="data/processed_urls.json"):
    """
    Load the database of already processed URLs
    
    Args:
        processed_db_file: Path to the JSON file tracking processed URLs
        
    Returns:
        Set of already processed URLs
    """
    db_path = Path(processed_db_file)
    if db_path.exists():
        try:
            with open(db_path, 'r') as f:
                data = json.load(f)
                processed = set(data.get("processed_urls", []))
                if not processed:
                    print(f"[WARNING] Processed URLs database {processed_db_file} is empty.")
                else:
                    print(f"[INFO] Loaded {len(processed)} processed URLs from {processed_db_file}.")
                return processed
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading processed URLs database: {e}")
            return set()
    print(f"[WARNING] Processed URLs database {processed_db_file} does not exist.")
    return set()


def save_processed_urls(urls, processed_db_file="data/processed_urls.json"):
    """
    Save URLs to the processed database
    
    Args:
        urls: Set of URLs to mark as processed
        processed_db_file: Path to the JSON file tracking processed URLs
    """
    db_path = Path(processed_db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing data if present
    processed = load_processed_urls(processed_db_file)
    
    # Update with new URLs
    processed.update(urls)
    
    # Save back to file
    try:
        with open(db_path, 'w') as f:
            json.dump({"processed_urls": list(processed)}, f, indent=2)
    except IOError as e:
        print(f"Error saving processed URLs database: {e}")


async def collect_tiktok_video_urls(count, output_file, hashtag, processed_db_file="data/processed_urls.json"):
    """
    Scroll TikTok hashtag page, collect unique video URLs, and save to output_file.
    Args:
        count (int): Number of unique video URLs to collect (not already in output_file).
        output_file (str): Path to output file.
        hashtag (str): Hashtag to target (without #)
        processed_db_file (str): Path to the processed URLs database
    """
    # Load URLs that are already in the output file
    existing_urls = load_existing_urls(output_file)
    
    # Load URLs that have been previously processed
    processed_urls = load_processed_urls(processed_db_file)
    
    # Initialize set for new URLs to collect
    urls = set()
    tiktok_url = TIKTOK_URL_TEMPLATE.format(hashtag=hashtag)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(tiktok_url)
        await page.wait_for_timeout(5000)
        screenshot_path = Path(output_file).with_suffix('.screenshot.png')
        await page.screenshot(path=str(screenshot_path))
        print(f"Screenshot saved to {screenshot_path}")
        
        last_height = await page.evaluate("document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 50
        
        print(f"[INFO] Existing URLs in output file: {len(existing_urls)}")
        print(f"[INFO] Processed URLs in database: {len(processed_urls)}")
        
        while len(urls) < count and scroll_attempts < max_scroll_attempts:
            elements = await page.query_selector_all('a[href*="/video/"]')
            print(f"[INFO] Found {len(elements)} video link elements on page.")
            
            for el in elements:
                href = await el.get_attribute('href')
                if (href and is_valid_tiktok_url(href) and 
                    href not in existing_urls and 
                    href not in urls and
                    href not in processed_urls):
                    urls.add(href)
                    print(f"[INFO] Added new URL: {href}")
                    if len(urls) >= count:
                        break
                elif href in processed_urls:
                    print(f"[DEBUG] Skipped already processed URL: {href}")
                elif href in existing_urls:
                    print(f"[DEBUG] Skipped already in output file: {href}")
                elif href in urls:
                    print(f"[DEBUG] Skipped duplicate in current run: {href}")
                        
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate("document.body.scrollHeight")
            
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            last_height = new_height
            
        await browser.close()
    
    # Write new URLs to output file (overwrite the file with only new URLs)
    with open(output_file, "w") as f:
        for url in urls:
            f.write(url + "\n")
    
    print(f"[INFO] Total new URLs collected: {len(urls)}")
    
    # Return the URLs for potential further processing
    return urls


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Collect unique TikTok video URLs by scrolling a TikTok hashtag page.")
    parser.add_argument('--count', type=int, required=True, help='Number of new video URLs to collect')
    parser.add_argument('--output', type=str, default='tiktok_urls.txt', help='Output file for URLs')
    parser.add_argument('--hashtag', type=str, default='funny', help='Hashtag to target (without #)')
    parser.add_argument('--processed-db', type=str, default='data/processed_urls.json', 
                        help='Path to the processed URLs database file')
    args = parser.parse_args()
    
    urls = asyncio.run(collect_tiktok_video_urls(
        args.count, 
        args.output, 
        args.hashtag,
        args.processed_db
    ))
    
    # Only update the processed URLs database if we actually find and compile videos
    if urls:
        # Note: In this implementation, we're not marking URLs as processed here
        # We'll update the processed database after successful compilation in the main script
        pass

# Wrapper function to match the import in main.py
async def scrape_urls(count, hashtag, output_file, save_screenshot=False, processed_db_file="data/processed_urls.json"):
    """
    Wrapper for collect_tiktok_video_urls to maintain compatibility with main.py
    
    Args:
        count (int): Number of unique video URLs to collect
        hashtag (str): Hashtag to target (without #)
        output_file (str): Path to output file
        save_screenshot (bool): Not used in current implementation but kept for API compatibility
        processed_db_file (str): Path to the processed URLs database
        
    Returns:
        Set of collected URLs
    """
    return await collect_tiktok_video_urls(
        count=count,
        output_file=output_file,
        hashtag=hashtag,
        processed_db_file=processed_db_file
    )

if __name__ == "__main__":
    main() 