import logging
import os
from typing import List, Dict, Any, Optional

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config.config import GIGACHAT_API_KEY, AI_SETTINGS


class GigaChatHandler:
    """
    Class for working with GigaChat API
    """
    
    def __init__(self):
        """Initialize GigaChat handler"""
        self.logger = logging.getLogger(__name__)
        
        self.client = GigaChat(
            credentials=GIGACHAT_API_KEY,
            verify_ssl_certs=False
        )
        
        self.system_prompt = """Ты - полезный ассистент образовательного проекта "Академия Знаний".
Твоя задача - помогать пользователям узнавать о курсах, отвечать на вопросы и регистрировать на занятия.
Общайся вежливо, дружелюбно и информативно. Используй официально-деловой стиль, но будь достаточно дружелюбным.
Ты должен называть себя "Ассистент Академии Знаний".
"""
    
    def detect_intent(self, message: str) -> str:
        """
        Detect user's intent from message
        
        Args:
            message: User's message
            
        Returns:
            String with detected intent
        """
        prompt = f"""Определи интент пользователя из следующего сообщения:
"{message}"

Возможные интенты:
- registration: Пользователь хочет записаться на курс или занятие
- consultation: Пользователь хочет получить консультацию по курсам
- question: Пользователь задает общий вопрос о курсах
- greeting: Пользователь здоровается или начинает разговор
- other: Другой интент

Верни только название интента без дополнительного текста.
"""
        
        try:
            chat_request = Chat(
                messages=[
                    Messages(role=MessagesRole.SYSTEM, content="Ты должен определить интент пользователя"),
                    Messages(role=MessagesRole.USER, content=prompt)
                ],
                temperature=0.1
            )
            
            response = self.client.chat(chat_request)
            
            intent = response.choices[0].message.content.strip().lower()
            
            for valid_intent in ["registration", "consultation", "question", "greeting", "other"]:
                if valid_intent in intent:
                    return valid_intent
            
            return "other"
        except Exception as e:
            self.logger.error(f"Error detecting intent: {e}")
            return "other"
    
    def generate_response(self, message: str, message_history: List[Dict[str, str]], user_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate response to user message
        
        Args:
            message: Current user message
            message_history: Message history
            user_data: User data (optional)
            
        Returns:
            Response message
        """
        try:
            context = ""
            if user_data:
                context = f"""
Данные о пользователе:
- Имя: {user_data.get('name', 'неизвестно')}
- Email: {user_data.get('email', 'неизвестно')}
- Телефон: {user_data.get('phone', 'неизвестно')}
- Интересующие курсы: {user_data.get('interests', 'неизвестно')}
"""
            
            messages = [
                Messages(role=MessagesRole.SYSTEM, content=self.system_prompt + context)
            ]
            
            for msg in message_history:
                role = MessagesRole.USER if msg["role"] == "user" else MessagesRole.ASSISTANT
                messages.append(Messages(role=role, content=msg["text"]))
            
            if not message_history or message_history[-1]["role"] != "user" or message_history[-1]["text"] != message:
                messages.append(Messages(role=MessagesRole.USER, content=message))
            
            chat_request = Chat(
                messages=messages,
                temperature=0.7
            )
            
            response = self.client.chat(chat_request)
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз позже." 