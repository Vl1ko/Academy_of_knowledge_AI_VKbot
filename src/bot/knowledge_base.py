import json
import os
import re
from difflib import SequenceMatcher
from typing import Dict, Any, List, Tuple, Optional


class KnowledgeBase:
    """
    Класс для работы с базой знаний в JSON файлах
    """
    
    def __init__(self, base_dir: str = "data/knowledge_base"):
        """
        Инициализация базы знаний
        
        Args:
            base_dir: Директория с файлами базы знаний
        """
        self.base_dir = base_dir
        self.knowledge: Dict[str, Dict[str, str]] = {}
        self.load_all_knowledge()
    
    def load_all_knowledge(self) -> None:
        """
        Загрузка всех файлов знаний
        """
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)
        
        # Перебираем все JSON файлы в директории
        for filename in os.listdir(self.base_dir):
            if filename.endswith('.json'):
                category = filename.replace('.json', '')
                self.load_knowledge(category)
    
    def load_knowledge(self, category: str) -> None:
        """
        Загрузка знаний из категории
        
        Args:
            category: Категория знаний
        """
        filepath = os.path.join(self.base_dir, f"{category}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    self.knowledge[category] = json.load(file)
            except json.JSONDecodeError:
                # Если файл пустой или имеет неверный формат, создаем пустой словарь
                self.knowledge[category] = {}
        else:
            # Если файл не существует, создаем его с пустым словарем
            self.knowledge[category] = {}
            self.save_knowledge(category)
    
    def save_knowledge(self, category: str) -> bool:
        """
        Сохранение знаний в категорию
        
        Args:
            category: Категория знаний
            
        Returns:
            Успешность операции
        """
        filepath = os.path.join(self.base_dir, f"{category}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump(self.knowledge.get(category, {}), file, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def add_knowledge(self, category: str, key: str, value: str) -> bool:
        """
        Добавление знаний в категорию
        
        Args:
            category: Категория знаний
            key: Ключ
            value: Значение
            
        Returns:
            Успешность операции
        """
        if category not in self.knowledge:
            self.knowledge[category] = {}
        
        self.knowledge[category][key] = value
        return self.save_knowledge(category)
    
    def get_knowledge(self, category: str, key: str) -> Optional[str]:
        """
        Получение знания по категории и ключу
        
        Args:
            category: Категория знаний
            key: Ключ
            
        Returns:
            Значение или None, если не найдено
        """
        return self.knowledge.get(category, {}).get(key)
    
    def similar(self, a: str, b: str) -> float:
        """
        Вычисление схожести строк
        
        Args:
            a: Первая строка
            b: Вторая строка
            
        Returns:
            Коэффициент схожести от 0 до 1
        """
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def find_best_match(self, query: str, min_ratio: float = 0.7) -> Tuple[Optional[str], Optional[str], float]:
        """
        Поиск наиболее похожего ключа во всех категориях
        
        Args:
            query: Запрос
            min_ratio: Минимальный коэффициент схожести
            
        Returns:
            Категория, ключ и коэффициент схожести или None, если не найдено соответствий
        """
        best_category = None
        best_key = None
        best_ratio = 0.0
        
        # Нормализация запроса
        query = query.strip().lower()
        
        # Проверка на прямое соответствие сначала
        for category, items in self.knowledge.items():
            for key in items:
                if query == key.lower():
                    return category, key, 1.0
        
        # Поиск наиболее похожего ключа
        for category, items in self.knowledge.items():
            for key in items:
                ratio = self.similar(query, key)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_category = category
                    best_key = key
        
        if best_ratio >= min_ratio:
            return best_category, best_key, best_ratio
        return None, None, 0.0
    
    def get_response(self, query: str, min_ratio: float = 0.7) -> Optional[str]:
        """
        Получение ответа на запрос
        
        Args:
            query: Запрос
            min_ratio: Минимальный коэффициент схожести
            
        Returns:
            Ответ или None, если не найден подходящий ответ
        """
        category, key, ratio = self.find_best_match(query, min_ratio)
        if category and key:
            return self.knowledge[category][key]
        return None
    
    def get_all_categories(self) -> List[str]:
        """
        Получение списка всех категорий
        
        Returns:
            Список категорий
        """
        return list(self.knowledge.keys())
    
    def get_all_keys(self, category: str) -> List[str]:
        """
        Получение списка всех ключей в категории
        
        Args:
            category: Категория
            
        Returns:
            Список ключей
        """
        return list(self.knowledge.get(category, {}).keys())
    
    def delete_knowledge(self, category: str, key: str) -> bool:
        """
        Удаление знания из категории
        
        Args:
            category: Категория
            key: Ключ
            
        Returns:
            Успешность операции
        """
        if category in self.knowledge and key in self.knowledge[category]:
            del self.knowledge[category][key]
            return self.save_knowledge(category)
        return False
    
    def search_knowledge(self, query: str, threshold: float = 0.6) -> List[Tuple[str, str, str, float]]:
        """
        Поиск знаний по тексту
        
        Args:
            query: Запрос
            threshold: Порог схожести
            
        Returns:
            Список кортежей (категория, ключ, значение, коэффициент схожести)
        """
        results = []
        query = query.lower()
        
        for category, items in self.knowledge.items():
            for key, value in items.items():
                # Проверка ключа
                key_ratio = self.similar(query, key)
                
                # Проверка значения (если оно короткое)
                if len(value) < 200:  # Проверяем только короткие значения
                    value_ratio = self.similar(query, value)
                    ratio = max(key_ratio, value_ratio)
                else:
                    ratio = key_ratio
                
                if ratio >= threshold:
                    results.append((category, key, value, ratio))
        
        # Сортировка по коэффициенту схожести
        results.sort(key=lambda x: x[3], reverse=True)
        return results 