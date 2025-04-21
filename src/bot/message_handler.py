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
        self.logger.info(f"Обработка сообщения: '{message_text}'. Payload: {payload}")
        # Добавляем запись пользователя в БД, если его ещё нет
        if not self.db.get_user(user_id):
            self.logger.info(f"Новый пользователь {user_id} добавлен в базу данных")
            self.db.add_user(user_id)
        
        # Обновляем последнее сообщение пользователя и время активности
        self.db.update_user_last_message(user_id, message_text)
        
        # Получаем контекст диалога с пользователем
        conversation_state = self.conversation_manager.get_conversation_state(user_id)
        self.logger.debug(f"Состояние диалога для пользователя {user_id}: {conversation_state}")
        
        # Получаем последние сообщения пользователя для определения контекста
        last_messages = self.conversation_manager.get_messages(user_id, limit=5)
        last_context = self._extract_context_from_messages(last_messages)
        
        # Проверяем, нет ли повторяющихся ответов "да"
        message_lower = message_text.lower().strip()
        
        # Получаем последние два сообщения бота для проверки повторов
        bot_messages = [msg for msg in last_messages if msg.get("role") == "bot"]
        if len(bot_messages) >= 2 and message_lower in ["да", "хочу", "конечно", "давай"]:
            last_bot_message = bot_messages[-1].get("text", "")
            prev_bot_message = bot_messages[-2].get("text", "") if len(bot_messages) > 1 else ""
            
            # Если последние два сообщения бота идентичны, значит мы повторяемся
            if last_bot_message.strip() == prev_bot_message.strip():
                # Переходим к следующему шагу вместо повтора
                if "записаться на экскурсию" in last_bot_message or "записаться на консультацию" in last_bot_message:
                    response = "Отлично! Для записи на экскурсию или консультацию нам понадобится немного информации. Как вас зовут (ФИО)?"
                    self.conversation_manager.update_stage(user_id, "consultation_name")
                    self.conversation_manager.add_message(user_id, "user", message_text)
                    self.conversation_manager.add_message(user_id, "bot", response)
                    return {
                        'text': response,
                        'keyboard': self.keyboard_generator.generate_back_button()
                    }
                elif "узнать подробнее" in last_bot_message:
                    # Даем информацию о конкретных предметах, если ранее спрашивали о программе
                    if "программ" in last_bot_message or "образовательн" in last_bot_message:
                        response = "Давайте расскажу подробнее о нашем подходе к обучению. Для пятиклассников мы предлагаем:\n\n• Углубленное изучение математики с российскими и международными методиками\n• Интенсивный курс английского языка (6 часов в неделю)\n• Дополнительные часы по русскому языку и литературе\n• Проектную деятельность для развития исследовательских навыков\n• Профессиональную психологическую поддержку при адаптации к средней школе\n• Внеурочную активность по выбору (спорт, творчество, программирование)\n\nУ каждого ученика есть собственный тьютор, который помогает в организации учебного процесса. Хотите узнать о каком-то предмете подробнее?"
                        self.conversation_manager.add_message(user_id, "user", message_text)
                        self.conversation_manager.add_message(user_id, "bot", response)
                        return {
                            'text': response,
                            'keyboard': self.keyboard_generator.generate_main_menu()
                        }
        
        # Проверяем, если пользователь согласился на предложение записаться на экскурсию
        if message_lower in ["да", "хочу", "конечно", "давай", "запишите", "запишусь", "хочу записаться", "записаться", "запись", "да, давайте"]:
            # Проверяем, не находится ли пользователь уже в процессе сбора данных для консультации
            current_stage = self.conversation_manager.get_stage(user_id)
            if current_stage in ["consultation_name", "consultation_child_info", "consultation_wishes"]:
                # Пользователь уже в процессе записи на консультацию, продолжаем текущий процесс
                # В этом случае вернем текущее сообщение для соответствующего этапа
                return self._handle_conversation_stage(user_id, message_text, current_stage)
                
            # Проверяем, есть ли у нас уже данные о пользователе в базе
            user_data = self.db.get_user_data(user_id) or self.excel_handler.get_user(user_id)
            
            # Если у нас уже есть данные о пользователе, устанавливаем имя и переходим к следующему шагу
            if user_data and user_data.get('name'):
                # Устанавливаем сохраненные данные в conversation_manager
                self.conversation_manager.add_data(user_id, "name", user_data['name'])
                
                # Сразу переходим к запросу информации о ребенке
                self.conversation_manager.update_stage(user_id, "consultation_child_info")
                response = f"Отлично, {user_data['name']}! Укажите, пожалуйста, возраст и класс ребенка:"
                
                self.conversation_manager.add_message(user_id, "user", message_text)
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    'text': response,
                    'keyboard': self.keyboard_generator.generate_back_button()
                }
            
            # Сначала проверяем, не было ли предложения записаться в предыдущих сообщениях бота
            for msg in reversed(bot_messages):
                bot_message = msg.get("text", "").lower()
                # Если предыдущее сообщение бота содержало приглашение на экскурсию
                if any(word in bot_message for word in ["экскурсию", "пробное занятие", "консультацию", "запись", "записаться"]):
                    response = "Отлично! Для записи нам понадобится немного информации. Как вас зовут (ФИО)?"
                    self.conversation_manager.update_stage(user_id, "consultation_name")
                    self.conversation_manager.add_message(user_id, "user", message_text)
                    self.conversation_manager.add_message(user_id, "bot", response)
                    return {
                        'text': response,
                        'keyboard': self.keyboard_generator.generate_back_button()
                    }
            
            # Если нет контекста, но пользователь хочет записаться
            response = "Хорошо! Для записи на консультацию или экскурсию нам понадобится немного информации. Как вас зовут (ФИО)?"
            self.conversation_manager.update_stage(user_id, "consultation_name")
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_back_button()
            }
        
        # Прямые запросы на запись или консультацию
        if any(record_word in message_lower for record_word in ["запись", "консультация", "консультацию", "записаться", "экскурсия", "экскурсию", "пробное занятие", "запишите меня"]):
            response = "Отлично! Для записи нам понадобится немного информации. Как вас зовут (ФИО)?"
            self.conversation_manager.update_stage(user_id, "consultation_name")
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_back_button()
            }
        
        # Обрабатываем payload, если он есть
        if payload:
            try:
                payload_dict = json.loads(payload)
                self.logger.info(f"Обработка payload: {payload_dict}")
                
                if 'action' in payload_dict:
                    action = payload_dict['action']
                    
                    # Обрабатываем различные действия из payload
                    if action == 'add_faq':
                        return self._handle_add_faq_action(user_id)
                    
                    elif action == 'add_knowledge':
                        return self._handle_add_knowledge_action(user_id)
                    
                    elif action == 'start_excel_upload':
                        return self._handle_excel_upload_action(user_id)
                    
                    elif action == 'cancel':
                        return self._handle_cancel_action(user_id)
                    
                    elif action == 'show_faq':
                        return self._handle_show_faq_action()
                
            except json.JSONDecodeError:
                self.logger.error(f"Неверный формат payload: {payload}")
        
        # Проверяем, находится ли пользователь в процессе добавления FAQ
        if conversation_state.get('state') == 'adding_faq_question':
            self.logger.info(f"Пользователь {user_id} добавляет вопрос FAQ")
            return self._handle_faq_question_input(user_id, message_text)
        
        elif conversation_state.get('state') == 'adding_faq_answer':
            self.logger.info(f"Пользователь {user_id} добавляет ответ FAQ")
            return self._handle_faq_answer_input(user_id, message_text)
        
        # Проверяем, находится ли пользователь в процессе добавления знаний
        elif conversation_state.get('state') == 'adding_knowledge_question':
            self.logger.info(f"Пользователь {user_id} добавляет вопрос в базу знаний")
            return self._handle_knowledge_question_input(user_id, message_text)
        
        elif conversation_state.get('state') == 'adding_knowledge_answer':
            self.logger.info(f"Пользователь {user_id} добавляет ответ в базу знаний")
            return self._handle_knowledge_answer_input(user_id, message_text)
        
        # Проверяем, находится ли пользователь в процессе загрузки Excel
        elif conversation_state.get('state') == 'uploading_excel':
            self.logger.info(f"Пользователь {user_id} загружает Excel файл")
            return self._handle_excel_file_upload(user_id, message_text)
        
        # Специальная обработка коротких запросов о школе или детском саде
        message_lower = message_text.lower().strip()
        
        # Проверяем на запрос подробной информации
        is_detailed_request = any(detail_word in message_lower for detail_word in 
                                ["подробн", "детальн", "расскаж", "подробнее", "детальнее", "расскажи", "больше", "подробности"])
        
        # Обработка простого согласия "да", "хочу", "конечно" в контексте предыдущего сообщения о школе/садике
        simple_agreement = message_lower in ["да", "хочу", "конечно", "интересно", "интересует", "узнать", "хотим", "давай"]
        if simple_agreement and last_context:
            # Если в последнем сообщении бота содержится фраза "хотите записаться"
            if len(bot_messages) > 0:
                last_bot_msg = bot_messages[-1].get("text", "").lower()
                if "хотите записаться" in last_bot_msg or "запись" in last_bot_msg or "записаться" in last_bot_msg:
                    response = "Отлично! Для записи на экскурсию или консультацию нам понадобится немного информации. Как вас зовут (ФИО)?"
                    self.conversation_manager.update_stage(user_id, "consultation_name")
                    self.conversation_manager.add_message(user_id, "user", message_text)
                    self.conversation_manager.add_message(user_id, "bot", response)
                    return {
                        'text': response,
                        'keyboard': self.keyboard_generator.generate_back_button()
                    }
                
            if "школа" in last_context:
                is_detailed_request = True
                message_lower = "о школе подробнее"
            elif "сад" in last_context or "садик" in last_context:
                is_detailed_request = True
                message_lower = "о садике подробнее"
            elif "программ" in last_context:
                is_detailed_request = True
                message_lower = "о программах подробнее"
            elif "стоимост" in last_context or "цен" in last_context:
                is_detailed_request = True
                message_lower = "о стоимости подробнее"
        
        # Обработка прямого запроса "расскажи подробнее" без указания темы
        if is_detailed_request and not any(topic in message_lower for topic in ["школ", "сад", "программ", "стоимост", "цен"]):
            if "школа" in last_context:
                message_lower = "о школе подробнее"
            elif "сад" in last_context or "садик" in last_context:
                message_lower = "о садике подробнее"
            elif "программ" in last_context:
                message_lower = "о программах подробнее"
            elif "стоимост" in last_context or "цен" in last_context:
                message_lower = "о стоимости подробнее"
        
        # Запросы о школе
        if any(school_word in message_lower for school_word in ["школа", "про школу", "о школе", "школьное", "школьник", "школьное образование"]):
            if is_detailed_request:
                response = "Частная школа «Академия знаний» предлагает качественное образование для детей с 1 по 11 класс. Наши основные преимущества:\n\n• Маленькие классы до 15 человек, что позволяет уделить внимание каждому ребенку\n• Индивидуальный подход к обучению с учетом особенностей и интересов каждого ученика\n• Углубленное изучение английского языка с профессиональными педагогами\n• Современное техническое оснащение классов и лабораторий\n• Расширенная программа по основным предметам\n• Дополнительные занятия по робототехнике, программированию, искусству\n• Квалифицированные педагоги с большим опытом работы\n• Психологическое сопровождение учебного процесса\n• Сбалансированное 5-разовое питание\n• Комфортные и безопасные условия обучения\n\nХотите записаться на экскурсию по школе или пробное занятие, чтобы увидеть всё своими глазами?"
            else:
                response = "Частная школа «Академия знаний» предлагает качественное образование для детей с 1 по 11 класс. У нас небольшие классы (до 15 человек), индивидуальный подход к каждому ученику, углубленное изучение английского языка, современная образовательная среда. Хотите узнать подробнее о программе обучения или записаться на экскурсию по школе?"
            
            self.db.log_successful_kb_response(user_id, message_text, response)
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Запросы о детском саде    
        if any(kindergarten_word in message_lower for kindergarten_word in ["сад", "детский сад", "садик", "про сад", "о садике", "дошкольное"]):
            if is_detailed_request:
                response = "Детский сад «Академик» - это комфортное и безопасное пространство для развития детей от 1.5 до 7 лет. Наша программа включает:\n\n• Развивающие занятия, адаптированные под возраст детей\n• Подготовку к школе для старших групп\n• Творческие мастерские (рисование, лепка, аппликация)\n• Музыкальные занятия и хореографию\n• Изучение английского языка в игровой форме\n• Спортивные мероприятия и активные игры\n• Индивидуальный подход к каждому ребенку\n• Пятиразовое сбалансированное питание с учетом индивидуальных потребностей\n• Просторные, светлые и уютные помещения\n• Собственную закрытую территорию для прогулок\n• Квалифицированных воспитателей с педагогическим образованием\n• Медицинское сопровождение\n\nХотите записаться на экскурсию, чтобы познакомиться с нашим садом и воспитателями?"
            else:
                response = "Детский сад «Академик» принимает детей от 1.5 до 7 лет. У нас создана уютная и безопасная среда для развития малышей, работают опытные воспитатели, проводятся развивающие занятия, подготовка к школе, творческие мастерские. Питание 5-разовое, учитываем индивидуальные особенности. Хотите узнать подробнее о программе или записаться на экскурсию?"
            
            self.db.log_successful_kb_response(user_id, message_text, response)
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Запросы о программах обучения
        if any(program_word in message_lower for program_word in ["программ", "курс", "направлен", "занятия", "уроки", "предмет"]):
            if is_detailed_request:
                response = "В «Академии знаний» представлены следующие образовательные программы:\n\n• Начальная школа (1-4 классы): развитие базовых навыков чтения, письма, счета, логического мышления, творческого потенциала\n• Средняя школа (5-9 классы): углубленное изучение основных предметов, профориентация, развитие критического мышления\n• Старшая школа (10-11 классы): подготовка к ЕГЭ, профильное обучение по выбранным направлениям\n\nВсе ученики изучают основные предметы школьной программы:\n• Русский язык и литература\n• Математика, алгебра, геометрия\n• История и обществознание\n• География\n• Биология, химия, физика\n• Информатика\n• Английский язык (углубленное изучение)\n• Физическая культура\n• Технология и искусство\n\nДополнительные программы:\n• Робототехника и программирование\n• Математический клуб\n• Лингвистический центр (английский, немецкий, китайский языки)\n• Художественная студия\n• Музыкальная школа\n• Спортивные секции\n\nДля 5-классников у нас особое внимание уделяется адаптации при переходе в среднюю школу и развитию самостоятельности. Хотите записаться на индивидуальную консультацию с завучем для обсуждения программы 5 класса?"
            else:
                response = "В нашей школе представлены все основные предметы школьной программы: русский язык и литература, математика, история, география, биология, химия, физика, информатика, английский язык (углубленно), физкультура, технология и искусство. Также есть дополнительные занятия: робототехника, программирование, математический клуб, языковые курсы, художественная студия, музыка и спорт. Хотите узнать подробнее о программе для конкретного класса?"
            
            self.db.log_successful_kb_response(user_id, message_text, response)
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Запросы о стоимости
        if any(cost_word in message_lower for cost_word in ["стоимост", "цен", "оплат", "сколько стоит", "платить"]):
            if is_detailed_request:
                response = "Стоимость обучения в Академии знаний зависит от выбранной программы:\n\n• Начальная школа (1-4 классы): от 35 000 руб./месяц\n• Средняя школа (5-9 классы): от 38 000 руб./месяц\n• Старшая школа (10-11 классы): от 42 000 руб./месяц\n\nВ стоимость включено:\n• Обучение по основной программе\n• Питание (5-разовое)\n• Продленка до 19:00\n• Базовые дополнительные занятия\n\nДетский сад «Академик»:\n• Группа полного дня (7:30-19:30): от 33 000 руб./месяц\n• Группа неполного дня (до 15:00): от 27 000 руб./месяц\n\nТакже доступны скидки при записи двух и более детей из одной семьи. Хотите записаться на консультацию для обсуждения индивидуальных условий?"
                self.db.log_successful_kb_response(user_id, message_text, response)
                self.conversation_manager.add_message(user_id, "user", message_text)
                self.conversation_manager.add_message(user_id, "bot", response)
                return {
                    'text': response,
                    'keyboard': self.keyboard_generator.generate_main_menu()
                }
        
        # Проверяем на приветствие
        if self._is_greeting(message_text):
            self.logger.info(f"Обнаружено приветствие от пользователя {user_id}")
            response = self._generate_greeting_response()
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Определяем интент сообщения
        self.logger.info(f"Определение интента для сообщения: '{message_text}'")
        intent = self.ai_handler.detect_intent(message_text)
        self.logger.info(f"Определен интент: {intent}")
        
        # Специальная обработка запросов о возможностях бота
        message_lower = message_text.lower()
        bot_abilities_phrases = ["что ты", "какие у тебя", "твои возможности", "что умеешь", "можешь делать", 
                               "кто ты", "расскажи о себе", "что ты можешь", "твои функции", "какие функции", 
                               "что делаешь", "помоги", "помочь", "как общаться", "твоя задача", "твое назначение"]
        
        if any(phrase in message_lower for phrase in bot_abilities_phrases):
            self.logger.info(f"Определен запрос о возможностях бота")
            response = "Могу рассказать о программах обучения в Академии знаний, помочь с записью на консультацию или мероприятие, предоставить информацию о школе и детском саде. Отвечу на вопросы о стоимости, расписании, педагогах, питании, дополнительных занятиях. Также помогу записаться на пробное занятие или экскурсию по школе и детскому саду. Какое направление обучения вас интересует?"
            
            self.db.log_successful_kb_response(user_id, message_text, response)
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", response)
            
            return {
                'text': response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Проверяем базу знаний на наличие ответа
        self.logger.info(f"Поиск ответа в базе знаний для: '{message_text}'")
        kb_response = self.knowledge_base.get_response(message_text, min_ratio=0.65)
        
        if kb_response:
            self.logger.info(f"Найден ответ в базе знаний")
            # Записываем успешный ответ из базы знаний
            self.db.log_successful_kb_response(user_id, message_text, kb_response)
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", kb_response)
            
            # Возвращаем ответ с клавиатурой
            return {
                'text': kb_response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        
        # Если ответ не найден в базе знаний, генерируем ответ с помощью ИИ
        self.logger.info(f"Ответ не найден в БЗ, генерация ответа с помощью ИИ")
        try:
            ai_response = self.ai_handler.generate_response(message_text, self.conversation_manager.get_message_history(user_id))
            
            # Записываем успешный ответ от ИИ
            self.db.log_successful_ai_response(user_id, message_text, ai_response)
            self.conversation_manager.add_message(user_id, "user", message_text)
            self.conversation_manager.add_message(user_id, "bot", ai_response)
            
            return {
                'text': ai_response,
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
        except Exception as e:
            self.logger.error(f"Ошибка при генерации ответа ИИ: {e}")
            return {
                'text': "Извините, у меня возникла проблема с генерацией ответа. Пожалуйста, попробуйте задать вопрос по-другому или немного позже.",
                'keyboard': self.keyboard_generator.generate_main_menu()
            }
    
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
                # Метод для сохранения консультации
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
                context += " " + msg.get("text", "")
                
        return context.lower() 