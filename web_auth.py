"""
Web authentication module for the Discord bot.
Provides commands for generating tokens to use with the web interface.
"""

import jwt
import secrets
import datetime
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from permissions import check_permissions
from logger import setup_logger

logger = setup_logger('web_auth')

JWT_SECRET = secrets.token_hex(32)

class WebAuthCog(commands.Cog):
    """Cog for handling web authentication."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_name = 'data/leveling.db'
        
    @app_commands.command(
        name="webtoken", 
        description="Generate a token for accessing your data via the web interface"
    )
    async def webtoken(self, interaction: discord.Interaction):
        """Generate a token for accessing your data via the web interface."""

        if not await check_permissions(interaction):
            return

        user_id = interaction.user.id
        username = interaction.user.name

        token_expiry = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        token_data = {
            'user_id': str(user_id),
            'username': username,
            'exp': token_expiry
        }
        
        try:

            token = jwt.encode(token_data, JWT_SECRET, algorithm='HS256')

            conn = sqlite3.connect(self.db_name)
            with conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM user_tokens WHERE user_id=?", (str(user_id),))
                token_exists = cursor.fetchone()[0] > 0
                
                if token_exists:

                    cursor.execute(
                        "UPDATE user_tokens SET token=?, expires_at=? WHERE user_id=?",
                        (token, token_expiry.timestamp(), str(user_id))
                    )
                else:

                    cursor.execute(
                        "INSERT INTO user_tokens (user_id, username, token, expires_at) VALUES (?, ?, ?, ?)",
                        (str(user_id), username, token, token_expiry.timestamp())
                    )

                conn.commit()

            try:
                await interaction.user.send(f"Here is your web access token. It will expire in 24 hours:\n\n`{token}`\n\nUse this token to authenticate with the web interface. Never share this token with anyone!")
                await interaction.response.send_message("Token generated! Check your DMs for the token details.", ephemeral=True)
            except Exception as e:

                logger.error(f"Failed to send token via DM: {e}")
                await interaction.response.send_message(f"Here is your web access token. It will expire in 24 hours:\n\n`{token}`\n\nUse this token to authenticate with the web interface. Never share this token with anyone!", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error generating token: {e}")
            await interaction.response.send_message("There was an error generating your token. Please try again later.", ephemeral=True)

async def setup(bot):
    """Add the web auth cog to the bot."""

    db_name = 'data/leveling.db'
    conn = sqlite3.connect(db_name)
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            UNIQUE(user_id)
        )
        ''')
        conn.commit()

    await bot.add_cog(WebAuthCog(bot))