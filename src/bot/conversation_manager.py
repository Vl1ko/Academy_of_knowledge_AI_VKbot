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
    
    def __init__(self, timeout_minutes: int = 30):
        """
        Initialize conversation manager
        
        Args:
            timeout_minutes: Conversation timeout in minutes
        """
        self.logger = logging.getLogger(__name__)
        self.states: Dict[int, ConversationState] = {}
        self.timeout_minutes = timeout_minutes
    
    def get_state(self, user_id: int) -> ConversationState:
        """
        Get user conversation state
        
        Args:
            user_id: User ID
            
        Returns:
            Conversation state
        """
        # Clean expired states
        self._clean_expired_states()
        
        if user_id not in self.states:
            self.states[user_id] = ConversationState(user_id)
        
        return self.states[user_id]
    
    def get_conversation_state(self, user_id: int) -> Dict[str, Any]:
        """
        Get user conversation state as a dictionary
        
        Args:
            user_id: User ID
            
        Returns:
            Conversation state as a dictionary
        """
        state = self.get_state(user_id)
        return {
            "state": state.current_stage,
            "data": state.data
        }
    
    def get_stage(self, user_id: int) -> str:
        """
        Get user conversation stage
        
        Args:
            user_id: User ID
            
        Returns:
            Current conversation stage
        """
        return self.get_state(user_id).current_stage
    
    def update_stage(self, user_id: int, stage: str) -> None:
        """
        Update user conversation stage
        
        Args:
            user_id: User ID
            stage: New stage
        """
        self.get_state(user_id).update_stage(stage)
    
    def add_data(self, user_id: int, key: str, value: Any) -> None:
        """
        Add data to user conversation
        
        Args:
            user_id: User ID
            key: Data key
            value: Data value
        """
        self.get_state(user_id).add_data(key, value)
    
    def get_data(self, user_id: int, key: str) -> Optional[Any]:
        """
        Get data from user conversation
        
        Args:
            user_id: User ID
            key: Data key
            
        Returns:
            Data value or None if not found
        """
        state = self.get_state(user_id)
        return state.data.get(key)
    
    def reset_state(self, user_id: int) -> None:
        """
        Reset user conversation state
        
        Args:
            user_id: User ID
        """
        if user_id in self.states:
            self.states[user_id].reset()
    
    def add_message(self, user_id: int, role: str, text: str) -> None:
        """
        Add message to conversation history
        
        Args:
            user_id: User ID
            role: Message role ('user' or 'bot')
            text: Message text
        """
        self.get_state(user_id).add_message(role, text)
    
    def get_history(self, user_id: int, max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Get conversation history
        
        Args:
            user_id: User ID
            max_items: Maximum number of history items to return
            
        Returns:
            List of history items
        """
        state = self.get_state(user_id)
        return state.history[-max_items:] if state.history else []
    
    def get_messages(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent messages from conversation history
        
        Args:
            user_id: User ID
            limit: Maximum number of messages to return
            
        Returns:
            List of messages
        """
        state = self.get_state(user_id)
        return state.history[-limit:] if state.history else []
    
    def get_message_history(self, user_id: int, limit: int = 5) -> List[Dict[str, str]]:
        """
        Get message history in format suitable for AI processing
        
        Args:
            user_id: User ID
            limit: Maximum number of messages to return
            
        Returns:
            List of messages with role and text
        """
        messages = self.get_messages(user_id, limit)
        return [{"role": msg["role"], "text": msg["text"]} for msg in messages] if messages else []
    
    def _clean_expired_states(self) -> None:
        """Clean expired conversation states"""
        expired_users = []
        
        for user_id, state in self.states.items():
            if state.is_expired(self.timeout_minutes):
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.states[user_id] 