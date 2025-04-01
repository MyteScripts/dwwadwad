import discord
import random
import asyncio
import time
import logging
import json
import os
from discord import app_commands
from discord.ext import commands
from database import Database

logger = logging.getLogger(__name__)

class WorkCog(commands.Cog):
    """Cog for managing the work command"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

        self.settings = self.db.get_settings()

        self.cooldown_file = 'data/work_cooldowns.json'

        self.last_work = self.load_cooldowns()

        self.cooldown = 3600

        self.cleanup_expired_cooldowns()

        self.work_messages = [
            "You worked at a local grocery store and earned {coins} coins.",
            "You delivered packages for a courier service and earned {coins} coins.",
            "You helped fix someone's computer and earned {coins} coins.",
            "You worked as a server at a restaurant and earned {coins} coins.",
            "You wrote an article for a website and earned {coins} coins.",
            "You walked several dogs in the neighborhood and earned {coins} coins.",
            "You tutored a student and earned {coins} coins.",
            "You helped someone move to a new apartment and earned {coins} coins.",
            "You sold some handmade crafts and earned {coins} coins.",
            "You worked a few hours at a coffee shop and earned {coins} coins.",
            "You did some gardening work for a neighbor and earned {coins} coins.",
            "You designed a logo for a small business and earned {coins} coins.",
            "You helped organize an event and earned {coins} coins.",
            "You fixed someone's leaky pipe and earned {coins} coins.",
            "You cleaned houses for a few hours and earned {coins} coins."
        ]
    
    def load_cooldowns(self):
        """Load work cooldowns from file."""
        try:
            if os.path.exists(self.cooldown_file):
                with open(self.cooldown_file, 'r') as f:

                    data = json.load(f)
                    return {int(user_id): timestamp for user_id, timestamp in data.items()}
            else:
                logger.info("No work cooldowns file found, creating a new one")
                return {}
        except Exception as e:
            logger.error(f"Error loading work cooldowns: {e}")
            return {}
    
    def save_cooldowns(self):
        """Save work cooldowns to file."""
        try:

            os.makedirs(os.path.dirname(self.cooldown_file), exist_ok=True)

            data = {str(user_id): timestamp for user_id, timestamp in self.last_work.items()}
            
            with open(self.cooldown_file, 'w') as f:
                json.dump(data, f)
            logger.debug("Work cooldowns saved to file")
        except Exception as e:
            logger.error(f"Error saving work cooldowns: {e}")
    
    def cleanup_expired_cooldowns(self):
        """Remove expired cooldowns to keep the storage file clean."""
        current_time = time.time()
        expired_users = []

        for user_id, timestamp in self.last_work.items():
            if current_time - timestamp >= self.cooldown:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self.last_work[user_id]
        
        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired work cooldowns")

            self.save_cooldowns()
    
    def cog_unload(self):
        """Called when the cog is unloaded."""

        self.save_cooldowns()

        if hasattr(self, 'db'):
            self.db.close()
            
    @app_commands.command(
        name="work",
        description="Work to earn coins (can be used once per hour)"
    )
    async def work(self, interaction: discord.Interaction):
        """
        Work to earn coins. Can be used once per hour.
        Earns between 10-60 coins per use.
        This command is available to @everyone.
        """
        user_id = interaction.user.id
        username = interaction.user.display_name
        current_time = time.time()

        if user_id in self.last_work:
            elapsed = current_time - self.last_work[user_id]
            if elapsed < self.cooldown:
                remaining = self.cooldown - elapsed

                minutes, seconds = divmod(int(remaining), 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    time_str = f"{hours} hour{'s' if hours != 1 else ''}"
                elif minutes > 0:
                    time_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
                else:
                    time_str = f"{seconds} second{'s' if seconds != 1 else ''}"
                    
                embed = discord.Embed(
                    title="Cooldown Active",
                    description=f"You need to wait {time_str} before working again.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="You can work once per hour")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        coins_earned = random.randint(10, 60)

        updated_user = self.db.add_coins(user_id, username, coins_earned)
        if updated_user is None:
            logger.error(f"Failed to add coins to user {username} ({user_id})")

            embed = discord.Embed(
                title="Error",
                description="Something went wrong while adding coins. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.last_work[user_id] = current_time

        self.save_cooldowns()

        work_message = random.choice(self.work_messages).format(coins=coins_earned)

        embed = discord.Embed(
            title="💼 Work Completed",
            description=work_message,
            color=discord.Color.green()
        )

        if updated_user and 'coins' in updated_user:
            embed.add_field(
                name="Your Balance",
                value=f"🪙 {updated_user['coins']} coins",
                inline=False
            )
        
        embed.set_footer(text="You can work again in 1 hour")

        logger.info(f"💰 WORK: {username} ({user_id}) worked and earned {coins_earned} coins")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    """Add the work cog to the bot."""
    await bot.add_cog(WorkCog(bot))
    logger.info("Work cog loaded")