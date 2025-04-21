import logging
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
from typing import Dict, List, Any, Optional
import json

from src.database.excel_handler import ExcelHandler


class AnalyticsManager:
    """
    Manager for analytics and reporting
    """
    
    def __init__(self, excel_handler: ExcelHandler = None, reports_dir: str = "data/reports"):
        """
        Initialize analytics manager
        
        Args:
            excel_handler: Excel handler instance
            reports_dir: Directory for reports
        """
        self.logger = logging.getLogger(__name__)
        self.excel_handler = excel_handler or ExcelHandler()
        self.reports_dir = reports_dir
        
        # Create reports directory if not exists
        os.makedirs(reports_dir, exist_ok=True)
    
    def generate_monthly_report(self, month: int = None, year: int = None) -> str:
        """
        Generate monthly report
        
        Args:
            month: Month number (1-12), current month if None
            year: Year number, current year if None
            
        Returns:
            Path to saved report
        """
        try:
            # Set default month and year to current if not provided
            if month is None:
                month = datetime.now().month
            if year is None:
                year = datetime.now().year
            
            month_name = datetime(year, month, 1).strftime("%B")
            
            # Get data
            clients_df = self.excel_handler.export_user_data()
            events_df = self.excel_handler.export_event_data()
            registrations_df = self.excel_handler.export_registration_data()
            
            # Convert dates to datetime
            if 'created_at' in clients_df.columns:
                clients_df['created_at'] = pd.to_datetime(clients_df['created_at'])
            
            if 'registration_date' in registrations_df.columns:
                registrations_df['registration_date'] = pd.to_datetime(registrations_df['registration_date'])
            
            # Filter by month and year
            clients_month = clients_df[
                (clients_df['created_at'].dt.month == month) & 
                (clients_df['created_at'].dt.year == year)
            ] if 'created_at' in clients_df.columns else pd.DataFrame()
            
            registrations_month = registrations_df[
                (registrations_df['registration_date'].dt.month == month) & 
                (registrations_df['registration_date'].dt.year == year)
            ] if 'registration_date' in registrations_df.columns else pd.DataFrame()
            
            # Generate report
            report = {
                "month": month_name,
                "year": year,
                "new_clients": len(clients_month),
                "total_clients": len(clients_df),
                "new_registrations": len(registrations_month),
                "total_registrations": len(registrations_df),
                "interests": self._get_top_interests(clients_df),
                "popular_events": self._get_popular_events(registrations_df, events_df),
                "child_age_distribution": self._get_age_distribution(clients_df),
                "daily_activity": self._get_daily_activity(registrations_month),
                "generated_at": datetime.now().isoformat()
            }
            
            # Save report
            report_filename = f"monthly_report_{year}_{month:02d}.json"
            report_path = os.path.join(self.reports_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            # Generate visualization if there's data
            if not clients_month.empty:
                self._generate_visualizations(report, year, month)
            
            return report_path
        
        except Exception as e:
            self.logger.error(f"Error generating monthly report: {e}")
            return ""
    
    def _get_top_interests(self, clients_df: pd.DataFrame, top_n: int = 5) -> Dict[str, int]:
        """
        Get top client interests
        
        Args:
            clients_df: Clients DataFrame
            top_n: Number of top interests to return
            
        Returns:
            Dictionary of interest -> count
        """
        if 'interests' not in clients_df.columns or clients_df.empty:
            return {}
        
        # Count interests (assuming interests are comma-separated values)
        all_interests = []
        for interests_str in clients_df['interests'].dropna():
            if isinstance(interests_str, str):
                interests = [i.strip() for i in interests_str.split(',')]
                all_interests.extend(interests)
        
        # Count occurrences
        interest_counts = {}
        for interest in all_interests:
            if interest:  # Skip empty strings
                interest_counts[interest] = interest_counts.get(interest, 0) + 1
        
        # Sort by count
        sorted_interests = sorted(interest_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Take top N
        return dict(sorted_interests[:top_n])
    
    def _get_popular_events(self, registrations_df: pd.DataFrame, events_df: pd.DataFrame, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Get most popular events
        
        Args:
            registrations_df: Registrations DataFrame
            events_df: Events DataFrame
            top_n: Number of top events to return
            
        Returns:
            List of event data dictionaries
        """
        if registrations_df.empty or events_df.empty:
            return []
        
        # Count registrations per event
        event_counts = registrations_df['event_id'].value_counts().reset_index()
        event_counts.columns = ['event_id', 'count']
        
        # Join with events data
        if not event_counts.empty and not events_df.empty:
            popular_events = pd.merge(
                event_counts, 
                events_df, 
                left_on='event_id', 
                right_on='id',
                how='left'
            )
            
            # Sort by count and take top N
            popular_events = popular_events.sort_values('count', ascending=False).head(top_n)
            
            # Convert to dictionaries
            result = []
            for _, row in popular_events.iterrows():
                result.append({
                    'id': row['id'],
                    'name': row['name'] if 'name' in row else f"Event {row['id']}",
                    'registrations': int(row['count']),
                    'capacity': int(row['max_participants']) if 'max_participants' in row else 0
                })
            
            return result
        
        return []
    
    def _get_age_distribution(self, clients_df: pd.DataFrame) -> Dict[str, int]:
        """
        Get distribution of child ages
        
        Args:
            clients_df: Clients DataFrame
            
        Returns:
            Dictionary of age group -> count
        """
        if 'child_age' not in clients_df.columns or clients_df.empty:
            return {}
        
        # Drop NaN values
        ages = clients_df['child_age'].dropna()
        
        if ages.empty:
            return {}
        
        # Define age groups
        age_groups = {
            "0-3": 0,
            "4-6": 0,
            "7-10": 0,
            "11-14": 0,
            "15+": 0
        }
        
        # Count by age group
        for age in ages:
            if pd.notnull(age):
                try:
                    age_val = int(age)
                    if age_val <= 3:
                        age_groups["0-3"] += 1
                    elif age_val <= 6:
                        age_groups["4-6"] += 1
                    elif age_val <= 10:
                        age_groups["7-10"] += 1
                    elif age_val <= 14:
                        age_groups["11-14"] += 1
                    else:
                        age_groups["15+"] += 1
                except (ValueError, TypeError):
                    continue
        
        # Remove empty groups
        return {k: v for k, v in age_groups.items() if v > 0}
    
    def _get_daily_activity(self, registrations_df: pd.DataFrame) -> Dict[str, int]:
        """
        Get daily activity based on registrations
        
        Args:
            registrations_df: Registrations DataFrame for the month
            
        Returns:
            Dictionary of day -> count
        """
        if 'registration_date' not in registrations_df.columns or registrations_df.empty:
            return {}
        
        # Count by day
        daily_counts = registrations_df.groupby(
            registrations_df['registration_date'].dt.date
        ).size().to_dict()
        
        # Convert dates to strings
        return {str(date): count for date, count in daily_counts.items()}
    
    def _generate_visualizations(self, report: Dict[str, Any], year: int, month: int) -> None:
        """
        Generate visualizations for report
        
        Args:
            report: Report data
            year: Year number
            month: Month number
        """
        try:
            plt.figure(figsize=(10, 6))
            
            # Age distribution pie chart
            if report['child_age_distribution']:
                plt.clf()
                plt.pie(
                    report['child_age_distribution'].values(),
                    labels=report['child_age_distribution'].keys(),
                    autopct='%1.1f%%',
                    startangle=90
                )
                plt.axis('equal')
                plt.title(f'Child Age Distribution - {report["month"]} {year}')
                
                chart_path = os.path.join(
                    self.reports_dir, 
                    f"age_distribution_{year}_{month:02d}.png"
                )
                plt.savefig(chart_path)
            
            # Daily activity bar chart
            if report['daily_activity']:
                plt.clf()
                dates = list(report['daily_activity'].keys())
                counts = list(report['daily_activity'].values())
                
                plt.bar(dates, counts)
                plt.xticks(rotation=45)
                plt.xlabel('Date')
                plt.ylabel('Registrations')
                plt.title(f'Daily Activity - {report["month"]} {year}')
                plt.tight_layout()
                
                chart_path = os.path.join(
                    self.reports_dir, 
                    f"daily_activity_{year}_{month:02d}.png"
                )
                plt.savefig(chart_path)
        
        except Exception as e:
            self.logger.error(f"Error generating visualizations: {e}")
    
    def get_conversation_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get statistics about conversations
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary with statistics
        """
        # This would require chat history from the database
        # For now, we'll just return a placeholder
        return {
            "total_conversations": 0,
            "average_messages_per_user": 0,
            "popular_topics": {},
            "period": f"Last {days} days"
        }
    
    def get_user_activity(self, vk_id: int) -> Dict[str, Any]:
        """
        Get activity statistics for specific user
        
        Args:
            vk_id: VK user ID
            
        Returns:
            Dictionary with user activity data
        """
        try:
            # Get user data
            user = self.excel_handler.get_user(vk_id)
            if not user:
                return {}
            
            # Get user events
            user_events = self.excel_handler.get_user_events(vk_id)
            
            return {
                "vk_id": vk_id,
                "name": user.get("name", "Unknown"),
                "registration_date": user.get("created_at", "Unknown"),
                "events_registered": len(user_events),
                "events": user_events,
                "child_age": user.get("child_age", "Unknown")
            }
        except Exception as e:
            self.logger.error(f"Error getting user activity: {e}")
            return {} 