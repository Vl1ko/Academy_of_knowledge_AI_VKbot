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
from src.ai.rag_singleton import RAGSingleton


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
        
        # Initialize RAG singleton
        self.rag = RAGSingleton()
        
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
        
        # Greeting patterns
        if any(word in message for word in ["привет", "здравствуй", "добрый", "доброе утро", "добрый день", "добрый вечер"]):
            return "greeting"
            
        # Question patterns
        if any(word in message for word in ["как", "где", "когда", "сколько", "какой", "какая", "какие", "что", "чем", "кто", "почему"]):
            return "question"
            
        # Registration patterns
        if any(word in message for word in ["запись", "записаться", "поступить", "зачислить", "регистрация"]):
            return "registration"
            
        # Consultation patterns
        if any(word in message for word in ["консультация", "проконсультировать", "посоветовать", "помочь", "помощь"]):
            return "consultation"
            
        # Event patterns
        if any(word in message for word in ["мероприятие", "событие", "праздник", "концерт", "выступление"]):
            return "event"
            
        # Feedback patterns
        if any(word in message for word in ["отзыв", "жалоба", "претензия", "благодарность", "спасибо"]):
            return "feedback"
            
        return "other"
    
    def _prepare_system_prompt(self, message_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Prepare system prompt for the model
        
        Args:
            message_history: Optional list of previous messages
            
        Returns:
            System prompt string
        """
        base_prompt = """Ты — живой, дружелюбный помощник школы и детского сада «Академик». Помогай родителям, отвечай по делу и по‑человечески.

Как общаться:
- Пиши естественно, без канцелярита и без шаблонных заголовков. Не используй разделители вроде «Короткий ответ», «Подробный ответ», «1., 2.» и т. п.
- Не используй Markdown. Текст — обычный, с короткими абзацами; списки — простые маркеры без нумерации, только если это реально помогает.
- Приветствуйся только в самом начале диалога и только уместно. Не начинай каждый ответ с «Здравствуйте!», если пользователь уже задал вопрос.
- Если точного ответа нет — честно скажи об этом и предложи связаться с администратором.
- Держи тон вежливым и человеческим; избегай повторов и излишней формальности.
- Показывай только релевантные цены из базы знаний. Если данных не хватает — попроси уточнить запрос.
 - Используй информацию именно «Академии знаний» / «Академика». Не давай общих советов про сторонние школы/центры и не перенаправляй к ним.

Как строить ответы:
- Дай прямой ответ на вопрос в 1–2 коротких предложениях.
- Добавь важные детали. Если удобно, оформи их ненумерованным списком.
- Заверши уместным уточняющим вопросом или мягким предложением записаться на консультацию/экскурсию.

Особые случаи:
- Если вопрос про поступление в 6–7 лет, фокусируйся на 1 классе нашей школы: стоимость, что входит, режим (время), наличие мест. В конце — приглашение на экскурсию или к записи/консультации. Не предлагай «другие школы» и не уходи в общие рассуждения.

Пример подачи (образец стиля, без заголовков и нумерации):
Стоимость обучения в 1 классе — 26100 рублей в месяц. В сумму входит пребывание с 8:00 до 18:00, углублённая программа, усиленный английский, выполнение домашнего задания в школе, прогулки и обратная связь для родителей. Питание оплачивается отдельно: «завтрак, обед, полдник» — 450 руб/день; «завтрак, обед, полдник, ужин» — 500 руб/день. Хотите, расскажу подробнее о программе или подскажу по записи?

Если спрашивают о стоимости — укажи точную цену из базы, что входит, и возможные доп. расходы. Если спрашивают о наличии мест — укажи актуальные места и предложи экскурсию или резерв при отсутствии мест.
"""

        if message_history:
            context = "\n\nИстория диалога:\n"
            for msg in message_history[-5:]:  # Only use last 5 messages for context
                role = "Пользователь" if msg["role"] == "user" else "Бот"
                context += f"{role}: {msg['content']}\n"
            base_prompt += context
            
        return base_prompt
    
    def generate_response(
        self,
        message: str,
        message_history: Optional[List[Dict[str, str]]] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Generate response using GigaChat API
        
        Args:
            message: User message
            message_history: Optional list of previous messages
            additional_context: Optional additional context from RAG
            
        Returns:
            Generated response
        """
        if not self.client_id or not self.client_secret or not GIGACHAT_SDK_AVAILABLE:
            self.logger.warning("API key missing or SDK not available, using fallback")
            return self._fallback_response(message)
            
        try:
            self._wait_for_rate_limit()
            
            # Get relevant context from RAG
            rag_response, relevant_docs = self.rag.get_rag_response(message)
            if rag_response:
                if additional_context:
                    additional_context = f"{additional_context}\n\nРелевантная информация из базы знаний:\n{rag_response}"
                else:
                    additional_context = f"Релевантная информация из базы знаний:\n{rag_response}"
            
            system_prompt = self._prepare_system_prompt(message_history)
            if additional_context:
                system_prompt += f"\n\nДополнительный контекст:\n{additional_context}"
            
            messages = [
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=system_prompt
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=message
                )
            ]
            
            # Add message history if available
            if message_history:
                for msg in message_history[-5:]:  # Only use last 5 messages
                    role = MessagesRole.USER if msg["role"] == "user" else MessagesRole.ASSISTANT
                    messages.append(Messages(role=role, content=msg["content"]))
            
            chat = Chat(
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            self.logger.info("Sending request to GigaChat API")
            response = self.giga.chat(chat)
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return self._fallback_response(message)
    
    def _fallback_response(self, message: str) -> str:
        """
        Generate fallback response when API is not available
        
        Args:
            message: User message
            
        Returns:
            Fallback response
        """
        # Try to get response from RAG first
        try:
            rag_response, _ = self.rag.get_rag_response(message)
            if rag_response:
                return rag_response
        except Exception as e:
            self.logger.error(f"Error getting RAG response: {e}")
        
        return "Извините, я не могу сейчас дать точный ответ на ваш вопрос. Предлагаю записаться на консультацию с нашим администратором, который сможет подробно ответить на все ваши вопросы. Хотите записаться на консультацию?"