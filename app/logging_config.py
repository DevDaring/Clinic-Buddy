"""
Logging configuration for Clinical Trial Predictor.
Creates both console and file logging with detailed formatting.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

def setup_logging(log_level=logging.INFO):
    """
    Setup application-wide logging.
    
    Creates:
    - logs/app.log - Main application log (rotates at 10MB, keeps 5 backups)
    - logs/error.log - Error-only log
    - Console output with colored formatting
    """
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console Handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler - Main Log (rotating, 10MB, 5 backups)
    main_log_file = log_dir / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        main_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # File Handler - Error Log (errors only)
    error_log_file = log_dir / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Daily rotating log for tracking
    daily_log_file = log_dir / f"daily_{datetime.now():%Y%m%d}.log"
    daily_handler = logging.FileHandler(daily_log_file, encoding='utf-8')
    daily_handler.setLevel(logging.DEBUG)
    daily_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(daily_handler)
    
    # Log startup message
    root_logger.info("="*80)
    root_logger.info(f"Logging initialized - Log files in: {log_dir.absolute()}")
    root_logger.info(f"Main log: {main_log_file}")
    root_logger.info(f"Error log: {error_log_file}")
    root_logger.info(f"Daily log: {daily_log_file}")
    root_logger.info("="*80)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)
