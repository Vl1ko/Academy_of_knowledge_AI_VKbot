import logging
import json
from typing import Dict, List, Any, Optional
import re

import vk_api
from vk_api.exceptions import VkApiError

from src.ai.gigachat_handler import GigaChatHandler
from src.database.db_handler import DatabaseHandler
from src.bot.knowledge_base import KnowledgeBase
from src.bot.conversation_manager import ConversationManager
from src.bot.keyboard_generator import KeyboardGenerator
from src.database.excel_handler import ExcelHandler
from src.bot.structured_response import StructuredResponseHandler
from src.ai.rag_singleton import RAGSingleton
from src.utils.document_manager import DocumentManager
from config.config import VK_TOKEN


class MessageHandler:
    """
    Message handler using AI for generating responses
    """
    
    def __init__(self, db: DatabaseHandler):
        """
        Initialize message handler
        
        Args:
            db: Database instance
        """
        self.logger = logging.getLogger(__name__)
        self.db = db
        self.ai_handler = GigaChatHandler()
        self.knowledge_base = KnowledgeBase()
        self.conversation_manager = ConversationManager()
        self.keyboard_generator = KeyboardGenerator()
        self.excel_handler = ExcelHandler()
        self.response_handler = StructuredResponseHandler(self.knowledge_base)
        self.rag_handler = RAGSingleton()
        self.document_manager = DocumentManager()
        
        # Инициализация VK API для отправки уведомлений
        try:
            import vk_api
            from config.config import VK_TOKEN
            vk_session = vk_api.VkApi(token=VK_TOKEN)
            self.vk = vk_session.get_api()
        except Exception as e:
            self.logger.error(f"Ошибка инициализации VK API: {e}")
            self.vk = None

    def _send_admin_notification(self, admin_id: int, message: str) -> None:
        """
        Send notification to admin
        
        Args:
            admin_id: Admin VK ID
            message: Message text
        """
        try:
            if self.vk:
                self.vk.messages.send(
                    user_id=admin_id,
                    message=message,
                    random_id=0
                )
            else:
                self.logger.warning(f"VK API не инициализирован, уведомление администратору {admin_id} не отправлено")
        except Exception as e:
            self.logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")
        
    def _augment_query_for_rag(self, message_text: str) -> str:
        """
        Лёгкая нормализация запроса для RAG, чтобы он лучше находил ответы из базы знаний.
        Например: "куда можно поступить в 7 лет" -> "Поступление в школу в 7 лет".
        """
        text = message_text.strip().lower()
        # Простая эвристика для возраста
        age_map = {
            "7": ["7 лет", "семь лет"],
            "6": ["6 лет", "шесть лет"],
        }
        age_detected = None
        for age_key, variants in age_map.items():
            if any(v in text for v in variants):
                age_detected = age_key
                break
        if any(kw in text for kw in ["куда можно поступ", "куда поступ", "куда идти", "поступлен", "в какой класс", "в первый класс", "в 1 класс", "в школу"]):
            if age_detected == "7":
                return "Поступление в 1 класс в 7 лет"
            if age_detected == "6":
                return "Поступление в 1 класс в 6 лет"
            return "Поступление в 1 класс"
        return message_text

    def _is_age_enrollment_request(self, text: str) -> bool:
        """Распознаёт запросы вида "куда поступить в N лет", "в какой класс", "в 1 класс" и т.п."""
        t = text.strip().lower()
        age_keywords = [
            "7 лет", "семь лет", "6 лет", "шесть лет", "в 1 класс", "в первый класс",
            "в какой класс", "первый класс", "в школу", "куда поступ"
        ]
        return any(kw in t for kw in age_keywords)

    def process_message(self, user_id: int, message_text: str, payload: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user message
        
        Args:
            user_id: User ID
            message_text: Message text
            payload: Button payload (optional)
            
        Returns:
            Dictionary with response text and keyboard
        """
        self.logger.info(f"Processing message from user {user_id}: {message_text}")
        
        # Добавляем запись пользователя в БД, если его ещё нет
        if not self.db.get_user(user_id):
            self.logger.info(f"Новый пользователь {user_id} добавлен в базу данных")
            self.db.add_user(user_id)
        
        # Обновляем последнее сообщение пользователя и время активности
        self.db.update_user_last_message(user_id, message_text)
        
        # Добавляем сообщение пользователя в историю
        self.logger.info(f"Adding user message to history: {message_text}")
        self.conversation_manager.add_message(user_id, "user", message_text)
        
        # Получаем состояние диалога
        conversation_state = self.conversation_manager.get_conversation_state(user_id)
        
        # Проверяем, не отключен ли ИИ для этого пользователя
        if self.conversation_manager.is_ai_disabled(user_id):
            # Проверяем, не является ли сообщение командой от администратора
            if message_text == "Перевожу Вас на нашего ассистента" and self._is_admin(user_id):
                self.conversation_manager.enable_ai(user_id)
                return {
                    'text': "Я снова на связи! Чем могу помочь?",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            # Проверяем, не является ли это кнопкой завершения диалога
            if payload:
                try:
                    payload_data = json.loads(payload)
                    if payload_data.get("command") == "finish_dialog":
                        self.conversation_manager.enable_ai(user_id)
                        # Очищаем историю диалога для этого пользователя
                        self.conversation_manager.clear_message_history(user_id)
                        return {
                            'text': "Диалог с менеджером завершен. Я снова на связи! Чем могу помочь?",
                            'keyboard': self.keyboard_generator.generate_main_menu()
                        }
                except (json.JSONDecodeError, TypeError):
                    pass
            # Не отправляем никаких сообщений, пока пользователь не нажмет "Завершить диалог"
            return None
        
        # Обрабатываем payload кнопок
        if payload:
            try:
                payload_data = json.loads(payload)
                command = payload_data.get("command")
                if command:
                    return self._handle_command(user_id, command, payload_data, message_text)
            except (json.JSONDecodeError, TypeError) as e:
                self.logger.error(f"Error parsing payload: {e}")
        
        # Административные команды /add и /del обрабатываются в vk_bot.py
        # Проверяем другие административные команды (если есть)
        if self._is_admin_command(message_text):
            return self._handle_admin_command(user_id, message_text)
        
        # Проверяем первое сообщение с номером телефона
        if self._is_first_message_with_phone(user_id, message_text):
            return self._handle_first_message_with_phone(user_id, message_text)
        
        # Проверяем, указал ли пользователь время после первого сообщения с телефоном
        if self._is_time_response_after_phone(user_id, message_text):
            return self._handle_time_response_after_phone(user_id, message_text)
        
        # Проверяем, находится ли пользователь в процессе заполнения формы
        if conversation_state.get('state') == 'consultation_form':
            return self._handle_consultation_form(user_id, message_text, conversation_state)
        
        # Простое приветствие — отвечаем коротко и по-человечески без ИИ
        if self._is_greeting(message_text):
            response = self._generate_greeting_response()
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Проверяем прощание и благодарность (всегда обрабатываем ИИ)
        if self._is_farewell(message_text):
            return self._handle_farewell(user_id)
        
        # Проверяем вопрос о доступности мест в группе (ИИ может ответить)
        if self._is_group_availability_request(message_text):
            return self._handle_group_availability_request(user_id)
        
        # Проверяем подтверждение записи на экскурсию после вопроса о доступности
        if self._is_excursion_confirmation(user_id, message_text):
            return self._handle_excursion_request(user_id)
        
        # Проверяем подтверждение записи на экскурсию (по предыдущему вопросу бота)
        if self._is_excursion_confirmation(user_id, message_text):
            return self._handle_excursion_request(user_id)
        
        # Проверяем запрос на экскурсию (переводим на менеджера)
        if self._is_excursion_request(message_text):
            return self._handle_excursion_request(user_id)
        
        # Проверяем запрос на консультацию (переводим на менеджера)
        if self._is_consultation_request(message_text):
            return self._handle_admin_help_request(user_id, message_text)
        
        try:
            # Получаем релевантную информацию из RAG (с учетом нормализации запроса)
            rag_query = self._augment_query_for_rag(message_text)
            rag_response, relevant_docs = self.rag_handler.get_rag_response(rag_query)
            
            # Получаем историю сообщений
            message_history = self.conversation_manager.get_message_history(user_id)
            self.logger.info(f"Retrieved message history for GigaChat: {message_history}")
            
            # Формируем контекст для GigaChat с учетом RAG
            context = ""
            if rag_response:
                context = f"\nРелевантная информация из базы знаний:\n{rag_response}\n"
                self.logger.info(f"Found relevant RAG response: {rag_response}")
            
            # Генерируем ответ с помощью GigaChat с учетом контекста из RAG (всегда форматируем)
            ai_response = self.ai_handler.generate_response(
                message_text,
                message_history,
                additional_context=context
            )
            self.logger.info(f"Generated AI response: {ai_response}")
            
            # Пост-обработка ответа: убираем приветствия, Markdown, повторы
            formatted_ai_response = self.response_handler.format_response(ai_response)
            
            # Добавляем сообщение бота в историю
            self.logger.info(f"Adding bot response to history: {formatted_ai_response}")
            self.conversation_manager.add_message(user_id, "bot", formatted_ai_response)
            
            # Логируем успешный ответ
            self.db.log_successful_ai_response(user_id, message_text, formatted_ai_response)
            
            return {
                'text': formatted_ai_response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        except Exception as e:
            self.logger.error(f"Ошибка при генерации ответа ИИ: {e}")
            return {
                'text': "Извините, произошла ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору.",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
    
    def _is_consultation_request(self, message: str) -> bool:
        """Check if message is a consultation request"""
        message = message.lower()
        consultation_phrases = [
            "консультац", "встреч", "обсуд",
            "хочу поговорить", "нужна помощь", "нужна консультация",
            "записаться на консультацию", "записаться на встречу", "записаться на обсуждение"
        ]
        
        # Проверяем, содержит ли сообщение запросы на консультацию
        if any(phrase in message for phrase in consultation_phrases):
            # Исключаем простые информационные запросы
            info_phrases = [
                "хочу узнать", "расскажите", "что такое", "как работает",
                "информация о", "про школу", "про детский сад", "про программу",
                "какие есть", "сколько стоит", "какие программы", "какие занятия"
            ]
            
            # Если это информационный запрос, не считаем консультацией
            if any(phrase in message for phrase in info_phrases):
                return False
                
            return True
            
        return False
    
    def _is_excursion_request(self, message: str) -> bool:
        """Check if message is an excursion request"""
        message = message.lower()
        excursion_phrases = [
            "экскурс", "посмотреть школу", "посмотреть детский сад", "приехать посмотреть",
            "прийти посмотреть", "показать", "показать школу", "показать детский сад",
            "записаться на экскурсию", "записаться на просмотр", "хочу посмотреть"
        ]
        return any(phrase in message for phrase in excursion_phrases)
    
    def _is_group_availability_request(self, message: str) -> bool:
        """Check if message is asking about group availability"""
        message = message.lower()
        availability_phrases = [
            "есть ли место", "есть ли места", "свободные места", "свободное место",
            "набор в группу", "можно ли записаться", "принимаете ли",
            "есть ли свободные места", "есть ли свободное место",
            "набор открыт", "набор закрыт", "группа полная", "группа заполнена"
        ]
        return any(phrase in message for phrase in availability_phrases)
    
    def _is_excursion_confirmation(self, user_id: int, message_text: str) -> bool:
        """Check if user is confirming excursion after availability question"""
        # Проверяем, было ли предыдущее сообщение бота о доступности мест
        message_history = self.conversation_manager.get_message_history(user_id)
        if len(message_history) < 2:
            return False
        
        # Получаем последнее сообщение бота
        last_bot_message = None
        for msg in reversed(message_history):
            if msg.get("role") == "bot":
                last_bot_message = msg.get("content", "")
                break
        
        if not last_bot_message:
            return False
        
        # Проверяем, содержало ли последнее сообщение бота предложение/вопрос о записи на экскурсию
        last_bot_lower = last_bot_message.lower()
        asked_about_excursion_signup = (
            "готовы записаться на экскурсию" in last_bot_lower
            or "хотите записаться на экскурсию" in last_bot_lower
            or "записаться на экскурсию" in last_bot_lower
            or ("записаться" in last_bot_lower and "экскурс" in last_bot_lower)
            or "есть вопросы или хотите записаться на экскурсию" in last_bot_lower
        )
        if not asked_about_excursion_signup:
            return False
        
        # Проверяем, является ли текущее сообщение подтверждением
        message_text = message_text.lower()
        confirmation_phrases = [
            "да", "конечно", "готов", "готова", "хочу", "давайте", "согласен", "согласна",
            "запишите", "запишите меня", "хочу записаться", "хочу прийти", "хочу приехать"
        ]
        return any(phrase in message_text for phrase in confirmation_phrases)
    
    def _is_farewell(self, message: str) -> bool:
        """Check if message is a farewell or thank you"""
        message = message.lower()
        farewell_phrases = [
            # Благодарности
            "спасибо", "благодарю", "благодарен", "благодарна", "спс", "thx", "thanks",
            "большое спасибо", "огромное спасибо", "спасибо большое", "спасибо огромное",
            
            # Прощания
            "до свидания", "до встречи", "пока", "прощай", "увидимся", "всего доброго",
            "всего хорошего", "удачи", "успехов", "хорошего дня", "хорошего вечера",
            "хороших выходных", "хорошей недели", "хорошего настроения",
            
            # Завершения диалога
            "все понятно", "все ясно", "все понятно спасибо", "все ясно спасибо",
            "больше вопросов нет", "вопросов больше нет", "все вопросы решены",
            "все решено", "все хорошо", "все отлично", "все супер",
            
            # Вежливые завершения
            "хорошо", "ладно", "понятно", "ясно", "ок", "окей", "все", "всего"
        ]
        return any(phrase in message for phrase in farewell_phrases)
    
    def _handle_farewell(self, user_id: int) -> Dict[str, Any]:
        """Handle farewell or thank you message"""
        response = "Пожалуйста! В случае возникновения дополнительных вопросов, с радостью Вас проконсультируем!"
        
        self.conversation_manager.add_message(user_id, "bot", response)
        return {
            "text": response,
            "keyboard": self.keyboard_generator.generate_main_menu()
        }
    
    def _handle_group_availability_request(self, user_id: int) -> Dict[str, Any]:
        """Handle group availability request"""
        response = "Да, на текущий момент Вы можете присоединиться к группе. Готовы записаться на экскурсию?"
        
        self.conversation_manager.add_message(user_id, "bot", response)
        return {
            "text": response,
            "keyboard": self.keyboard_generator.generate_main_menu()
        }
    
    def _handle_excursion_request(self, user_id: int) -> Dict[str, Any]:
        """Handle excursion request"""
        # Отключаем ИИ для этого пользователя
        self.conversation_manager.disable_ai(user_id)
        
        # Уведомляем администраторов
        self._notify_admins_about_excursion_request(user_id)
        
        return {
            'text': "Отлично, сейчас уточняем возможные дни и время для экскурсии. В ближайшее время дадим ответ",
            'keyboard': self.keyboard_generator.generate_finish_dialog_keyboard()
        }
    
    def _start_consultation_form(self, user_id: int) -> Dict[str, Any]:
        """Start consultation form flow"""
        self.conversation_manager.update_state(user_id, {
            'state': 'consultation_form',
            'stage': 'name'
        })
        
        response = "Для записи на консультацию мне нужно собрать немного информации. Как вас зовут (ФИО)?"
        self.conversation_manager.add_message(user_id, "bot", response)
        
        return {
            'text': response,
            'keyboard': self.keyboard_generator.generate_cancel_button()
        }
    
    def _handle_consultation_form(self, user_id: int, message: str, state: Dict) -> Dict[str, Any]:
        """Handle consultation form input"""
        stage = state.get('stage')
        
        if message.lower() in ['отмена', 'cancel', 'назад', 'back']:
            self.conversation_manager.reset_state(user_id)
            return {
                'text': "Заполнение формы отменено. Чем еще могу помочь?",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        if stage == 'name':
            # Validate name (simple check for now)
            if len(message.split()) < 2:
                return {
                    'text': "Пожалуйста, укажите полное ФИО (фамилию и имя).",
                    'keyboard': self.keyboard_generator.generate_cancel_button()
                }
            
            self.conversation_manager.update_state(user_id, {
                'state': 'consultation_form',
                'stage': 'phone',
                'data': {'name': message}
            })
            
            response = "Спасибо! Теперь, пожалуйста, укажите ваш контактный телефон:"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_cancel_button()
            }
            
        elif stage == 'phone':
            # Validate phone number (simple check for now)
            phone = ''.join(filter(str.isdigit, message))
            if len(phone) < 10:
                return {
                    'text': "Пожалуйста, укажите корректный номер телефона.",
                    'keyboard': self.keyboard_generator.generate_cancel_button()
                }
            
            self.conversation_manager.update_state(user_id, {
                'state': 'consultation_form',
                'stage': 'contact_time',
                'data': {**state.get('data', {}), 'phone': message}
            })
            
            response = "В какое время вам удобно, чтобы мы с вами связались? Пожалуйста, укажите предпочтительное время для звонка в промежутке с 10:00 до 17:00 по будним дням:"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_cancel_button()
            }
            
        elif stage == 'contact_time':
            # Validate contact time format and range
            time_str = message.lower().replace('с', '').replace('до', '-').strip()
            # Simple validation - just ensure it mentions time between 10:00 and 17:00
            if not any(str(hour) in time_str for hour in range(10, 18)):
                return {
                    'text': "Пожалуйста, укажите время для звонка с 10:00 до 17:00 в рабочие дни.",
                    'keyboard': self.keyboard_generator.generate_cancel_button()
                }
            
            # Save consultation request
            name = state.get('data', {}).get('name', '')
            phone = state.get('data', {}).get('phone', '')
            self.db.save_consultation_request(user_id, name, phone, time_str)
            
            # Notify admins
            self._notify_admins_about_consultation(name, phone, time_str)
            
            # Reset conversation state
            self.conversation_manager.reset_state(user_id)
            
            response = f"Спасибо за заявку! Мы свяжемся с вами в указанное время ({time_str}) для подтверждения консультации."
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
    
    def _is_time_response_after_phone(self, user_id: int, message_text: str) -> bool:
        """
        Check if this is a time response after first message with phone
        
        Args:
            user_id: User ID
            message_text: Message text
            
        Returns:
            True if this is time response after phone message
        """
        # Получаем историю сообщений
        message_history = self.conversation_manager.get_message_history(user_id)
        
        # Нужно минимум 2 сообщения: первое с телефоном и ответ бота
        if len(message_history) < 2:
            return False
        
        # Проверяем, что последнее сообщение бота содержит стандартный ответ
        last_bot_message = None
        for msg in reversed(message_history):
            if msg.get('role') == 'bot':
                last_bot_message = msg.get('content', '')
                break
        
        if not last_bot_message:
            return False
        
        # Проверяем, что это стандартный ответ на первое сообщение с телефоном
        if "Укажите удобное время для звонка с 10.00 до 18.00" not in last_bot_message:
            return False
        
        # Проверяем, что текущее сообщение похоже на время
        return self._is_time_format(message_text)
    
    def _is_time_format(self, message: str) -> bool:
        """
        Check if message contains time format
        
        Args:
            message: Message text
            
        Returns:
            True if message contains time format
        """
        # Очищаем сообщение от лишних символов
        clean_message = message.strip().lower()
        
        # Паттерны для времени
        time_patterns = [
            r'^\d{1,2}:\d{2}$',  # 10:00, 9:30
            r'^\d{1,2}\.\d{2}$',  # 10.00, 9.30
            r'^\d{1,2}\s\d{2}$',  # 10 00, 9 30
            r'^\d{1,2}ч\s*\d{0,2}м?$',  # 10ч, 10ч 30м
            r'^\d{1,2}\s*часа?\s*\d{0,2}\s*минут?$',  # 10 часов, 10 часов 30 минут
            r'^\d{1,2}\s*часа?$',  # 10 часов
        ]
        
        for pattern in time_patterns:
            if re.match(pattern, clean_message):
                return True
        
        # Проверяем простые числовые форматы времени
        if re.match(r'^\d{1,2}$', clean_message):  # 10, 15
            time_num = int(clean_message)
            if 8 <= time_num <= 20:  # Разумный диапазон времени
                return True
        
        return False
    
    def _extract_time_from_message(self, message: str) -> str:
        """
        Extract time from message
        
        Args:
            message: Message text
            
        Returns:
            Formatted time string
        """
        # Очищаем сообщение
        clean_message = message.strip().lower()
        
        # Если это просто число, добавляем :00
        if re.match(r'^\d{1,2}$', clean_message):
            time_num = int(clean_message)
            return f"{time_num:02d}:00"
        
        # Если это формат с двоеточием
        if re.match(r'^\d{1,2}:\d{2}$', clean_message):
            return clean_message
        
        # Если это формат с точкой
        if re.match(r'^\d{1,2}\.\d{2}$', clean_message):
            return clean_message.replace('.', ':')
        
        # Если это формат с пробелом
        if re.match(r'^\d{1,2}\s\d{2}$', clean_message):
            return clean_message.replace(' ', ':')
        
        # Для других форматов возвращаем как есть
        return clean_message
    
    def _handle_time_response_after_phone(self, user_id: int, message_text: str) -> Dict[str, Any]:
        """
        Handle time response after first message with phone
        
        Args:
            user_id: User ID
            message_text: Message text
            
        Returns:
            Response dictionary
        """
        # Извлекаем время из сообщения
        time_str = self._extract_time_from_message(message_text)
        
        # Получаем данные пользователя
        user_data = self.db.get_user_data(user_id)
        phone = user_data.get('phone') if user_data else None
        
        # Если телефон не найден в БД, пытаемся извлечь из истории
        if not phone:
            message_history = self.conversation_manager.get_message_history(user_id)
            for msg in message_history:
                if msg.get('role') == 'user':
                    extracted_phone = self._extract_phone_number(msg.get('content', ''))
                    if extracted_phone:
                        phone = extracted_phone
                        break
        
        # Формируем ответ пользователю
        response = f"Благодарим за заявку, менеджер свяжется с Вами в {time_str}"
        
        # Добавляем сообщение бота в историю
        self.conversation_manager.add_message(user_id, "bot", response)
        
        # Уведомляем администраторов
        if phone:
            self._notify_admins_about_phone_time_request(user_id, phone, time_str)
        
        # Логируем успешный ответ
        self.db.log_successful_ai_response(user_id, message_text, response)
        
        return {
            'text': response,
            'keyboard': self.keyboard_generator.generate_main_menu()
        }
    
    def _notify_admins_about_phone_time_request(self, user_id: int, phone: str, time: str) -> None:
        """
        Notify admins about phone and time request
        
        Args:
            user_id: User ID
            phone: Phone number
            time: Preferred time
        """
        admin_ids = self.db.get_admin_ids()
        
        # Получаем имя пользователя из VK API
        user_name = self._get_vk_user_name(user_id)
        if user_name:
            notification = f"Пользователь {user_name} (ID: {user_id}) оставил номер телефона {phone} и просит связаться с ним в {time}"
        else:
            notification = f"Пользователь {user_id} оставил номер телефона {phone} и просит связаться с ним в {time}"
        
        for admin_id in admin_ids:
            try:
                self.vk.messages.send(
                    user_id=admin_id,
                    message=notification,
                    random_id=0
                )
            except Exception as e:
                self.logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")
    
    def _is_admin_help_request(self, message: str) -> bool:
        """Check if message is requesting admin help"""
        message = message.lower()
        
        # Только прямые запросы на администратора или запись
        direct_admin_phrases = [
            # Прямые запросы на администратора
            "оператор", "администратор", "менеджер", "человек",
            "поговорить с человеком", "нужен человек", "свяжите с",
            "переключите на", "переключите меня", "переведите на",
            
            # Запросы на запись/регистрацию
            "записаться", "запись", "регистрация", "зарегистрироваться",
            
            # Запросы на звонок
            "позвоните", "позвонить", "звонок",
            "связаться", "связаться со мной", "перезвоните",
            
            # Конкретные проблемы
            "есть проблема", "не получается", "не могу", "помогите с",
            "нужна помощь с", "требуется помощь с"
        ]
        
        # Проверяем только прямые запросы
        return any(phrase in message for phrase in direct_admin_phrases)
    
    def _handle_admin_help_request(self, user_id: int, message: str) -> Dict[str, Any]:
        """Handle request for admin help"""
        # Disable AI for this user
        self.conversation_manager.disable_ai(user_id)
        
        # Notify admins
        self._notify_admins_about_help_request(user_id, message)
        
        return {
            'text': "Я перевожу Вас на администратора. Пожалуйста, подождите немного.",
            'keyboard': self.keyboard_generator.generate_finish_dialog_keyboard()
        }
    
    def _notify_admins_about_consultation(self, name: str, phone: str, time: str) -> None:
        """Notify admins about new consultation request"""
        admin_ids = self.db.get_admin_ids()
        message = f"Новая заявка на консультацию:\nИмя: {name}\nТелефон: {phone}\nВремя: {time}"
        
        for admin_id in admin_ids:
            self._send_admin_notification(admin_id, message)
    
    def _notify_admins_about_help_request(self, user_id: int, message: str) -> None:
        """Notify admins about help request"""
        admin_ids = self.db.get_admin_ids()
        
        # Получаем имя пользователя из VK API
        user_name = self._get_vk_user_name(user_id)
        if user_name:
            notification = f"Пользователь {user_name} (ID: {user_id}) вызывает администратора.\nСообщение: {message}"
        else:
            notification = f"Пользователь {user_id} вызывает администратора.\nСообщение: {message}"
        
        for admin_id in admin_ids:
            self._send_admin_notification(admin_id, notification)
    
    def _notify_admins_about_excursion_request(self, user_id: int) -> None:
        """Notify admins about excursion request"""
        admin_ids = self.db.get_admin_ids()
        
        # Получаем имя пользователя из VK API
        user_name = self._get_vk_user_name(user_id)
        if user_name:
            notification = f"Пользователь {user_name} (ID: {user_id}) вызывает администратора.\nСообщение: запрос на экскурсию"
        else:
            notification = f"Пользователь {user_id} вызывает администратора.\nСообщение: запрос на экскурсию"
        
        for admin_id in admin_ids:
            self._send_admin_notification(admin_id, notification)
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        admin_ids = self.db.get_admin_ids()
        return user_id in admin_ids
    
    def _is_greeting(self, text: str) -> bool:
        """
        Определяет, является ли текст приветствием
        
        Args:
            text: Текст сообщения
            
        Returns:
            True, если текст является приветствием, иначе False
        """
        greetings = [
            "привет", "здравствуй", "здравствуйте", "добрый день", "доброе утро", 
            "добрый вечер", "здарова", "приветствую", "хай", "хеллоу", "hello", "hi"
        ]
        
        text = text.lower().strip()
        
        # Проверяем точное совпадение
        if text in greetings:
            return True
        
        # Проверяем, начинается ли текст с приветствия
        for greeting in greetings:
            if text.startswith(greeting):
                return True
                
        return False
        
    def _generate_greeting_response(self) -> str:
        """
        Генерирует ответ на приветствие
        
        Returns:
            Текст приветствия
        """
        import random
        
        greetings = [
            "Добрый день! Подскажите, что именно хотите узнать?",
            "Здравствуйте! Чем могу помочь — стоимость, программы, расписание?",
            "Добрый день! О чем рассказать в первую очередь: школа, садик или кружки?",
            "Здравствуйте! Сориентировать по стоимости или рассказать про программы?",
            "Добрый день! Готов помочь — что интересует больше всего?"
        ]
        
        return random.choice(greetings)
    
    def _handle_command(self, user_id: int, command: str, payload: Dict[str, Any], message_text: str) -> Dict[str, Any]:
        """
        Handle command from button payload
        
        Args:
            user_id: User ID
            command: Command name
            payload: Full payload dictionary
            message_text: Original message text
            
        Returns:
            Response dictionary
        """
        # Reset any ongoing conversation
        if command == "main_menu":
            self.conversation_manager.reset_state(user_id)
            # Очищаем историю диалога при возврате в главное меню
            self.conversation_manager.clear_message_history(user_id)
            return {
                "text": "Главное меню:",
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # About school command
        elif command == "about_school":
            response = self.knowledge_base.get_response("О школе", "school") or \
                       "Частная школа «Академия знаний» - это современное образовательное учреждение, " \
                       "которое сочетает высокие стандарты образования с индивидуальным подходом к каждому ученику."
            
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # About kindergarten command
        elif command == "about_kindergarten":
            response = self.knowledge_base.get_response("О детском саде", "kindergarten") or \
                       "Частный детский сад «Академик» - это пространство для гармоничного развития детей, " \
                       "где созданы все условия для обучения, игры и творчества."
            
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Consultation request command
        elif command == "consultation":
            self.conversation_manager.update_stage(user_id, "consultation_name")
            response = "Чтобы записать вас на консультацию, мне нужно немного информации. Как вас зовут (ФИО)?"
            
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Admin help request command
        elif command == "admin_help":
            # Отключаем ИИ для этого пользователя
            self.conversation_manager.disable_ai(user_id)
            
            # Уведомляем администраторов
            self._notify_admins_about_help_request(user_id, "запрос на связь с администратором")
            
            return {
                'text': "Я перевожу Вас на администратора. Пожалуйста, подождите немного.",
                'keyboard': self.keyboard_generator.generate_finish_dialog_keyboard()
            }
        
        # Events list command
        elif command == "events":
            events = self.excel_handler.get_events(active_only=True)
            
            if not events:
                response = "В настоящее время нет предстоящих мероприятий. Пожалуйста, проверьте позже."
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            response = "Предстоящие мероприятия:\n\n"
            for event in events[:5]:  # Limit to 5 events in text
                event_date = event.get("date", "Дата не указана")
                if hasattr(event_date, "strftime"):
                    event_date = event_date.strftime("%d.%m.%Y %H:%M")
                
                response += f"• {event.get('name', 'Без названия')}\n"
                response += f"  Дата: {event_date}\n"
                response += f"  Свободных мест: {event.get('max_participants', 0) - event.get('current_participants', 0)}\n\n"
            
            response += "Выберите мероприятие для получения подробной информации и регистрации:"
            
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_events_keyboard(events)
            }
        
        # Event info command
        elif command == "event_info":
            event_id = payload.get("event_id")
            if not event_id:
                return {
                    "text": "Не указан идентификатор мероприятия.",
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            events = self.excel_handler.get_events(active_only=False)
            event = next((e for e in events if e.get("id") == event_id), None)
            
            if not event:
                return {
                    "text": "Мероприятие не найдено.",
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            event_date = event.get("date", "Дата не указана")
            if hasattr(event_date, "strftime"):
                event_date = event_date.strftime("%d.%m.%Y %H:%M")
            
            response = f"Информация о мероприятии:\n\n"
            response += f"Название: {event.get('name', 'Без названия')}\n"
            response += f"Дата: {event_date}\n"
            response += f"Описание: {event.get('description', 'Описание отсутствует')}\n"
            response += f"Свободных мест: {event.get('max_participants', 0) - event.get('current_participants', 0)}\n\n"
            response += "Хотите зарегистрироваться на это мероприятие?"
            
            self.conversation_manager.update_stage(user_id, "event_registration")
            self.conversation_manager.add_data(user_id, "event_id", event_id)
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_yes_no_keyboard("event_register_yes", "event_register_no")
            }
        
        # Event registration confirmation
        elif command == "event_register_yes":
            event_id = self.conversation_manager.get_data(user_id, "event_id")
            if not event_id:
                return {
                    "text": "Не удалось найти информацию о мероприятии.",
                    "keyboard": self.keyboard_generator.generate_main_menu()
                }
            
            # Get user info
            user_data = self.db.get_user_data(user_id) or self.excel_handler.get_user(user_id)
            
            # If we don't have user data, we need to collect it
            if not user_data or not user_data.get("name") or not user_data.get("phone"):
                self.conversation_manager.update_stage(user_id, "registration_name")
                response = "Для регистрации на мероприятие мне нужна дополнительная информация. Как вас зовут (ФИО)?"
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            # Register user for event
            success = self.excel_handler.register_for_event(user_id, event_id)
            
            if success:
                response = "Вы успешно зарегистрированы на мероприятие! Мы свяжемся с вами для подтверждения."
            else:
                response = "К сожалению, не удалось зарегистрировать вас на мероприятие. Возможно, нет свободных мест или произошла ошибка."
            
            self.conversation_manager.reset_state(user_id)
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # Event registration cancellation
        elif command == "event_register_no":
            self.conversation_manager.reset_state(user_id)
            response = "Регистрация отменена. Вы можете выбрать другое мероприятие или вернуться в главное меню."
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # FAQ command
        elif command == "faq":
            # Получаем все ключи из категории faq
            faq_keys = self.knowledge_base.get_all_keys("faq")
            
            if not faq_keys:
                response = "В настоящее время у нас нет часто задаваемых вопросов. Вы можете задать свой вопрос, и мы постараемся на него ответить."
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            response = "Часто задаваемые вопросы:\n\n"
            questions = faq_keys[:5]  # Limit to 5 questions in text
            
            for i, question in enumerate(questions, 1):
                response += f"{i}. {question}\n"
            
            response += "\nВыберите вопрос, чтобы получить ответ:"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_faq_keyboard(questions)
            }
        
        # FAQ question command
        elif command == "faq_question":
            question = payload.get("question")
            if not question:
                return {
                    "text": "Вопрос не найден.",
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            # Заменяем обращение к несуществующему атрибуту categories
            answer = self.knowledge_base.get_knowledge("faq", question)
            
            if not answer:
                return {
                    "text": "К сожалению, ответ на этот вопрос не найден.",
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            response = f"Вопрос: {question}\n\nОтвет: {answer}"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Document management commands
        elif command == "docs_list":
            category = payload.get("category")
            documents = self.document_manager.list_documents(category)
            
            if not documents:
                response = "В базе знаний пока нет документов."
                if category:
                    response = f"В категории {category} пока нет документов."
            else:
                response = "Документы в базе знаний:\n\n"
                for doc in documents:
                    info = self.document_manager.get_document_info(str(doc))
                    if info:
                        response += f"📄 {info['name']}\n"
                        response += f"   Категория: {info['category']}\n"
                        response += f"   Добавлен: {info['created'][:10]}\n\n"
            
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
            
        elif command == "doc_info":
            doc_path = payload.get("doc_path")
            if not doc_path:
                return {
                    "text": "Не указан путь к документу.",
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            info = self.document_manager.get_document_info(doc_path)
            if not info:
                return {
                    "text": "Документ не найден.",
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            response = f"Информация о документе:\n\n"
            response += f"📄 Название: {info['name']}\n"
            response += f"📁 Категория: {info['category']}\n"
            response += f"📅 Добавлен: {info['created'][:10]}\n"
            response += f"🔄 Изменен: {info['modified'][:10]}\n"
            response += f"📊 Размер: {info['size']} байт\n"
            
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Unknown command
        else:
            return {
                "text": "Неизвестная команда. Пожалуйста, выберите действие из меню.",
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
    
    def _handle_conversation_stage(self, user_id: int, message_text: str, current_stage: str) -> Dict[str, Any]:
        """
        Handle conversation based on current stage
        
        Args:
            user_id: User ID
            message_text: Message text
            current_stage: Current conversation stage
            
        Returns:
            Response dictionary
        """
        # Registration flow - collecting name
        if current_stage == "registration_name" or current_stage == "consultation_name":
            if len(message_text) < 3:
                response = "Пожалуйста, введите ваше полное имя (ФИО)."
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            self.conversation_manager.add_data(user_id, "name", message_text)
            
            next_stage = "registration_phone" if current_stage == "registration_name" else "consultation_child_info"
            self.conversation_manager.update_stage(user_id, next_stage)
            
            if next_stage == "registration_phone":
                response = "Спасибо! Теперь, пожалуйста, введите ваш номер телефона:"
            else:
                response = "Спасибо! Укажите, пожалуйста, возраст и класс ребенка:"
            
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Registration flow - collecting phone
        elif current_stage == "registration_phone":
            # Validate phone number
            phone_pattern = re.compile(r'^\+?[0-9()\-\s]{10,15}$')
            if not phone_pattern.match(message_text):
                response = "Пожалуйста, введите корректный номер телефона (например, +7XXXXXXXXXX или 8XXXXXXXXXX)."
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            self.conversation_manager.add_data(user_id, "phone", message_text)
            self.conversation_manager.update_stage(user_id, "registration_child_age")
            
            response = "Спасибо! Укажите, пожалуйста, возраст вашего ребенка:"
            
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
            
        # Consultation flow - collecting child info (age and class)
        elif current_stage == "consultation_child_info":
            self.conversation_manager.add_data(user_id, "child_info", message_text)
            self.conversation_manager.update_stage(user_id, "consultation_wishes")
            
            response = "Спасибо! Опишите, пожалуйста, ваши пожелания или вопросы, которые вы хотели бы обсудить на консультации:"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
            
        # Consultation flow - collecting wishes
        elif current_stage == "consultation_wishes":
            self.conversation_manager.add_data(user_id, "wishes", message_text)
            
            # Save consultation data
            name = self.conversation_manager.get_data(user_id, "name")
            child_info = self.conversation_manager.get_data(user_id, "child_info")
            wishes = self.conversation_manager.get_data(user_id, "wishes")
            
            # Save user data if needed
            user_data = self.db.get_user_data(user_id) or self.excel_handler.get_user(user_id)
            if not user_data:
                user_data = {
                    "vk_id": user_id,
                    "name": name
                }
                self.excel_handler.add_user(user_data)
                self.db.create_user(user_id, name, None, None)
            
            # Сохраняем данные о консультации
            consultation_data = {
                "vk_id": user_id,
                "name": name,
                "child_info": child_info,
                "wishes": wishes,
                "status": "new"
            }
            
            try:
                # Метод для сохранения консультации (необходимо создать в excel_handler)
                self.excel_handler.add_consultation(consultation_data)
                self.logger.info(f"Консультация сохранена для пользователя {user_id}: {consultation_data}")
            except Exception as e:
                self.logger.error(f"Ошибка при сохранении консультации: {e}")
            
            # Complete consultation request
            self.conversation_manager.reset_state(user_id)
            
            response = f"Спасибо, {name}! Ваша заявка на консультацию принята. Наш администратор свяжется с вами в ближайшее время через сообщения."
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # Registration flow - collecting child age
        elif current_stage == "registration_child_age":
            try:
                age = int(message_text.strip())
                if age < 0 or age > 18:
                    raise ValueError("Age out of range")
            except (ValueError, TypeError):
                response = "Пожалуйста, введите корректный возраст ребенка (число от 0 до 18)."
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_back_button()
                }
            
            self.conversation_manager.add_data(user_id, "child_age", age)
            self.conversation_manager.update_stage(user_id, "registration_interests")
            
            response = "Спасибо! Какие направления обучения вас интересуют? (например: математика, английский язык, программирование и т.д.)"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Registration flow - collecting interests
        elif current_stage == "registration_interests":
            self.conversation_manager.add_data(user_id, "interests", message_text)
            
            # Save user data
            name = self.conversation_manager.get_data(user_id, "name")
            phone = self.conversation_manager.get_data(user_id, "phone")
            child_age = self.conversation_manager.get_data(user_id, "child_age")
            interests = self.conversation_manager.get_data(user_id, "interests")
            
            # Event registration if we came from event flow
            event_id = self.conversation_manager.get_data(user_id, "event_id")
            
            user_data = {
                "vk_id": user_id,
                "name": name,
                "phone": phone,
                "child_age": child_age,
                "interests": interests
            }
            
            # Save to Excel
            self.excel_handler.add_user(user_data)
            
            # Save to database
            self.db.create_user(user_id, name, phone, child_age)
            
            # Complete registration
            self.conversation_manager.reset_state(user_id)
            
            # If we have an event ID, register for event
            if event_id:
                success = self.excel_handler.register_for_event(user_id, event_id)
                
                if success:
                    response = f"Спасибо за предоставленную информацию, {name}! Вы успешно зарегистрированы на мероприятие. Мы свяжемся с вами для подтверждения."
                else:
                    response = f"Спасибо за предоставленную информацию, {name}! К сожалению, не удалось зарегистрировать вас на мероприятие. Возможно, нет свободных мест или произошла ошибка."
            else:
                response = f"Спасибо за предоставленную информацию, {name}! Мы свяжемся с вами в ближайшее время для обсуждения обучения в нашей школе."
            
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # Consultation flow - collecting preferred date
        elif current_stage == "consultation_date":
            # Если сообщение содержит и телефон, и дату, разделим их
            parts = message_text.split()
            has_phone = False
            
            # Проверяем, есть ли в сообщении телефон
            phone_pattern = re.compile(r'^\+?[0-9()\-\s]{10,15}$')
            for part in parts:
                if phone_pattern.match(part):
                    # Обновляем телефон пользователя, если он был указан
                    self.conversation_manager.add_data(user_id, "phone", part)
                    has_phone = True
                    # Удалить телефон из сообщения, чтобы оставить только дату
                    message_text = message_text.replace(part, "", 1).strip()
                    break
            
            self.conversation_manager.add_data(user_id, "preferred_date", message_text)
            self.conversation_manager.update_stage(user_id, "consultation_topic")
            
            response = "Спасибо! Пожалуйста, кратко опишите тему консультации или вопросы, которые вы хотели бы обсудить:"
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_back_button()
            }
        
        # Consultation flow - collecting topic
        elif current_stage == "consultation_topic":
            self.conversation_manager.add_data(user_id, "topic", message_text)
            
            # Save consultation data
            name = self.conversation_manager.get_data(user_id, "name")
            phone = self.conversation_manager.get_data(user_id, "phone")
            preferred_date = self.conversation_manager.get_data(user_id, "preferred_date")
            topic = self.conversation_manager.get_data(user_id, "topic")
            
            # Save user data if needed
            user_data = self.db.get_user_data(user_id) or self.excel_handler.get_user(user_id)
            if not user_data:
                user_data = {
                    "vk_id": user_id,
                    "name": name,
                    "phone": phone
                }
                self.excel_handler.add_user(user_data)
                self.db.create_user(user_id, name, phone, None)
            
            # Сохраняем данные о консультации
            consultation_data = {
                "vk_id": user_id,
                "name": name,
                "phone": phone,
                "preferred_date": preferred_date,
                "topic": topic,
                "status": "new"
            }
            
            try:
                # Метод для сохранения консультации (необходимо создать в excel_handler)
                self.excel_handler.add_consultation(consultation_data)
                self.logger.info(f"Консультация сохранена для пользователя {user_id}: {consultation_data}")
            except Exception as e:
                    self.logger.error(f"Ошибка при сохранении консультации: {e}")
            
            # Complete consultation request
            self.conversation_manager.reset_state(user_id)
            
            response = f"Спасибо, {name}! Ваша заявка на консультацию принята. Мы свяжемся с вами для подтверждения даты и времени ({preferred_date})."
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # Event registration
        elif current_stage == "event_registration":
            # This should be handled by commands, but just in case
            if message_text.lower() in ["да", "yes", "конечно", "хочу"]:
                return self._handle_command(user_id, "event_register_yes", {"command": "event_register_yes"}, message_text)
            elif message_text.lower() in ["нет", "no", "не хочу", "отмена"]:
                return self._handle_command(user_id, "event_register_no", {"command": "event_register_no"}, message_text)
            else:
                response = "Пожалуйста, ответьте 'Да' или 'Нет'."
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_yes_no_keyboard("event_register_yes", "event_register_no")
                }
        
        # Unknown stage - reset and return to main menu
        else:
            self.conversation_manager.reset_state(user_id)
            response = "Произошла ошибка в диалоге. Давайте начнем сначала. Чем я могу вам помочь?"
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                "text": response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            } 
    
    def _extract_context_from_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Извлекает контекст из последних сообщений диалога
        
        Args:
            messages: Список сообщений
            
        Returns:
            Строка с контекстом
        """
        if not messages:
            return ""
            
        context = ""
        # Собираем все сообщения в один текст для анализа контекста
        for msg in messages:
            if msg.get("role") == "bot":
                context += " " + msg.get("content", "")
                
        return context.lower() 

    def _handle_user_message(self, user_id: int, message_text: str) -> Dict[str, Any]:
        """
        Handle user message
        
        Args:
            user_id: User ID
            message_text: Message text
            
        Returns:
            Response data
        """
        # Сохраняем сообщение пользователя
        self.conversation_manager.add_message(user_id, "user", message_text)
        
        # Пробуем получить ответ через RAG
        rag_response, relevant_docs = self.rag_handler.get_rag_response(message_text)
        
        if rag_response:
            # Проверяем уверенность в ответе
            if "не уверен" in rag_response.lower() or "возможно" in rag_response.lower():
                # Сначала предлагаем переформулировать вопрос
                response = "Извините, я не могу дать точный ответ на ваш вопрос. Не могли бы вы переформулировать его, чтобы я лучше понял, что именно вас интересует?"
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    "text": response,
                    "keyboard": self.keyboard_generator.generate_main_menu()
                }
            
            # Форматируем ответ через StructuredResponseHandler
            formatted_response = self.response_handler.format_response(rag_response)
            
            # Добавляем информацию об источниках, если есть релевантные документы
            if relevant_docs:
                context_info = "\n\nИспользованные источники:\n"
                for i, doc in enumerate(relevant_docs, 1):
                    context = doc.get("context", "").strip()
                    if context:
                        context_info += f"{i}. Раздел: {context}\n"
                formatted_response += context_info
            
            self.conversation_manager.add_message(user_id, "bot", formatted_response)
            return {
                "text": formatted_response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # Если RAG не нашел ответ, пробуем обычный поиск
        structured_response = self.response_handler.get_structured_response(message_text)
        
        if structured_response:
            self.conversation_manager.add_message(user_id, "bot", structured_response)
            return {
                "text": structured_response,
                "keyboard": self.keyboard_generator.generate_main_menu()
            }
        
        # Если ни один метод не нашел точного ответа
        response = "Извините, я не могу дать точный ответ на ваш вопрос. Пожалуйста, переформулируйте его, чтобы я лучше понял, что именно вас интересует. Вы также можете уточнить детали или задать более конкретный вопрос. Если у вас есть сложные вопросы, требующие индивидуального подхода, вы можете связаться с нашим менеджером."
        self.conversation_manager.add_message(user_id, "bot", response)
        
        return {
            "text": response,
            "keyboard": self.keyboard_generator.generate_main_menu()
        } 

    def _extract_phone_number(self, message: str) -> Optional[str]:
        """
        Extract phone number from message
        
        Args:
            message: Message text
            
        Returns:
            Phone number if found, None otherwise
        """
        # Паттерны для поиска номера телефона
        phone_patterns = [
            r'\+?7\s?\(?(\d{3})\)?\s?(\d{3})\s?(\d{2})\s?(\d{2})',  # +7 (XXX) XXX XX XX
            r'8\s?\(?(\d{3})\)?\s?(\d{3})\s?(\d{2})\s?(\d{2})',    # 8 (XXX) XXX XX XX
            r'\+?7(\d{10})',  # +7XXXXXXXXXX
            r'8(\d{10})',     # 8XXXXXXXXXX
            r'(\d{3})\s?(\d{3})\s?(\d{2})\s?(\d{2})',  # XXX XXX XX XX
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, message)
            if match:
                if len(match.groups()) == 4:
                    # Формат с группами
                    return f"+7{match.group(1)}{match.group(2)}{match.group(3)}{match.group(4)}"
                elif len(match.groups()) == 1:
                    # Формат с одной группой
                    return f"+7{match.group(1)}"
        
        return None
    
    def _extract_name(self, message: str) -> Optional[str]:
        """
        Extract name from message (simple heuristic)
        
        Args:
            message: Message text
            
        Returns:
            Name if found, None otherwise
        """
        # Удаляем номер телефона из сообщения для поиска имени
        phone = self._extract_phone_number(message)
        if phone:
            message = message.replace(phone, '').strip()
        
        # Ищем слова с заглавной буквы (возможные имена)
        words = message.split()
        names = []
        
        for word in words:
            # Убираем знаки препинания
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 1:
                # Проверяем, что это не служебные слова
                if clean_word.lower() not in ['привет', 'здравствуйте', 'добрый', 'доброе', 'просто', 'текст', 'без', 'имени', 'телефона', 'номер', 'мой', 'ваш', 'наш']:
                    names.append(clean_word)
        
        if names:
            return ' '.join(names[:2])  # Возвращаем максимум 2 слова (имя и фамилия)
        
        return None
    
    def _is_first_message_with_phone(self, user_id: int, message_text: str) -> bool:
        """
        Check if this is the first message from user containing a phone number
        
        Args:
            user_id: User ID
            message_text: Message text
            
        Returns:
            True if this is first message with phone number
        """
        # Проверяем, есть ли номер телефона в сообщении
        phone = self._extract_phone_number(message_text)
        if not phone:
            return False
        
        # Проверяем, есть ли история диалога
        message_history = self.conversation_manager.get_message_history(user_id)
        
        # Если это первое сообщение (история пустая или содержит только текущее сообщение)
        if len(message_history) <= 1:
            return True
        
        return False
    
    def _handle_first_message_with_phone(self, user_id: int, message_text: str) -> Dict[str, Any]:
        """
        Handle first message from user containing a phone number
        
        Args:
            user_id: User ID
            message_text: Message text
            
        Returns:
            Response dictionary
        """
        # Извлекаем номер телефона и имя из сообщения
        phone = self._extract_phone_number(message_text)
        name = self._extract_name(message_text)
        
        # Если имя не найдено в сообщении, пытаемся получить из VK API
        if not name:
            name = self._get_vk_user_name(user_id)
        
        # Если имя все еще не найдено, используем "Клиент"
        if not name:
            name = "Клиент"
        
        # Сохраняем данные пользователя в базу данных
        try:
            # Обновляем или создаем пользователя с телефоном
            user_data = self.db.get_user_data(user_id)
            if user_data:
                # Обновляем существующего пользователя
                self.db.update_user_phone(user_id, phone)
            else:
                # Создаем нового пользователя
                self.db.create_user(user_id, name, phone, None)
        except Exception as e:
            self.logger.error(f"Error saving user data: {e}")
        
        # Формируем ответ согласно требованиям
        response = f"Здравствуйте, {name}! Укажите удобное время для звонка с 10.00 до 18.00 в любой будний день. Менеджер обязательно с Вами свяжется."
        
        # Добавляем сообщение бота в историю
        self.conversation_manager.add_message(user_id, "bot", response)
        
        # Логируем успешный ответ
        self.db.log_successful_ai_response(user_id, message_text, response)
        
        return {
            'text': response,
            'keyboard': self.keyboard_generator.generate_main_menu()
        }
    
    def _get_vk_user_name(self, user_id: int) -> Optional[str]:
        """
        Get user name from VK API
        
        Args:
            user_id: VK user ID
            
        Returns:
            User name or None if not found
        """
        try:
            # Инициализируем VK API
            vk_session = vk_api.VkApi(token=VK_TOKEN)
            vk = vk_session.get_api()
            
            # Получаем информацию о пользователе
            user_info = vk.users.get(user_ids=user_id, fields='first_name,last_name')
            
            if user_info and len(user_info) > 0:
                user = user_info[0]
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                
                # Формируем полное имя
                if first_name and last_name:
                    return f"{first_name} {last_name}"
                elif first_name:
                    return first_name
                elif last_name:
                    return last_name
                else:
                    return None
            else:
                return None
                
        except VkApiError as e:
            self.logger.error(f"VK API error getting user info for {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting user info from VK for {user_id}: {e}")
            return None

    def _is_admin_command(self, message: str) -> bool:
        """
        Check if message is an admin command
        
        Args:
            message: Message text
            
        Returns:
            True if message is an admin command
        """
        message = message.strip()
        return message.startswith('/add ') or message.startswith('/del ')

    def _handle_admin_command(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Handle admin commands (/add, /del)
        
        Args:
            user_id: User ID
            message: Message text
            
        Returns:
            Response dictionary
        """
        # Проверяем, является ли пользователь администратором
        if not self._is_admin(user_id):
            return {
                'text': "У вас нет прав для выполнения административных команд.",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        message = message.strip()
        
        # Обрабатываем команду /add
        if message.startswith('/add '):
            return self._handle_add_admin_command(user_id, message)
        
        # Обрабатываем команду /del
        elif message.startswith('/del '):
            return self._handle_del_admin_command(user_id, message)
        
        else:
            return {
                'text': "Неизвестная административная команда. Используйте /add <ID> или /del <ID>",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }

    def _handle_add_admin_command(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Handle /add admin command
        
        Args:
            user_id: User ID of the command sender
            message: Full message text
            
        Returns:
            Response dictionary
        """
        try:
            # Извлекаем ID из команды
            parts = message.split()
            if len(parts) != 2:
                return {
                    'text': "Неверный формат команды. Используйте: /add <VK_ID>",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            target_vk_id = int(parts[1])
            
            # Проверяем, что ID положительный
            if target_vk_id <= 0:
                return {
                    'text': "VK ID должен быть положительным числом.",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            # Получаем имя пользователя из VK API
            user_name = self._get_vk_user_name(target_vk_id)
            if not user_name:
                user_name = "Неизвестный пользователь"
            
            # Проверяем, существует ли пользователь в базе
            existing_user = self.db.session.query(self.db.User).filter_by(vk_id=target_vk_id).first()
            
            if existing_user:
                # Пользователь существует, обновляем статус администратора
                existing_user.is_admin = True
                if not existing_user.name:
                    existing_user.name = user_name
                self.db.session.commit()
                response = f"✅ Пользователь {user_name} (ID: {target_vk_id}) назначен администратором"
            else:
                # Создаем нового пользователя-администратора
                new_admin = self.db.User(
                    vk_id=target_vk_id,
                    name=user_name,
                    is_admin=True
                )
                self.db.session.add(new_admin)
                self.db.session.commit()
                response = f"✅ Создан новый администратор {user_name} (ID: {target_vk_id})"
            
            self.logger.info(f"Admin {user_id} added admin {target_vk_id} ({user_name})")
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
            
        except ValueError:
            return {
                'text': "VK ID должен быть числом. Используйте: /add <VK_ID>",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        except Exception as e:
            self.logger.error(f"Error adding admin {target_vk_id}: {e}")
            self.db.session.rollback()
            return {
                'text': f"❌ Ошибка при добавлении администратора: {str(e)}",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }

    def _handle_del_admin_command(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Handle /del admin command
        
        Args:
            user_id: User ID of the command sender
            message: Full message text
            
        Returns:
            Response dictionary
        """
        try:
            # Извлекаем ID из команды
            parts = message.split()
            if len(parts) != 2:
                return {
                    'text': "Неверный формат команды. Используйте: /del <VK_ID>",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            target_vk_id = int(parts[1])
            
            # Проверяем, что ID положительный
            if target_vk_id <= 0:
                return {
                    'text': "VK ID должен быть положительным числом.",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            # Проверяем, не пытается ли пользователь удалить сам себя
            if target_vk_id == user_id:
                return {
                    'text': "❌ Вы не можете удалить права администратора у самого себя.",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            # Ищем пользователя в базе
            user = self.db.session.query(self.db.User).filter_by(vk_id=target_vk_id).first()
            
            if not user:
                return {
                    'text': f"❌ Пользователь с ID {target_vk_id} не найден в базе данных.",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            if not user.is_admin:
                return {
                    'text': f"❌ Пользователь {user.name or target_vk_id} не является администратором.",
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
            
            # Удаляем права администратора
            user.is_admin = False
            self.db.session.commit()
            
            user_name = user.name or f"ID: {target_vk_id}"
            response = f"✅ Права администратора удалены у пользователя {user_name}"
            
            self.logger.info(f"Admin {user_id} removed admin rights from {target_vk_id} ({user_name})")
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
            
        except ValueError:
            return {
                'text': "VK ID должен быть числом. Используйте: /del <VK_ID>",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        except Exception as e:
            self.logger.error(f"Error removing admin {target_vk_id}: {e}")
            self.db.session.rollback()
            return {
                'text': f"❌ Ошибка при удалении прав администратора: {str(e)}",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }