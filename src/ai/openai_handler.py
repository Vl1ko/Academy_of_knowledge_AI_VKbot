import logging
from typing import Dict, Optional
import openai
from config.config import OPENAI_API_KEY, AI_SETTINGS

class OpenAIHandler:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.logger = logging.getLogger(__name__)
        self.model = AI_SETTINGS['openai_model']
        self.temperature = AI_SETTINGS['temperature']
        self.max_tokens = AI_SETTINGS['max_tokens']

    def detect_intent(self, message: str, context: str = "") -> str:
        """
        Determine user intent with OpenAI
        
        Args:
            message: User message text
            context: Conversation context
            
        Returns:
            str: Intent type (consultation, registration, information, unknown)
        """
        try:
            system_prompt = """You are a system for determining user intentions. 
            Determine the type of request: consultation (request for consultation), 
            registration (event registration), information (information request), 
            unknown (unknown request)."""
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            if context:
                messages.append({"role": "system", "content": f"Conversation context:\n{context}"})
            
            messages.append({"role": "user", "content": message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=50
            )
            
            intent = response.choices[0].message.content.strip().lower()
            return intent
            
        except Exception as e:
            self.logger.error(f"Error detecting intent: {e}")
            return "unknown"

    def generate_response(self, message: str, context: str = "", user_data: Optional[Dict] = None) -> str:
        """
        Generate response with OpenAI
        
        Args:
            message: User message text
            context: Conversation context
            user_data: User data from database
            
        Returns:
            str: Generated response
        """
        try:
            system_prompt = """You are an assistant for the private school "Academy of Knowledge" and private kindergarten "Academic".
            Your task is to help parents get information about the school and kindergarten, schedule consultations and events.
            Always be polite, professionally answer questions.
            At the end of the message, ask a clarifying question or suggest the next step."""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if context:
                messages.append({"role": "system", "content": f"Conversation context:\n{context}"})
            
            if user_data:
                user_info = f"User information: {user_data}"
                messages.append({"role": "system", "content": user_info})
            
            messages.append({"role": "user", "content": message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return "Sorry, an error occurred while processing your request. Please try again later." 