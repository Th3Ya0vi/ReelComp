#!/usr/bin/env python3
"""
Diagnostic script for video files.
This script will analyze a video file and report on any issues that might cause problems
with the multi-clip shorts generator.
"""

import os
import sys
import argparse
from pathlib import Path

# Add the parent directory to the path to import from src
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
import ffmpeg
from moviepy.editor import VideoFileClip
from src.utils.logger_config import setup_logger


def analyze_video_with_ffprobe(video_path):
    """
    Analyze a video file using ffprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        dict: Video information
    """
    try:
        probe = ffmpeg.probe(video_path)
        video_info = next((stream for stream in probe['streams'] 
                           if stream['codec_type'] == 'video'), None)
        audio_info = next((stream for stream in probe['streams'] 
                           if stream['codec_type'] == 'audio'), None)
        
        if video_info:
            logger.info("Video stream found:")
            logger.info(f"  Codec: {video_info.get('codec_name')}")
            logger.info(f"  Resolution: {video_info.get('width')}x{video_info.get('height')}")
            logger.info(f"  Duration: {video_info.get('duration', '?')}s")
            logger.info(f"  Bit rate: {video_info.get('bit_rate', '?')} bps")
            logger.info(f"  Format: {video_info.get('pix_fmt', '?')}")
            
            # Check for rotation metadata
            if 'tags' in video_info and 'rotate' in video_info['tags']:
                logger.warning(f"  Rotation: {video_info['tags']['rotate']} degrees")
                logger.warning("  Rotated videos may cause problems with the shorts generator")
        else:
            logger.error("No video stream found in the file")
        
        if audio_info:
            logger.info("Audio stream found:")
            logger.info(f"  Codec: {audio_info.get('codec_name')}")
            logger.info(f"  Sample rate: {audio_info.get('sample_rate')} Hz")
            logger.info(f"  Channels: {audio_info.get('channels')}")
            logger.info(f"  Bit rate: {audio_info.get('bit_rate', '?')} bps")
        else:
            logger.warning("No audio stream found in the file")
        
        return probe
    except Exception as e:
        logger.error(f"Error analyzing video with ffprobe: {str(e)}")
        return None


def analyze_video_with_moviepy(video_path):
    """
    Analyze a video file using MoviePy.
    
    Args:
        video_path: Path to the video file
    """
    try:
        logger.info("Testing video with MoviePy...")
        with VideoFileClip(video_path) as clip:
            if clip is None:
                logger.error("Failed to load video with MoviePy")
                return False
            
            logger.info(f"MoviePy successfully loaded the video")
            logger.info(f"  Duration: {clip.duration:.2f}s")
            logger.info(f"  Size: {clip.size}")
            
            # Check FPS - this is critical for shorts generation
            if not hasattr(clip, 'fps') or clip.fps is None:
                logger.error("  FPS: MISSING (this will cause errors during shorts generation)")
                logger.info("  Recommendation: Use --repair to fix this issue")
            elif clip.fps <= 0:
                logger.error(f"  FPS: {clip.fps} (invalid value, should be positive)")
                logger.info("  Recommendation: Use --repair to fix this issue")
            else:
                logger.info(f"  FPS: {clip.fps}")
            
            if clip.audio is not None:
                logger.info(f"  Audio: Yes (fps: {clip.audio.fps}, nchannels: {clip.audio.nchannels})")
            else:
                logger.info("  Audio: No")
            
            # Test frame access
            try:
                logger.info("Testing frame access...")
                frame = clip.get_frame(0)
                logger.info(f"  First frame successfully retrieved (shape: {frame.shape})")
            except Exception as e:
                logger.error(f"  Failed to access frames: {str(e)}")
                return False
            
            # Test middle and end frames
            try:
                mid_time = clip.duration / 2
                frame = clip.get_frame(mid_time)
                logger.info(f"  Mid-point frame successfully retrieved")
            except Exception as e:
                logger.error(f"  Failed to access mid-point frame: {str(e)}")
            
            try:
                end_time = max(0, clip.duration - 0.1)
                frame = clip.get_frame(end_time)
                logger.info(f"  End frame successfully retrieved")
            except Exception as e:
                logger.error(f"  Failed to access end frame: {str(e)}")
            
            # Test audio if available
            if clip.audio is not None:
                try:
                    logger.info("Testing audio access...")
                    audio_frame = clip.audio.get_frame(0)
                    logger.info(f"  Audio frame successfully retrieved")
                except Exception as e:
                    logger.warning(f"  Failed to access audio: {str(e)}")
            
            # If the FPS is missing, that's a critical error for shorts generation,
            # but we can fix it during repair
            if not hasattr(clip, 'fps') or clip.fps is None or clip.fps <= 0:
                logger.error("Missing valid FPS value will cause problems during shorts generation")
                return False
                
            return True
    except Exception as e:
        logger.error(f"Error analyzing video with MoviePy: {str(e)}")
        return False


