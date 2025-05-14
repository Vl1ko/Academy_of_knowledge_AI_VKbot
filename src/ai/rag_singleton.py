import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import docx
from transformers import AutoTokenizer, AutoModel
import torch
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class RAGSingleton:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger(__name__)
            self.knowledge_base_dir = Path("data/knowledge_base")
            self.tokenizer = AutoTokenizer.from_pretrained('bert-base-multilingual-cased')
            self.model = AutoModel.from_pretrained('bert-base-multilingual-cased')
            self.embeddings_cache = {}
            self.knowledge_base = {}
            self._initialized = True
            
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embeddings for a text using BERT"""
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        # Use the [CLS] token embedding as the sentence embedding
        embeddings = outputs.last_hidden_state[:, 0, :].numpy()
        return embeddings[0]  # Return the first (and only) embedding
            
    def initialize(self):
        """
        Инициализация RAG: загрузка базы знаний и создание эмбеддингов.
        Должна вызываться один раз при запуске приложения.
        """
        self.logger.info("Initializing RAG system...")
        self.knowledge_base = self._load_knowledge_base()
        self._create_embeddings()
        self.logger.info("RAG system initialized successfully")
    
    def _load_knowledge_base(self) -> Dict[str, Any]:
        """Загрузка всех документов из базы знаний"""
        knowledge_base = {"documents": []}
        
        # Загружаем все DOCX файлы
        for file_path in self.knowledge_base_dir.glob("*.docx"):
            try:
                doc = docx.Document(file_path)
                current_heading = ""
                current_text = []
                
                for paragraph in doc.paragraphs:
                    if paragraph.style.name.startswith('Heading'):
                        # Если есть накопленный текст, сохраняем его
                        if current_text:
                            knowledge_base["documents"].append({
                                "text": " ".join(current_text),
                                "question": current_heading,
                                "answer": " ".join(current_text),
                                "context": current_heading
                            })
                            current_text = []
                        current_heading = paragraph.text.strip()
                    else:
                        text = paragraph.text.strip()
                        if text:  # Добавляем только непустые параграфы
                            current_text.append(text)
                
                # Добавляем последний блок текста
                if current_text:
                    knowledge_base["documents"].append({
                        "text": " ".join(current_text),
                        "question": current_heading,
                        "answer": " ".join(current_text),
                        "context": current_heading
                    })
                
                self.logger.info(f"Loaded knowledge base from: {file_path}")
            except Exception as e:
                self.logger.error(f"Error loading {file_path}: {e}")
                
        return knowledge_base
    
    def _create_embeddings(self) -> None:
        """Создание эмбеддингов для всех документов"""
        documents = self.knowledge_base.get("documents", [])
        total_docs = len(documents)
        processed_docs = 0
        
        if "documents" not in self.embeddings_cache:
            self.embeddings_cache["documents"] = {}
        
        for doc in documents:
            text = doc["text"]
            if text not in self.embeddings_cache["documents"]:
                self.embeddings_cache["documents"][text] = self._get_embedding(text)
            processed_docs += 1
            
            if processed_docs % 10 == 0:  # Log progress every 10 documents
                self.logger.info(f"Created embeddings for {processed_docs}/{total_docs} documents")
    
    def get_rag_response(self, query: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Получение ответа с использованием RAG"""
        # Получаем релевантные документы
        relevant_docs = self._get_relevant_documents(query)
        
        if not relevant_docs:
            return None, []
        
        # Возвращаем наиболее релевантный ответ
        best_doc = relevant_docs[0]
        return best_doc["answer"], relevant_docs
    
    def _get_relevant_documents(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Поиск релевантных документов для запроса"""
        query_embedding = self._get_embedding(query)
        
        all_scores = []
        all_docs = []
        
        # Ищем по всем документам
        documents = self.knowledge_base.get("documents", [])
        for doc in documents:
            text = doc["text"]
            doc_embedding = self.embeddings_cache["documents"][text]
            
            # Вычисляем косинусную близость
            similarity = cosine_similarity(
                query_embedding.reshape(1, -1),
                doc_embedding.reshape(1, -1)
            )[0][0]
            
            all_scores.append(similarity)
            all_docs.append(doc)
        
        # Сортируем по релевантности
        sorted_pairs = sorted(zip(all_scores, all_docs), key=lambda x: x[0], reverse=True)
        
        return [doc for score, doc in sorted_pairs[:top_k]] 