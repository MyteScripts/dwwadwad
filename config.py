import os
from dotenv import load_dotenv

class BotConfig:
    """Configuration settings for the Discord bot."""
    
    def __init__(self):

        load_dotenv()

        self.bot_name = os.getenv('BOT_NAME', 'GridBot Beta')
        self.bot_description = "A Discord bot with an advanced leveling system"

        self.reconnect_attempts = int(os.getenv('RECONNECT_ATTEMPTS', 5))
        self.reconnect_backoff_multiplier = float(os.getenv('RECONNECT_BACKOFF_MULTIPLIER', 1.5))
        self.reconnect_initial_delay = int(os.getenv('RECONNECT_INITIAL_DELAY', 1))

        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_file = os.getenv('LOG_FILE', 'bot.log')

        self.status_change_interval = int(os.getenv('STATUS_CHANGE_INTERVAL', 30))  # minutes
