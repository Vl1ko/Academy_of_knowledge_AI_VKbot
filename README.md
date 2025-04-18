# AI VK Bot for Academy of Knowledge

A VK chatbot powered by AI models (GigaChat, OpenAI, DeepSeek) for the educational project "Academy of Knowledge". The bot helps users learn about courses, answers questions, and registers for classes.

## Features

- Multi-model AI integration (GigaChat, OpenAI, DeepSeek)
- Intent detection and conversation management
- User data collection and storage
- Course and event registration
- Chat history tracking
- Consultation scheduling

## Project Structure

```
Academy_of_knowledge_AI_VKbot/
├── config/           # Configuration files
├── data/             # Data files
├── logs/             # Log files
├── src/              # Source code
│   ├── ai/           # AI model handlers
│   │   ├── gigachat_handler.py    # GigaChat integration
│   │   ├── openai_handler.py      # OpenAI integration
│   │   └── deepseek_handler.py    # DeepSeek integration
│   ├── bot/          # Bot implementation
│   │   ├── vk_bot.py # VK bot implementation
│   │   └── message_handler.py     # Message processing logic
│   ├── database/     # Database operations
│   │   └── db_handler.py          # SQLAlchemy models and handlers
│   └── utils/        # Utility modules
│       ├── statistics.py           # Statistics gathering
│       └── excel_handler.py        # Excel export/import
├── main.py           # Entry point
├── requirements.txt  # Dependencies
└── .env.example      # Environment variables example
```

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run the bot: `python main.py`

## Environment Variables

Create a `.env` file with the following variables:

```
# VK API
VK_TOKEN=your_vk_token
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
```

## AI Models

The bot can use three different AI models:

- **GigaChat**: Fast Russian-language model with excellent understanding of educational topics.
- **OpenAI**: GPT-4 model with high intelligence and knowledge of various subjects.
- **DeepSeek**: Alternative model with competitive performance.

The active model can be selected in the configuration.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 