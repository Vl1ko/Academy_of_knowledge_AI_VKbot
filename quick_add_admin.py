#!/usr/bin/env python3
"""
Быстрое добавление администратора в базу данных
Использование: python3 quick_add_admin.py <VK_ID>
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database.db_handler import DatabaseHandler
import vk_api
from vk_api.exceptions import VkApiError
from config.config import VK_TOKEN

def get_vk_user_name(vk_id: int) -> str:
    """Получить имя пользователя из VK API"""
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        user_info = vk.users.get(user_ids=vk_id, fields='first_name,last_name')
        
        if user_info and len(user_info) > 0:
            user = user_info[0]
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
            
            if first_name and last_name:
                return f"{first_name} {last_name}"
            elif first_name:
                return first_name
            elif last_name:
                return last_name
            else:
                return "Неизвестный пользователь"
        else:
            return "Неизвестный пользователь"
            
    except Exception as e:
        print(f"Ошибка при получении информации о пользователе {vk_id}: {e}")
        return "Неизвестный пользователь"

def add_admin(vk_id: int) -> bool:
    """Добавить администратора в базу данных"""
    db = DatabaseHandler()
    
    try:
        # Получаем имя из VK API
        name = get_vk_user_name(vk_id)
        
        # Проверяем, существует ли пользователь
        existing_user = db.session.query(db.User).filter_by(vk_id=vk_id).first()
        
        if existing_user:
            # Пользователь существует, обновляем статус администратора
            existing_user.is_admin = True
            if not existing_user.name:
                existing_user.name = name
            db.session.commit()
            print(f"✅ Пользователь {name} (ID: {vk_id}) назначен администратором")
            return True
        else:
            # Создаем нового пользователя-администратора
            new_admin = db.User(
                vk_id=vk_id,
                name=name,
                is_admin=True
            )
            db.session.add(new_admin)
            db.session.commit()
            print(f"✅ Создан новый администратор {name} (ID: {vk_id})")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при добавлении администратора {vk_id}: {e}")
        db.session.rollback()
        return False

def main():
    """Основная функция"""
    if len(sys.argv) != 2:
        print("Использование: python3 quick_add_admin.py <VK_ID>")
        print("Пример: python3 quick_add_admin.py 123456789")
        sys.exit(1)
    
    try:
        vk_id = int(sys.argv[1])
        add_admin(vk_id)
    except ValueError:
        print("❌ VK ID должен быть числом")
        sys.exit(1)

if __name__ == "__main__":
    main() 