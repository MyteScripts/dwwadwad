import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import json
import os
import logging
import string
import sqlite3
from datetime import datetime, timedelta
from permissions import has_admin_permissions

logger = logging.getLogger(__name__)

class MiniGameSettings:
    """Class to store mini-game settings."""
    def __init__(self):
        self.type_race = {
            "min_coins": 5,
            "max_coins": 20,
            "min_xp": 10,
            "max_xp": 30,
            "frequency": 60,  # minutes
            "enabled": False,
            "channel_id": None,
            "last_run": None
        }
        
        self.memory_game = {
            "min_coins": 5,
            "max_coins": 20,
            "min_xp": 10,
            "max_xp": 30,
            "frequency": 60,  # minutes
            "enabled": False,
            "channel_id": None,
            "last_run": None
        }
        
        self.reverse_spelling = {
            "min_coins": 5,
            "max_coins": 20,
            "min_xp": 10,
            "max_xp": 30,
            "frequency": 60,  # minutes
            "enabled": False,
            "channel_id": None,
            "last_run": None
        }
        
        self.true_false = {
            "min_coins": 5,
            "max_coins": 20,
            "min_xp": 10,
            "max_xp": 30,
            "frequency": 60,  # minutes
            "enabled": False,
            "channel_id": None,
            "last_run": None
        }

