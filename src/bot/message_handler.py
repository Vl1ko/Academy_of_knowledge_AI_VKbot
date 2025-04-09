import logging
from typing import Tuple, Optional

from ..ai.openai_handler import OpenAIHandler
from ..ai.deepseek_handler import DeepSeekHandler
from ..database.db_handler import DatabaseHandler
from ..database.chat_history import ChatHistoryManager
from .keyboard import Keyboard

class MessageHandler:
    def __init__(self):
        self.openai = OpenAIHandler()
        self.deepseek = DeepSeekHandler()
        self.db = DatabaseHandler()
        self.chat_history = ChatHistoryManager()
        self.keyboard = Keyboard()
        self.logger = logging.getLogger(__name__)

    def handle_message(self, message: str, user_id: int) -> Tuple[str, Optional[dict]]:
        """
        Process incoming message and generate response
        
        Args:
            message: User message text
            user_id: VK user ID
            
        Returns:
            Tuple[str, Optional[dict]]: Response and keyboard (if needed)
        """
        try:
            # Save user message to history
            self.chat_history.add_message(user_id, message, is_bot=False)
            
            # Get conversation context
            context = self.chat_history.get_conversation_context(user_id)
            
            # Determine request type with NLP
            intent = self._detect_intent(message, context)
            
            # Save intent to history
            self.chat_history.add_message(user_id, message, is_bot=False, intent=intent)
            
            # Process request based on its type
            if intent == 'consultation':
                response, keyboard = self._handle_consultation(message, user_id, context)
            elif intent == 'registration':
                response, keyboard = self._handle_registration(message, user_id, context)
            elif intent == 'information':
                response, keyboard = self._handle_information(message, context)
            else:
                response, keyboard = self._handle_unknown(message, context)
            
            # Save bot response to history
            self.chat_history.add_message(user_id, response, is_bot=True)
            
            return response, keyboard
                
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            error_message = "Sorry, an error occurred. Please try again later."
            self.chat_history.add_message(user_id, error_message, is_bot=True)
            return error_message, None

    def _detect_intent(self, message: str, context: str) -> str:
        """Determine request type with NLP"""
        # Use OpenAI to determine intent with context
        intent = self.openai.detect_intent(message, context)
        return intent

    def _handle_consultation(self, message: str, user_id: int, context: str) -> Tuple[str, Optional[dict]]:
        """Handle consultation request"""
        # Check if user exists in database
        user_data = self.db.get_user(user_id)
        
        if not user_data:
            # If user is not in database, request contact information
            return "To schedule a consultation, please provide your name and phone number.", self.keyboard.get_contact_keyboard()
        
        # Generate response with AI using context
        response = self.openai.generate_response(message, context=context, user_data=user_data)
        return response, self.keyboard.get_main_keyboard()

    def _handle_registration(self, message: str, user_id: int, context: str) -> Tuple[str, Optional[dict]]:
        """Handle event registration request"""
        # Check for available spots
        if self.db.check_event_availability():
            # Save registration
            self.db.register_for_event(user_id)
            return "You have been successfully registered for the event! We will send you a confirmation.", self.keyboard.get_main_keyboard()
        else:
            return "Unfortunately, there are no available spots for this event.", self.keyboard.get_main_keyboard()

    def _handle_information(self, message: str, context: str) -> Tuple[str, Optional[dict]]:
        """Handle information request"""
        # Generate response with AI using context
        response = self.openai.generate_response(message, context=context)
        return response, self.keyboard.get_info_keyboard()

    def _handle_unknown(self, message: str, context: str) -> Tuple[str, Optional[dict]]:
        """Handle unknown request"""
        return "I'm sorry, I didn't quite understand your request. Could you rephrase it?", self.keyboard.get_main_keyboard() 