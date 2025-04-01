import os
import logging
import discord
from dotenv import load_dotenv

import os

os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot')

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.presences = True  # For presence information
intents.guilds = True     # For server information

class SimpleBot(discord.Client):
    async def on_ready(self):
        """Event triggered when the bot has successfully connected to Discord."""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guild(s)')

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, 
                name="the server"
            ),
            status=discord.Status.online
        )
    
    async def on_guild_join(self, guild):
        """Event triggered when the bot joins a new server."""
        logger.info(f'Bot has joined a new guild: {guild.name} (id: {guild.id})')
    
    async def on_disconnect(self):
        """Event triggered when the bot disconnects from Discord."""
        logger.warning('Bot has been disconnected from Discord')

    async def on_error(self, event, *args, **kwargs):
        """Global error handler for all events."""
        logger.error(f'An error occurred in event {event}')
        logger.error(f'Args: {args}')
        logger.error(f'Kwargs: {kwargs}')
        raise

def start_bot():
    """Initialize and start the Discord bot."""
    if not TOKEN:
        logger.error("Discord token not found. Please check your .env file.")
        return
    
    try:
        client = SimpleBot(intents=intents)
        logger.info("Starting bot...")
        client.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("Invalid Discord token. Please check your token.")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    start_bot()