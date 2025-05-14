from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import logging
from pathlib import Path
import re

class RAGHandler:
    """
    Retrieval Augmented Generation handler для улучшения качества ответов
    """
    
    def __init__(self, knowledge_base_dir: str = "data/knowledge_base"):
        """
        Инициализация RAG обработчика
        
        Args:
            knowledge_base_dir: Директория с файлами базы знаний
        """
        self.logger = logging.getLogger(__name__)
        self.knowledge_base_dir = Path(knowledge_base_dir)
        
        # Загружаем модель для эмбеддингов
        self.model = SentenceTransformer('distiluse-base-multilingual-cased-v1')
        
        # Кэш для эмбеддингов
        self.embeddings_cache = {}
        
        # Загружаем и индексируем базу знаний
        self.knowledge_base = self._load_knowledge_base()
        self._create_embeddings()
        
    def _load_knowledge_base(self) -> Dict[str, Any]:
        """
        Загрузка всех документов из базы знаний
        
        Returns:
            Словарь с документами
        """
        knowledge_base = {}
        
        # Загружаем все JSON файлы
        for file_path in self.knowledge_base_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    category = file_path.stem
                    data = json.load(f)
                    knowledge_base[category] = self._flatten_knowledge(data)
            except Exception as e:
                self.logger.error(f"Ошибка при загрузке {file_path}: {e}")
                
        return knowledge_base
    
    def _flatten_knowledge(self, data: Dict) -> List[Dict[str, str]]:
        """
        Преобразование структурированных данных в плоский список документов
        
        Args:
            data: Структурированные данные
            
        Returns:
            Список документов
        """
        documents = []
        
        def extract_age_info(text: str) -> Optional[Dict[str, Any]]:
            """Extract age-related information from text"""
            age_info = {
                'min_age': None,
                'max_age': None,
                'has_age_info': False
            }
            
            # Поиск упоминаний возраста в тексте
            age_patterns = [
                r'от (\d+)(?:\s*-\s*|\s+до\s+)(\d+)\s*лет',
                r'(\d+)(?:\s*-\s*|\s+до\s+)(\d+)\s*лет',
                r'старше (\d+)\s*лет',
                r'младше (\d+)\s*лет',
                r'(\d+)\s*лет'
            ]
            
            for pattern in age_patterns:
                matches = re.finditer(pattern, text.lower())
                for match in matches:
                    age_info['has_age_info'] = True
                    if len(match.groups()) == 2:
                        age_info['min_age'] = int(match.group(1))
                        age_info['max_age'] = int(match.group(2))
                    elif 'старше' in text.lower():
                        age_info['min_age'] = int(match.group(1))
                    elif 'младше' in text.lower():
                        age_info['max_age'] = int(match.group(1))
                    else:
                        age = int(match.group(1))
                        age_info['min_age'] = age
                        age_info['max_age'] = age
                    
                    return age_info
            
            return age_info
        
        def process_item(item, context=""):
            if isinstance(item, dict):
                # Если есть прямая пара вопрос-ответ
                if "вопрос" in item and "ответ" in item:
                    # Извлекаем информацию о возрасте из вопроса и ответа
                    question_age_info = extract_age_info(item['вопрос'])
                    answer_age_info = extract_age_info(item['ответ'])
                    
                    # Объединяем информацию о возрасте
                    age_info = {
                        'min_age': question_age_info['min_age'] or answer_age_info['min_age'],
                        'max_age': question_age_info['max_age'] or answer_age_info['max_age'],
                        'has_age_info': question_age_info['has_age_info'] or answer_age_info['has_age_info']
                    }
                    
                    documents.append({
                        "text": f"{item['вопрос']} {item['ответ']}",
                        "question": item['вопрос'],
                        "answer": item['ответ'],
                        "context": context,
                        "age_info": age_info
                    })
                # Если есть массив вопросов
                elif "question" in item and "answer" in item:
                    answer_age_info = extract_age_info(item['answer'])
                    
                    if isinstance(item["question"], list):
                        for q in item["question"]:
                            question_age_info = extract_age_info(q)
                            age_info = {
                                'min_age': question_age_info['min_age'] or answer_age_info['min_age'],
                                'max_age': question_age_info['max_age'] or answer_age_info['max_age'],
                                'has_age_info': question_age_info['has_age_info'] or answer_age_info['has_age_info']
                            }
                            
                            documents.append({
                                "text": f"{q} {item['answer']}",
                                "question": q,
                                "answer": item["answer"],
                                "context": context,
                                "age_info": age_info
                            })
                    else:
                        question_age_info = extract_age_info(item['question'])
                        age_info = {
                            'min_age': question_age_info['min_age'] or answer_age_info['min_age'],
                            'max_age': question_age_info['max_age'] or answer_age_info['max_age'],
                            'has_age_info': question_age_info['has_age_info'] or answer_age_info['has_age_info']
                        }
                        
                        documents.append({
                            "text": f"{item['question']} {item['answer']}",
                            "question": item["question"],
                            "answer": item["answer"],
                            "context": context,
                            "age_info": age_info
                        })
                
                # Рекурсивно обрабатываем вложенные объекты
                for key, value in item.items():
                    new_context = f"{context} {key}".strip()
                    process_item(value, new_context)
                    
            elif isinstance(item, list):
                for subitem in item:
                    process_item(subitem, context)
                    
        process_item(data)
        return documents
    
    def _create_embeddings(self) -> None:
        """
        Создание эмбеддингов для всех документов
        """
        for category, documents in self.knowledge_base.items():
            if category not in self.embeddings_cache:
                self.embeddings_cache[category] = {}
                
            for doc in documents:
                # Создаем эмбеддинги для полного текста
                text = doc["text"]
                if text not in self.embeddings_cache[category]:
                    self.embeddings_cache[category][text] = self.model.encode(text)
    
    def _get_relevant_documents(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов для запроса с улучшенным ранжированием
        
        Args:
            query: Текст запроса
            top_k: Количество возвращаемых документов
            
        Returns:
            Список релевантных документов
        """
        query_embedding = self.model.encode(query)
        query_age_info = self._extract_age_info(query)
        
        # Извлекаем ключевые слова из запроса
        query_keywords = set(self._normalize_text(query).split())
        
        all_scores = []
        all_docs = []
        
        # Ищем по всем категориям
        for category, documents in self.knowledge_base.items():
            for doc in documents:
                text = doc["text"]
                doc_embedding = self.embeddings_cache[category][text]
                
                # Базовая косинусная близость
                base_similarity = cosine_similarity(
                    query_embedding.reshape(1, -1),
                    doc_embedding.reshape(1, -1)
                )[0][0]
                
                # Начальный score
                final_similarity = base_similarity
                
                # Увеличиваем вес документов с совпадающими ключевыми словами
                doc_text = self._normalize_text(text)
                keyword_matches = len(query_keywords.intersection(doc_text.split()))
                if keyword_matches > 0:
                    final_similarity *= (1 + 0.1 * keyword_matches)
                
                # Учитываем возрастную информацию
                if query_age_info['has_age_info'] and doc.get('age_info', {}).get('has_age_info', False):
                    query_min = query_age_info['min_age']
                    query_max = query_age_info['max_age']
                    doc_min = doc['age_info']['min_age']
                    doc_max = doc['age_info']['max_age']
                    
                    if (query_min is not None and doc_min is not None and 
                        query_max is not None and doc_max is not None):
                        # Проверяем пересечение диапазонов
                        if (query_min <= doc_max and query_max >= doc_min):
                            # Увеличиваем релевантность для документов с пересекающимися возрастными диапазонами
                            final_similarity *= 1.5
                            # Дополнительный бонус за точное совпадение возрастного диапазона
                            if query_min == doc_min and query_max == doc_max:
                                final_similarity *= 1.2
                        else:
                            # Уменьшаем релевантность для документов с непересекающимися возрастными диапазонами
                            final_similarity *= 0.5
                    elif query_min is not None and doc_min is not None:
                        # Если указаны только минимальные возрасты
                        if abs(query_min - doc_min) <= 2:
                            final_similarity *= 1.3
                    elif query_max is not None and doc_max is not None:
                        # Если указаны только максимальные возрасты
                        if abs(query_max - doc_max) <= 2:
                            final_similarity *= 1.3
                
                # Учитываем длину ответа (предпочитаем более подробные ответы)
                answer_length = len(doc["answer"])
                if answer_length > 200:  # Длинные, подробные ответы
                    final_similarity *= 1.2
                elif answer_length < 50:  # Короткие ответы
                    final_similarity *= 0.8
                
                # Учитываем наличие цен в ответе
                if any(price_word in text.lower() for price_word in ['руб', 'рублей', 'стоит', 'цена', 'стоимость']):
                    final_similarity *= 1.1
                
                # Учитываем наличие важных требований
                if any(req_word in text.lower() for req_word in ['требуется', 'необходимо', 'нужно', 'обязательно']):
                    final_similarity *= 1.1
                
                # Добавляем небольшой случайный фактор для разнообразия при близких значениях
                final_similarity *= (1 + np.random.normal(0, 0.01))
                
                all_scores.append(final_similarity)
                all_docs.append(doc)
        
        # Сортируем по релевантности
        sorted_pairs = sorted(zip(all_scores, all_docs), key=lambda x: x[0], reverse=True)
        
        # Убираем дубликаты ответов, сохраняя порядок
        seen_answers = set()
        unique_docs = []
        for score, doc in sorted_pairs:
            answer = doc["answer"]
            if answer not in seen_answers:
                seen_answers.add(answer)
                unique_docs.append(doc)
            if len(unique_docs) >= top_k:
                break
        
        return unique_docs
    
    def _determine_context(self, query: str) -> Dict[str, Any]:
        """
        Определение контекста запроса
        
        Args:
            query: Текст запроса
            
        Returns:
            Словарь с информацией о контексте
        """
        context = {
            'is_school': False,
            'is_kindergarten': False,
            'is_price_query': False,
            'is_schedule_query': False,
            'age_mentioned': False
        }
        
        # Нормализуем запрос
        query_lower = query.lower()
        
        # Определяем контекст школы
        school_keywords = {'школа', 'класс', 'ученик', 'школьник', 'учитель', 'урок', 'школьный'}
        context['is_school'] = any(keyword in query_lower for keyword in school_keywords)
        
        # Определяем контекст детского сада
        kindergarten_keywords = {'сад', 'садик', 'детский сад', 'дошкольный', 'дошкольник', 'воспитатель', 'группа'}
        context['is_kindergarten'] = any(keyword in query_lower for keyword in kindergarten_keywords)
        
        # Определяем запрос о ценах
        price_keywords = {'цена', 'стоимость', 'цены', 'стоит', 'оплата', 'платить', 'рублей', 'руб'}
        context['is_price_query'] = any(keyword in query_lower for keyword in price_keywords)
        
        # Определяем запрос о расписании
        schedule_keywords = {'расписание', 'график', 'режим', 'время', 'занятия', 'распорядок'}
        context['is_schedule_query'] = any(keyword in query_lower for keyword in schedule_keywords)
        
        # Проверяем упоминание возраста
        age_info = self._extract_age_info(query)
        context['age_mentioned'] = age_info['has_age_info']
        context['age_info'] = age_info
        
        return context

    def get_rag_response(self, query: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Получение подробного ответа с использованием RAG
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Tuple[ответ, список использованных документов]
        """
        # Определяем контекст запроса
        context = self._determine_context(query)
        
        # Модифицируем запрос для поиска с учетом контекста
        search_query = query
        if context['is_school']:
            search_query = f"школа {query}"
        elif context['is_kindergarten']:
            search_query = f"детский сад {query}"
        
        # Получаем релевантные документы
        relevant_docs = self._get_relevant_documents(search_query, top_k=5)
        
        if not relevant_docs:
            # Если не нашли документов, задаем уточняющий вопрос
            if context['is_school']:
                return "В какой класс планируете поступать? Это поможет мне предоставить точную информацию о программе обучения, стоимости и условиях.", []
            elif context['is_kindergarten']:
                return "Какой возраст ребенка вас интересует? Это поможет мне рассказать о подходящей группе и программе развития.", []
            else:
                return "Что именно вас интересует - школа или детский сад? Я помогу подобрать оптимальный вариант.", []
        
        # Фильтруем документы по контексту
        filtered_docs = []
        for doc in relevant_docs:
            doc_text = f"{doc['question']} {doc['answer']}".lower()
            
            # Проверяем соответствие контексту
            if context['is_school'] and not any(keyword in doc_text for keyword in ['школа', 'класс', 'ученик']):
                continue
            if context['is_kindergarten'] and not any(keyword in doc_text for keyword in ['сад', 'садик', 'группа']):
                continue
                
            filtered_docs.append(doc)
        
        # Если после фильтрации не осталось документов, используем исходные
        if not filtered_docs:
            filtered_docs = relevant_docs
        
        # Проверяем, достаточно ли информации для полного ответа
        has_pricing = any('стоимость' in doc['answer'].lower() or 'цена' in doc['answer'].lower() for doc in filtered_docs)
        has_program = any('программа' in doc['answer'].lower() or 'занятия' in doc['answer'].lower() for doc in filtered_docs)
        has_schedule = any('расписание' in doc['answer'].lower() or 'график' in doc['answer'].lower() for doc in filtered_docs)
        
        # Структура для хранения дополнительной информации
        additional_info = {
            'age_specific': [],
            'related_topics': set(),
            'pricing_info': [],
            'requirements': [],
            'additional_details': [],
            'clarifying_questions': []
        }
        
        # Формируем уточняющие вопросы на основе контекста
        if context['is_school']:
            if not context.get('grade_mentioned', False):
                additional_info['clarifying_questions'].append("В какой класс планируете поступать?")
            if not has_pricing and not context['is_price_query']:
                additional_info['clarifying_questions'].append("Хотите узнать подробнее о стоимости обучения?")
            if not has_program:
                additional_info['clarifying_questions'].append("Интересует ли вас информация о программе обучения и дополнительных занятиях?")
        elif context['is_kindergarten']:
            if not context['age_mentioned']:
                additional_info['clarifying_questions'].append("Какой возраст ребенка вас интересует?")
            if not has_pricing and not context['is_price_query']:
                additional_info['clarifying_questions'].append("Хотите узнать подробнее о стоимости посещения?")
            if not has_schedule:
                additional_info['clarifying_questions'].append("Интересует ли вас режим работы и расписание занятий?")
        
        # Собираем дополнительную информацию из всех релевантных документов
        for doc in filtered_docs[1:]:
            doc_text = f"{doc['question']} {doc['answer']}"
            
            # Добавляем возрастную информацию только если она явно запрошена или упомянута в запросе
            if context['age_mentioned'] and doc.get('age_info', {}).get('has_age_info', False):
                doc_min = doc['age_info']['min_age']
                doc_max = doc['age_info']['max_age']
                if doc_min is not None and doc_max is not None:
                    if doc_min == doc_max:
                        additional_info['age_specific'].append(f"Для возраста {doc_min} лет: {doc['answer']}")
                    else:
                        additional_info['age_specific'].append(f"Для возраста {doc_min}-{doc_max} лет: {doc['answer']}")
                elif doc_min is not None:
                    additional_info['age_specific'].append(f"Для детей старше {doc_min} лет: {doc['answer']}")
                elif doc_max is not None:
                    additional_info['age_specific'].append(f"Для детей младше {doc_max} лет: {doc['answer']}")
            
            # Извлекаем информацию о ценах только для соответствующих запросов
            if context['is_price_query'] and any(price_word in doc_text.lower() for price_word in ['руб', 'рублей', 'стоит', 'цена', 'стоимость']):
                additional_info['pricing_info'].append(doc['answer'])
            
            # Извлекаем требования
            if any(req_word in doc_text.lower() for req_word in ['требуется', 'необходимо', 'нужно', 'обязательно']):
                additional_info['requirements'].append(doc['answer'])
            
            # Добавляем связанные темы из контекста
            if doc['context']:
                additional_info['related_topics'].add(doc['context'])
            
            # Добавляем дополнительные детали
            if len(doc['answer']) > 50:  # Если ответ достаточно подробный
                additional_info['additional_details'].append(doc['answer'])
        
        # Формируем основной ответ из лучшего совпадения
        best_doc = filtered_docs[0]
        main_answer = best_doc["answer"]
        
        # Добавляем информацию о возрасте только если она явно запрошена или упомянута
        if context['age_mentioned'] and best_doc.get('age_info', {}).get('has_age_info', False):
            doc_min = best_doc['age_info']['min_age']
            doc_max = best_doc['age_info']['max_age']
            if doc_min is not None and doc_max is not None:
                if doc_min == doc_max:
                    main_answer = f"Для возраста {doc_min} лет:\n{main_answer}"
                else:
                    main_answer = f"Для возраста {doc_min}-{doc_max} лет:\n{main_answer}"
            elif doc_min is not None:
                main_answer = f"Для детей старше {doc_min} лет:\n{main_answer}"
            elif doc_max is not None:
                main_answer = f"Для детей младше {doc_max} лет:\n{main_answer}"
        
        # Формируем полный ответ
        full_answer = [main_answer]
        
        # Добавляем дополнительную информацию по возрастам только если она явно запрошена
        if context['age_mentioned'] and additional_info['age_specific']:
            full_answer.append("\nДополнительная информация по возрастам:")
            full_answer.extend(additional_info['age_specific'])
        
        # Добавляем информацию о ценах только для соответствующих запросов
        if context['is_price_query'] and additional_info['pricing_info']:
            full_answer.append("\nИнформация о стоимости:")
            full_answer.extend(additional_info['pricing_info'])
        
        # Добавляем требования
        if additional_info['requirements']:
            full_answer.append("\nВажные требования:")
            full_answer.extend(additional_info['requirements'])
        
        # Добавляем дополнительные детали
        if additional_info['additional_details']:
            full_answer.append("\nДополнительная информация:")
            full_answer.extend(additional_info['additional_details'])
        
        # Добавляем связанные темы
        if additional_info['related_topics']:
            full_answer.append("\nСвязанные темы:")
            full_answer.extend(list(additional_info['related_topics']))
        
        # Добавляем уточняющие вопросы в конец
        if additional_info['clarifying_questions']:
            full_answer.append("\nЧтобы предоставить более точную информацию, ответьте, пожалуйста:")
            full_answer.extend(additional_info['clarifying_questions'])
        
        # Объединяем все части ответа
        final_answer = '\n'.join(full_answer)
        
        return final_answer, filtered_docs
    
    def _is_similar_question(self, query: str, question: str, threshold: float = 0.85) -> bool:
        """
        Проверка схожести вопросов
        
        Args:
            query: Запрос пользователя
            question: Вопрос из базы знаний
            threshold: Порог схожести
            
        Returns:
            True если вопросы похожи
        """
        # Нормализуем тексты
        query = self._normalize_text(query)
        question = self._normalize_text(question)
        
        # Проверяем через эмбеддинги
        query_embedding = self.model.encode(query)
        question_embedding = self.model.encode(question)
        
        similarity = cosine_similarity(
            query_embedding.reshape(1, -1),
            question_embedding.reshape(1, -1)
        )[0][0]
        
        return similarity >= threshold
    
    def _normalize_text(self, text: str) -> str:
        """
        Нормализация текста для сравнения
        
        Args:
            text: Исходный текст
            
        Returns:
            Нормализованный текст
        """
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Удаляем пунктуацию
        text = re.sub(r'[^\w\s]', '', text)
        
        # Удаляем множественные пробелы
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip() 