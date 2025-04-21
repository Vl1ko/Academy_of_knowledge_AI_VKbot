import json
import logging
from typing import List, Dict, Any, Optional


class KeyboardGenerator:
    """
    Generator for VK bot keyboards
    """
    
    def __init__(self):
        """Initialize keyboard generator"""
        self.logger = logging.getLogger(__name__)
    
    def generate_main_menu(self) -> str:
        """
        Generate main menu keyboard
        
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
                            "label": "О школе",
                            "payload": json.dumps({"command": "about_school"})
                        },
                        "color": "primary"
                    },
                    {
                        "action": {
                            "type": "text",
                            "label": "О детском саде",
                            "payload": json.dumps({"command": "about_kindergarten"})
                        },
                        "color": "primary"
                    }
                ],
                [
                    {
                        "action": {
                            "type": "text",
                            "label": "Записаться на консультацию",
                            "payload": json.dumps({"command": "consultation"})
                        },
                        "color": "positive"
                    }
                ],
                [
                    {
                        "action": {
                            "type": "text",
                            "label": "Предстоящие мероприятия",
                            "payload": json.dumps({"command": "events"})
                        },
                        "color": "secondary"
                    },
                    {
                        "action": {
                            "type": "text",
                            "label": "FAQ",
                            "payload": json.dumps({"command": "faq"})
                        },
                        "color": "secondary"
                    }
                ]
            ]
        }
        
        return json.dumps(keyboard, ensure_ascii=False)
    
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