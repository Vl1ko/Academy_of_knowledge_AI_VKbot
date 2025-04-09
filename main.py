import logging
import logging.config
import os
from dotenv import load_dotenv

from src.bot.vk_bot import VkBot
from config.config import LOGGING

def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов, если она не существует
    os.makedirs('logs', exist_ok=True)
    
    # Настраиваем логирование
    logging.config.dictConfig(LOGGING)

def main():
    """Основная функция запуска бота"""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Создаем и запускаем бота
        bot = VkBot()
        logger.info("Бот запущен и готов к работе")
        bot.run()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    main() 