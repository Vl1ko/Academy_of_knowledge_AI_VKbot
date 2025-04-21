import logging
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class ExcelHandler:
    """
    Handler for Excel database integration
    """
    
    def __init__(self, excel_path: str = "data/clients.xlsx"):
        """
        Initialize Excel handler
        
        Args:
            excel_path: Path to Excel file
        """
        self.logger = logging.getLogger(__name__)
        self.excel_path = excel_path
        
        # Create directory if not exists
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        # Create file if not exists
        if not os.path.exists(excel_path):
            self._create_initial_excel()
        
        # Load Excel file
        try:
            self.df_clients = pd.read_excel(excel_path, sheet_name="Clients")
            self.df_events = pd.read_excel(excel_path, sheet_name="Events")
            self.df_registrations = pd.read_excel(excel_path, sheet_name="Registrations")
            
            # Load consultations sheet or create it if it doesn't exist
            try:
                self.df_consultations = pd.read_excel(excel_path, sheet_name="Consultations")
                
                # Проверим, содержит ли таблица новые поля, и обновим её при необходимости
                if "phone" in self.df_consultations.columns and "child_info" not in self.df_consultations.columns:
                    self.logger.info("Updating Consultations sheet structure to include child_info and wishes fields")
                    # Создаем новые поля
                    self.df_consultations["child_info"] = None
                    self.df_consultations["wishes"] = None
                    
                    # Копируем данные из старых полей в новые, если это возможно
                    if "topic" in self.df_consultations.columns:
                        self.df_consultations["wishes"] = self.df_consultations["topic"]
                    
                    # Удаляем старые поля
                    if "phone" in self.df_consultations.columns:
                        self.df_consultations = self.df_consultations.drop("phone", axis=1)
                    if "preferred_date" in self.df_consultations.columns:
                        self.df_consultations = self.df_consultations.drop("preferred_date", axis=1)
                    if "topic" in self.df_consultations.columns:
                        self.df_consultations = self.df_consultations.drop("topic", axis=1)
                    
                    self._save_excel()
                
            except Exception:
                self.df_consultations = pd.DataFrame(columns=[
                    "id", "vk_id", "name", "child_info", "wishes", 
                    "status", "created_at", "notes"
                ])
                self._save_excel()
                
        except Exception as e:
            self.logger.error(f"Error loading Excel file: {e}")
            self._create_initial_excel()
            self.df_clients = pd.read_excel(excel_path, sheet_name="Clients")
            self.df_events = pd.read_excel(excel_path, sheet_name="Events")
            self.df_registrations = pd.read_excel(excel_path, sheet_name="Registrations")
            self.df_consultations = pd.read_excel(excel_path, sheet_name="Consultations")
    
    def _create_initial_excel(self) -> None:
        """Create initial Excel file with empty sheets"""
        try:
            # Create clients dataframe
            df_clients = pd.DataFrame(columns=[
                "vk_id", "name", "phone", "email", "child_name", "child_age",
                "source", "interests", "created_at", "notes"
            ])
            
            # Create events dataframe
            df_events = pd.DataFrame(columns=[
                "id", "name", "description", "date", "max_participants",
                "current_participants", "status", "created_at"
            ])
            
            # Create registrations dataframe
            df_registrations = pd.DataFrame(columns=[
                "id", "user_vk_id", "event_id", "registration_date", "status"
            ])
            
            # Create consultations dataframe
            df_consultations = pd.DataFrame(columns=[
                "id", "vk_id", "name", "child_info", "wishes", 
                "status", "created_at", "notes"
            ])
            
            # Create Excel file with multiple sheets
            with pd.ExcelWriter(self.excel_path, engine="openpyxl") as writer:
                df_clients.to_excel(writer, sheet_name="Clients", index=False)
                df_events.to_excel(writer, sheet_name="Events", index=False)
                df_registrations.to_excel(writer, sheet_name="Registrations", index=False)
                df_consultations.to_excel(writer, sheet_name="Consultations", index=False)
            
            self.logger.info(f"Created new Excel file at {self.excel_path}")
        except Exception as e:
            self.logger.error(f"Error creating Excel file: {e}")
            raise
    
    def _save_excel(self) -> None:
        """Save dataframes to Excel file"""
        try:
            with pd.ExcelWriter(self.excel_path, engine="openpyxl") as writer:
                self.df_clients.to_excel(writer, sheet_name="Clients", index=False)
                self.df_events.to_excel(writer, sheet_name="Events", index=False)
                self.df_registrations.to_excel(writer, sheet_name="Registrations", index=False)
                self.df_consultations.to_excel(writer, sheet_name="Consultations", index=False)
            
            self.logger.info(f"Saved Excel file at {self.excel_path}")
        except Exception as e:
            self.logger.error(f"Error saving Excel file: {e}")
            raise
    
    def get_user(self, vk_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by VK ID
        
        Args:
            vk_id: VK user ID
            
        Returns:
            User data as dictionary or None if not found
        """
        try:
            user = self.df_clients[self.df_clients["vk_id"] == vk_id]
            if user.empty:
                return None
            
            return user.iloc[0].to_dict()
        except Exception as e:
            self.logger.error(f"Error getting user: {e}")
            return None
    
    def add_user(self, user_data: Dict[str, Any]) -> bool:
        """
        Add new user to Excel
        
        Args:
            user_data: User data dictionary
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Check if user already exists
            existing_user = self.df_clients[self.df_clients["vk_id"] == user_data["vk_id"]]
            if not existing_user.empty:
                # Update existing user
                for key, value in user_data.items():
                    if key in self.df_clients.columns:
                        self.df_clients.loc[existing_user.index[0], key] = value
            else:
                # Ensure all required columns are in user_data
                for col in self.df_clients.columns:
                    if col not in user_data:
                        user_data[col] = None
                
                # Set created_at if not provided
                if not user_data.get("created_at"):
                    user_data["created_at"] = datetime.now()
                
                # Add new user
                self.df_clients = pd.concat([self.df_clients, pd.DataFrame([user_data])], ignore_index=True)
            
            # Save Excel file
            self._save_excel()
            return True
        except Exception as e:
            self.logger.error(f"Error adding user: {e}")
            return False
    
    def update_user(self, vk_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update user data
        
        Args:
            vk_id: VK user ID
            updates: Dictionary with updates
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            user_idx = self.df_clients[self.df_clients["vk_id"] == vk_id].index
            if user_idx.empty:
                return False
            
            for key, value in updates.items():
                if key in self.df_clients.columns:
                    self.df_clients.loc[user_idx[0], key] = value
            
            self._save_excel()
            return True
        except Exception as e:
            self.logger.error(f"Error updating user: {e}")
            return False
    
    def get_events(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of events
        
        Args:
            active_only: Get only active events
            
        Returns:
            List of event dictionaries
        """
        try:
            if active_only:
                events = self.df_events[
                    (self.df_events["status"] == "active") & 
                    (pd.to_datetime(self.df_events["date"]) > datetime.now())
                ]
            else:
                events = self.df_events
            
            return events.to_dict(orient="records")
        except Exception as e:
            self.logger.error(f"Error getting events: {e}")
            return []
    
    def add_event(self, event_data: Dict[str, Any]) -> Tuple[bool, int]:
        """
        Add new event
        
        Args:
            event_data: Event data dictionary
            
        Returns:
            Tuple of (success, event_id)
        """
        try:
            # Generate new event ID
            if self.df_events.empty:
                event_id = 1
            else:
                event_id = self.df_events["id"].max() + 1
            
            event_data["id"] = event_id
            
            # Set created_at if not provided
            if not event_data.get("created_at"):
                event_data["created_at"] = datetime.now()
            
            # Set status if not provided
            if not event_data.get("status"):
                event_data["status"] = "active"
            
            # Ensure all required columns are in event_data
            for col in self.df_events.columns:
                if col not in event_data:
                    event_data[col] = None
            
            # Add new event
            self.df_events = pd.concat([self.df_events, pd.DataFrame([event_data])], ignore_index=True)
            
            # Save Excel file
            self._save_excel()
            return True, event_id
        except Exception as e:
            self.logger.error(f"Error adding event: {e}")
            return False, 0
    
    def register_for_event(self, vk_id: int, event_id: int) -> bool:
        """
        Register user for event
        
        Args:
            vk_id: VK user ID
            event_id: Event ID
            
        Returns:
            True if registered successfully, False otherwise
        """
        try:
            # Check if registration already exists
            existing_reg = self.df_registrations[
                (self.df_registrations["user_vk_id"] == vk_id) & 
                (self.df_registrations["event_id"] == event_id)
            ]
            
            if not existing_reg.empty:
                # Update existing registration
                self.df_registrations.loc[existing_reg.index[0], "status"] = "registered"
                self._save_excel()
                return True
            
            # Check if event exists and has space
            event = self.df_events[self.df_events["id"] == event_id]
            if event.empty:
                return False
            
            if (event["current_participants"].iloc[0] >= event["max_participants"].iloc[0]):
                return False
            
            # Generate new registration ID
            if self.df_registrations.empty:
                reg_id = 1
            else:
                reg_id = self.df_registrations["id"].max() + 1
            
            # Add new registration
            new_reg = {
                "id": reg_id,
                "user_vk_id": vk_id,
                "event_id": event_id,
                "registration_date": datetime.now(),
                "status": "registered"
            }
            
            self.df_registrations = pd.concat([self.df_registrations, pd.DataFrame([new_reg])], ignore_index=True)
            
            # Increment current_participants in event
            event_idx = event.index[0]
            self.df_events.loc[event_idx, "current_participants"] += 1
            
            # Save Excel file
            self._save_excel()
            return True
        except Exception as e:
            self.logger.error(f"Error registering for event: {e}")
            return False
    
    def cancel_registration(self, vk_id: int, event_id: int) -> bool:
        """
        Cancel event registration
        
        Args:
            vk_id: VK user ID
            event_id: Event ID
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            # Find registration
            reg = self.df_registrations[
                (self.df_registrations["user_vk_id"] == vk_id) & 
                (self.df_registrations["event_id"] == event_id)
            ]
            
            if reg.empty:
                return False
            
            # Update registration status
            reg_idx = reg.index[0]
            self.df_registrations.loc[reg_idx, "status"] = "cancelled"
            
            # Decrement current_participants in event
            event = self.df_events[self.df_events["id"] == event_id]
            if not event.empty:
                event_idx = event.index[0]
                current = self.df_events.loc[event_idx, "current_participants"]
                if current > 0:
                    self.df_events.loc[event_idx, "current_participants"] -= 1
            
            # Save Excel file
            self._save_excel()
            return True
        except Exception as e:
            self.logger.error(f"Error cancelling registration: {e}")
            return False
    
    def get_user_events(self, vk_id: int) -> List[Dict[str, Any]]:
        """
        Get events registered by user
        
        Args:
            vk_id: VK user ID
            
        Returns:
            List of event dictionaries
        """
        try:
            # Get user registrations
            registrations = self.df_registrations[
                (self.df_registrations["user_vk_id"] == vk_id) & 
                (self.df_registrations["status"] == "registered")
            ]
            
            if registrations.empty:
                return []
            
            # Get events
            event_ids = registrations["event_id"].tolist()
            events = self.df_events[self.df_events["id"].isin(event_ids)]
            
            return events.to_dict(orient="records")
        except Exception as e:
            self.logger.error(f"Error getting user events: {e}")
            return []
    
    def export_user_data(self) -> pd.DataFrame:
        """
        Export user data for analysis
        
        Returns:
            DataFrame with user data
        """
        return self.df_clients.copy()
    
    def export_event_data(self) -> pd.DataFrame:
        """
        Export event data for analysis
        
        Returns:
            DataFrame with event data
        """
        return self.df_events.copy()
    
    def export_registration_data(self) -> pd.DataFrame:
        """
        Export registration data for analysis
        
        Returns:
            DataFrame with registration data
        """
        return self.df_registrations.copy()
    
    def add_consultation(self, consultation_data: Dict[str, Any]) -> bool:
        """
        Add new consultation request
        
        Args:
            consultation_data: Consultation data dictionary
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Ensure all required columns are in consultation_data
            for col in self.df_consultations.columns:
                if col not in consultation_data:
                    if col == "id":
                        # Generate new ID if not provided
                        max_id = 0 if self.df_consultations.empty else max(self.df_consultations["id"].fillna(0))
                        consultation_data["id"] = max_id + 1
                    elif col == "created_at":
                        # Set created_at if not provided
                        consultation_data["created_at"] = datetime.now()
                    else:
                        consultation_data[col] = None
            
            # Add new consultation
            self.df_consultations = pd.concat([self.df_consultations, pd.DataFrame([consultation_data])], ignore_index=True)
            
            # Save Excel file
            self._save_excel()
            return True
        except Exception as e:
            self.logger.error(f"Error adding consultation: {e}")
            return False 