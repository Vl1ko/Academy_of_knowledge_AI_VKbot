import logging
from typing import Dict, List
from datetime import datetime, timedelta
from collections import Counter

from ..database.db_handler import DatabaseHandler, User, Event, Consultation
from .excel_handler import ExcelHandler

class Statistics:
    def __init__(self):
        self.db = DatabaseHandler()
        self.excel = ExcelHandler()
        self.logger = logging.getLogger(__name__)

    def collect_daily_statistics(self) -> Dict:
        """
        Collect daily statistics
        
        Returns:
            Dict: Dictionary with statistics
        """
        try:
            today = datetime.utcnow().date()
            yesterday = today - timedelta(days=1)
            
            # Get data from database
            users = self.db.session.query(User).filter(
                User.created_at >= yesterday,
                User.created_at < today
            ).all()
            
            events = self.db.session.query(Event).filter(
                Event.date >= yesterday,
                Event.date < today
            ).all()
            
            # Form statistics
            stats = {
                'date': yesterday.strftime('%Y-%m-%d'),
                'new_users': len(users),
                'events': {
                    'total': len(events),
                    'participants': sum(event.current_participants for event in events)
                },
                'user_age_distribution': Counter(user.child_age for user in users),
                'event_types': Counter(event.name for event in events)
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Error collecting daily statistics: {e}")
            return {}

    def collect_weekly_statistics(self) -> Dict:
        """
        Collect weekly statistics
        
        Returns:
            Dict: Dictionary with statistics
        """
        try:
            today = datetime.utcnow().date()
            week_ago = today - timedelta(days=7)
            
            # Get data from database
            users = self.db.session.query(User).filter(
                User.created_at >= week_ago,
                User.created_at < today
            ).all()
            
            events = self.db.session.query(Event).filter(
                Event.date >= week_ago,
                Event.date < today
            ).all()
            
            consultations = self.db.session.query(Consultation).filter(
                Consultation.date >= week_ago,
                Consultation.date < today
            ).all()
            
            # Form statistics
            stats = {
                'period': {
                    'start': week_ago.strftime('%Y-%m-%d'),
                    'end': today.strftime('%Y-%m-%d')
                },
                'users': {
                    'total': len(users),
                    'age_distribution': Counter(user.child_age for user in users),
                    'by_day': Counter(user.created_at.date() for user in users)
                },
                'events': {
                    'total': len(events),
                    'total_participants': sum(event.current_participants for event in events),
                    'by_type': Counter(event.name for event in events),
                    'by_day': Counter(event.date.date() for event in events)
                },
                'consultations': {
                    'total': len(consultations),
                    'completed': len([c for c in consultations if c.status == 'completed']),
                    'cancelled': len([c for c in consultations if c.status == 'cancelled']),
                    'by_day': Counter(c.date.date() for c in consultations)
                }
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Error collecting weekly statistics: {e}")
            return {}

    def collect_monthly_statistics(self) -> Dict:
        """
        Collect monthly statistics
        
        Returns:
            Dict: Dictionary with statistics
        """
        try:
            today = datetime.utcnow().date()
            month_ago = today - timedelta(days=30)
            
            # Get data from database
            users = self.db.session.query(User).filter(
                User.created_at >= month_ago,
                User.created_at < today
            ).all()
            
            events = self.db.session.query(Event).filter(
                Event.date >= month_ago,
                Event.date < today
            ).all()
            
            consultations = self.db.session.query(Consultation).filter(
                Consultation.date >= month_ago,
                Consultation.date < today
            ).all()
            
            # Form statistics
            stats = {
                'period': {
                    'start': month_ago.strftime('%Y-%m-%d'),
                    'end': today.strftime('%Y-%m-%d')
                },
                'users': {
                    'total': len(users),
                    'age_distribution': Counter(user.child_age for user in users),
                    'by_week': Counter(user.created_at.isocalendar()[1] for user in users)
                },
                'events': {
                    'total': len(events),
                    'total_participants': sum(event.current_participants for event in events),
                    'by_type': Counter(event.name for event in events),
                    'by_week': Counter(event.date.isocalendar()[1] for event in events)
                },
                'consultations': {
                    'total': len(consultations),
                    'completed': len([c for c in consultations if c.status == 'completed']),
                    'cancelled': len([c for c in consultations if c.status == 'cancelled']),
                    'by_week': Counter(c.date.isocalendar()[1] for c in consultations)
                },
                'conversion': {
                    'users_to_consultations': len(consultations) / len(users) if users else 0,
                    'consultations_to_completed': len([c for c in consultations if c.status == 'completed']) / len(consultations) if consultations else 0
                }
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Error collecting monthly statistics: {e}")
            return {}

    def export_statistics(self, period: str = 'daily') -> bool:
        """
        Export statistics to Excel
        
        Args:
            period: Statistics period (daily, weekly, monthly)
            
        Returns:
            bool: Operation success
        """
        try:
            if period == 'daily':
                stats = self.collect_daily_statistics()
            elif period == 'weekly':
                stats = self.collect_weekly_statistics()
            elif period == 'monthly':
                stats = self.collect_monthly_statistics()
            else:
                raise ValueError(f"Unknown period: {period}")
            
            return self.excel.export_statistics_to_excel(stats)
        except Exception as e:
            self.logger.error(f"Error exporting statistics: {e}")
            return False 