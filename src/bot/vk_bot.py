import logging
import traceback
import json
from typing import Optional, Dict, Any

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from src.bot.message_handler import MessageHandler
from src.bot.keyboard_generator import KeyboardGenerator
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
        self.school_group_id = BOT_SETTINGS['group_ids']['school']
        self.kindergarten_group_id = BOT_SETTINGS['group_ids']['kindergarten']
        
        # Инициализация VK API для школы
        self.vk_session_school = vk_api.VkApi(token=VK_TOKEN)
        self.vk_school = self.vk_session_school.get_api()
        self.longpoll_school = VkBotLongPoll(self.vk_session_school, self.school_group_id)
        
        # Инициализация VK API для детского сада (если ID отличается)
        if self.school_group_id != self.kindergarten_group_id:
            self.vk_session_kindergarten = vk_api.VkApi(token=VK_TOKEN)
            self.vk_kindergarten = self.vk_session_kindergarten.get_api()
            self.longpoll_kindergarten = VkBotLongPoll(self.vk_session_kindergarten, self.kindergarten_group_id)
        else:
            self.vk_session_kindergarten = self.vk_session_school
            self.vk_kindergarten = self.vk_school
            self.longpoll_kindergarten = self.longpoll_school
        
        # Инициализация обработчика сообщений
        self.message_handler = MessageHandler(db)
        self.keyboard_generator = KeyboardGenerator()
        
        # Список администраторов
        self.admin_ids = BOT_SETTINGS['admin_ids']
    
    def start(self) -> None:
        """Start the bot and process events"""
        self.logger.info("Запуск VK бота для группы школы")
        
        try:
            # Start handling events for school group
            self._start_handling_events()
        except Exception as e:
            self.logger.critical(f"Critical bot error: {e}")
            self.logger.debug(traceback.format_exc())
    
    def _start_handling_events(self) -> None:
        """Handle events from both school and kindergarten groups"""
        import threading
        
        # Start handling school group events in a separate thread
        school_thread = threading.Thread(target=self._handle_group_events, args=(self.longpoll_school, self.vk_school, "school"))
        school_thread.daemon = True
        school_thread.start()
        
        # If kindergarten group ID is different, start handling its events in a separate thread
        if self.school_group_id != self.kindergarten_group_id:
            kindergarten_thread = threading.Thread(target=self._handle_group_events, args=(self.longpoll_kindergarten, self.vk_kindergarten, "kindergarten"))
            kindergarten_thread.daemon = True
            kindergarten_thread.start()
        
        # Ждем завершения потоков
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Bot shutdown requested")
            return
    
    def _handle_group_events(self, longpoll, vk, group_type: str) -> None:
        """
        Handle events for a specific group
        
        Args:
            longpoll: VkBotLongPoll instance
            vk: VK API instance
            group_type: Group type ("school" or "kindergarten")
        """
        self.logger.info(f"Started handling events for {group_type} group")
        
        try:
            for event in longpoll.listen():
                try:
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self._process_new_message(event, vk, group_type)
                except Exception as e:
                    self.logger.error(f"Error processing event in {group_type} group: {e}")
                    self.logger.debug(traceback.format_exc())
        except Exception as e:
            self.logger.critical(f"Critical error in {group_type} group event handling: {e}")
            self.logger.debug(traceback.format_exc())
    
    def _process_new_message(self, event, vk, group_type: str) -> None:
        """
        Process new message
        
        Args:
            event: New message event
            vk: VK API instance
            group_type: Group type ("school" or "kindergarten")
        """
        message = event.obj.message
        message_text = message['text']
        peer_id = message['peer_id']
        user_id = message['from_id']
        
        # Get payload if any
        payload = None
        if 'payload' in message:
            payload = message['payload']
        
        # Детальное логирование входящего сообщения
        self.logger.info(f"Входящее сообщение от ID {user_id} (peer_id: {peer_id}): '{message_text}'")
        if payload:
            self.logger.info(f"Payload сообщения: {payload}")
        
        # Игнорируем сообщения от групп и сообществ
        if user_id < 0:
            self.logger.info(f"Игнорирование сообщения от группы/сообщества ID {user_id}")
            return
        
        # Проверяем на команды администратора
        if user_id in self.admin_ids and message_text.startswith('/'):
            self.logger.info(f"Получена команда администратора: '{message_text}'")
            self._handle_admin_command(user_id, message_text, peer_id, vk)
            return
        
        try:
            # Обрабатываем сообщение
            self.logger.debug(f"Передача сообщения в MessageHandler для пользователя {user_id}")
            response = self.message_handler.process_message(user_id, message_text, payload)
            
            # Получаем ответ
            response_text = response.get('text', 'Извините, произошла ошибка при обработке вашего сообщения.')
            keyboard = response.get('keyboard')
            
            # Обрезаем длинный ответ для лога
            log_response = response_text[:100] + "..." if len(response_text) > 100 else response_text
            self.logger.info(f"Исходящее сообщение к ID {user_id}: '{log_response}'")
            
            # Проверяем, чтобы не отправлять пустой ответ
            if not response_text:
                response_text = "Извините, не могу сформировать ответ. Пожалуйста, попробуйте еще раз."
            
            # Отправляем ответ
            self._send_message(peer_id, response_text, vk, keyboard)
            
        except Exception as e:
            error_msg = f"Ошибка при обработке сообщения от {user_id}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self._send_message(peer_id, "Извините, произошла ошибка при обработке вашего запроса.", vk)
    
    def _send_message(self, peer_id: int, message: str, vk=None, keyboard: Optional[str] = None) -> None:
        """
        Send message to user
        
        Args:
            peer_id: Recipient ID
            message: Message text
            vk: VK API instance
            keyboard: JSON keyboard string (optional)
        """
        if vk is None:
            self.logger.error(f"Ошибка при отправке сообщения: не указан API ВКонтакте")
            return
            
        # Предварительный просмотр сообщения для логирования (ограничиваем длину)
        message_preview = message if len(message) <= 100 else message[:97] + "..."
        self.logger.info(f"Исходящее сообщение к ID {peer_id}: '{message_preview}'")
        
        params = {
            'peer_id': peer_id,
            'message': message,
            'random_id': 0,
            'access_token': VK_TOKEN,
            'v': '5.131'
        }
        
        if keyboard:
            self.logger.debug(f"Добавление клавиатуры к сообщению для пользователя {peer_id}")
            params['keyboard'] = keyboard
        
        try:
            vk.messages.send(**params)
        except vk_api.VkApiError as e:
            self.logger.error(f"Ошибка при отправке сообщения пользователю {peer_id}: {str(e)}", exc_info=True)
    
    def _handle_admin_command(self, user_id: int, command: str, peer_id: int, vk) -> None:
        """
        Handle admin command
        
        Args:
            user_id: Admin user ID
            command: Command text
            peer_id: Peer ID for response
            vk: VK API instance
        """
        command_parts = command.split()
        command_name = command_parts[0].lower()
        
        if command_name == '/stats':
            # Generate statistics
            response = self._generate_stats()
            self._send_message(peer_id, response, vk)
        
        elif command_name == '/addfaq':
            # Add FAQ entry
            if len(command_parts) < 3:
                self._send_message(peer_id, "Использование: /addfaq <вопрос> | <ответ>", vk)
                return
            
            # Split by first pipe character
            faq_text = ' '.join(command_parts[1:])
            parts = faq_text.split('|', 1)
            
            if len(parts) != 2:
                self._send_message(peer_id, "Использование: /addfaq <вопрос> | <ответ>", vk)
                return
            
            question = parts[0].strip()
            answer = parts[1].strip()
            
            result = self.message_handler.knowledge_base.add_knowledge('faq', question, answer)
            
            if result:
                self._send_message(peer_id, f"FAQ добавлен: {question}", vk)
            else:
                self._send_message(peer_id, "Ошибка при добавлении FAQ", vk)
        
        elif command_name == '/addknowledge':
            # Add knowledge
            if len(command_parts) < 4:
                self._send_message(peer_id, "Использование: /addknowledge <категория> <ключ> | <значение>", vk)
                return
            
            category = command_parts[1].strip()
            knowledge_text = ' '.join(command_parts[2:])
            parts = knowledge_text.split('|', 1)
            
            if len(parts) != 2:
                self._send_message(peer_id, "Использование: /addknowledge <категория> <ключ> | <значение>", vk)
                return
            
            key = parts[0].strip()
            value = parts[1].strip()
            
            result = self.message_handler.knowledge_base.add_knowledge(category, key, value)
            
            if result:
                self._send_message(peer_id, f"Знание добавлено в категорию {category}: {key}", vk)
            else:
                self._send_message(peer_id, f"Ошибка при добавлении знания в категорию {category}", vk)
        
        elif command_name == '/addevent':
            # Add event
            if len(command_parts) < 6:
                self._send_message(peer_id, "Использование: /addevent <название> | <описание> | <дата> | <макс_участников>", vk)
                return
            
            event_text = ' '.join(command_parts[1:])
            parts = event_text.split('|')
            
            if len(parts) != 4:
                self._send_message(peer_id, "Использование: /addevent <название> | <описание> | <дата> | <макс_участников>", vk)
                return
            
            name = parts[0].strip()
            description = parts[1].strip()
            date_str = parts[2].strip()
            max_participants_str = parts[3].strip()
            
            try:
                from datetime import datetime
                date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                max_participants = int(max_participants_str)
                
                event_data = {
                    "name": name,
                    "description": description,
                    "date": date,
                    "max_participants": max_participants,
                    "current_participants": 0,
                    "status": "active"
                }
                
                success, event_id = self.message_handler.excel_handler.add_event(event_data)
                
                if success:
                    self._send_message(peer_id, f"Мероприятие добавлено: {name} (ID: {event_id})", vk)
                else:
                    self._send_message(peer_id, "Ошибка при добавлении мероприятия", vk)
            
            except (ValueError, TypeError) as e:
                self._send_message(peer_id, f"Ошибка в формате даты или количества участников: {e}", vk)
        
        elif command_name == '/help':
            # Show admin help
            help_text = """Команды администратора:
/stats - Статистика бота
/addfaq <вопрос> | <ответ> - Добавить вопрос и ответ в FAQ
/addknowledge <категория> <ключ> | <значение> - Добавить знание в базу знаний
/addevent <название> | <описание> | <дата> | <макс_участников> - Добавить мероприятие
/help - Показать эту справку

Формат даты: ДД.ММ.ГГГГ ЧЧ:ММ (например, 01.01.2023 12:00)
Категории знаний: general, school, kindergarten, faq, documents"""
            
            self._send_message(peer_id, help_text, vk)
        
        else:
            self._send_message(peer_id, "Неизвестная команда. Используйте /help для справки.", vk)
    
    def _generate_stats(self) -> str:
        """
        Generate bot statistics
        
        Returns:
            Statistics text
        """
        try:
            # Get statistics from Excel handler
            clients_df = self.message_handler.excel_handler.export_user_data()
            events_df = self.message_handler.excel_handler.export_event_data()
            registrations_df = self.message_handler.excel_handler.export_registration_data()
            
            total_users = len(clients_df)
            total_events = len(events_df)
            total_registrations = len(registrations_df)
            
            # Count active events
            import pandas as pd
            from datetime import datetime
            
            active_events = 0
            if not events_df.empty and 'status' in events_df.columns and 'date' in events_df.columns:
                active_events = len(events_df[
                    (events_df['status'] == 'active') & 
                    (pd.to_datetime(events_df['date']) > datetime.now())
                ])
            
            stats = f"""Статистика бота:
Всего пользователей: {total_users}
Всего мероприятий: {total_events}
Активных мероприятий: {active_events}
Всего регистраций: {total_registrations}
            """
            
            return stats
        
        except Exception as e:
            self.logger.error(f"Error generating stats: {e}")
            return "Ошибка при генерации статистики"

