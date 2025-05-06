import json
import logging
import os
import time
import base64
import requests
from typing import List, Dict, Any, Optional

try:
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole
    GIGACHAT_SDK_AVAILABLE = True
except ImportError:
    GIGACHAT_SDK_AVAILABLE = False

from dotenv import load_dotenv


class GigaChatHandler:
    """
    Handler for GigaChat API
    """
    
    def __init__(self):
        """
        Initialize the GigaChat handler
        """
        load_dotenv()
        self.logger = logging.getLogger(__name__)
        
        # Get credentials from environment
        self.client_id = os.getenv("GIGACHAT_CLIENT_ID")
        self.client_secret = os.getenv("GIGACHAT_CLIENT_SECRET")
        
        if not self.client_id or not self.client_secret:
            self.logger.warning("GIGACHAT_CLIENT_ID or GIGACHAT_CLIENT_SECRET not set in environment variables")
            return
            
        # Initialize GigaChat client
        try:
            # Create authorization header
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')
            
            self.giga = GigaChat(
                credentials=base64_auth,
                scope="GIGACHAT_API_PERS",
                verify_ssl_certs=False
            )
            self.logger.info("Successfully initialized GigaChat client")
        except Exception as e:
            self.logger.error(f"Error initializing GigaChat client: {e}")
            self.giga = None
        
        # Rate limiting settings
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum time between requests in seconds
        
        # Load knowledge base
        self.knowledge_base = self._load_knowledge_base()
        
        # Check if SDK is available
        if not GIGACHAT_SDK_AVAILABLE:
            self.logger.warning("GigaChat SDK not installed. Using fallback implementation.")
    
    def _get_access_token(self) -> str:
        """
        Get access token using client credentials
        """
        try:
            # Create authorization header
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': str(int(time.time())),
                'Authorization': f'Basic {base64_auth}'
            }
            
            data = {
                'scope': 'GIGACHAT_API_PERS'
            }
            
            self.logger.info(f"Attempting to get access token with client_id: {self.client_id[:5]}...")
            self.logger.debug(f"Request URL: {self.api_url}/oauth")
            self.logger.debug(f"Request headers: {headers}")
            self.logger.debug(f"Request data: {data}")
            
            response = requests.post(
                f"{self.api_url}/oauth",
                headers=headers,
                data=data,
                verify=False,
                timeout=30
            )
            
            self.logger.info(f"OAuth response status: {response.status_code}")
            self.logger.debug(f"OAuth response headers: {dict(response.headers)}")
            self.logger.debug(f"OAuth response body: {response.text}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.logger.info("Successfully obtained access token")
                return token_data['access_token']
            else:
                error_msg = f"Error getting access token: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.logger.error(f"Error in _get_access_token: {str(e)}")
            raise
    
    def _wait_for_rate_limit(self):
        """
        Wait if needed to respect rate limits
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def detect_intent(self, message: str) -> str:
        """
        Detect user intent from message
        
        Args:
            message: User message
            
        Returns:
            Intent category (greeting, question, registration, consultation, event, feedback, other)
        """
        # If GigaChat API is not available or SDK not installed, use simple rule-based detection
        if not self.client_id or not self.client_secret or not GIGACHAT_SDK_AVAILABLE:
            self.logger.warning("API key missing or SDK not available, using simple intent detection")
            return self._simple_intent_detection(message)
        
        try:
            self._wait_for_rate_limit()  # Add rate limiting
            self.logger.info(f"Определение интента для сообщения: {message}")
            prompt = f"""Определи категорию намерения пользователя на основе этого сообщения: "{message}"
            Выбери одну из следующих категорий:
            - greeting: приветствие, начало разговора
            - question: вопрос о школе, детском саде, программах
            - registration: запись в школу или детский сад
            - consultation: запрос на консультацию
            - event: вопрос о мероприятиях
            - feedback: отзыв или жалоба
            - other: другое
            
            Верни только название категории без дополнительных пояснений."""
            
            with GigaChatSDK(
                credentials=self._get_access_token(),
                base_url="https://gigachat.devices.sberbank.ru/api/v1",
                scope="GIGACHAT_API_PERS",
                verify_ssl_certs=False,
                verbose=True
            ) as giga:
                chat = Chat(
                    messages=[
                        Messages(
                            role=MessagesRole.SYSTEM,
                            content="Ты - помощник для определения намерений пользователей."
                        ),
                        Messages(
                            role=MessagesRole.USER,
                            content=prompt
                        )
                    ],
                    temperature=0.1,
                    max_tokens=10
                )
                
                self.logger.info("Отправка запроса в GigaChat API")
                response = giga.chat(chat)
                intent = response.choices[0].message.content.strip().lower()
                self.logger.info(f"Получен ответ от GigaChat API: {intent}")
                
                # Validate that we got a valid intent
                valid_intents = ["greeting", "question", "registration", "consultation", "event", "feedback", "other"]
                if intent in valid_intents:
                    return intent
                else:
                    self.logger.warning(f"Invalid intent from API: '{intent}', using fallback")
                    return self._simple_intent_detection(message)
                
        except Exception as e:
            self.logger.error(f"Error detecting intent: {e}")
            return self._simple_intent_detection(message)
    
    def _simple_intent_detection(self, message: str) -> str:
        """
        Simple rule-based intent detection
        
        Args:
            message: User message
            
        Returns:
            Intent category
        """
        message = message.lower()
        
        # Greeting detection
        greeting_phrases = ["привет", "здравствуй", "добрый день", "доброе утро", "добрый вечер", "hello", "hi"]
        if any(phrase in message for phrase in greeting_phrases) or len(message) < 10:
            return "greeting"
        
        # Registration detection
        registration_phrases = ["запис", "поступ", "зачисл", "прием", "принять", "подать заявл"]
        if any(phrase in message for phrase in registration_phrases):
            return "registration"
        
        # Consultation detection
        consultation_phrases = ["консультац", "посовет", "встреч", "пообщат", "обсуд"]
        if any(phrase in message for phrase in consultation_phrases):
            return "consultation"
        
        # Event detection
        event_phrases = ["мероприят", "событ", "праздник", "выступлен", "концерт", "собран"]
        if any(phrase in message for phrase in event_phrases):
            return "event"
        
        # Feedback detection
        feedback_phrases = ["отзыв", "мнени", "впечатл", "жалоб", "претензи", "понравил", "не понравил"]
        if any(phrase in message for phrase in feedback_phrases):
            return "feedback"
        
        # Question detection (default for longer messages)
        if "?" in message or len(message) > 20:
            return "question"
        
        # Default intent
        return "other"
    
    def _load_knowledge_base(self) -> Dict[str, Any]:
        """
        Load all knowledge base files
        """
        knowledge_base = {}
        base_path = "data/knowledge_base"
        
        try:
            # Load FAQ
            with open(f"{base_path}/faq.json", "r", encoding="utf-8") as f:
                knowledge_base["faq"] = json.load(f)
            
            # Load school info
            with open(f"{base_path}/school.json", "r", encoding="utf-8") as f:
                knowledge_base["school"] = json.load(f)
            
            # Load kindergarten info
            with open(f"{base_path}/kindergarten.json", "r", encoding="utf-8") as f:
                knowledge_base["kindergarten"] = json.load(f)
            
            # Load other knowledge files
            for file in ["schedule.json", "documents.json", "general.json"]:
                try:
                    with open(f"{base_path}/{file}", "r", encoding="utf-8") as f:
                        knowledge_base[file.replace(".json", "")] = json.load(f)
                except FileNotFoundError:
                    self.logger.warning(f"Knowledge base file {file} not found")
                
        except Exception as e:
            self.logger.error(f"Error loading knowledge base: {e}")
            
        return knowledge_base
    
    def _prepare_system_prompt(self, message_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Prepare system prompt for GigaChat"""
        return f"""Ты - дружелюбный и профессиональный ассистент частной школы "Академия знаний" в группе ВК. 
Твоя задача - помогать родителям получить информацию о школе и образовательных программах.

Источник информации:
{json.dumps(self.knowledge_base, ensure_ascii=False, indent=2)}

Контекст диалога:
{message_history}

Правила общения:
1. Если это первое сообщение в диалоге, то начинай с приветствия
2. Используй дружелюбный, но профессиональный тон
3. Отвечай развернуто и информативно
4. Используй эмодзи для выделения ключевых моментов
5. В конце каждого ответа всегда задавай уточняющий вопрос для продолжения диалога, на основе контекста

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
    
    def generate_response(self, message: str, message_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Generate response to user message using GigaChat
        """
        try:
            self.logger.info(f"Received message: {message}")
            self.logger.info(f"Message history: {message_history}")
            
            # Prepare context from history
            context = ""
            if message_history:
                for msg in message_history:
                    role = "assistant" if msg.get("role") == "bot" else "user"
                    text = msg.get("content", "")
                    if text:  # Add only non-empty messages
                        context += f"{role}: {text}\n"
            
            self.logger.info(f"Formed context: {context}")
            
            # Check if we need to add a greeting
            needs_greeting = True
            if message_history:
                for msg in message_history:
                    self.logger.info(f"Checking message: {msg}")
                    if msg.get("role") == "bot":
                        content = msg.get("content", "").lower()
                        self.logger.info(f"Bot message content: {content}")
                        if any(greeting in content for greeting in ["здравствуйте", "добрый день", "привет"]):
                            needs_greeting = False
                            self.logger.info("Found greeting in history, no need to add another one")
                            break
            
            self.logger.info(f"Needs greeting: {needs_greeting}")
            
            # Prepare system prompt with knowledge base
            system_prompt = self._prepare_system_prompt(message_history)
            
            user_prompt = f"""
            Контекст диалога:
            {context}

            Текущий запрос:
            "{message}"

            Сформируй оптимальный ответ, учитывая:
            1. НЕ добавляй приветствие, так как оно уже есть в контексте
            2. Используй информацию из базы знаний как основу, но генерируй уникальный ответ
            3. Полноту информации (все ключевые аспекты запроса)
            4. Точность данных (только проверенная информация)
            5. Естественность общения (дружелюбный профессиональный тон)
            6. В конце задай релевантный вопрос для продолжения диалога на основе контекста
            7. Используй информацию ТОЛЬКО из базы знаний, не придумывай информацию от себя
            8. Не используй форматирование в ответе, используй только текст
            """
            
            self.logger.info(f"User prompt: {user_prompt}")
            
            if not self.giga:
                raise Exception("GigaChat client not initialized")
            
            self._wait_for_rate_limit()
            
            chat = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.SYSTEM,
                        content=system_prompt
                    ),
                    Messages(
                        role=MessagesRole.USER,
                        content=user_prompt
                    )
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            self.logger.info("Sending request to GigaChat API")
            response = self.giga.chat(chat)
            
            generated_response = response.choices[0].message.content.strip()
            self.logger.info(f"Received response from GigaChat API: {generated_response}")
            
            # Remove greeting if it's not needed
            if not needs_greeting:
                # List of common greetings to remove
                greetings = ["добрый день", "доброе утро", "добрый вечер", "здравствуйте", "привет"]
                for greeting in greetings:
                    if generated_response.lower().startswith(greeting):
                        # Remove the greeting and any following punctuation
                        generated_response = generated_response[len(greeting):].lstrip("!,. ")
                        break
            
            self.logger.info(f"Final response after greeting check: {generated_response}")
            return generated_response
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return self._fallback_response(message)
    
    def _fallback_response(self, message: str) -> str:
        """
        Generate fallback response using knowledge base when API is not available
        """
        message_lower = message.lower()
        
        # Try to find relevant information in knowledge base
        for section in self.knowledge_base.values():
            if isinstance(section, dict):
                for key, value in section.items():
                    if isinstance(key, str) and key.lower() in message_lower:
                        return value
                    if isinstance(value, str) and value.lower() in message_lower:
                        return value
        
        # Default response if no relevant information found
        return "Извините, я не могу сейчас дать точный ответ на ваш вопрос. Предлагаю записаться на консультацию с нашим администратором, который сможет подробно ответить на все ваши вопросы. Хотите записаться на консультацию?"