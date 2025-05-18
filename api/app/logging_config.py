"""
Logging configuration for the Ekko API.
Provides standardized logging setup across different modules.
"""

import logging
import os
import sys
from datetime import datetime

# Define log levels based on environment
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = logging.DEBUG if DEBUG_MODE else logging.INFO

# Configure root logger
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name):
    """Get a configured logger for the given name."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Add a file handler specifically for alert logs if needed
    if name.startswith("ekko.alert") and not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        try:
            # Create logs directory if it doesn't exist
            os.makedirs("logs", exist_ok=True)
            
            # Add a file handler for alerts
            date_str = datetime.now().strftime("%Y-%m-%d")
            file_handler = logging.FileHandler(f"logs/alerts_{date_str}.log")
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(file_handler)
        except Exception as e:
            # Don't fail if we can't set up file logging, just log to console
            logging.warning(f"Could not set up file logging for alerts: {e}")
    
    return logger

# Pre-configured loggers for different components
alert_logger = get_logger("ekko.alert")
job_spec_logger = get_logger("ekko.alert.jobspec")
api_logger = get_logger("ekko.api")
