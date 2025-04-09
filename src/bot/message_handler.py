import logging
from typing import Tuple, Optional

from ..ai.openai_handler import OpenAIHandler
from ..ai.deepseek_handler import DeepSeekHandler
from ..database.db_handler import DatabaseHandler
from .keyboard import Keyboard

class MessageHandler:
    def __init__(self):
        self.openai = OpenAIHandler()
        self.deepseek = DeepSeekHandler()
        self.db = DatabaseHandler()
        self.keyboard = Keyboard()
        self.logger = logging.getLogger(__name__)

    def handle_message(self, message: str, user_id: int) -> Tuple[str, Optional[dict]]:
        """
        Обработка входящего сообщения и генерация ответа
        
        Args:
            message: Текст сообщения
            user_id: ID пользователя ВКонтакте
            
        Returns:
            Tuple[str, Optional[dict]]: Ответ и клавиатура (если нужна)
        """
        try:
            # Определяем тип запроса с помощью NLP
            intent = self._detect_intent(message)
            
            # Обрабатываем запрос в зависимости от его типа
            if intent == 'consultation':
                return self._handle_consultation(message, user_id)
            elif intent == 'registration':
                return self._handle_registration(message, user_id)
            elif intent == 'information':
                return self._handle_information(message)
            else:
                return self._handle_unknown(message)
                
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения: {e}")
            return "Извините, произошла ошибка. Пожалуйста, попробуйте позже.", None

    def _detect_intent(self, message: str) -> str:
        """Определение типа запроса с помощью NLP"""
        # Используем OpenAI для определения намерения
        intent = self.openai.detect_intent(message)
        return intent

    def _handle_consultation(self, message: str, user_id: int) -> Tuple[str, Optional[dict]]:
        """Обработка запроса на консультацию"""
        # Проверяем, есть ли пользователь в базе
        user_data = self.db.get_user(user_id)
        
        if not user_data:
            # Если пользователя нет в базе, запрашиваем контактные данные
            return "Для записи на консультацию, пожалуйста, укажите ваше имя и телефон.", self.keyboard.get_contact_keyboard()
        
        # Генерируем ответ с помощью AI
        response = self.openai.generate_response(message, context=user_data)
        return response, self.keyboard.get_main_keyboard()

    def _handle_registration(self, message: str, user_id: int) -> Tuple[str, Optional[dict]]:
        """Обработка запроса на регистрацию на мероприятие"""
        # Проверяем наличие свободных мест
        if self.db.check_event_availability():
            # Сохраняем запись
            self.db.register_for_event(user_id)
            return "Вы успешно записаны на мероприятие! Мы отправим вам подтверждение.", self.keyboard.get_main_keyboard()
        else:
            return "К сожалению, на данное мероприятие нет свободных мест.", self.keyboard.get_main_keyboard()

    def _handle_information(self, message: str) -> Tuple[str, Optional[dict]]:
        """Обработка информационного запроса"""
        # Генерируем ответ с помощью AI
        response = self.openai.generate_response(message)
        return response, self.keyboard.get_info_keyboard()

    def _handle_unknown(self, message: str) -> Tuple[str, Optional[dict]]:
        """Обработка неизвестного запроса"""
        return "Извините, я не совсем понял ваш запрос. Можете переформулировать?", self.keyboard.get_main_keyboard() 