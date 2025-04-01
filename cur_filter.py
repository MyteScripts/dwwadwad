import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
import logging
from logger import setup_logger

logger = setup_logger('cur_filter')

class CurFilterCog(commands.Cog):
    """Cog for handling the cur filter functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.cur_users = set()  # Set to store user IDs who have the filter active
        self.load_cur_users()
    
    def load_cur_users(self):
        """Load the list of users with active cur filter from file"""
        try:
            if os.path.exists('data/cur_users.json'):
                with open('data/cur_users.json', 'r') as f:
                    users = json.load(f)
                    self.cur_users = set(users)
                    logger.info(f"Loaded {len(self.cur_users)} users with active cur filter")
        except Exception as e:
            logger.error(f"Error loading cur users: {e}")
    
    def save_cur_users(self):
        """Save the list of users with active cur filter to file"""
        try:

            os.makedirs('data', exist_ok=True)
            
            with open('data/cur_users.json', 'w') as f:
                json.dump(list(self.cur_users), f)
                logger.info(f"Saved {len(self.cur_users)} users with active cur filter")
        except Exception as e:
            logger.error(f"Error saving cur users: {e}")
    
    @app_commands.command(name="cur", description="Activate the cur filter on your messages")
    async def cur(self, interaction: discord.Interaction):
        """Activate the cur filter for the user"""
        user_id = interaction.user.id
        
        if user_id in self.cur_users:
            await interaction.response.send_message("🔄 Your cur filter is already active!", ephemeral=True)
            return
        
        self.cur_users.add(user_id)
        self.save_cur_users()
        
        await interaction.response.send_message("✅ Cur filter activated! Your messages will now be curified.", ephemeral=True)
        logger.info(f"User {user_id} activated cur filter")
    
    @app_commands.command(name="uncur", description="Deactivate the cur filter on your messages")
    async def uncur(self, interaction: discord.Interaction):
        """Deactivate the cur filter for the user"""
        user_id = interaction.user.id
        
        if user_id not in self.cur_users:
            await interaction.response.send_message("ℹ️ You don't have the cur filter active.", ephemeral=True)
            return
        
        self.cur_users.remove(user_id)
        self.save_cur_users()
        
        await interaction.response.send_message("✅ Cur filter deactivated! Your messages will now be normal.", ephemeral=True)
        logger.info(f"User {user_id} deactivated cur filter")
    
    def curify_message(self, text):
        """Convert text to a pattern of 'm' and 'f' characters while keeping spaces and punctuation"""
        result = ""
        for char in text:
            if char.isalpha():
                result += random.choice(['m', 'f'])
            else:
                result += char  # Keep spaces, punctuation, etc.
        return result
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages and apply the cur filter if needed"""

        if message.author.bot:
            return

        if message.author.id in self.cur_users:

            try:
                await message.delete()

                webhook = None
                for existing_webhook in await message.channel.webhooks():
                    if existing_webhook.user.id == self.bot.user.id:
                        webhook = existing_webhook
                        break
                
                if webhook is None:
                    webhook = await message.channel.create_webhook(name="CurFilter")

                curified_text = self.curify_message(message.content)

                await webhook.send(
                    content=curified_text,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    allowed_mentions=discord.AllowedMentions.none()
                )
                
                logger.debug(f"Curified message from {message.author.id} in {message.channel.id}")
            except Exception as e:
                logger.error(f"Error processing cur filter for message: {e}")

async def setup(bot):
    """Add the cur filter cog to the bot"""
    await bot.add_cog(CurFilterCog(bot))
    logger.info("Cur filter cog loaded")