class MiniGamesCog(commands.Cog):
    """Cog for mini-games that reward XP and coins."""
    
    @discord.app_commands.command(name="minigames", description="Open mini-games settings panel (Admin only)")
    async def minigames(
        self,
        interaction: discord.Interaction
    ):
        """Open a panel to manage all mini-games (Admin only)."""
        # Check if user has admin permissions
        is_admin = await has_admin_permissions(interaction.user.id, interaction.guild.id, self.bot)
        if not is_admin:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
            
        # Create and send the mini-games panel
        view = MiniGamesMainPanel(self)
        
        embed = discord.Embed(
            title="🎮 Mini-Games Settings",
            description="Select a mini-game to configure from the buttons below.",
            color=discord.Color.blurple()
        )
        
        mini_games_status = ""
        
        # Type Race status
        type_race_status = "✅ Enabled" if self.settings.type_race.get("enabled", False) else "❌ Disabled"
        type_race_channel = self.bot.get_channel(self.settings.type_race.get("channel_id", 0))
        type_race_channel_mention = type_race_channel.mention if type_race_channel else "None"
        mini_games_status += f"**⌨️ Type Race:** {type_race_status} in {type_race_channel_mention}\n"
        
        # Memory Game status
        memory_status = "✅ Enabled" if self.settings.memory_game.get("enabled", False) else "❌ Disabled"
        memory_channel = self.bot.get_channel(self.settings.memory_game.get("channel_id", 0))
        memory_channel_mention = memory_channel.mention if memory_channel else "None"
        mini_games_status += f"**🧠 Memory Game:** {memory_status} in {memory_channel_mention}\n"
        
        # Reverse Spelling status
        spelling_status = "✅ Enabled" if self.settings.reverse_spelling.get("enabled", False) else "❌ Disabled"
        spelling_channel = self.bot.get_channel(self.settings.reverse_spelling.get("channel_id", 0))
        spelling_channel_mention = spelling_channel.mention if spelling_channel else "None"
        mini_games_status += f"**🔄 Reverse Spelling:** {spelling_status} in {spelling_channel_mention}\n"
        
        # True/False status
        tf_status = "✅ Enabled" if self.settings.true_false.get("enabled", False) else "❌ Disabled"
        tf_channel = self.bot.get_channel(self.settings.true_false.get("channel_id", 0))
        tf_channel_mention = tf_channel.mention if tf_channel else "None"
        mini_games_status += f"**✅❌ True/False:** {tf_status} in {tf_channel_mention}\n"
        
        embed.add_field(name="Mini-Games Status", value=mini_games_status, inline=False)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def __init__(self, bot):
        self.bot = bot
        self.settings_file = "data/mini_games.json"
        self.settings = MiniGameSettings()
        self.type_race_task = None
        self.memory_game_task = None
        self.reverse_spelling_task = None
        self.true_false_task = None
        self.active_games = {}  # Track active games by channel
        
        # Word list for games
        self.words = [
            "discord", "server", "gaming", "community", "friends", 
            "message", "voice", "channel", "emoji", "reaction",
            "role", "member", "bot", "command", "moderator",
            "admin", "level", "experience", "rank", "reward",
            "points", "coins", "currency", "economy", "shop",
            "inventory", "item", "purchase", "collect", "daily",
            "weekly", "mining", "resource", "craft", "upgrade",
            "mission", "quest", "challenge", "achievement", "leaderboard"
        ]
        
        # Short sentences for type race
        self.sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "I love being part of this amazing Discord community!",
            "Gaming with friends is my favorite weekend activity.",
            "Don't forget to check the announcements channel regularly.",
            "Remember to be kind and respectful to all community members.",
            "The mining system lets you gather valuable resources.",
            "Invest your coins wisely to earn passive income.",
            "Helping others is rewarding and builds community spirit.",
            "Regular participation will help you level up faster.",
            "Complete daily missions to earn bonus rewards.",
            "Higher levels unlock special roles and perks.",
            "Check your rank to see how you compare to others.",
            "The shop has many useful items you can purchase.",
            "Maintenance is important for keeping your investments profitable.",
            "Join voice channels to connect with other members."
        ]
        
        # True/False facts
        self.true_facts = [
            "Discord was launched in May 2015.",
            "The original name for PlayStation was 'Play Station'.",
            "Nintendo was founded in 1889 as a playing card company.",
            "The first computer mouse was made of wood.",
            "The first video game console was released in 1972.",
            "The world's first website is still online today.",
            "QWERTY keyboard layout was designed to slow typists down.",
            "The first computer virus was created in 1986.",
            "The original Xbox contained modified Windows 2000 code.",
            "The first version of Windows was released in 1985."
        ]
        
        self.false_facts = [
            "Discord was originally designed as an educational platform.",
            "The PlayStation was originally a Nintendo product.",
            "Minecraft was initially created as a mobile game.",
            "The computer mouse was invented in the 1980s.",
            "The most common password is 'qwerty123'.",
            "The first emoji was created in 2010.",
            "The first video game was released in 1990.",
            "HTML is a programming language.",
            "Facebook was founded by Bill Gates.",
            "Java was named after the island of Java."
        ]
        
        # Load settings and start tasks
        self.load_settings()
        
    async def cog_load(self):
        """Called when the cog is loaded."""
        # Start the game loops if enabled
        await self.start_game_tasks()
        
    async def start_game_tasks(self):
        """Start all the game tasks based on settings."""
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Cancel any existing tasks
        if self.type_race_task:
            self.type_race_task.cancel()
        if self.memory_game_task:
            self.memory_game_task.cancel()
        if self.reverse_spelling_task:
            self.reverse_spelling_task.cancel()
        if self.true_false_task:
            self.true_false_task.cancel()
            
        # Start new tasks if enabled
        if self.settings.type_race["enabled"] and self.settings.type_race["channel_id"]:
            self.type_race_task = asyncio.create_task(self.run_type_race())
            
        if self.settings.memory_game["enabled"] and self.settings.memory_game["channel_id"]:
            self.memory_game_task = asyncio.create_task(self.run_memory_game())
            
        if self.settings.reverse_spelling["enabled"] and self.settings.reverse_spelling["channel_id"]:
            self.reverse_spelling_task = asyncio.create_task(self.run_reverse_spelling())
            
        if self.settings.true_false["enabled"] and self.settings.true_false["channel_id"]:
            self.true_false_task = asyncio.create_task(self.run_true_false())
    
    def load_settings(self):
        """Load mini-game settings from JSON file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    
                    # Update settings from file
                    if "type_race" in data:
                        self.settings.type_race.update(data["type_race"])
                    if "memory_game" in data:
                        self.settings.memory_game.update(data["memory_game"])
                    if "reverse_spelling" in data:
                        self.settings.reverse_spelling.update(data["reverse_spelling"])
                    if "true_false" in data:
                        self.settings.true_false.update(data["true_false"])
            else:
                # Create default settings file
                self.save_settings()
        except Exception as e:
            logger.error(f"Error loading mini-game settings: {e}")
    
    def save_settings(self):
        """Save mini-game settings to JSON file."""
        try:
            data = {
                "type_race": self.settings.type_race,
                "memory_game": self.settings.memory_game,
                "reverse_spelling": self.settings.reverse_spelling,
                "true_false": self.settings.true_false
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
                
            return True
        except Exception as e:
            logger.error(f"Error saving mini-game settings: {e}")
            return False
    
    async def award_rewards(self, user_id, username, xp, coins):
        """Award XP and coins to a user."""
        try:
            # Get the database from Database module
            from database import Database
            db = Database()
            
            # Add XP directly to the database
            db.add_xp(user_id, username, xp_amount=xp)
            
            # Add coins directly to the database
            db.add_coins(user_id, username, coins)
            
            return True
        except Exception as e:
            logger.error(f"Error awarding rewards in mini-game: {e}")
            return False
    
    @app_commands.command(name="editrace", description="Configure Type Race mini-game settings (Admin only)")
    async def editrace(
        self,
        interaction: discord.Interaction
    ):
        """Configure Type Race mini-game settings (Admin only)."""
        # Show current settings
        current_settings = self.settings.type_race
        channel = self.bot.get_channel(current_settings.get("channel_id", 0))
        channel_mention = channel.mention if channel else "None"
        
        embed = discord.Embed(
            title="⌨️ Type Race Settings",
            description="Use the buttons below to configure the Type Race mini-game.",
            color=discord.Color.blue()
        )
        
        status = "Enabled" if current_settings.get("enabled", False) else "Disabled"
        
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Status:** {status}\n"
                f"**Channel:** {channel_mention}\n"
                f"**Coin Rewards:** {current_settings.get('min_coins', 0)}-{current_settings.get('max_coins', 0)}\n"
                f"**XP Rewards:** {current_settings.get('min_xp', 0)}-{current_settings.get('max_xp', 0)}\n"
                f"**Frequency:** Every {current_settings.get('frequency', 0)} minutes"
            ),
            inline=False
        )
        
        # Create the view with buttons
        view = TypeRaceSettingsView(self)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="editmemory", description="Configure Memory Game mini-game settings (Admin only)")
    @app_commands.describe(
        channel="Channel for the Memory Game events",
        min_coins="Minimum coins reward",
        max_coins="Maximum coins reward",
        min_xp="Minimum XP reward",
        max_xp="Maximum XP reward",
        frequency="How often to run the game (in minutes)",
        enabled="Enable or disable the game"
    )
    async def editmemory(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        min_coins: int, 
        max_coins: int, 
        min_xp: int, 
        max_xp: int, 
        frequency: int,
        enabled: bool
    ):
        """Configure Memory Game mini-game settings (Admin only)."""
        
        # Update settings
        self.settings.memory_game["channel_id"] = channel.id
        self.settings.memory_game["min_coins"] = min_coins
        self.settings.memory_game["max_coins"] = max_coins
        self.settings.memory_game["min_xp"] = min_xp
        self.settings.memory_game["max_xp"] = max_xp
        self.settings.memory_game["frequency"] = frequency
        self.settings.memory_game["enabled"] = enabled
        
        # Save settings
        self.save_settings()
        
        # Restart task
        if self.memory_game_task:
            self.memory_game_task.cancel()
            
        if enabled:
            self.memory_game_task = asyncio.create_task(self.run_memory_game())
        
        # Confirm changes
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ Memory Game settings updated!\n\n"
            f"Channel: {channel.mention}\n"
            f"Rewards: {min_coins}-{max_coins} coins, {min_xp}-{max_xp} XP\n"
            f"Frequency: Every {frequency} minutes\n"
            f"Status: {status}",
            ephemeral=True
        )
    
    @app_commands.command(name="editspelling", description="Configure Reverse Spelling mini-game settings (Admin only)")
    @app_commands.describe(
        channel="Channel for the Reverse Spelling events",
        min_coins="Minimum coins reward",
        max_coins="Maximum coins reward",
        min_xp="Minimum XP reward",
        max_xp="Maximum XP reward",
        frequency="How often to run the game (in minutes)",
        enabled="Enable or disable the game"
    )
    async def editspelling(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        min_coins: int, 
        max_coins: int, 
        min_xp: int, 
        max_xp: int, 
        frequency: int,
        enabled: bool
    ):
        """Configure Reverse Spelling mini-game settings (Admin only)."""
        
        # Update settings
        self.settings.reverse_spelling["channel_id"] = channel.id
        self.settings.reverse_spelling["min_coins"] = min_coins
        self.settings.reverse_spelling["max_coins"] = max_coins
        self.settings.reverse_spelling["min_xp"] = min_xp
        self.settings.reverse_spelling["max_xp"] = max_xp
        self.settings.reverse_spelling["frequency"] = frequency
        self.settings.reverse_spelling["enabled"] = enabled
        
        # Save settings
        self.save_settings()
        
        # Restart task
        if self.reverse_spelling_task:
            self.reverse_spelling_task.cancel()
            
        if enabled:
            self.reverse_spelling_task = asyncio.create_task(self.run_reverse_spelling())
        
        # Confirm changes
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ Reverse Spelling settings updated!\n\n"
            f"Channel: {channel.mention}\n"
            f"Rewards: {min_coins}-{max_coins} coins, {min_xp}-{max_xp} XP\n"
            f"Frequency: Every {frequency} minutes\n"
            f"Status: {status}",
            ephemeral=True
        )
    
    @app_commands.command(name="edittruefalse", description="Configure True or False mini-game settings (Admin only)")
    @app_commands.describe(
        channel="Channel for the True or False events",
        min_coins="Minimum coins reward",
        max_coins="Maximum coins reward",
        min_xp="Minimum XP reward",
        max_xp="Maximum XP reward",
        frequency="How often to run the game (in minutes)",
        enabled="Enable or disable the game"
    )
    async def edittruefalse(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        min_coins: int, 
        max_coins: int, 
        min_xp: int, 
        max_xp: int, 
        frequency: int,
        enabled: bool
    ):
        """Configure True or False mini-game settings (Admin only)."""
        
        # Update settings
        self.settings.true_false["channel_id"] = channel.id
        self.settings.true_false["min_coins"] = min_coins
        self.settings.true_false["max_coins"] = max_coins
        self.settings.true_false["min_xp"] = min_xp
        self.settings.true_false["max_xp"] = max_xp
        self.settings.true_false["frequency"] = frequency
        self.settings.true_false["enabled"] = enabled
        
        # Save settings
        self.save_settings()
        
        # Restart task
        if self.true_false_task:
            self.true_false_task.cancel()
            
        if enabled:
            self.true_false_task = asyncio.create_task(self.run_true_false())
        
        # Confirm changes
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ True or False settings updated!\n\n"
            f"Channel: {channel.mention}\n"
            f"Rewards: {min_coins}-{max_coins} coins, {min_xp}-{max_xp} XP\n"
            f"Frequency: Every {frequency} minutes\n"
            f"Status: {status}",
            ephemeral=True
        )
    
    async def run_type_race(self):
        """Background task to run type race games."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            channel_id = None  # Initialize channel_id
            try:
                # Check if enabled
                if not self.settings.type_race["enabled"]:
                    break
                
                channel_id = self.settings.type_race["channel_id"]
                channel = self.bot.get_channel(channel_id)
                
                if not channel:
                    logger.error(f"Type Race channel {channel_id} not found")
                    await asyncio.sleep(60)  # Wait and try again
                    continue
                
                # Check if we should run (based on frequency)
                now = datetime.now()
                last_run = self.settings.type_race["last_run"]
                
                if last_run:
                    # Convert string date to datetime
                    last_run = datetime.fromisoformat(last_run)
                    next_run = last_run + timedelta(minutes=self.settings.type_race["frequency"])
                    
                    if now < next_run:
                        # Not time yet, sleep until next run
                        sleep_time = (next_run - now).total_seconds()
                        await asyncio.sleep(sleep_time)
                
                # Check if channel is already running a game
                if channel_id in self.active_games:
                    await asyncio.sleep(30)  # Try again in 30 seconds
                    continue
                
                self.active_games[channel_id] = "type_race"
                
                # Run the game
                sentence = random.choice(self.sentences)
                
                embed = discord.Embed(
                    title="⌨️ Type Race!",
                    description="Be the first to type the following sentence correctly:",
                    color=discord.Color.blue()
                )
                
                embed.add_field(name="Sentence", value=f"```{sentence}```", inline=False)
                embed.add_field(name="Rewards", value=f"{self.settings.type_race['min_coins']}-{self.settings.type_race['max_coins']} coins and {self.settings.type_race['min_xp']}-{self.settings.type_race['max_xp']} XP", inline=False)
                
                # Send the challenge
                await channel.send(embed=embed)
                
                # Update last run time
                self.settings.type_race["last_run"] = now.isoformat()
                self.save_settings()
                
                # Wait for correct answer
                def check(message):
                    if message.channel.id != channel.id:
                        return False
                    return message.content.strip().lower() == sentence.lower()
                
                try:
                    # Wait for correct answer (timeout after 5 minutes)
                    winner_message = await self.bot.wait_for('message', check=check, timeout=300)
                    
                    # Generate rewards
                    coins = random.randint(self.settings.type_race["min_coins"], self.settings.type_race["max_coins"])
                    xp = random.randint(self.settings.type_race["min_xp"], self.settings.type_race["max_xp"])
                    
                    # Award the winner
                    await self.award_rewards(winner_message.author.id, winner_message.author.name, xp, coins)
                    
                    # Announce winner
                    await channel.send(
                        f"🎉 Congratulations {winner_message.author.mention}! You typed the sentence correctly first and earned **{coins} coins** and **{xp} XP**!"
                    )
                    
                except asyncio.TimeoutError:
                    # No one got it right
                    await channel.send("⏱️ Time's up! No one typed the sentence correctly.")
                
                # Remove active game flag
                self.active_games.pop(channel_id, None)
                
                # Wait before next game (minimum 1 minute)
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in Type Race game: {e}")
                # Remove active game flag in case of error
                if channel_id in self.active_games:
                    self.active_games.pop(channel_id, None)
                await asyncio.sleep(60)  # Wait before trying again
    
    async def run_memory_game(self):
        """Background task to run memory games."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            channel_id = None  # Initialize channel_id
            try:
                # Check if enabled
                if not self.settings.memory_game["enabled"]:
                    break
                
                channel_id = self.settings.memory_game["channel_id"]
                channel = self.bot.get_channel(channel_id)
                
                if not channel:
                    logger.error(f"Memory Game channel {channel_id} not found")
                    await asyncio.sleep(60)  # Wait and try again
                    continue
                
                # Check if we should run (based on frequency)
                now = datetime.now()
                last_run = self.settings.memory_game["last_run"]
                
                if last_run:
                    # Convert string date to datetime
                    last_run = datetime.fromisoformat(last_run)
                    next_run = last_run + timedelta(minutes=self.settings.memory_game["frequency"])
                    
                    if now < next_run:
                        # Not time yet, sleep until next run
                        sleep_time = (next_run - now).total_seconds()
                        await asyncio.sleep(sleep_time)
                
                # Check if channel is already running a game
                if channel_id in self.active_games:
                    await asyncio.sleep(30)  # Try again in 30 seconds
                    continue
                    
                self.active_games[channel_id] = "memory_game"
                
                # Generate a random emoji sequence
                emojis = ["😀", "😎", "😍", "🤩", "🥳", "🚀", "⭐", "🔥", "💖", "🎮", 
                          "🎲", "🎯", "🏆", "💎", "🎁", "🎈", "🎵", "🎬", "📱", "💻"]
                
                # Select 5-8 random emojis
                sequence_length = random.randint(5, 8)
                emoji_sequence = random.sample(emojis, sequence_length)
                
                # Display time based on difficulty (1 second per emoji)
                display_time = sequence_length
                
                embed = discord.Embed(
                    title="🧠 Memory Game!",
                    description=f"Memorize this sequence of emojis! You have {display_time} seconds.",
                    color=discord.Color.purple()
                )
                
                # Add sequence to embed
                embed.add_field(name="Sequence", value=" ".join(emoji_sequence), inline=False)
                embed.add_field(name="Rewards", value=f"{self.settings.memory_game['min_coins']}-{self.settings.memory_game['max_coins']} coins and {self.settings.memory_game['min_xp']}-{self.settings.memory_game['max_xp']} XP", inline=False)
                
                # Send the challenge
                message = await channel.send(embed=embed)
                
                # Update last run time
                self.settings.memory_game["last_run"] = now.isoformat()
                self.save_settings()
                
                # Wait for the display time
                await asyncio.sleep(display_time)
                
                # Edit message to hide sequence
                embed.clear_fields()
                embed.description = "Now type the sequence of emojis in the correct order!"
                embed.add_field(name="Rewards", value=f"{self.settings.memory_game['min_coins']}-{self.settings.memory_game['max_coins']} coins and {self.settings.memory_game['min_xp']}-{self.settings.memory_game['max_xp']} XP", inline=False)
                
                await message.edit(embed=embed)
                
                # Wait for correct answer
                correct_sequence = " ".join(emoji_sequence)
                
                def check(message):
                    if message.channel.id != channel.id:
                        return False
                    return message.content.strip() == correct_sequence
                
                try:
                    # Wait for correct answer (timeout after 2 minutes)
                    winner_message = await self.bot.wait_for('message', check=check, timeout=120)
                    
                    # Generate rewards
                    coins = random.randint(self.settings.memory_game["min_coins"], self.settings.memory_game["max_coins"])
                    xp = random.randint(self.settings.memory_game["min_xp"], self.settings.memory_game["max_xp"])
                    
                    # Award the winner
                    await self.award_rewards(winner_message.author.id, winner_message.author.name, xp, coins)
                    
                    # Announce winner
                    await channel.send(
                        f"🎉 Congratulations {winner_message.author.mention}! You remembered the sequence correctly and earned **{coins} coins** and **{xp} XP**!"
                    )
                    
                except asyncio.TimeoutError:
                    # No one got it right
                    await channel.send(f"⏱️ Time's up! The correct sequence was: {correct_sequence}")
                
                # Remove active game flag
                self.active_games.pop(channel_id, None)
                
                # Wait before next game (minimum 1 minute)
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in Memory Game: {e}")
                # Remove active game flag in case of error
                if channel_id in self.active_games:
                    self.active_games.pop(channel_id, None)
                await asyncio.sleep(60)  # Wait before trying again
    
    async def run_reverse_spelling(self):
        """Background task to run reverse spelling games."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            channel_id = None  # Initialize channel_id
            try:
                # Check if enabled
                if not self.settings.reverse_spelling["enabled"]:
                    break
                
                channel_id = self.settings.reverse_spelling["channel_id"]
                channel = self.bot.get_channel(channel_id)
                
                if not channel:
                    logger.error(f"Reverse Spelling channel {channel_id} not found")
                    await asyncio.sleep(60)  # Wait and try again
                    continue
                
                # Check if we should run (based on frequency)
                now = datetime.now()
                last_run = self.settings.reverse_spelling["last_run"]
                
                if last_run:
                    # Convert string date to datetime
                    last_run = datetime.fromisoformat(last_run)
                    next_run = last_run + timedelta(minutes=self.settings.reverse_spelling["frequency"])
                    
                    if now < next_run:
                        # Not time yet, sleep until next run
                        sleep_time = (next_run - now).total_seconds()
                        await asyncio.sleep(sleep_time)
                
                # Check if channel is already running a game
                if channel_id in self.active_games:
                    await asyncio.sleep(30)  # Try again in 30 seconds
                    continue
                    
                self.active_games[channel_id] = "reverse_spelling"
                
                # Choose a random word
                word = random.choice(self.words)
                
                # Reverse the word
                reversed_word = word[::-1]
                
                embed = discord.Embed(
                    title="🔄 Reverse Spelling!",
                    description="Be the first to unscramble this reversed word:",
                    color=discord.Color.gold()
                )
                
                embed.add_field(name="Reversed Word", value=f"```{reversed_word}```", inline=False)
                embed.add_field(name="Rewards", value=f"{self.settings.reverse_spelling['min_coins']}-{self.settings.reverse_spelling['max_coins']} coins and {self.settings.reverse_spelling['min_xp']}-{self.settings.reverse_spelling['max_xp']} XP", inline=False)
                
                # Send the challenge
                await channel.send(embed=embed)
                
                # Update last run time
                self.settings.reverse_spelling["last_run"] = now.isoformat()
                self.save_settings()
                
                # Wait for correct answer
                def check(message):
                    if message.channel.id != channel.id:
                        return False
                    return message.content.strip().lower() == word.lower()
                
                try:
                    # Wait for correct answer (timeout after 3 minutes)
                    winner_message = await self.bot.wait_for('message', check=check, timeout=180)
                    
                    # Generate rewards
                    coins = random.randint(self.settings.reverse_spelling["min_coins"], self.settings.reverse_spelling["max_coins"])
                    xp = random.randint(self.settings.reverse_spelling["min_xp"], self.settings.reverse_spelling["max_xp"])
                    
                    # Award the winner
                    await self.award_rewards(winner_message.author.id, winner_message.author.name, xp, coins)
                    
                    # Announce winner
                    await channel.send(
                        f"🎉 Congratulations {winner_message.author.mention}! You unscrambled the word correctly and earned **{coins} coins** and **{xp} XP**!"
                    )
                    
                except asyncio.TimeoutError:
                    # No one got it right
                    await channel.send(f"⏱️ Time's up! The correct word was: **{word}**")
                
                # Remove active game flag
                self.active_games.pop(channel_id, None)
                
                # Wait before next game (minimum 1 minute)
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in Reverse Spelling game: {e}")
                # Remove active game flag in case of error
                if channel_id in self.active_games:
                    self.active_games.pop(channel_id, None)
                await asyncio.sleep(60)  # Wait before trying again
    
    async def run_true_false(self):
        """Background task to run true or false games."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            channel_id = None  # Initialize channel_id
            try:
                # Check if enabled
                if not self.settings.true_false["enabled"]:
                    break
                
                channel_id = self.settings.true_false["channel_id"]
                channel = self.bot.get_channel(channel_id)
                
                if not channel:
                    logger.error(f"True/False channel {channel_id} not found")
                    await asyncio.sleep(60)  # Wait and try again
                    continue
                
                # Check if we should run (based on frequency)
                now = datetime.now()
                last_run = self.settings.true_false["last_run"]
                
                if last_run:
                    # Convert string date to datetime
                    last_run = datetime.fromisoformat(last_run)
                    next_run = last_run + timedelta(minutes=self.settings.true_false["frequency"])
                    
                    if now < next_run:
                        # Not time yet, sleep until next run
                        sleep_time = (next_run - now).total_seconds()
                        await asyncio.sleep(sleep_time)
                
                # Check if channel is already running a game
                if channel_id in self.active_games:
                    await asyncio.sleep(30)  # Try again in 30 seconds
                    continue
                    
                self.active_games[channel_id] = "true_false"
                
                # Decide if the fact will be true or false
                is_true = random.choice([True, False])
                
                # Select a fact
                fact = random.choice(self.true_facts if is_true else self.false_facts)
                
                embed = discord.Embed(
                    title="✅ True or ❌ False?",
                    description="React with ✅ for True or ❌ for False:",
                    color=discord.Color.teal()
                )
                
                embed.add_field(name="Fact", value=fact, inline=False)
                embed.add_field(name="Rewards", value=f"{self.settings.true_false['min_coins']}-{self.settings.true_false['max_coins']} coins and {self.settings.true_false['min_xp']}-{self.settings.true_false['max_xp']} XP", inline=False)
                
                # Send the challenge
                message = await channel.send(embed=embed)
                
                # Add reactions
                await message.add_reaction("✅")
                await message.add_reaction("❌")
                
                # Update last run time
                self.settings.true_false["last_run"] = now.isoformat()
                self.save_settings()
                
                # Wait for answers (60 seconds)
                await asyncio.sleep(60)
                
                # Get the message with reactions
                message = await channel.fetch_message(message.id)
                
                # Get users who reacted correctly
                correct_emoji = "✅" if is_true else "❌"
                incorrect_emoji = "❌" if is_true else "✅"
                
                # Find the correct reaction
                correct_reaction = None
                for reaction in message.reactions:
                    if str(reaction.emoji) == correct_emoji:
                        correct_reaction = reaction
                        break
                
                if correct_reaction:
                    # Get users who reacted correctly
                    users = []
                    async for user in correct_reaction.users():
                        if not user.bot:  # Exclude bot reactions
                            users.append(user)
                    
                    if users:
                        # Award all correct users
                        rewards_text = ""
                        
                        for user in users:
                            # Generate rewards
                            coins = random.randint(self.settings.true_false["min_coins"], self.settings.true_false["max_coins"])
                            xp = random.randint(self.settings.true_false["min_xp"], self.settings.true_false["max_xp"])
                            
                            # Award the user
                            await self.award_rewards(user.id, user.name, xp, coins)
                            
                            rewards_text += f"• {user.mention}: **{coins} coins** and **{xp} XP**\n"
                        
                        # Announce winners
                        await channel.send(
                            f"The fact was **{'True' if is_true else 'False'}**!\n\n"
                            f"🎉 Congratulations to the {len(users)} player(s) who guessed correctly:\n{rewards_text}"
                        )
                    else:
                        await channel.send(f"The fact was **{'True' if is_true else 'False'}**, but no one guessed correctly!")
                else:
                    await channel.send(f"The fact was **{'True' if is_true else 'False'}**, but no one guessed correctly!")
                
                # Remove active game flag
                self.active_games.pop(channel_id, None)
                
                # Wait before next game (minimum 1 minute)
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in True/False game: {e}")
                # Remove active game flag in case of error
                if channel_id in self.active_games:
                    self.active_games.pop(channel_id, None)
                await asyncio.sleep(60)  # Wait before trying again

class TypeRaceSettingsView(discord.ui.View):
    """View with buttons for Type Race settings configuration."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        
    @discord.ui.button(label="Toggle Status", style=discord.ButtonStyle.primary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle enabled/disabled status."""
        current = self.cog.settings.type_race.get("enabled", False)
        self.cog.settings.type_race["enabled"] = not current
        self.cog.save_settings()
        
        # Restart task if needed
        if self.cog.type_race_task:
            self.cog.type_race_task.cancel()
            
        if self.cog.settings.type_race["enabled"]:
            self.cog.type_race_task = asyncio.create_task(self.cog.run_type_race())
        
        # Update embed
        await self.update_settings_embed(interaction)
        
    @discord.ui.button(label="Set Channel", style=discord.ButtonStyle.primary)
    async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set channel."""
        await interaction.response.send_modal(SetChannelModal(self.cog))
        
    @discord.ui.button(label="Set Rewards", style=discord.ButtonStyle.primary)
    async def rewards_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set rewards."""
        await interaction.response.send_modal(SetRewardsModal(self.cog))
        
    @discord.ui.button(label="Set Frequency", style=discord.ButtonStyle.primary)
    async def frequency_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set frequency."""
        await interaction.response.send_modal(SetFrequencyModal(self.cog))
        
    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to main mini-games panel."""
        await interaction.response.defer()
        await self.cog.minigames(interaction)
    
    async def update_settings_embed(self, interaction):
        """Update the settings embed with current values."""
        current_settings = self.cog.settings.type_race
        channel = self.cog.bot.get_channel(current_settings.get("channel_id", 0))
        channel_mention = channel.mention if channel else "None"
        
        status = "Enabled" if current_settings.get("enabled", False) else "Disabled"
        
        embed = discord.Embed(
            title="⌨️ Type Race Settings",
            description="Use the buttons below to configure the Type Race mini-game.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Status:** {status}\n"
                f"**Channel:** {channel_mention}\n"
                f"**Coin Rewards:** {current_settings.get('min_coins', 0)}-{current_settings.get('max_coins', 0)}\n"
                f"**XP Rewards:** {current_settings.get('min_xp', 0)}-{current_settings.get('max_xp', 0)}\n"
                f"**Frequency:** Every {current_settings.get('frequency', 0)} minutes"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)


class SetChannelModal(discord.ui.Modal, title="Set Type Race Channel"):
    """Modal for setting the Type Race channel."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Right-click channel & Copy ID",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            channel_id = int(self.channel_id.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found. Please provide a valid channel ID.", ephemeral=True)
                return
                
            self.cog.settings.type_race["channel_id"] = channel_id
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = TypeRaceSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid channel ID (numbers only).", ephemeral=True)


class SetRewardsModal(discord.ui.Modal, title="Set Type Race Rewards"):
    """Modal for setting Type Race rewards."""
    
    min_coins = discord.ui.TextInput(
        label="Minimum Coins",
        placeholder="Enter minimum coins reward",
        required=True
    )
    
    max_coins = discord.ui.TextInput(
        label="Maximum Coins",
        placeholder="Enter maximum coins reward",
        required=True
    )
    
    min_xp = discord.ui.TextInput(
        label="Minimum XP",
        placeholder="Enter minimum XP reward",
        required=True
    )
    
    max_xp = discord.ui.TextInput(
        label="Maximum XP",
        placeholder="Enter maximum XP reward",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default values
        self.min_coins.default = str(self.cog.settings.type_race.get("min_coins", 5))
        self.max_coins.default = str(self.cog.settings.type_race.get("max_coins", 15))
        self.min_xp.default = str(self.cog.settings.type_race.get("min_xp", 5))
        self.max_xp.default = str(self.cog.settings.type_race.get("max_xp", 15))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            min_coins = int(self.min_coins.value)
            max_coins = int(self.max_coins.value)
            min_xp = int(self.min_xp.value)
            max_xp = int(self.max_xp.value)
            
            if min_coins > max_coins:
                await interaction.response.send_message("❌ Minimum coins cannot be greater than maximum coins.", ephemeral=True)
                return
                
            if min_xp > max_xp:
                await interaction.response.send_message("❌ Minimum XP cannot be greater than maximum XP.", ephemeral=True)
                return
                
            self.cog.settings.type_race["min_coins"] = min_coins
            self.cog.settings.type_race["max_coins"] = max_coins
            self.cog.settings.type_race["min_xp"] = min_xp
            self.cog.settings.type_race["max_xp"] = max_xp
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = TypeRaceSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields.", ephemeral=True)


class SetFrequencyModal(discord.ui.Modal, title="Set Type Race Frequency"):
    """Modal for setting Type Race frequency."""
    
    frequency = discord.ui.TextInput(
        label="Frequency (minutes)",
        placeholder="How often to run the game (in minutes)",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default value
        self.frequency.default = str(self.cog.settings.type_race.get("frequency", 30))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            frequency = int(self.frequency.value)
            
            if frequency < 1:
                await interaction.response.send_message("❌ Frequency must be at least 1 minute.", ephemeral=True)
                return
                
            self.cog.settings.type_race["frequency"] = frequency
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = TypeRaceSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for frequency.", ephemeral=True)


class MiniGamesMainPanel(discord.ui.View):
    """Main panel for selecting which mini-game to configure."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        
    @discord.ui.button(label="Type Race", style=discord.ButtonStyle.primary, emoji="⌨️")
    async def type_race_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Type Race settings panel."""
        await interaction.response.defer()
        await self.cog.editrace(interaction)
        
    @discord.ui.button(label="Memory Game", style=discord.ButtonStyle.primary, emoji="🧠")
    async def memory_game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Memory Game settings panel."""
        view = MemoryGameSettingsView(self.cog)
        await view.update_settings_embed(interaction)
        
    @discord.ui.button(label="Reverse Spelling", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reverse_spelling_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Reverse Spelling settings panel."""
        view = ReverseSpellingSettingsView(self.cog)
        await view.update_settings_embed(interaction)
        
    @discord.ui.button(label="True/False", style=discord.ButtonStyle.primary, emoji="✅")
    async def true_false_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open True/False settings panel."""
        view = TrueFalseSettingsView(self.cog)
        await view.update_settings_embed(interaction)


class MemoryGameSettingsView(discord.ui.View):
    """View with buttons for Memory Game settings configuration."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        
    @discord.ui.button(label="Toggle Status", style=discord.ButtonStyle.primary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle enabled/disabled status."""
        current = self.cog.settings.memory_game.get("enabled", False)
        self.cog.settings.memory_game["enabled"] = not current
        self.cog.save_settings()
        
        # Restart task if needed
        if self.cog.memory_game_task:
            self.cog.memory_game_task.cancel()
            
        if self.cog.settings.memory_game["enabled"]:
            self.cog.memory_game_task = asyncio.create_task(self.cog.run_memory_game())
        
        # Update embed
        await self.update_settings_embed(interaction)
        
    @discord.ui.button(label="Set Channel", style=discord.ButtonStyle.primary)
    async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set channel."""
        await interaction.response.send_modal(SetMemoryChannelModal(self.cog))
        
    @discord.ui.button(label="Set Rewards", style=discord.ButtonStyle.primary)
    async def rewards_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set rewards."""
        await interaction.response.send_modal(SetMemoryRewardsModal(self.cog))
        
    @discord.ui.button(label="Set Frequency", style=discord.ButtonStyle.primary)
    async def frequency_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set frequency."""
        await interaction.response.send_modal(SetMemoryFrequencyModal(self.cog))
    
    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to main mini-games panel."""
        await interaction.response.defer()
        await self.cog.minigames(interaction)
    
    async def update_settings_embed(self, interaction):
        """Update the settings embed with current values."""
        current_settings = self.cog.settings.memory_game
        channel = self.cog.bot.get_channel(current_settings.get("channel_id", 0))
        channel_mention = channel.mention if channel else "None"
        
        status = "Enabled" if current_settings.get("enabled", False) else "Disabled"
        
        embed = discord.Embed(
            title="🧠 Memory Game Settings",
            description="Use the buttons below to configure the Memory Game mini-game.",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Status:** {status}\n"
                f"**Channel:** {channel_mention}\n"
                f"**Coin Rewards:** {current_settings.get('min_coins', 0)}-{current_settings.get('max_coins', 0)}\n"
                f"**XP Rewards:** {current_settings.get('min_xp', 0)}-{current_settings.get('max_xp', 0)}\n"
                f"**Frequency:** Every {current_settings.get('frequency', 0)} minutes"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self) if interaction.response.is_done() else await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class ReverseSpellingSettingsView(discord.ui.View):
    """View with buttons for Reverse Spelling settings configuration."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        
    @discord.ui.button(label="Toggle Status", style=discord.ButtonStyle.primary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle enabled/disabled status."""
        current = self.cog.settings.reverse_spelling.get("enabled", False)
        self.cog.settings.reverse_spelling["enabled"] = not current
        self.cog.save_settings()
        
        # Restart task if needed
        if self.cog.reverse_spelling_task:
            self.cog.reverse_spelling_task.cancel()
            
        if self.cog.settings.reverse_spelling["enabled"]:
            self.cog.reverse_spelling_task = asyncio.create_task(self.cog.run_reverse_spelling())
        
        # Update embed
        await self.update_settings_embed(interaction)
        
    @discord.ui.button(label="Set Channel", style=discord.ButtonStyle.primary)
    async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set channel."""
        await interaction.response.send_modal(SetReverseSpellingChannelModal(self.cog))
        
    @discord.ui.button(label="Set Rewards", style=discord.ButtonStyle.primary)
    async def rewards_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set rewards."""
        await interaction.response.send_modal(SetReverseSpellingRewardsModal(self.cog))
        
    @discord.ui.button(label="Set Frequency", style=discord.ButtonStyle.primary)
    async def frequency_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set frequency."""
        await interaction.response.send_modal(SetReverseSpellingFrequencyModal(self.cog))
    
    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to main mini-games panel."""
        await interaction.response.defer()
        await self.cog.minigames(interaction)
    
    async def update_settings_embed(self, interaction):
        """Update the settings embed with current values."""
        current_settings = self.cog.settings.reverse_spelling
        channel = self.cog.bot.get_channel(current_settings.get("channel_id", 0))
        channel_mention = channel.mention if channel else "None"
        
        status = "Enabled" if current_settings.get("enabled", False) else "Disabled"
        
        embed = discord.Embed(
            title="🔄 Reverse Spelling Settings",
            description="Use the buttons below to configure the Reverse Spelling mini-game.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Status:** {status}\n"
                f"**Channel:** {channel_mention}\n"
                f"**Coin Rewards:** {current_settings.get('min_coins', 0)}-{current_settings.get('max_coins', 0)}\n"
                f"**XP Rewards:** {current_settings.get('min_xp', 0)}-{current_settings.get('max_xp', 0)}\n"
                f"**Frequency:** Every {current_settings.get('frequency', 0)} minutes"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self) if interaction.response.is_done() else await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class TrueFalseSettingsView(discord.ui.View):
    """View with buttons for True/False settings configuration."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        
    @discord.ui.button(label="Toggle Status", style=discord.ButtonStyle.primary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle enabled/disabled status."""
        current = self.cog.settings.true_false.get("enabled", False)
        self.cog.settings.true_false["enabled"] = not current
        self.cog.save_settings()
        
        # Restart task if needed
        if self.cog.true_false_task:
            self.cog.true_false_task.cancel()
            
        if self.cog.settings.true_false["enabled"]:
            self.cog.true_false_task = asyncio.create_task(self.cog.run_true_false())
        
        # Update embed
        await self.update_settings_embed(interaction)
        
    @discord.ui.button(label="Set Channel", style=discord.ButtonStyle.primary)
    async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set channel."""
        await interaction.response.send_modal(SetTrueFalseChannelModal(self.cog))
        
    @discord.ui.button(label="Set Rewards", style=discord.ButtonStyle.primary)
    async def rewards_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set rewards."""
        await interaction.response.send_modal(SetTrueFalseRewardsModal(self.cog))
        
    @discord.ui.button(label="Set Frequency", style=discord.ButtonStyle.primary)
    async def frequency_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set frequency."""
        await interaction.response.send_modal(SetTrueFalseFrequencyModal(self.cog))
    
    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to main mini-games panel."""
        await interaction.response.defer()
        await self.cog.minigames(interaction)
    
    async def update_settings_embed(self, interaction):
        """Update the settings embed with current values."""
        current_settings = self.cog.settings.true_false
        channel = self.cog.bot.get_channel(current_settings.get("channel_id", 0))
        channel_mention = channel.mention if channel else "None"
        
        status = "Enabled" if current_settings.get("enabled", False) else "Disabled"
        
        embed = discord.Embed(
            title="✅❌ True/False Settings",
            description="Use the buttons below to configure the True/False mini-game.",
            color=discord.Color.teal()
        )
        
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Status:** {status}\n"
                f"**Channel:** {channel_mention}\n"
                f"**Coin Rewards:** {current_settings.get('min_coins', 0)}-{current_settings.get('max_coins', 0)}\n"
                f"**XP Rewards:** {current_settings.get('min_xp', 0)}-{current_settings.get('max_xp', 0)}\n"
                f"**Frequency:** Every {current_settings.get('frequency', 0)} minutes"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self) if interaction.response.is_done() else await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


# Modal classes for Memory Game
class SetMemoryChannelModal(discord.ui.Modal, title="Set Memory Game Channel"):
    """Modal for setting the Memory Game channel."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Right-click channel & Copy ID",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            channel_id = int(self.channel_id.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found. Please provide a valid channel ID.", ephemeral=True)
                return
                
            self.cog.settings.memory_game["channel_id"] = channel_id
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = MemoryGameSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid channel ID (numbers only).", ephemeral=True)


class SetMemoryRewardsModal(discord.ui.Modal, title="Set Memory Game Rewards"):
    """Modal for setting Memory Game rewards."""
    
    min_coins = discord.ui.TextInput(
        label="Minimum Coins",
        placeholder="Enter minimum coins reward",
        required=True
    )
    
    max_coins = discord.ui.TextInput(
        label="Maximum Coins",
        placeholder="Enter maximum coins reward",
        required=True
    )
    
    min_xp = discord.ui.TextInput(
        label="Minimum XP",
        placeholder="Enter minimum XP reward",
        required=True
    )
    
    max_xp = discord.ui.TextInput(
        label="Maximum XP",
        placeholder="Enter maximum XP reward",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default values
        self.min_coins.default = str(self.cog.settings.memory_game.get("min_coins", 5))
        self.max_coins.default = str(self.cog.settings.memory_game.get("max_coins", 15))
        self.min_xp.default = str(self.cog.settings.memory_game.get("min_xp", 5))
        self.max_xp.default = str(self.cog.settings.memory_game.get("max_xp", 15))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            min_coins = int(self.min_coins.value)
            max_coins = int(self.max_coins.value)
            min_xp = int(self.min_xp.value)
            max_xp = int(self.max_xp.value)
            
            if min_coins > max_coins:
                await interaction.response.send_message("❌ Minimum coins cannot be greater than maximum coins.", ephemeral=True)
                return
                
            if min_xp > max_xp:
                await interaction.response.send_message("❌ Minimum XP cannot be greater than maximum XP.", ephemeral=True)
                return
                
            self.cog.settings.memory_game["min_coins"] = min_coins
            self.cog.settings.memory_game["max_coins"] = max_coins
            self.cog.settings.memory_game["min_xp"] = min_xp
            self.cog.settings.memory_game["max_xp"] = max_xp
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = MemoryGameSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields.", ephemeral=True)


class SetMemoryFrequencyModal(discord.ui.Modal, title="Set Memory Game Frequency"):
    """Modal for setting Memory Game frequency."""
    
    frequency = discord.ui.TextInput(
        label="Frequency (minutes)",
        placeholder="How often to run the game (in minutes)",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default value
        self.frequency.default = str(self.cog.settings.memory_game.get("frequency", 30))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            frequency = int(self.frequency.value)
            
            if frequency < 1:
                await interaction.response.send_message("❌ Frequency must be at least 1 minute.", ephemeral=True)
                return
                
            self.cog.settings.memory_game["frequency"] = frequency
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = MemoryGameSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for frequency.", ephemeral=True)


# Modal classes for Reverse Spelling
class SetReverseSpellingChannelModal(discord.ui.Modal, title="Set Reverse Spelling Channel"):
    """Modal for setting the Reverse Spelling channel."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Right-click channel & Copy ID",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            channel_id = int(self.channel_id.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found. Please provide a valid channel ID.", ephemeral=True)
                return
                
            self.cog.settings.reverse_spelling["channel_id"] = channel_id
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = ReverseSpellingSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid channel ID (numbers only).", ephemeral=True)


class SetReverseSpellingRewardsModal(discord.ui.Modal, title="Set Reverse Spelling Rewards"):
    """Modal for setting Reverse Spelling rewards."""
    
    min_coins = discord.ui.TextInput(
        label="Minimum Coins",
        placeholder="Enter minimum coins reward",
        required=True
    )
    
    max_coins = discord.ui.TextInput(
        label="Maximum Coins",
        placeholder="Enter maximum coins reward",
        required=True
    )
    
    min_xp = discord.ui.TextInput(
        label="Minimum XP",
        placeholder="Enter minimum XP reward",
        required=True
    )
    
    max_xp = discord.ui.TextInput(
        label="Maximum XP",
        placeholder="Enter maximum XP reward",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default values
        self.min_coins.default = str(self.cog.settings.reverse_spelling.get("min_coins", 5))
        self.max_coins.default = str(self.cog.settings.reverse_spelling.get("max_coins", 15))
        self.min_xp.default = str(self.cog.settings.reverse_spelling.get("min_xp", 5))
        self.max_xp.default = str(self.cog.settings.reverse_spelling.get("max_xp", 15))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            min_coins = int(self.min_coins.value)
            max_coins = int(self.max_coins.value)
            min_xp = int(self.min_xp.value)
            max_xp = int(self.max_xp.value)
            
            if min_coins > max_coins:
                await interaction.response.send_message("❌ Minimum coins cannot be greater than maximum coins.", ephemeral=True)
                return
                
            if min_xp > max_xp:
                await interaction.response.send_message("❌ Minimum XP cannot be greater than maximum XP.", ephemeral=True)
                return
                
            self.cog.settings.reverse_spelling["min_coins"] = min_coins
            self.cog.settings.reverse_spelling["max_coins"] = max_coins
            self.cog.settings.reverse_spelling["min_xp"] = min_xp
            self.cog.settings.reverse_spelling["max_xp"] = max_xp
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = ReverseSpellingSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields.", ephemeral=True)


class SetReverseSpellingFrequencyModal(discord.ui.Modal, title="Set Reverse Spelling Frequency"):
    """Modal for setting Reverse Spelling frequency."""
    
    frequency = discord.ui.TextInput(
        label="Frequency (minutes)",
        placeholder="How often to run the game (in minutes)",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default value
        self.frequency.default = str(self.cog.settings.reverse_spelling.get("frequency", 30))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            frequency = int(self.frequency.value)
            
            if frequency < 1:
                await interaction.response.send_message("❌ Frequency must be at least 1 minute.", ephemeral=True)
                return
                
            self.cog.settings.reverse_spelling["frequency"] = frequency
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = ReverseSpellingSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for frequency.", ephemeral=True)


# Modal classes for True/False
class SetTrueFalseChannelModal(discord.ui.Modal, title="Set True/False Channel"):
    """Modal for setting the True/False channel."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Right-click channel & Copy ID",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            channel_id = int(self.channel_id.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found. Please provide a valid channel ID.", ephemeral=True)
                return
                
            self.cog.settings.true_false["channel_id"] = channel_id
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = TrueFalseSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid channel ID (numbers only).", ephemeral=True)


class SetTrueFalseRewardsModal(discord.ui.Modal, title="Set True/False Rewards"):
    """Modal for setting True/False rewards."""
    
    min_coins = discord.ui.TextInput(
        label="Minimum Coins",
        placeholder="Enter minimum coins reward",
        required=True
    )
    
    max_coins = discord.ui.TextInput(
        label="Maximum Coins",
        placeholder="Enter maximum coins reward",
        required=True
    )
    
    min_xp = discord.ui.TextInput(
        label="Minimum XP",
        placeholder="Enter minimum XP reward",
        required=True
    )
    
    max_xp = discord.ui.TextInput(
        label="Maximum XP",
        placeholder="Enter maximum XP reward",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default values
        self.min_coins.default = str(self.cog.settings.true_false.get("min_coins", 5))
        self.max_coins.default = str(self.cog.settings.true_false.get("max_coins", 15))
        self.min_xp.default = str(self.cog.settings.true_false.get("min_xp", 5))
        self.max_xp.default = str(self.cog.settings.true_false.get("max_xp", 15))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            min_coins = int(self.min_coins.value)
            max_coins = int(self.max_coins.value)
            min_xp = int(self.min_xp.value)
            max_xp = int(self.max_xp.value)
            
            if min_coins > max_coins:
                await interaction.response.send_message("❌ Minimum coins cannot be greater than maximum coins.", ephemeral=True)
                return
                
            if min_xp > max_xp:
                await interaction.response.send_message("❌ Minimum XP cannot be greater than maximum XP.", ephemeral=True)
                return
                
            self.cog.settings.true_false["min_coins"] = min_coins
            self.cog.settings.true_false["max_coins"] = max_coins
            self.cog.settings.true_false["min_xp"] = min_xp
            self.cog.settings.true_false["max_xp"] = max_xp
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = TrueFalseSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields.", ephemeral=True)


class SetTrueFalseFrequencyModal(discord.ui.Modal, title="Set True/False Frequency"):
    """Modal for setting True/False frequency."""
    
    frequency = discord.ui.TextInput(
        label="Frequency (minutes)",
        placeholder="How often to run the game (in minutes)",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        # Set default value
        self.frequency.default = str(self.cog.settings.true_false.get("frequency", 30))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            frequency = int(self.frequency.value)
            
            if frequency < 1:
                await interaction.response.send_message("❌ Frequency must be at least 1 minute.", ephemeral=True)
                return
                
            self.cog.settings.true_false["frequency"] = frequency
            self.cog.save_settings()
            
            # Update the view with the new settings
            view = TrueFalseSettingsView(self.cog)
            await view.update_settings_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for frequency.", ephemeral=True)


async def setup(bot):
    """Add the mini-games cog to the bot."""
    await bot.add_cog(MiniGamesCog(bot))