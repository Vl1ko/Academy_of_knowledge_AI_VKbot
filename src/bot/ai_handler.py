import logging
from typing import Dict, List, Optional
import os
from langchain.chat_models import GigaChat
from langchain.schema import HumanMessage, SystemMessage, AIMessage
import re

class GigaChatHandler:
    def __init__(self):
        """Initialize GigaChat handler"""
        self.logger = logging.getLogger(__name__)
        
        # Get GigaChat credentials from environment
        self.credentials = os.getenv("GIGACHAT_CREDENTIALS")
        if not self.credentials:
            raise ValueError("GIGACHAT_CREDENTIALS environment variable not set")
        
        # Initialize GigaChat
        try:
            self.chat = GigaChat(credentials=self.credentials, verify_ssl_certs=False)
            self.logger.info("GigaChat initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing GigaChat: {e}")
            raise
        
        # System prompt for the bot
        self.system_prompt = f"""Ты - дружелюбный и профессиональный ассистент частной школы "Академия знаний" в группе ВК. 
Твоя задача - помогать родителям получить информацию о школе и образовательных программах.

Правила общения:
1. Если это первое сообщение в диалоге, то начинай с приветствия
2. Используй дружелюбный, но профессиональный тон
3. Отвечай развернуто и информативно
4. Используй эмодзи для выделения ключевых моментов
5. В конце каждого ответа всегда задавай уточняющий вопрос для продолжения диалога, на основе контекста
6. Не пытайся использовать Markdown в ответе, используй только текст, но грамотно разделяй его на абзацы и пункты при перечислении

Структура ответа:
1. Основная информация по запросу
2. Дополнительные интересные факты или детали
3. Всегда Уточняющий вопрос для продолжения диалога

Пример хорошего ответа:
Стоимость обучения в нашей школе составляет 26100 рублей в месяц. 
В эту сумму входит:
• Обучение по основной образовательной программе
• Группы до 15 человек
• Работа с 8:00 до 18:00
• Дополнительные предметы: английский язык, шахматы, робототехника

Хотите узнать подробнее о какой-то конкретной программе или у вас есть другие вопросы? 😊"

Используй эту структуру для всех ответов, даже если вопрос кажется простым. Всегда старайся добавить что-то интересное и полезное, что может заинтересовать родителей. Обязательно задавай уточняющий вопрос для продолжения диалога, на основе контекста."""
    
    def generate_response(self, user_message: str, message_history: Optional[List[Dict]] = None) -> str:
        """
        Generate response using GigaChat
        
        Args:
            user_message: User message
            message_history: Previous messages (optional)
            
        Returns:
            Generated response
        """
        try:
            # Convert message history to LangChain format
            messages = [SystemMessage(content=self.system_prompt)]
            
            if message_history:
                for msg in message_history:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "bot":
                        messages.append(AIMessage(content=msg["content"]))
            
            # Add current user message
            messages.append(HumanMessage(content=user_message))
            
            # Generate response
            response = self.chat(messages)
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже или обратитесь к администратору."
    
    def _clean_response(self, response: str) -> str:
        """
        Clean and format AI response
        
        Args:
            response: Raw AI response
            
        Returns:
            Cleaned response
        """
        # Remove any system-like prefixes
        response = re.sub(r'^(Assistant|Bot|AI):\s*', '', response)
        
        # Remove multiple newlines
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        # Remove trailing whitespace
        response = response.strip()
        
        return response 