# Функция для обработки сообщений
def _process_message(event: dict, message_handler: MessageHandler) -> None:
    """
    Process incoming message
    
    Args:
        event: VK event
        message_handler: Message handler
    """
    user_id = event['object']['message']['from_id']
    peer_id = event['object']['message']['peer_id']
    
    # Проверяем, что это не сообщение от бота
    if user_id < 0:
        return
    
    # Получаем текст сообщения
    message_text = event['object']['message'].get('text', '')
    logger.info(f"Входящее сообщение от ID {user_id} (peer_id: {peer_id}): '{message_text}'")
    
    # Получаем payload, если есть
    payload = None
    if 'payload' in event['object']['message']:
        payload = event['object']['message']['payload']
    
    # Обрабатываем сообщение
    response = message_handler.process_message(user_id, message_text, payload)
    
    # Отправляем ответ
    keyboard = response.get('keyboard')
    response_text = response.get('text', 'Извините, произошла ошибка при обработке вашего сообщения.')
    
    # Обрезаем длинный ответ для логирования
    log_response = response_text[:50] + "..." if len(response_text) > 50 else response_text
    logger.info(f"Исходящее сообщение к ID {user_id}: '{log_response}'")
    
    # Проверяем, чтобы не отправлять пустой ответ
    if not response_text:
        response_text = "Извините, не могу сформировать ответ. Пожалуйста, попробуйте еще раз."
    
    # Отправляем сообщение
    vk_api.messages.send(
        peer_id=peer_id,
        user_id=user_id,
        message=response_text,
        keyboard=keyboard if keyboard else None,
        random_id=int(time.time() * 1000)
    ) 