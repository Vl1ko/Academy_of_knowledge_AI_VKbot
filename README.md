# Бот-менеджер для ВКонтакте "Академия знаний"

Бот-менеджер для социальной сети ВКонтакте, предназначенный для консультации клиентов и ведения клиентской базы для частной школы "Академия знаний" и частного сада "Академик".

## Функциональность

- Автоматизированные ответы на частые вопросы
- Обработка запросов с использованием NLP
- Сбор и хранение данных пользователей
- Запись на мероприятия
- Рассылка уведомлений
- Интеграция с базой данных Excel
- Сбор статистики и аналитики

## Технологии

- Python 3.12.9+
- vk_api 11.9.9
- OpenAI API 1.12.0
- DeepSeek
- pandas 2.2.0
- SQLAlchemy (для работы с базой данных)

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/Vl1ko/Academy_of_knowledge_AI_VKbot.git
cd Academy_of_knowledge_AI_VKbot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
venv\Scripts\activate  # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте необходимые переменные окружения:
```
VK_TOKEN=your_vk_token
OPENAI_API_KEY=your_openai_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

## Структура проекта

```
academy-bot/
├── src/
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── vk_bot.py
│   │   ├── message_handler.py
│   │   └── keyboard.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── openai_handler.py
│   │   └── deepseek_handler.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── db_handler.py
│   └── utils/
│       ├── __init__.py
│       ├── excel_handler.py
│       └── statistics.py
├── config/
│   └── config.py
├── data/
│   └── responses.json
├── tests/
│   └── __init__.py
├── .env
├── .gitignore
├── requirements.txt
└── main.py
```

## Использование

1. Настройте конфигурацию в файле `config/config.py`
2. Запустите бота:
```bash
python main.py
```

## Лицензия

MIT 