import logging
import traceback
from typing import Optional

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from src.bot.message_handler import MessageHandler
from config.config import VK_TOKEN, BOT_SETTINGS
from src.database.db_handler import DatabaseHandler


class VkBot:
    """
    VK API bot class for handling user messages
    """
    
    def __init__(self, db: DatabaseHandler):
        """
        Initialize VK bot
        
        Args:
            db: Database instance
        """
        self.logger = logging.getLogger(__name__)
        self.db = db
        self.group_id = BOT_SETTINGS['group_ids']['school']
        
        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, self.group_id)
        
        # Инициализация обработчика сообщений
        self.message_handler = MessageHandler(db)
    
    def start(self) -> None:
        """Start the bot and process events"""
        self.logger.info("Запуск VK бота")
        
        try:
            for event in self.longpoll.listen():
                try:
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self._process_new_message(event)
                except Exception as e:
                    self.logger.error(f"Error processing event: {e}")
                    self.logger.debug(traceback.format_exc())
        except Exception as e:
            self.logger.critical(f"Critical bot error: {e}")
            self.logger.debug(traceback.format_exc())
    
    def _process_new_message(self, event) -> None:
        """
        Process new message
        
        Args:
            event: New message event
        """
        message_text = event.obj.message['text']
        peer_id = event.obj.message['peer_id']
        user_id = event.obj.message['from_id']
        
        self.logger.info(f"Получено сообщение от пользователя {user_id}: {message_text}")
        
        # Проверяем, не исходит ли сообщение от группы
        if user_id < 0:
            self.logger.debug(f"Сообщение от группы {user_id}, игнорируем")
            return
        
        # Обрабатываем сообщение
        response = self.message_handler.process_message(user_id, message_text)
        
        # Отправляем ответ пользователю
        self._send_message(peer_id, response)
    
    def _send_message(self, peer_id: int, message: str, keyboard: Optional[str] = None) -> None:
        """
        Send message to user
        
        Args:
            peer_id: Recipient ID
            message: Message text
            keyboard: JSON keyboard string (optional)
        """
        params = {
            'peer_id': peer_id,
            'message': message,
            'random_id': 0
        }
        
        if keyboard:
            params['keyboard'] = keyboard
        
        try:
            self.vk.messages.send(**params)
            self.logger.info(f"Отправлено сообщение пользователю {peer_id}")
        except vk_api.VkApiError as e:
            self.logger.error(f"Error sending message: {e}")

    def _handle_message(self, event):
        """
        Обработка входящего сообщения
        
        Args:
            event: Событие сообщения VK
        """
        try:
            # Получаем идентификатор пользователя из event.object
            # Исправлено: event.object содержит словарь message, в котором находится from_id
            user_id = event.object.message['from_id']
            
            # Получаем текст сообщения
            message_text = event.object.message['text']
            
            self.logger.info(f"Получено сообщение от пользователя {user_id}: {message_text}")
            
            # Обрабатываем сообщение
            response = self.message_handler.process_message(user_id, message_text)
            
            # Отправляем ответ
            self.vk_session.method('messages.send', {
                'user_id': user_id,
                'message': response,
                'random_id': self._get_random_id()
            })
            
            self.logger.info(f"Отправлен ответ пользователю {user_id}: {response}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения: {e}") 