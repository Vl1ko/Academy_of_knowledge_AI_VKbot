import logging
import os
import json
from typing import Dict, List, Any, Optional
import pandas as pd
from pathlib import Path

class KnowledgeBase:
    """
    Class for working with the knowledge base of the academy
    """
    
    def __init__(self, knowledge_dir: str = "data/knowledge_base"):
        """
        Initialize knowledge base handler
        
        Args:
            knowledge_dir: Directory with knowledge base files
        """
        self.logger = logging.getLogger(__name__)
        self.knowledge_dir = Path(knowledge_dir)
        
        # Ensure the directory exists
        os.makedirs(self.knowledge_dir, exist_ok=True)
        
        # Initialize knowledge categories
        self.categories = {
            "general": self._load_or_create_json("general.json"),
            "school": self._load_or_create_json("school.json"),
            "kindergarten": self._load_or_create_json("kindergarten.json"),
            "faq": self._load_or_create_json("faq.json"),
            "documents": self._load_or_create_json("documents.json")
        }
        
        # Load document full texts if any
        self.documents = {}
        self._load_documents()
    
    def _load_or_create_json(self, filename: str) -> Dict:
        """
        Load JSON file or create empty one if not exists
        
        Args:
            filename: JSON filename
            
        Returns:
            Loaded data as dictionary
        """
        file_path = self.knowledge_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading knowledge base file {filename}: {e}")
                return {}
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            return {}
    
    def _load_documents(self) -> None:
        """Load full text documents from the docs directory"""
        docs_dir = self.knowledge_dir / "docs"
        if not docs_dir.exists():
            os.makedirs(docs_dir, exist_ok=True)
            return
            
        for file in docs_dir.glob("*.txt"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.documents[file.stem] = f.read()
            except Exception as e:
                self.logger.error(f"Error loading document {file.name}: {e}")
    
    def get_response(self, query: str, category: str = None) -> Optional[str]:
        """
        Get response from knowledge base
        
        Args:
            query: User query
            category: Knowledge category (optional)
            
        Returns:
            Response from knowledge base or None if not found
        """
        if category and category in self.categories:
            return self._search_in_category(query, self.categories[category])
        
        # Search in all categories
        for cat_name, cat_data in self.categories.items():
            result = self._search_in_category(query, cat_data)
            if result:
                return result
                
        return None
    
    def _search_in_category(self, query: str, category_data: Dict) -> Optional[str]:
        """
        Search for response in category data
        
        Args:
            query: User query
            category_data: Category data
            
        Returns:
            Response or None if not found
        """
        # Simple keyword matching for now
        query = query.lower()
        for key, value in category_data.items():
            if key.lower() in query:
                return value
        return None
    
    def add_knowledge(self, category: str, key: str, value: str) -> bool:
        """
        Add knowledge to category
        
        Args:
            category: Knowledge category
            key: Knowledge key
            value: Knowledge value
            
        Returns:
            True if added successfully, False otherwise
        """
        if category not in self.categories:
            self.logger.error(f"Unknown category: {category}")
            return False
        
        try:
            self.categories[category][key] = value
            self._save_category(category)
            return True
        except Exception as e:
            self.logger.error(f"Error adding knowledge: {e}")
            return False
    
    def _save_category(self, category: str) -> None:
        """
        Save category data to file
        
        Args:
            category: Category name
        """
        try:
            file_path = self.knowledge_dir / f"{category}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.categories[category], f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving category {category}: {e}")
    
    def add_document(self, doc_name: str, content: str) -> bool:
        """
        Add full document text to knowledge base
        
        Args:
            doc_name: Document name
            content: Document content
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            docs_dir = self.knowledge_dir / "docs"
            os.makedirs(docs_dir, exist_ok=True)
            
            file_path = docs_dir / f"{doc_name}.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.documents[doc_name] = content
            return True
        except Exception as e:
            self.logger.error(f"Error adding document: {e}")
            return False
    
    def get_document(self, doc_name: str) -> Optional[str]:
        """
        Get document content by name
        
        Args:
            doc_name: Document name
            
        Returns:
            Document content or None if not found
        """
        return self.documents.get(doc_name)
    
    def import_from_excel(self, file_path: str) -> bool:
        """
        Import knowledge base from Excel file
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            True if imported successfully, False otherwise
        """
        try:
            df = pd.read_excel(file_path)
            for _, row in df.iterrows():
                if 'category' in row and 'key' in row and 'value' in row:
                    category = row['category']
                    key = row['key']
                    value = row['value']
                    
                    if category not in self.categories:
                        self.categories[category] = {}
                    
                    self.categories[category][key] = value
                    self._save_category(category)
            
            return True
        except Exception as e:
            self.logger.error(f"Error importing from Excel: {e}")
            return False 