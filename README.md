# Academy of Knowledge - ВКонтакте AI Bot

Бот-менеджер для социальной сети ВКонтакте с использованием искусственного интеллекта для частной школы "Академия знаний" и детского сада "Академик".

## Описание проекта

Чат-бот предназначен для консультации клиентов в сообщениях двух групп социальной сети «Вконтакте», ведения клиентской базы и автоматизации процессов взаимодействия с потенциальными и существующими клиентами.

### Основные функции

1. **Автоматизированные ответы:**
   - Ответы на часто задаваемые вопросы с использованием базы знаний
   - Ответы на сложные вопросы с использованием ИИ (GigaChat)
   - Возможность администраторам добавлять новую информацию

2. **Обработка запросов:**
   - Прием сообщений от пользователей
   - Определение типа запроса с помощью NLP
   - Многоступенчатые диалоги для сбора информации

3. **Сбор данных пользователей:**
   - Сбор контактной информации (ФИО, телефон, возраст ребенка)
   - Хранение данных в базе данных SQL и Excel-таблице

4. **Запись на мероприятия:**
   - Возможность просмотра и записи на открытые мероприятия
   - Управление участниками мероприятий
   - Отправка подтверждений о записи

5. **Управление и статистика:**
   - Административные команды для управления ботом
   - Статистика по взаимодействию пользователей с ботом
   - Генерация отчетов для анализа эффективности

## Технические требования

- Python 3.8+
- VK API Token
- GigaChat API Key (или другой LLM провайдер)
- База данных SQLite или PostgreSQL

## Установка и настройка

### Обычная установка

1. **Клонирование репозитория:**
   ```bash
   git clone https://github.com/yourusername/Academy_of_knowledge_AI_VKbot.git
   cd Academy_of_knowledge_AI_VKbot
   ```

2. **Установка зависимостей:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Настройка переменных окружения:**  
   Создайте файл `.env` в корне проекта со следующими параметрами:
   ```
   VK_TOKEN=ваш_токен_вк
   GIGACHAT_API_KEY=ваш_ключ_gigachat
   OPENAI_API_KEY=ваш_ключ_openai (опционально)
   DEEPSEEK_API_KEY=ваш_ключ_deepseek (опционально)
   
   SCHOOL_GROUP_ID=id_группы_школы
   KINDERGARTEN_GROUP_ID=id_группы_детсада
   
   ADMIN_IDS=id1,id2,id3
   
   DATABASE_URL=sqlite:///academy_bot.db
   ```

4. **Создание базы знаний:**  
   Создайте директорию для базы знаний:
   ```bash
   mkdir -p data/knowledge_base/docs
   ```

5. **Запуск бота:**
   ```bash
   python main.py
   ```

### Запуск с использованием Docker

1. **Клонирование репозитория:**
   ```bash
   git clone https://github.com/yourusername/Academy_of_knowledge_AI_VKbot.git
   cd Academy_of_knowledge_AI_VKbot
   ```

2. **Настройка переменных окружения:**  
   Создайте файл `.env` в корне проекта как указано выше.

3. **Сборка и запуск с помощью Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Просмотр логов:**
   ```bash
   docker-compose logs -f
   ```

5. **Остановка бота:**
   ```bash
   docker-compose down
   ```

## Структура проекта

```
Academy_of_knowledge_AI_VKbot/
├── config/                 # Конфигурационные файлы
│   └── config.py           # Основной конфиг
├── src/                    # Исходный код
│   ├── ai/                 # Модули для работы с ИИ
│   │   ├── gigachat_handler.py  # Обработчик GigaChat
│   │   └── knowledge_base.py    # База знаний
│   ├── analytics/          # Аналитика и отчёты
│   │   └── analytics_manager.py # Менеджер аналитики
│   ├── bot/                # Модули бота
│   │   ├── conversation_manager.py  # Управление диалогами
│   │   ├── keyboard_generator.py    # Генератор клавиатур
│   │   ├── message_handler.py       # Обработчик сообщений
│   │   └── vk_bot.py               # Основной класс бота
│   ├── database/           # Работа с базами данных
│   │   ├── db_handler.py   # Обработчик SQL базы данных
│   │   └── excel_handler.py # Обработчик Excel файлов
├── data/                   # Данные
│   ├── knowledge_base/     # База знаний
│   ├── reports/            # Отчеты и статистика
│   └── clients.xlsx        # Excel база клиентов
├── logs/                   # Журналы логов
├── main.py                 # Основной файл запуска
├── .env                    # Переменные окружения
├── requirements.txt        # Зависимости
├── Dockerfile              # Файл для сборки Docker-образа
├── docker-compose.yml      # Конфигурация Docker Compose
└── README.md               # Документация
```

## Администрирование бота

Для администрирования бота используются специальные команды, которые могут отправлять пользователи из списка администраторов:

- `/stats` - Статистика бота
- `/addfaq <вопрос> | <ответ>` - Добавить вопрос и ответ в FAQ
- `/addknowledge <категория> <ключ> | <значение>` - Добавить знание в базу знаний
- `/addevent <название> | <описание> | <дата> | <макс_участников>` - Добавить мероприятие
- `/help` - Показать справку

## Добавление контента в базу знаний

База знаний поддерживает несколько категорий:
- `general` - Общая информация
- `school` - Информация о школе
- `kindergarten` - Информация о детском саде
- `faq` - Часто задаваемые вопросы
- `documents` - Выдержки из документов

Для загрузки документов, поместите текстовые файлы в директорию `data/knowledge_base/docs/`.

## Лицензия

Проект доступен под лицензией MIT.

## Поддержка и обновления

Для получения поддержки или предложения улучшений, создайте issue в этом репозитории. 