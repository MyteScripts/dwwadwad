import os
import json
import logging
from logger import setup_logger

logger = setup_logger('settings_storage')

class SettingsStorage:
    """
    Class for managing persistent storage of bot settings.
    This ensures all settings are saved even when the bot restarts.
    """
    
    def __init__(self):
        self.settings_file = 'settings.json'

        self.settings = {
            "coin_drop_settings": {},
            "xp_drop_settings": {}
        }

        self.load_settings()
        logger.info("Settings storage initialized")
    
    def load_settings(self):
        """Load settings from file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)

                    self.settings.update(loaded_settings)
                logger.info("Settings loaded from file")
            else:
                logger.info("No settings file found, using defaults")
                self.save_settings()  # Create the file with defaults
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            logger.info("Settings saved to file")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def get_coin_drop_settings(self):
        """Get coin drop settings."""
        return self.settings.get("coin_drop_settings", {})
    
    def save_coin_drop_settings(self, guild_id, settings_dict):
        """
        Save coin drop settings for a guild.
        
        Args:
            guild_id (str): The ID of the guild
            settings_dict (dict): Dictionary with coin drop settings
        """
        guild_id = str(guild_id)  # Convert to string for JSON compatibility
        
        if "coin_drop_settings" not in self.settings:
            self.settings["coin_drop_settings"] = {}
        
        self.settings["coin_drop_settings"][guild_id] = settings_dict
        self.save_settings()
    
    def get_xp_drop_settings(self):
        """Get XP drop settings."""
        return self.settings.get("xp_drop_settings", {})
    
    def save_xp_drop_settings(self, guild_id, settings_dict):
        """
        Save XP drop settings for a guild.
        
        Args:
            guild_id (str): The ID of the guild
            settings_dict (dict): Dictionary with XP drop settings
        """
        guild_id = str(guild_id)  # Convert to string for JSON compatibility
        
        if "xp_drop_settings" not in self.settings:
            self.settings["xp_drop_settings"] = {}
        
        self.settings["xp_drop_settings"][guild_id] = settings_dict
        self.save_settings()

settings_storage = SettingsStorage()