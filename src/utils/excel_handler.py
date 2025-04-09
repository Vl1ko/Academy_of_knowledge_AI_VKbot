import logging
from typing import Dict, List
import pandas as pd
from datetime import datetime
from config.config import PATHS

class ExcelHandler:
    def __init__(self):
        self.excel_path = PATHS['excel_db']
        self.logger = logging.getLogger(__name__)

    def export_users_to_excel(self, users: List[Dict]) -> bool:
        """
        Экспорт данных пользователей в Excel
        
        Args:
            users: Список словарей с данными пользователей
            
        Returns:
            bool: Успешность операции
        """
        try:
            df = pd.DataFrame(users)
            df.to_excel(self.excel_path, index=False)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при экспорте данных в Excel: {e}")
            return False

    def import_users_from_excel(self) -> List[Dict]:
        """
        Импорт данных пользователей из Excel
        
        Returns:
            List[Dict]: Список словарей с данными пользователей
        """
        try:
            df = pd.read_excel(self.excel_path)
            return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"Ошибка при импорте данных из Excel: {e}")
            return []

    def export_events_to_excel(self, events: List[Dict]) -> bool:
        """
        Экспорт данных о мероприятиях в Excel
        
        Args:
            events: Список словарей с данными о мероприятиях
            
        Returns:
            bool: Успешность операции
        """
        try:
            df = pd.DataFrame(events)
            df['date'] = pd.to_datetime(df['date'])
            df.to_excel(self.excel_path.replace('.xlsx', '_events.xlsx'), index=False)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при экспорте мероприятий в Excel: {e}")
            return False

    def export_statistics_to_excel(self, statistics: Dict) -> bool:
        """
        Экспорт статистики в Excel
        
        Args:
            statistics: Словарь со статистикой
            
        Returns:
            bool: Успешность операции
        """
        try:
            # Создаем DataFrame для каждого типа статистики
            dfs = {}
            for key, value in statistics.items():
                if isinstance(value, list):
                    dfs[key] = pd.DataFrame(value)
                elif isinstance(value, dict):
                    dfs[key] = pd.DataFrame([value])
            
            # Сохраняем каждый DataFrame на отдельный лист
            with pd.ExcelWriter(self.excel_path.replace('.xlsx', '_statistics.xlsx')) as writer:
                for sheet_name, df in dfs.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при экспорте статистики в Excel: {e}")
            return False

    def generate_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """
        Генерация отчета за период
        
        Args:
            start_date: Начальная дата периода
            end_date: Конечная дата периода
            
        Returns:
            Dict: Словарь с данными отчета
        """
        try:
            # Читаем данные из Excel
            users_df = pd.read_excel(self.excel_path)
            events_df = pd.read_excel(self.excel_path.replace('.xlsx', '_events.xlsx'))
            
            # Фильтруем данные по периоду
            users_df['created_at'] = pd.to_datetime(users_df['created_at'])
            users_in_period = users_df[
                (users_df['created_at'] >= start_date) & 
                (users_df['created_at'] <= end_date)
            ]
            
            events_df['date'] = pd.to_datetime(events_df['date'])
            events_in_period = events_df[
                (events_df['date'] >= start_date) & 
                (events_df['date'] <= end_date)
            ]
            
            # Формируем отчет
            report = {
                'period': {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                },
                'users': {
                    'total': len(users_in_period),
                    'by_child_age': users_in_period['child_age'].value_counts().to_dict()
                },
                'events': {
                    'total': len(events_in_period),
                    'total_participants': events_in_period['current_participants'].sum(),
                    'by_name': events_in_period['name'].value_counts().to_dict()
                }
            }
            
            return report
        except Exception as e:
            self.logger.error(f"Ошибка при генерации отчета: {e}")
            return {} 