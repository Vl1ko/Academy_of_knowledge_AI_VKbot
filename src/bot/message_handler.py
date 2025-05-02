import logging
import json
from typing import Dict, List, Any, Optional
import re

from src.ai.gigachat_handler import GigaChatHandler
from src.database.db_handler import DatabaseHandler
from src.bot.knowledge_base import KnowledgeBase
from src.bot.conversation_manager import ConversationManager
from src.bot.keyboard_generator import KeyboardGenerator
from src.database.excel_handler import ExcelHandler


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
            # Не отправляем никаких сообщений, пока пользователь не нажмет "Завершить диалог"
            return None
        
        # Проверяем, находится ли пользователь в процессе заполнения формы
        if conversation_state.get('state') == 'consultation_form':
            return self._handle_consultation_form(user_id, message_text, conversation_state)
        
        # Проверяем запрос на консультацию
        if self._is_consultation_request(message_text):
            return self._start_consultation_form(user_id)
        
        # Проверяем запрос на помощь администратора
        if self._is_admin_help_request(message_text):
            return self._handle_admin_help_request(user_id, message_text)
        
        # Всегда используем GigaChat для генерации ответов
        try:
            # Получаем историю сообщений
            message_history = self.conversation_manager.get_message_history(user_id)
            self.logger.info(f"Retrieved message history for GigaChat: {message_history}")
            
            # Генерируем ответ с помощью GigaChat
            ai_response = self.ai_handler.generate_response(message_text, message_history)
            self.logger.info(f"Generated AI response: {ai_response}")
            
            # Добавляем сообщение бота в историю
            self.logger.info(f"Adding bot response to history: {ai_response}")
            self.conversation_manager.add_message(user_id, "bot", ai_response)
            
            # Логируем успешный ответ
            self.db.log_successful_ai_response(user_id, message_text, ai_response)
            
            return {
                'text': ai_response,
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
            "консультац", "записаться", "запись", "встреч", "обсуд",
            "хочу узнать", "хочу поговорить", "нужна помощь", "нужна консультация"
        ]
        return any(phrase in message for phrase in consultation_phrases)
    
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
            
            # Save consultation request
            name = state.get('data', {}).get('name', '')
            self.db.save_consultation_request(user_id, name, phone)
            
            # Notify admins
            self._notify_admins_about_consultation(name, phone)
            
            # Reset conversation state
            self.conversation_manager.reset_state(user_id)
            
            response = f"Спасибо за заявку! Мы свяжемся с вами в ближайшее время для подтверждения консультации."
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
    
    def _is_admin_help_request(self, message: str) -> bool:
        """Check if message is requesting admin help"""
        message = message.lower()
        help_phrases = [
            "оператор", "администратор", "менеджер", "помощь",
            "человек", "поговорить с человеком", "нужен человек",
            "свяжите с", "переключите на", "нужна помощь"
        ]
        return any(phrase in message for phrase in help_phrases)
    
    def _handle_admin_help_request(self, user_id: int, message: str) -> Dict[str, Any]:
        """Handle request for admin help"""
        # Disable AI for this user
        self.conversation_manager.disable_ai(user_id)
        
        # Notify admins
        self._notify_admins_about_help_request(user_id, message)
        
        return {
            'text': "Я перевожу Вас на администратора. Пожалуйста, подождите немного.",
            'keyboard': None
        }
    
    def _notify_admins_about_consultation(self, name: str, phone: str) -> None:
        """Notify admins about new consultation request"""
        admin_ids = self.db.get_admin_ids()
        message = f"Новая заявка на консультацию:\nИмя: {name}\nТелефон: {phone}"
        
        for admin_id in admin_ids:
            try:
                self.vk.messages.send(
                    user_id=admin_id,
                    message=message,
                    random_id=0
                )
            except Exception as e:
                self.logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")
    
    def _notify_admins_about_help_request(self, user_id: int, message: str) -> None:
        """Notify admins about help request"""
        admin_ids = self.db.get_admin_ids()
        notification = f"Пользователь {user_id} запросил помощь администратора.\nСообщение: {message}"
        
        for admin_id in admin_ids:
            try:
                self.vk.messages.send(
                    user_id=admin_id,
                    message=notification,
                    random_id=0
                )
            except Exception as e:
                self.logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")
    
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
            "Здравствуйте! Интересуетесь образовательными программами для вашего ребенка?",
            "Добрый день! Чем могу помочь в выборе образовательной программы для вашего ребенка?",
            "Приветствую! Расскажите, какое направление обучения вас интересует?",
            "Здравствуйте! Хотите узнать подробнее о наших образовательных программах?",
            "Здравствуйте! Рассматриваете варианты образования для вашего ребенка?"
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