import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Токены и ключи API
VK_TOKEN = os.getenv('VK_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
GIGACHAT_API_KEY = os.getenv('GIGACHAT_API_KEY')

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///academy_bot.db')

# Настройки бота
BOT_SETTINGS = {
    'group_ids': {
        'school': os.getenv('SCHOOL_GROUP_ID'),
        'kindergarten': os.getenv('KINDERGARTEN_GROUP_ID')
    },
    'admin_ids': [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id],
    'response_timeout': 30,  # секунды
    'max_message_length': 4096
}

# Настройки AI
AI_SETTINGS = {
    'openai_model': 'gpt-4-turbo-preview',
    'deepseek_model': 'deepseek-chat',
    'gigachat_model': 'GigaChat',
    'temperature': 0.7,
    'max_tokens': 1000
}

# Пути к файлам
PATHS = {
    'responses': 'data/responses.json',
    'excel_db': 'data/clients.xlsx',
    'logs': 'logs/bot.log'
}

# Настройки логирования
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': PATHS['logs'],
            'mode': 'a',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': True
        }
    }
} 