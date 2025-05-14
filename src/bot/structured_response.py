import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import json
import logging
from pathlib import Path

class StructuredResponseHandler:
    """
    Класс для формирования структурированных ответов на основе базы знаний
    """
    
    def __init__(self, knowledge_base):
        """
        Инициализация обработчика структурированных ответов
        
        Args:
            knowledge_base: Экземпляр класса KnowledgeBase
        """
        self.logger = logging.getLogger(__name__)
        self.knowledge_base = knowledge_base
        
    def format_response(self, answer: str) -> str:
        """
        Форматирование ответа согласно требованиям
        
        Args:
            answer: Исходный ответ
            
        Returns:
            Отформатированный ответ
        """
        # Разделяем текст на абзацы
        paragraphs = [p.strip() for p in answer.split('\n') if p.strip()]
        
        # Форматируем каждый абзац
        formatted_paragraphs = []
        for p in paragraphs:
            # Если это список (начинается с - или •)
            if p.startswith(('-', '•', '✓', '✔', '✅')):
                formatted_paragraphs.append(p)
            # Если это цена
            elif re.search(r'\d+\s*(?:руб(?:лей)?|₽)', p, re.IGNORECASE):
                formatted_paragraphs.append(self._format_price_info(p))
            else:
                formatted_paragraphs.append(p)
        
        # Добавляем уточняющий вопрос в конце
        follow_up = self._get_follow_up_question(answer)
        if follow_up:
            formatted_paragraphs.append(f"\n{follow_up}")
            
        # Добавляем информацию о времени для звонка
        formatted_paragraphs.append("\nУкажите удобное время для звонка в будний день с 10:00 до 17:00")
        
        return "\n\n".join(formatted_paragraphs)
    
    def _format_price_info(self, text: str) -> str:
        """
        Форматирование информации о ценах
        
        Args:
            text: Текст с ценой
            
        Returns:
            Отформатированный текст
        """
        # Находим цену
        price_match = re.search(r'(\d+)\s*(?:руб(?:лей)?|₽)', text, re.IGNORECASE)
        if not price_match:
            return text
            
        price = price_match.group(1)
        
        # Форматируем информацию о том, что входит в стоимость
        includes = []
        if "включено" in text.lower() or "входит" in text.lower():
            includes_match = re.search(r'(?:включено|входит)[:\s]+(.*?)(?:\.|$)', text, re.IGNORECASE)
            if includes_match:
                includes = [item.strip() for item in includes_match.group(1).split(',')]
        
        # Формируем структурированный ответ
        result = [f"Стоимость: {price}₽"]
        if includes:
            result.append("В стоимость входит:")
            result.extend(f"• {item}" for item in includes)
            
        return "\n".join(result)
    
    def _get_follow_up_question(self, answer: str) -> Optional[str]:
        """
        Подбор уточняющего вопроса на основе контекста ответа
        
        Args:
            answer: Ответ, на основе которого подбирается уточняющий вопрос
            
        Returns:
            Уточняющий вопрос или None
        """
        # Анализируем контекст ответа
        lower_answer = answer.lower()
        
        if "стоимость" in lower_answer or "цена" in lower_answer:
            return "Хотите узнать подробнее о способах оплаты и действующих скидках?"
        elif "расписание" in lower_answer or "время" in lower_answer:
            return "Хотите узнать подробнее о конкретных днях и времени занятий?"
        elif "программа" in lower_answer or "занятия" in lower_answer:
            return "Интересует более подробная информация о программе обучения?"
        elif "документы" in lower_answer or "справка" in lower_answer:
            return "Подсказать, какие документы необходимо подготовить?"
        
        return "Есть ли у вас дополнительные вопросы?"
    
    def get_structured_response(self, query: str) -> Optional[str]:
        """
        Получение структурированного ответа на вопрос
        
        Args:
            query: Вопрос пользователя
            
        Returns:
            Структурированный ответ или None, если ответ не найден
        """
        # Получаем базовый ответ
        response = self.knowledge_base.get_response(query)
        if not response:
            # Пробуем поиск по частичному совпадению
            results = self.knowledge_base.search_knowledge(query, threshold=0.6)
            if results:
                response = results[0][2]  # Берем значение из первого результата
        
        if response:
            return self.format_response(response)
            
        return None 