import logging
import logging.config
import os
import sys
from dotenv import load_dotenv

# Add current directory to import paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.bot.vk_bot import VkBot
from src.database.db_handler import DatabaseHandler
from config.config import LOGGING

def setup_logging():
    """Setup logging configuration"""
    os.makedirs('logs', exist_ok=True)
    logging.config.dictConfig(LOGGING)

def main():
    """Main function to start the bot"""
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        db = DatabaseHandler()
        bot = VkBot(db)
        logger.info("Bot started and ready")
        bot.start()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    main() 