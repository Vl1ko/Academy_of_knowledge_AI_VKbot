import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from .db_handler import Base, DatabaseHandler

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    message = Column(Text)
    is_bot = Column(Integer, default=0)  # 0 - user message, 1 - bot message
    timestamp = Column(DateTime, default=datetime.utcnow)
    intent = Column(String, nullable=True)  # detected intent of the message
    
    user = relationship("User", back_populates="chat_history")

class ChatHistoryManager:
    def __init__(self):
        self.db = DatabaseHandler()
        self.logger = logging.getLogger(__name__)
    
    def add_message(self, user_id: int, message: str, is_bot: bool = False, intent: Optional[str] = None) -> bool:
        """
        Add a message to chat history
        
        Args:
            user_id: User ID
            message: Message text
            is_bot: Whether the message is from bot
            intent: Detected intent of the message
            
        Returns:
            bool: Operation success
        """
        try:
            chat_entry = ChatHistory(
                user_id=user_id,
                message=message,
                is_bot=1 if is_bot else 0,
                intent=intent
            )
            self.db.session.add(chat_entry)
            self.db.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding message to chat history: {e}")
            self.db.session.rollback()
            return False
    
    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Get chat history for a user
        
        Args:
            user_id: User ID
            limit: Maximum number of messages to return
            
        Returns:
            List[Dict]: List of messages
        """
        try:
            history = self.db.session.query(ChatHistory).filter(
                ChatHistory.user_id == user_id
            ).order_by(ChatHistory.timestamp.desc()).limit(limit).all()
            
            return [{
                'message': entry.message,
                'is_bot': bool(entry.is_bot),
                'timestamp': entry.timestamp,
                'intent': entry.intent
            } for entry in history]
        except Exception as e:
            self.logger.error(f"Error getting user chat history: {e}")
            return []
    
    def get_conversation_context(self, user_id: int, limit: int = 5) -> str:
        """
        Get conversation context for AI
        
        Args:
            user_id: User ID
            limit: Maximum number of messages to include
            
        Returns:
            str: Formatted conversation context
        """
        try:
            history = self.db.session.query(ChatHistory).filter(
                ChatHistory.user_id == user_id
            ).order_by(ChatHistory.timestamp.desc()).limit(limit).all()
            
            # Reverse to get chronological order
            history.reverse()
            
            context = "Previous conversation:\n"
            for entry in history:
                sender = "Bot" if entry.is_bot else "User"
                context += f"{sender}: {entry.message}\n"
            
            return context
        except Exception as e:
            self.logger.error(f"Error getting conversation context: {e}")
            return ""
    
    def clear_history(self, user_id: int) -> bool:
        """
        Clear chat history for a user
        
        Args:
            user_id: User ID
            
        Returns:
            bool: Operation success
        """
        try:
            self.db.session.query(ChatHistory).filter(
                ChatHistory.user_id == user_id
            ).delete()
            self.db.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error clearing chat history: {e}")
            self.db.session.rollback()
            return False 