def attempt_repair(video_path, output_path=None):
    """
    Attempt to repair a video file by re-encoding it.
    
    Args:
        video_path: Path to the video file
        output_path: Path to save the repaired video (default: add _repaired suffix)
        
    Returns:
        str: Path to the repaired video, or None if repair failed
    """
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_repaired{ext}"
    
    try:
        logger.info(f"Attempting to repair video by re-encoding: {video_path}")
        logger.info(f"Output path: {output_path}")
        
        # First try to detect FPS from input
        try:
            probe = ffmpeg.probe(video_path)
            video_info = next((stream for stream in probe['streams'] 
                              if stream['codec_type'] == 'video'), None)
            
            # Try to extract fps from the video stream
            fps = None
            if video_info and 'r_frame_rate' in video_info:
                try:
                    # r_frame_rate is often in the format "30000/1001" for 29.97 fps
                    fps_fraction = video_info['r_frame_rate'].split('/')
                    if len(fps_fraction) == 2:
                        fps = float(fps_fraction[0]) / float(fps_fraction[1])
                    else:
                        fps = float(fps_fraction[0])
                    logger.info(f"Detected FPS from video stream: {fps}")
                except (ValueError, ZeroDivisionError) as e:
                    logger.warning(f"Could not parse FPS from r_frame_rate: {e}")
                    
            # If we couldn't detect FPS, use a default value
            if fps is None or fps <= 0:
                fps = 30.0
                logger.info(f"Using default FPS: {fps}")
                
            # Use ffmpeg to re-encode the video with explicit fps
            ffmpeg.input(video_path).output(
                output_path, 
                codec='libx264',
                preset='medium',
                r=fps,  # Explicitly set FPS
                audio_codec='aac',
                audio_bitrate='128k',
                **{'loglevel': 'quiet'}
            ).run(overwrite_output=True)
            
        except Exception as e:
            logger.warning(f"Error detecting FPS, using default settings: {e}")
            
            # Fallback to default settings if fps detection fails
            ffmpeg.input(video_path).output(
                output_path, 
                codec='libx264',
                preset='medium',
                r=30,  # Default to 30fps
                audio_codec='aac',
                audio_bitrate='128k',
                **{'loglevel': 'quiet'}
            ).run(overwrite_output=True)
        
        logger.info("Re-encoding complete, verifying repaired video...")
        success = analyze_video_with_moviepy(output_path)
        
        if success:
            logger.success(f"Video successfully repaired: {output_path}")
            return output_path
        else:
            logger.error("Repair attempt failed")
            return None
    except Exception as e:
        logger.error(f"Error repairing video: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Diagnose issues with video files")
    parser.add_argument("video_path", help="Path to the video file to diagnose")
    parser.add_argument("--repair", action="store_true", help="Attempt to repair the video by re-encoding")
    parser.add_argument("--output", help="Output path for repaired video (only used with --repair)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", 
                      help="Log level")
    args = parser.parse_args()
    
    # Setup logger
    setup_logger(args.log_level)
    
    video_path = args.video_path
    
    if not os.path.exists(video_path):
        logger.error(f"Video file does not exist: {video_path}")
        return 1
    
    logger.info(f"Analyzing video: {video_path}")
    logger.info(f"File size: {os.path.getsize(video_path) / (1024*1024):.2f} MB")
    
    # Analyze with ffprobe
    analyze_video_with_ffprobe(video_path)
    
    # Analyze with MoviePy
    success = analyze_video_with_moviepy(video_path)
    
    if not success and args.repair:
        repaired_path = attempt_repair(video_path, args.output)
        if repaired_path:
            logger.info("Video repair successful. You can use the repaired version for shorts generation.")
        else:
            logger.error("Video repair failed.")
    elif not success:
        logger.info("Use --repair to attempt fixing the video through re-encoding")
    else:
        logger.success("Video appears to be compatible with the shorts generator")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main()) 