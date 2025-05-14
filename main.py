import logging
import logging.config
import os
import sys
from dotenv import load_dotenv

# Add current directory to import paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.bot.vk_bot import VkBot
from src.database.db_handler import DatabaseHandler
from src.ai.rag_singleton import RAGSingleton
from config.config import LOGGING

def setup_logging():
    """Setup logging configuration"""
    os.makedirs('logs', exist_ok=True)
    logging.config.dictConfig(LOGGING)

def initialize_rag():
    """Initialize RAG system"""
    logger = logging.getLogger(__name__)
    logger.info("Initializing RAG system...")
    try:
        rag = RAGSingleton()
        rag.initialize()
        logger.info("RAG system initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing RAG system: {e}")

def main():
    """Main function"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting bot...")
    
    # Load environment variables
    load_dotenv()
    
    # Initialize RAG system
    initialize_rag()
    
    # Initialize database
    db = DatabaseHandler()
    
    # Create and start bot
    bot = VkBot(db)
    bot.start()

if __name__ == "__main__":
    main() 