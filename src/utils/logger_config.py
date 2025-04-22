"""
Logger Configuration Module

Sets up logging for the application using Loguru.
"""

import os
import sys
from pathlib import Path

from loguru import logger


def setup_logger(level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configure the application logger.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Configure log file path
    log_file = log_path / "tiktok_compilation.log"
    
    # Clear default handlers
    logger.remove()
    
    # Always show INFO and above in the console, regardless of file log level
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler with rotation
    logger.add(
        log_file,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="1 week",
        compression="zip"
    )
    
    logger.info(f"Logger initialized at level {level}")


# Example usage
if __name__ == "__main__":
    setup_logger("DEBUG")
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message") 