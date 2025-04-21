#!/usr/bin/env python3
import os
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Setup")

# Project directories
DIRECTORIES = [
    "data",
    "data/knowledge_base",
    "data/knowledge_base/docs",
    "data/reports",
    "logs",
]

# Sample knowledge base files
KNOWLEDGE_BASE_FILES = {
    "general.json": {
        "О проекте": "«Академия знаний» - это образовательный проект, включающий частную школу и детский сад «Академик». Мы предлагаем качественное образование с индивидуальным подходом к каждому ученику."
    },
    "school.json": {
        "О школе": "Частная школа «Академия знаний» - это современное образовательное учреждение, сочетающее высокие стандарты образования с индивидуальным подходом к каждому ученику."
    },
    "kindergarten.json": {
        "О детском саде": "Частный детский сад «Академик» - это пространство для гармоничного развития детей, где созданы все условия для обучения, игры и творчества."
    },
    "faq.json": {
        "Какие документы нужны для поступления?": "Для поступления в школу необходимы следующие документы: свидетельство о рождении ребенка, медицинская карта, заявление от родителей и документы, удостоверяющие личность родителей.",
        "Сколько стоит обучение?": "Стоимость обучения зависит от выбранной программы и класса. Пожалуйста, свяжитесь с нами для получения актуальной информации о ценах.",
        "Есть ли дополнительные занятия?": "Да, в нашей школе проводятся дополнительные занятия по различным предметам, включая иностранные языки, программирование, робототехнику, шахматы и творческие кружки."
    },
    "documents.json": {
        "Договор": "Информация о договоре оказания образовательных услуг",
        "Правила": "Внутренние правила учреждения"
    }
}

def create_directories():
    """Create project directories if they don't exist"""
    for directory in DIRECTORIES:
        dir_path = Path(directory)
        if not dir_path.exists():
            os.makedirs(dir_path)
            logger.info(f"Created directory: {dir_path}")
        else:
            logger.info(f"Directory already exists: {dir_path}")

def create_knowledge_base_files():
    """Create initial knowledge base files"""
    kb_dir = Path("data/knowledge_base")
    
    for filename, data in KNOWLEDGE_BASE_FILES.items():
        file_path = kb_dir / filename
        
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Created knowledge base file: {file_path}")
        else:
            logger.info(f"Knowledge base file already exists: {file_path}")

def create_env_example():
    """Create .env.example file"""
    env_example = """# VK API
VK_TOKEN=your_vk_token

# Group IDs
SCHOOL_GROUP_ID=your_school_group_id
KINDERGARTEN_GROUP_ID=your_kindergarten_group_id

# Admin IDs (comma-separated list)
ADMIN_IDS=123456789,987654321

# Database settings
DATABASE_URL=sqlite:///academy_bot.db

# AI API Keys
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key
GIGACHAT_API_KEY=your_gigachat_key
"""
    
    env_path = Path(".env.example")
    if not env_path.exists():
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_example)
        logger.info("Created .env.example file")
    else:
        logger.info(".env.example file already exists")

def create_sample_document():
    """Create a sample document for the knowledge base"""
    doc_dir = Path("data/knowledge_base/docs")
    doc_path = doc_dir / "sample_agreement.txt"
    
    if not doc_path.exists():
        sample_text = """ДОГОВОР ОБ ОКАЗАНИИ ОБРАЗОВАТЕЛЬНЫХ УСЛУГ

Настоящий договор заключается между образовательным учреждением "Академия знаний" и родителями (законными представителями) ученика с целью оказания образовательных услуг.

1. ПРЕДМЕТ ДОГОВОРА
1.1. Образовательное учреждение обязуется предоставить образовательные услуги ученику в соответствии с утвержденной программой обучения.
1.2. Родители (законные представители) обязуются выполнять условия настоящего договора и внутренние правила учреждения.

2. ПРАВА И ОБЯЗАННОСТИ СТОРОН
2.1. Образовательное учреждение обязуется:
- Обеспечить качественное обучение по утвержденной программе;
- Создать безопасную образовательную среду;
- Регулярно информировать родителей о прогрессе ученика.

2.2. Родители (законные представители) обязуются:
- Своевременно вносить плату за обучение;
- Обеспечивать регулярное посещение занятий учеником;
- Уважать права и достоинство всех участников образовательного процесса.

Данный текст является образцом договора и не является юридически обязывающим документом."""
        
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(sample_text)
        logger.info(f"Created sample document: {doc_path}")
    else:
        logger.info(f"Sample document already exists: {doc_path}")

def main():
    """Main setup function"""
    logger.info("Starting project setup...")
    
    create_directories()
    create_knowledge_base_files()
    create_env_example()
    create_sample_document()
    
    logger.info("Project setup completed successfully!")
    logger.info("To complete setup, create a .env file based on .env.example with your actual credentials.")

if __name__ == "__main__":
    main() 