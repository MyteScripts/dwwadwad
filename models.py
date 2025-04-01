import datetime
import secrets
from sqlalchemy.orm import DeclarativeBase
from flask_sqlalchemy import SQLAlchemy

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class BotStatus(db.Model):
    """Model for storing bot status information."""
    id = db.Column(db.Integer, primary_key=True)
    last_connected = db.Column(db.DateTime, nullable=True)
    total_servers = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<BotStatus servers={self.total_servers}>'

class ServerInfo(db.Model):
    """Model for storing information about Discord servers the bot is in."""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(20), unique=True, nullable=False)
    server_name = db.Column(db.String(100), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return f'<ServerInfo {self.server_name}>'

class UserToken(db.Model):
    """Model for storing user API tokens for web access to bot features."""
    id = db.Column(db.Integer, primary_key=True)
    discord_user_id = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=True)
    
    @staticmethod
    def generate_token():
        """Generate a secure random token."""
        return secrets.token_hex(32)
    
    def __repr__(self):
        return f'<UserToken {self.username}>'