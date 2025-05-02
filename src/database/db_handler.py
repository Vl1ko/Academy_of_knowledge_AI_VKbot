import logging
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

from config.config import DATABASE_URL

Base = declarative_base()

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    message = Column(Text)
    role = Column(String)  # 'user' or 'bot'
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="chat_history")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, unique=True)
    name = Column(String)
    phone = Column(String)
    is_admin = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    last_message = Column(Text)
    child_age = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    consultations = relationship("Consultation", back_populates="user")
    event_registrations = relationship("EventRegistration", back_populates="user")
    chat_history = relationship("ChatHistory", back_populates="user")
    consultation_requests = relationship("ConsultationRequest", back_populates="user")

class Consultation(Base):
    __tablename__ = 'consultations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    date = Column(DateTime)
    status = Column(String)  # scheduled, completed, cancelled
    notes = Column(String)
    user = relationship("User", back_populates="consultations")

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    date = Column(DateTime)
    max_participants = Column(Integer)
    current_participants = Column(Integer, default=0)
    registrations = relationship("EventRegistration", back_populates="event")

class EventRegistration(Base):
    __tablename__ = 'event_registrations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    event_id = Column(Integer, ForeignKey('events.id'))
    registration_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # registered, attended, cancelled
    user = relationship("User", back_populates="event_registrations")
    event = relationship("Event", back_populates="registrations")

class ConsultationRequest(Base):
    __tablename__ = 'consultation_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String)
    phone = Column(String)
    status = Column(String, default='new')  # new, confirmed, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="consultation_requests")

class AdminNotification(Base):
    __tablename__ = 'admin_notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String)  # consultation_request, help_request
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    user = relationship("User")

