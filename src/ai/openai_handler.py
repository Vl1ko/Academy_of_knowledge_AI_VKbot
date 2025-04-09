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

    def detect_intent(self, message: str) -> str:
        """
        Определение намерения пользователя с помощью OpenAI
        
        Args:
            message: Текст сообщения пользователя
            
        Returns:
            str: Тип намерения (consultation, registration, information, unknown)
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты - система определения намерений пользователя. "
                                                 "Определи тип запроса: consultation (запрос на консультацию), "
                                                 "registration (запись на мероприятие), "
                                                 "information (информационный запрос), "
                                                 "unknown (неизвестный запрос)."},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            intent = response.choices[0].message.content.strip().lower()
            return intent
            
        except Exception as e:
            self.logger.error(f"Ошибка при определении намерения: {e}")
            return "unknown"

    def generate_response(self, message: str, context: Optional[Dict] = None) -> str:
        """
        Генерация ответа с помощью OpenAI
        
        Args:
            message: Текст сообщения пользователя
            context: Контекст пользователя (опционально)
            
        Returns:
            str: Сгенерированный ответ
        """
        try:
            system_prompt = """Ты - помощник частной школы "Академия знаний" и частного сада "Академик".
            Твоя задача - помогать родителям получать информацию о школе и садике, записываться на консультации и мероприятия.
            Всегда будь вежлив, профессионально отвечай на вопросы.
            В конце сообщения задавай уточняющий вопрос или предлагай следующий шаг."""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if context:
                context_prompt = f"Информация о пользователе: {context}"
                messages.append({"role": "system", "content": context_prompt})
            
            messages.append({"role": "user", "content": message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Ошибка при генерации ответа: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже." 