import os
from utils.alert_processor import AlertProcessor
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('alert_processor')

def main():
    # Get database path from environment or use default
    db_path = os.getenv('DUCKDB_PATH', 'ekko.db')
    
    # Initialize alert processor
    processor = AlertProcessor()
    
    logger.info("Starting alert processor service...")
    try:
        # Run processor with 1 minute interval
        processor.run(interval=1)
    except KeyboardInterrupt:
        logger.info("Alert processor service stopped.")
    except Exception as e:
        logger.error(f"Error in alert processor service: {str(e)}")

if __name__ == "__main__":
    main()
