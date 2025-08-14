#!/usr/bin/env python3
"""
Скрипт для добавления администраторов в базу данных
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database.db_handler import DatabaseHandler
import vk_api
from vk_api.exceptions import VkApiError
from config.config import VK_TOKEN

def get_vk_user_name(vk_id: int) -> str:
    """
    Получить имя пользователя из VK API
    
    Args:
        vk_id: VK ID пользователя
        
    Returns:
        Имя пользователя или "Неизвестный пользователь"
    """
    try:
        # Инициализируем VK API
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Получаем информацию о пользователе
        user_info = vk.users.get(user_ids=vk_id, fields='first_name,last_name')
        
        if user_info and len(user_info) > 0:
            user = user_info[0]
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
            
            # Формируем полное имя
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
            
    except VkApiError as e:
        print(f"Ошибка VK API при получении информации о пользователе {vk_id}: {e}")
        return "Неизвестный пользователь"
    except Exception as e:
        print(f"Ошибка при получении информации о пользователе {vk_id}: {e}")
        return "Неизвестный пользователь"

def add_admin(vk_id: int, name: str = None) -> bool:
    """
    Добавить администратора в базу данных
    
    Args:
        vk_id: VK ID администратора
        name: Имя администратора (если не указано, будет получено из VK API)
        
    Returns:
        True если успешно, False если ошибка
    """
    db = DatabaseHandler()
    
    try:
        # Если имя не указано, получаем из VK API
        if not name:
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

def remove_admin(vk_id: int) -> bool:
    """
    Удалить права администратора у пользователя
    
    Args:
        vk_id: VK ID пользователя
        
    Returns:
        True если успешно, False если ошибка
    """
    db = DatabaseHandler()
    
    try:
        user = db.session.query(db.User).filter_by(vk_id=vk_id).first()
        
        if user:
            user.is_admin = False
            db.session.commit()
            print(f"✅ Права администратора удалены у пользователя {user.name} (ID: {vk_id})")
            return True
        else:
            print(f"❌ Пользователь с ID {vk_id} не найден в базе данных")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при удалении прав администратора у {vk_id}: {e}")
        db.session.rollback()
        return False

def list_admins():
    """
    Показать список всех администраторов
    """
    db = DatabaseHandler()
    
    try:
        admins = db.session.query(db.User).filter_by(is_admin=True).all()
        
        if admins:
            print("📋 Список администраторов:")
            print("-" * 50)
            for admin in admins:
                print(f"ID: {admin.vk_id} | Имя: {admin.name or 'Не указано'} | Создан: {admin.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 50)
            print(f"Всего администраторов: {len(admins)}")
        else:
            print("📋 Администраторы не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка при получении списка администраторов: {e}")

def main():
    """
    Основная функция
    """
    print("🔧 Управление администраторами бота")
    print("=" * 50)
    
    while True:
        print("\nВыберите действие:")
        print("1. Добавить администратора")
        print("2. Удалить права администратора")
        print("3. Показать список администраторов")
        print("4. Добавить администратора по VK ID (автоматическое получение имени)")
        print("5. Выход")
        
        choice = input("\nВведите номер действия (1-5): ").strip()
        
        if choice == "1":
            vk_id = input("Введите VK ID администратора: ").strip()
            name = input("Введите имя администратора (или нажмите Enter для автоматического получения): ").strip()
            
            if not vk_id.isdigit():
                print("❌ VK ID должен быть числом")
                continue
                
            if not name:
                name = None  # Будет получено из VK API
                
            add_admin(int(vk_id), name)
            
        elif choice == "2":
            vk_id = input("Введите VK ID пользователя для удаления прав администратора: ").strip()
            
            if not vk_id.isdigit():
                print("❌ VK ID должен быть числом")
                continue
                
            remove_admin(int(vk_id))
            
        elif choice == "3":
            list_admins()
            
        elif choice == "4":
            vk_id = input("Введите VK ID администратора: ").strip()
            
            if not vk_id.isdigit():
                print("❌ VK ID должен быть числом")
                continue
                
            add_admin(int(vk_id))
            
        elif choice == "5":
            print("👋 До свидания!")
            break
            
        else:
            print("❌ Неверный выбор. Пожалуйста, введите число от 1 до 5.")

if __name__ == "__main__":
    main() 