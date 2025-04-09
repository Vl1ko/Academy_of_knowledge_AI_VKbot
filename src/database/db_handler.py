import logging
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

from config.config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, unique=True)
    name = Column(String)
    phone = Column(String)
    child_age = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    consultations = relationship("Consultation", back_populates="user")
    event_registrations = relationship("EventRegistration", back_populates="user")

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

class DatabaseHandler:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.logger = logging.getLogger(__name__)

    def get_user(self, vk_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
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
            self.logger.error(f"Ошибка при получении пользователя: {e}")
            return None

    def create_user(self, vk_id: int, name: str, phone: str, child_age: int) -> bool:
        """Создание нового пользователя"""
        try:
            user = User(vk_id=vk_id, name=name, phone=phone, child_age=child_age)
            self.session.add(user)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при создании пользователя: {e}")
            self.session.rollback()
            return False

    def schedule_consultation(self, user_id: int, date: datetime) -> bool:
        """Запись на консультацию"""
        try:
            consultation = Consultation(user_id=user_id, date=date, status='scheduled')
            self.session.add(consultation)
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при записи на консультацию: {e}")
            self.session.rollback()
            return False

    def check_event_availability(self, event_id: int) -> bool:
        """Проверка наличия свободных мест на мероприятии"""
        try:
            event = self.session.query(Event).filter_by(id=event_id).first()
            if event and event.current_participants < event.max_participants:
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при проверке доступности мероприятия: {e}")
            return False

    def register_for_event(self, user_id: int, event_id: int) -> bool:
        """Регистрация на мероприятие"""
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
            self.logger.error(f"Ошибка при регистрации на мероприятие: {e}")
            self.session.rollback()
            return False

    def get_upcoming_events(self) -> List[Dict]:
        """Получение списка предстоящих мероприятий"""
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
            self.logger.error(f"Ошибка при получении списка мероприятий: {e}")
            return [] 