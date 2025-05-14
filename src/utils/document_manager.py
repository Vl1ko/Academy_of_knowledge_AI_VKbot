import logging
from pathlib import Path
from typing import List, Optional
import shutil
from datetime import datetime

class DocumentManager:
    """
    Утилита для управления документами в базе знаний
    """
    
    def __init__(self, base_dir: str = "data/knowledge_base"):
        """
        Инициализация менеджера документов
        
        Args:
            base_dir: Базовая директория
        """
        self.logger = logging.getLogger(__name__)
        self.base_dir = Path(base_dir)
        self.docs_dir = self.base_dir / "documents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        
    def add_document(self, file_path: str, category: str = "general") -> Optional[str]:
        """
        Добавление документа в базу знаний
        
        Args:
            file_path: Путь к файлу
            category: Категория документа
            
        Returns:
            Путь к сохраненному файлу или None в случае ошибки
        """
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                self.logger.error(f"Файл не найден: {file_path}")
                return None
                
            # Создаем директорию категории если её нет
            category_dir = self.docs_dir / category
            category_dir.mkdir(exist_ok=True)
            
            # Формируем имя файла с датой
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{source_path.stem}_{timestamp}{source_path.suffix}"
            target_path = category_dir / new_filename
            
            # Копируем файл
            shutil.copy2(source_path, target_path)
            
            self.logger.info(f"Документ добавлен: {target_path}")
            return str(target_path)
            
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении документа: {e}")
            return None
    
    def remove_document(self, file_path: str) -> bool:
        """
        Удаление документа из базы знаний
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если документ успешно удален
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                self.logger.info(f"Документ удален: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при удалении документа: {e}")
            return False
    
    def list_documents(self, category: Optional[str] = None) -> List[Path]:
        """
        Получение списка документов
        
        Args:
            category: Категория документов (опционально)
            
        Returns:
            Список путей к документам
        """
        if category:
            category_dir = self.docs_dir / category
            if not category_dir.exists():
                return []
            return list(category_dir.glob("*.*"))
        
        # Если категория не указана, возвращаем все документы
        return list(self.docs_dir.rglob("*.*"))
    
    def get_document_info(self, file_path: str) -> Optional[dict]:
        """
        Получение информации о документе
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Словарь с информацией о документе или None
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None
                
            return {
                "name": path.name,
                "category": path.parent.name,
                "size": path.stat().st_size,
                "created": datetime.fromtimestamp(path.stat().st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "path": str(path)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении информации о документе: {e}")
            return None 