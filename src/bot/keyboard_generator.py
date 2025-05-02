import json
import logging
from typing import List, Dict, Any, Optional
from vk_api.keyboard import VkKeyboard, VkKeyboardColor


class KeyboardGenerator:
    """
    Generator for VK bot keyboards
    """
    
    def __init__(self):
        """Initialize keyboard generator"""
        self.logger = logging.getLogger(__name__)
    
    def generate_main_menu(self) -> Dict[str, Any]:
        """Generate main menu keyboard"""
        keyboard = VkKeyboard(one_time=False)
        
        # First row
        keyboard.add_button("О школе", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button("О детском саде", color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        
        # Second row
        keyboard.add_button("Записаться на консультацию", color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        
        # Third row
        keyboard.add_button("Цены", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button("Расписание", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        
        # Fourth row
        keyboard.add_button("Связаться с администратором", color=VkKeyboardColor.NEGATIVE)
        
        return keyboard.get_keyboard()
    
    def generate_cancel_button(self) -> Dict[str, Any]:
        """Generate keyboard with cancel button"""
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("Отмена", color=VkKeyboardColor.NEGATIVE)
        return keyboard.get_keyboard()
    
    def generate_admin_menu(self) -> Dict[str, Any]:
        """Generate admin menu keyboard"""
        keyboard = VkKeyboard(one_time=False)
        
        # First row
        keyboard.add_button("Просмотр заявок", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button("Уведомления", color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        
        # Second row
        keyboard.add_button("Статистика", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button("Настройки", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        
        # Third row
        keyboard.add_button("Вернуться в обычный режим", color=VkKeyboardColor.NEGATIVE)
        
        return keyboard.get_keyboard()
    
    def generate_consultation_status_keyboard(self, request_id: int) -> Dict[str, Any]:
        """Generate keyboard for consultation request status management"""
        keyboard = VkKeyboard(one_time=False)
        
        # First row
        keyboard.add_button(
            "Подтвердить",
            color=VkKeyboardColor.POSITIVE,
            payload={"action": "confirm_consultation", "request_id": request_id}
        )
        keyboard.add_button(
            "Отменить",
            color=VkKeyboardColor.NEGATIVE,
            payload={"action": "cancel_consultation", "request_id": request_id}
        )
        keyboard.add_line()
        
        # Second row
        keyboard.add_button(
            "Завершить",
            color=VkKeyboardColor.PRIMARY,
            payload={"action": "complete_consultation", "request_id": request_id}
        )
        keyboard.add_button(
            "Назад",
            color=VkKeyboardColor.SECONDARY,
            payload={"action": "back_to_admin_menu"}
        )
        
        return keyboard.get_keyboard()
    
    def generate_notification_actions_keyboard(self, notification_id: int) -> Dict[str, Any]:
        """Generate keyboard for notification actions"""
        keyboard = VkKeyboard(one_time=False)
        
        # First row
        keyboard.add_button(
            "Ответить",
            color=VkKeyboardColor.POSITIVE,
            payload={"action": "reply_to_notification", "notification_id": notification_id}
        )
        keyboard.add_button(
            "Отметить как прочитанное",
            color=VkKeyboardColor.SECONDARY,
            payload={"action": "mark_notification_read", "notification_id": notification_id}
        )
        keyboard.add_line()
        
        # Second row
        keyboard.add_button(
            "Назад",
            color=VkKeyboardColor.NEGATIVE,
            payload={"action": "back_to_admin_menu"}
        )
        
        return keyboard.get_keyboard()
    
    def generate_confirmation_keyboard(self, action: str, **kwargs) -> Dict[str, Any]:
        """Generate confirmation keyboard"""
        keyboard = VkKeyboard(one_time=False)
        
        # Add payload to buttons
        payload = {"action": action}
        payload.update(kwargs)
        
        # First row
        keyboard.add_button(
            "Да",
            color=VkKeyboardColor.POSITIVE,
            payload={"confirm": True, **payload}
        )
        keyboard.add_button(
            "Нет",
            color=VkKeyboardColor.NEGATIVE,
            payload={"confirm": False, **payload}
        )
        
        return keyboard.get_keyboard()
    
    def generate_back_button(self, label: str = "Вернуться в меню") -> str:
        """
        Generate keyboard with back button
        
        Args:
            label: Button label
            
        Returns:
            Keyboard JSON string
        """
        keyboard = {
            "one_time": False,
            "buttons": [
                [
                    {
                        "action": {
                            "type": "text",
                            "label": label,
                            "payload": json.dumps({"command": "main_menu"})
                        },
                        "color": "secondary"
                    }
                ]
            ]
        }
        
        return json.dumps(keyboard, ensure_ascii=False)
    
    def generate_yes_no_keyboard(self, yes_payload: str = "yes", no_payload: str = "no") -> str:
        """
        Generate Yes/No keyboard
        
        Args:
            yes_payload: Payload for Yes button
            no_payload: Payload for No button
            
        Returns:
            Keyboard JSON string
        """
        keyboard = {
            "one_time": False,
            "buttons": [
                [
                    {
                        "action": {
                            "type": "text",
                            "label": "Да",
                            "payload": json.dumps({"command": yes_payload})
                        },
                        "color": "positive"
                    },
                    {
                        "action": {
                            "type": "text",
                            "label": "Нет",
                            "payload": json.dumps({"command": no_payload})
                        },
                        "color": "negative"
                    }
                ],
                [
                    {
                        "action": {
                            "type": "text",
                            "label": "Вернуться в меню",
                            "payload": json.dumps({"command": "main_menu"})
                        },
                        "color": "secondary"
                    }
                ]
            ]
        }
        
        return json.dumps(keyboard, ensure_ascii=False)
    
    def generate_faq_keyboard(self, questions: List[str]) -> str:
        """
        Generate FAQ keyboard with questions
        
        Args:
            questions: List of questions
            
        Returns:
            Keyboard JSON string
        """
        buttons = []
        
        for question in questions[:4]:  # Limit to 4 questions
            buttons.append([
                {
                    "action": {
                        "type": "text",
                        "label": question[:40],  # Limit length
                        "payload": json.dumps({"command": "faq_question", "question": question})
                    },
                    "color": "primary"
                }
            ])
        
        buttons.append([
            {
                "action": {
                    "type": "text",
                    "label": "Вернуться в меню",
                    "payload": json.dumps({"command": "main_menu"})
                },
                "color": "secondary"
            }
        ])
        
        keyboard = {
            "one_time": False,
            "buttons": buttons
        }
        
        return json.dumps(keyboard, ensure_ascii=False)
    
    def generate_events_keyboard(self, events: List[Dict[str, Any]]) -> str:
        """
        Generate keyboard with events
        
        Args:
            events: List of events
            
        Returns:
            Keyboard JSON string
        """
        buttons = []
        
        for event in events[:4]:  # Limit to 4 events
            buttons.append([
                {
                    "action": {
                        "type": "text",
                        "label": event['name'][:40],  # Limit length
                        "payload": json.dumps({"command": "event_info", "event_id": event['id']})
                    },
                    "color": "primary"
                }
            ])
        
        buttons.append([
            {
                "action": {
                    "type": "text",
                    "label": "Вернуться в меню",
                    "payload": json.dumps({"command": "main_menu"})
                },
                "color": "secondary"
            }
        ])
        
        keyboard = {
            "one_time": False,
            "buttons": buttons
        }
        
        return json.dumps(keyboard, ensure_ascii=False)
    
    def generate_custom_keyboard(self, buttons: List[Dict[str, Any]], one_time: bool = False) -> str:
        """
        Generate custom keyboard
        
        Args:
            buttons: List of button rows
            one_time: Whether keyboard is one-time (disappears after use)
            
        Returns:
            Keyboard JSON string
        """
        keyboard = {
            "one_time": one_time,
            "buttons": buttons
        }
        
        return json.dumps(keyboard, ensure_ascii=False) 