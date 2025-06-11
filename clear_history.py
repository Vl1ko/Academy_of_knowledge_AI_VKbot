import logging
from src.database.db_handler import DatabaseHandler, ChatHistory

def clear_chat_history():
    """Clear all chat history from the database"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        db = DatabaseHandler()
        # Delete all records from chat_history table
        db.session.query(ChatHistory).delete()
        db.session.commit()
        logger.info("Successfully cleared all chat history")
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        db.session.rollback()

if __name__ == "__main__":
    clear_chat_history() 