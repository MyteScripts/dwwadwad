import os
import logging
import datetime
from flask import Flask, render_template, redirect, url_for, session, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_dashboard')

load_dotenv()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_development")

if os.environ.get("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
else:

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data/web_dashboard.db"

db.init_app(app)

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
        import secrets
        return secrets.token_hex(32)
    
    def __repr__(self):
        return f'<UserToken {self.username}>'

class ServerInfo(db.Model):
    """Model for storing information about Discord servers the bot is in."""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(20), unique=True, nullable=False)
    server_name = db.Column(db.String(100), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return f'<ServerInfo {self.server_name}>'

class BotStatus(db.Model):
    """Model for storing bot status information."""
    id = db.Column(db.Integer, primary_key=True)
    last_connected = db.Column(db.DateTime, nullable=True)
    total_servers = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<BotStatus servers={self.total_servers}>'

with app.app_context():
    db.create_all()
    from web_views import register_views
    register_views(app, db)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)