class DatabaseHandler:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.logger = logging.getLogger(__name__)

    def get_user(self, vk_id: int) -> Optional[Dict]:
        """Get user information"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                return {
                    'id': user.id,
                    'name': user.name,
                    'phone': user.phone,
                    'child_age': user.child_age
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting user: {e}")
            return None

    def create_user(self, vk_id: int, name: str, phone: str, child_age: int) -> bool:
        """Create new user"""
        try:
            user = User(vk_id=vk_id, name=name, phone=phone, child_age=child_age)
            self.session.add(user)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            self.session.rollback()
            return False

    def schedule_consultation(self, user_id: int, date: datetime) -> bool:
        """Schedule a consultation"""
        try:
            consultation = Consultation(user_id=user_id, date=date, status='scheduled')
            self.session.add(consultation)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error scheduling consultation: {e}")
            self.session.rollback()
            return False

    def check_event_availability(self, event_id: int) -> bool:
        """Check event availability"""
        try:
            event = self.session.query(Event).filter_by(id=event_id).first()
            if event and event.current_participants < event.max_participants:
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking event availability: {e}")
            return False

    def register_for_event(self, user_id: int, event_id: int) -> bool:
        """Register user for event"""
        try:
            event = self.session.query(Event).filter_by(id=event_id).first()
            if event and event.current_participants < event.max_participants:
                registration = EventRegistration(
                    user_id=user_id,
                    event_id=event_id,
                    status='registered'
                )
                event.current_participants += 1
                self.session.add(registration)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error registering for event: {e}")
            self.session.rollback()
            return False

    def get_upcoming_events(self) -> List[Dict]:
        """Get list of upcoming events"""
        try:
            events = self.session.query(Event).filter(
                Event.date > datetime.utcnow()
            ).order_by(Event.date).all()
            
            return [{
                'id': event.id,
                'name': event.name,
                'description': event.description,
                'date': event.date,
                'available_spots': event.max_participants - event.current_participants
            } for event in events]
        except Exception as e:
            self.logger.error(f"Error getting upcoming events: {e}")
            return []

    def get_user_data(self, vk_id: int) -> Optional[Dict]:
        """Get user data for chatbot"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                return {
                    'id': user.id,
                    'name': user.name,
                    'phone': user.phone,
                    'child_age': user.child_age
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting user data: {e}")
            return None
            
    def update_user_intent(self, vk_id: int, intent: str, message: str) -> bool:
        """Update user intent based on message"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if not user:
                user = User(vk_id=vk_id)
                self.session.add(user)
                
            if intent == "consultation":
                pass
            
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating user intent: {e}")
            self.session.rollback()
            return False

    def add_user(self, vk_id: int) -> bool:
        """Add new user without detailed information"""
        try:
            user = User(vk_id=vk_id)
            self.session.add(user)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding user: {e}")
            self.session.rollback()
            return False
            
    def update_user_last_message(self, vk_id: int, message: str) -> bool:
        """Update user's last message and activity time"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                user.last_message = message
                user.last_activity = datetime.utcnow()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error updating user last message: {e}")
            self.session.rollback()
            return False
            
    def log_successful_kb_response(self, vk_id: int, query: str, response: str) -> bool:
        """Log successful knowledge base response"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                chat_history = ChatHistory(
                    user_id=user.id,
                    message=query,
                    role='user'
                )
                self.session.add(chat_history)
                
                bot_response = ChatHistory(
                    user_id=user.id,
                    message=response,
                    role='bot'
                )
                self.session.add(bot_response)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error logging KB response: {e}")
            self.session.rollback()
            return False
            
    def log_successful_ai_response(self, vk_id: int, query: str, response: str) -> bool:
        """Log successful AI response"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                chat_history = ChatHistory(
                    user_id=user.id,
                    message=query,
                    role='user'
                )
                self.session.add(chat_history)
                
                bot_response = ChatHistory(
                    user_id=user.id,
                    message=response,
                    role='bot'
                )
                self.session.add(bot_response)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error logging AI response: {e}")
            self.session.rollback()
            return False

    def get_admin_ids(self) -> List[int]:
        """Get list of admin VK IDs"""
        admins = self.session.query(User).filter_by(is_admin=True).all()
        return [admin.vk_id for admin in admins]

    def save_consultation_request(self, vk_id: int, name: str, phone: str) -> bool:
        """Save consultation request"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if not user:
                user = User(vk_id=vk_id)
                self.session.add(user)
            
            request = ConsultationRequest(
                user_id=user.id,
                name=name,
                phone=phone
            )
            self.session.add(request)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving consultation request: {e}")
            self.session.rollback()
            return False

    def get_consultation_requests(self, status: str = None) -> List[Dict]:
        """Get consultation requests"""
        try:
            query = self.session.query(ConsultationRequest)
            if status:
                query = query.filter_by(status=status)
            requests = query.order_by(ConsultationRequest.created_at.desc()).all()
            
            return [{
                'id': req.id,
                'user_id': req.user.vk_id,
                'name': req.name,
                'phone': req.phone,
                'status': req.status,
                'created_at': req.created_at.isoformat()
            } for req in requests]
        except Exception as e:
            self.logger.error(f"Error getting consultation requests: {e}")
            return []

    def update_consultation_status(self, request_id: int, status: str) -> bool:
        """Update consultation request status"""
        try:
            request = self.session.query(ConsultationRequest).get(request_id)
            if request:
                request.status = status
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error updating consultation status: {e}")
            self.session.rollback()
            return False

    def save_admin_notification(self, user_id: int, notification_type: str, message: str) -> bool:
        """Save admin notification"""
        try:
            user = self.session.query(User).filter_by(vk_id=user_id).first()
            if not user:
                return False
            
            notification = AdminNotification(
                user_id=user.id,
                type=notification_type,
                message=message
            )
            self.session.add(notification)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving admin notification: {e}")
            self.session.rollback()
            return False

    def get_unread_notifications(self) -> List[Dict]:
        """Get unread admin notifications"""
        try:
            notifications = self.session.query(AdminNotification)\
                .filter_by(is_read=False)\
                .order_by(AdminNotification.created_at.desc())\
                .all()
            
            return [{
                'id': notif.id,
                'user_id': notif.user.vk_id,
                'type': notif.type,
                'message': notif.message,
                'created_at': notif.created_at.isoformat()
            } for notif in notifications]
        except Exception as e:
            self.logger.error(f"Error getting unread notifications: {e}")
            return []

    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        try:
            notification = self.session.query(AdminNotification).get(notification_id)
            if notification:
                notification.is_read = True
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error marking notification as read: {e}")
            self.session.rollback()
            return False

    def get_user_history(self, vk_id: int, limit: int = 10) -> List[Dict]:
        """Get user's chat history"""
        try:
            user = self.session.query(User).filter_by(vk_id=vk_id).first()
            if not user:
                return []
            
            history = self.session.query(ChatHistory)\
                .filter_by(user_id=user.id)\
                .order_by(ChatHistory.timestamp.desc())\
                .limit(limit)\
                .all()
            
            return [{
                'message': entry.message,
                'role': entry.role,
                'timestamp': entry.timestamp.isoformat()
            } for entry in history]
        except Exception as e:
            self.logger.error(f"Error getting user history: {e}")
            return [] 