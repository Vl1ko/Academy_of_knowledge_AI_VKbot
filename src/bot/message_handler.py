import logging
from typing import Dict, List, Any, Optional

from src.ai.gigachat_handler import GigaChatHandler
from src.database.db_handler import DatabaseHandler


class MessageHandler:
    """
    Message handler using AI for generating responses
    """
    
    def __init__(self, db: DatabaseHandler):
        """
        Initialize message handler
        
        Args:
            db: Database instance
        """
        self.logger = logging.getLogger(__name__)
        self.db = db
        self.ai_handler = GigaChatHandler()
        self.message_history: Dict[int, List[Dict[str, str]]] = {}
        self.MAX_HISTORY_LENGTH = 10
        
    def process_message(self, user_id: int, message_text: str) -> str:
        """
        Process user message
        
        Args:
            user_id: User ID
            message_text: Message text
            
        Returns:
            Response message
        """
        try:
            if user_id not in self.message_history:
                self.message_history[user_id] = []
            
            user_data = self.db.get_user_data(user_id)
            
            intent = self.ai_handler.detect_intent(message_text)
            self.logger.info(f"Определен интент: {intent} для сообщения: {message_text}")
            
            self.message_history[user_id].append({
                "role": "user",
                "text": message_text
            })
            
            if len(self.message_history[user_id]) > self.MAX_HISTORY_LENGTH:
                self.message_history[user_id] = self.message_history[user_id][-self.MAX_HISTORY_LENGTH:]
            
            response = self.ai_handler.generate_response(
                message=message_text, 
                message_history=self.message_history[user_id],
                user_data=user_data
            )
            
            self.message_history[user_id].append({
                "role": "bot",
                "text": response
            })
            
            if intent in ["registration", "consultation"]:
                self.db.update_user_intent(user_id, intent, message_text)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            return "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз." 