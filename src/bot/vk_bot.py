import logging
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

from config.config import VK_TOKEN, BOT_SETTINGS
from .message_handler import MessageHandler
from .keyboard import Keyboard

class VkBot:
    def __init__(self):
        self.vk_session = VkApi(token=VK_TOKEN)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, BOT_SETTINGS['group_ids']['school'])
        self.message_handler = MessageHandler()
        self.keyboard = Keyboard()
        self.logger = logging.getLogger(__name__)

    def send_message(self, user_id: int, message: str, keyboard=None):
        """Отправка сообщения пользователю"""
        try:
            self.vk.messages.send(
                user_id=user_id,
                message=message,
                random_id=get_random_id(),
                keyboard=keyboard
            )
        except Exception as e:
            self.logger.error(f"Ошибка при отправке сообщения: {e}")

    def process_event(self, event):
        """Обработка события от ВКонтакте"""
        if event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
            self.logger.info(f"Получено сообщение от пользователя {event.user_id}: {event.text}")
            
            # Получаем ответ от обработчика сообщений
            response, keyboard = self.message_handler.handle_message(event.text, event.user_id)
            
            # Отправляем ответ пользователю
            self.send_message(event.user_id, response, keyboard)

    def run(self):
        """Запуск бота"""
        self.logger.info("Бот запущен")
        try:
            for event in self.longpoll.listen():
                self.process_event(event)
        except Exception as e:
            self.logger.error(f"Ошибка в работе бота: {e}")
            raise 