import logging
from typing import Dict, Optional
import requests
from config.config import DEEPSEEK_API_KEY, AI_SETTINGS

class DeepSeekHandler:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.model = AI_SETTINGS['deepseek_model']
        self.temperature = AI_SETTINGS['temperature']
        self.max_tokens = AI_SETTINGS['max_tokens']
        self.logger = logging.getLogger(__name__)
        self.api_url = "https://api.deepseek.com/v1/chat/completions"

    def generate_response(self, message: str, context: Optional[Dict] = None) -> str:
        """
        Генерация ответа с помощью DeepSeek
        
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
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            
            return response.json()["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            self.logger.error(f"Ошибка при генерации ответа с DeepSeek: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."

    def analyze_sentiment(self, message: str) -> str:
        """
        Анализ настроения пользователя
        
        Args:
            message: Текст сообщения пользователя
            
        Returns:
            str: Настроение (positive, negative, neutral)
        """
        try:
            system_prompt = "Проанализируй настроение пользователя и верни одно из значений: positive, negative, neutral"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 50
            }
            
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            
            return response.json()["choices"][0]["message"]["content"].strip().lower()
            
        except Exception as e:
            self.logger.error(f"Ошибка при анализе настроения: {e}")
            return "neutral" 