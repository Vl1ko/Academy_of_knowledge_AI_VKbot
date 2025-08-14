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
        # Убираем приветствия из начала ответа
        lines = answer.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Пропускаем строки с приветствиями
                if any(greeting in line.lower() for greeting in ['здравствуйте', 'добрый день', 'доброе утро', 'добрый вечер', 'привет']):
                    continue
                cleaned_lines.append(line)
        
        # Объединяем строки без лишнего форматирования
        result = '\n'.join(cleaned_lines)
        
        # Убираем markdown форматирование
        result = re.sub(r'\*\*(.*?)\*\*', r'\1', result)  # Убираем **жирный**
        result = re.sub(r'\*(.*?)\*', r'\1', result)      # Убираем *курсив*
        result = re.sub(r'`(.*?)`', r'\1', result)        # Убираем `код`
        result = re.sub(r'#+\s*', '', result)             # Убираем заголовки
        result = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', result)  # Убираем ссылки
        
        # Удаляем подряд идущие дублирующиеся строки (повторяющиеся пункты)
        deduped_lines = []
        seen_prev = None
        for ln in result.split('\n'):
            if ln != seen_prev:
                deduped_lines.append(ln)
            seen_prev = ln
        result = '\n'.join(deduped_lines)

        # Сжимаем лишние пустые строки (не более одной подряд)
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result
    
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