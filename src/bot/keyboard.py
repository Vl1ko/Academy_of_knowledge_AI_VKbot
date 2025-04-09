from typing import Dict, List

class Keyboard:
    def __init__(self):
        self.buttons = {
            'primary': 'primary',
            'secondary': 'secondary',
            'positive': 'positive',
            'negative': 'negative'
        }

    def _create_button(self, label: str, color: str, payload: Dict = None) -> Dict:
        """Создание кнопки"""
        button = {
            "action": {
                "type": "text",
                "label": label,
                "payload": payload or {}
            },
            "color": color
        }
        return button

    def _create_keyboard(self, buttons: List[List[Dict]], one_time: bool = False) -> Dict:
        """Создание клавиатуры"""
        keyboard = {
            "one_time": one_time,
            "buttons": buttons
        }
        return keyboard

    def get_main_keyboard(self) -> Dict:
        """Основная клавиатура"""
        buttons = [
            [
                self._create_button("Записаться на консультацию", self.buttons['primary']),
                self._create_button("Информация о школе", self.buttons['secondary'])
            ],
            [
                self._create_button("Расписание занятий", self.buttons['secondary']),
                self._create_button("Стоимость обучения", self.buttons['secondary'])
            ],
            [
                self._create_button("Записаться на мероприятие", self.buttons['positive'])
            ]
        ]
        return self._create_keyboard(buttons)

    def get_contact_keyboard(self) -> Dict:
        """Клавиатура для получения контактов"""
        buttons = [
            [
                self._create_button("Отправить контакт", self.buttons['primary'], {"type": "contact"})
            ]
        ]
        return self._create_keyboard(buttons, one_time=True)

    def get_info_keyboard(self) -> Dict:
        """Клавиатура с информационными кнопками"""
        buttons = [
            [
                self._create_button("О программе обучения", self.buttons['secondary']),
                self._create_button("О преподавателях", self.buttons['secondary'])
            ],
            [
                self._create_button("О поступлении", self.buttons['secondary']),
                self._create_button("О дополнительном образовании", self.buttons['secondary'])
            ],
            [
                self._create_button("Вернуться в главное меню", self.buttons['primary'])
            ]
        ]
        return self._create_keyboard(buttons)

    def get_event_keyboard(self, events: List[Dict]) -> Dict:
        """Клавиатура для выбора мероприятия"""
        buttons = []
        for event in events:
            buttons.append([
                self._create_button(
                    event['name'],
                    self.buttons['primary'],
                    {"type": "event", "event_id": event['id']}
                )
            ])
        buttons.append([
            self._create_button("Вернуться в главное меню", self.buttons['secondary'])
        ])
        return self._create_keyboard(buttons) 