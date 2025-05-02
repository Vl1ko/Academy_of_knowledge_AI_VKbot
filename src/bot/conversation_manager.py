import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class ConversationState:
    """User conversation state"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.current_stage = "initial"
        self.data = {}
        self.last_interaction = datetime.now()
        self.history = []
    
    def update_stage(self, stage: str) -> None:
        """Update conversation stage"""
        self.current_stage = stage
        self.last_interaction = datetime.now()
    
    def add_data(self, key: str, value: Any) -> None:
        """Add data to conversation"""
        self.data[key] = value
        self.last_interaction = datetime.now()
    
    def reset(self) -> None:
        """Reset conversation state"""
        self.current_stage = "initial"
        self.data = {}
        self.last_interaction = datetime.now()
    
    def add_message(self, role: str, text: str) -> None:
        """Add message to conversation history"""
        self.history.append({
            "role": role,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only the last 20 messages
        if len(self.history) > 20:
            self.history = self.history[-20:]
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if conversation state is expired"""
        return datetime.now() - self.last_interaction > timedelta(minutes=timeout_minutes)


class ConversationManager:
    """Manager for handling user conversation states"""
    
    def __init__(self):
        """Initialize conversation manager"""
        self.logger = logging.getLogger(__name__)
        self.conversations: Dict[int, Dict] = {}
        self.ai_disabled_users: Dict[int, bool] = {}
        self.message_history: Dict[int, List[Dict]] = {}
        self.last_activity: Dict[int, datetime] = {}
        
    def get_conversation_state(self, user_id: int) -> Dict:
        """Get conversation state for user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = {}
        return self.conversations[user_id]
    
    def update_state(self, user_id: int, state: Dict) -> None:
        """Update conversation state for user"""
        self.conversations[user_id] = state
        self.last_activity[user_id] = datetime.utcnow()
    
    def reset_state(self, user_id: int) -> None:
        """Reset conversation state for user"""
        self.conversations[user_id] = {}
        self.last_activity[user_id] = datetime.utcnow()
    
    def disable_ai(self, user_id: int) -> None:
        """Disable AI responses for user"""
        self.ai_disabled_users[user_id] = True
        self.last_activity[user_id] = datetime.utcnow()
    
    def enable_ai(self, user_id: int) -> None:
        """Enable AI responses for user"""
        if user_id in self.ai_disabled_users:
            del self.ai_disabled_users[user_id]
        self.last_activity[user_id] = datetime.utcnow()
    
    def is_ai_disabled(self, user_id: int) -> bool:
        """Check if AI is disabled for user"""
        return self.ai_disabled_users.get(user_id, False)
    
    def add_message(self, user_id: int, role: str, message: str) -> None:
        """Add message to conversation history"""
        self.logger.info(f"Adding message to history - User: {user_id}, Role: {role}, Message: {message}")
        
        if user_id not in self.message_history:
            self.message_history[user_id] = []
        
        self.message_history[user_id].append({
            'role': role,
            'content': message,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 10 messages for more relevant context
        if len(self.message_history[user_id]) > 10:
            self.message_history[user_id] = self.message_history[user_id][-10:]
        
        self.logger.info(f"Current message history for user {user_id}: {self.message_history[user_id]}")
        self.last_activity[user_id] = datetime.utcnow()
    
    def get_message_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get conversation history for user"""
        if user_id not in self.message_history:
            self.logger.info(f"No message history found for user {user_id}")
            return []
        
        history = self.message_history[user_id]
        result = history[-limit:] if limit else history
        self.logger.info(f"Retrieved message history for user {user_id}: {result}")
        return result
    
    def clear_message_history(self, user_id: int) -> None:
        """Clear conversation history for user"""
        if user_id in self.message_history:
            del self.message_history[user_id]
        self.last_activity[user_id] = datetime.utcnow()
    
    def cleanup_inactive_conversations(self, timeout_minutes: int = 30) -> None:
        """Remove data for inactive users"""
        current_time = datetime.utcnow()
        timeout = timedelta(minutes=timeout_minutes)
        
        inactive_users = [
            user_id for user_id, last_active in self.last_activity.items()
            if current_time - last_active > timeout
        ]
        
        for user_id in inactive_users:
            if user_id in self.conversations:
                del self.conversations[user_id]
            if user_id in self.message_history:
                del self.message_history[user_id]
            if user_id in self.ai_disabled_users:
                del self.ai_disabled_users[user_id]
            del self.last_activity[user_id]
            
        if inactive_users:
            self.logger.info(f"Cleaned up data for {len(inactive_users)} inactive users") 