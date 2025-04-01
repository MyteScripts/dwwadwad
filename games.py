import discord
from discord import app_commands
from discord.ext import commands
import logging
import datetime
import json
import os
import random
import asyncio
import string
import re

class GamesCog(commands.Cog):
    """Cog for running fun mini-games in text channels."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('games')
        
        # Settings
        self.enabled = True
        self.cooldown_minutes = 15
        self.last_game_time = 0
        self.xp_rewards = (10, 50)  # Min and max XP rewards
        self.coin_rewards = (5, 25)  # Min and max coin rewards
        self.allowed_channels = []
        
        # Active games
        self.active_games = {}
        
        # Load settings
        self.load_settings()
        
        # Start the game spawner - will be initialized in cog_load
        self.spawn_game_task = None
    
    def load_settings(self):
        """Load games settings from settings.json."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                games_settings = settings.get('games', {})
                
                self.enabled = games_settings.get('enabled', True)
                self.cooldown_minutes = games_settings.get('cooldown_minutes', 15)
                self.xp_rewards = games_settings.get('xp_rewards', (10, 50))
                self.coin_rewards = games_settings.get('coin_rewards', (5, 25))
                self.allowed_channels = games_settings.get('allowed_channels', [])
        except Exception as e:
            self.logger.error(f"Failed to load games settings: {e}")
    
    def save_settings(self):
        """Save games settings to settings.json."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
            
            if 'games' not in settings:
                settings['games'] = {}
            
            settings['games']['enabled'] = self.enabled
            settings['games']['cooldown_minutes'] = self.cooldown_minutes
            settings['games']['xp_rewards'] = self.xp_rewards
            settings['games']['coin_rewards'] = self.coin_rewards
            settings['games']['allowed_channels'] = self.allowed_channels
            
            with open('settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save games settings: {e}")
    
    async def cog_load(self):
        """Initialize tasks when the cog is loaded."""
        # Start the game spawner with async context
        self.spawn_game_task = asyncio.create_task(self.spawn_games_loop())
    
    def cog_unload(self):
        """Clean up when the cog is unloaded."""
        if self.spawn_game_task:
            self.spawn_game_task.cancel()
    
    async def spawn_games_loop(self):
        """Loop that spawns games periodically."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                # Check if games are enabled
                if not self.enabled:
                    await asyncio.sleep(60)
                    continue
                
                # Check cooldown
                current_time = datetime.datetime.now().timestamp()
                if current_time - self.last_game_time < self.cooldown_minutes * 60:
                    await asyncio.sleep(30)
                    continue
                
                # Randomly decide whether to spawn a game now
                if random.random() < 0.25:  # 25% chance every check
                    await self.spawn_random_game()
                    self.last_game_time = current_time
                
                # Wait before checking again
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Error in spawn_games_loop: {e}")
                await asyncio.sleep(60)
    
    async def spawn_random_game(self):
        """Spawn a random game in an allowed channel."""
        if not self.allowed_channels:
            return
        
        # Get a random allowed channel
        channel_id = random.choice(self.allowed_channels)
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return
        
        # Choose a random game type
        game_type = random.choice(['typing', 'emoji', 'math'])
        
        if game_type == 'typing':
            await self.spawn_typing_game(channel)
        elif game_type == 'emoji':
            await self.spawn_emoji_game(channel)
        elif game_type == 'math':
            await self.spawn_math_game(channel)
    
    async def spawn_typing_game(self, channel):
        """Spawn a typing game in the specified channel."""
        # List of phrases
        phrases = [
            "The quick brown fox jumps over the lazy dog",
            "All that glitters is not gold",
            "A journey of a thousand miles begins with a single step",
            "Rome wasn't built in a day",
            "Actions speak louder than words",
            "The early bird catches the worm",
            "Practice makes perfect",
            "Better late than never",
            "Don't judge a book by its cover",
            "You can't teach an old dog new tricks",
            "Where there's a will there's a way",
            "When in Rome, do as the Romans do",
            "The pen is mightier than the sword",
            "Fortune favors the bold",
            "A picture is worth a thousand words"
        ]
        
        # Choose a random phrase
        phrase = random.choice(phrases)
        
        # Create embed
        embed = discord.Embed(
            title="⌨️ Typing Challenge",
            description="First to type the following text correctly wins a reward!",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Type this:", value=f"```{phrase}```", inline=False)
        embed.set_footer(text="Type exactly as shown (case sensitive)")
        
        # Send the game message
        message = await channel.send(embed=embed)
        
        # Store the active game
        self.active_games[channel.id] = {
            'type': 'typing',
            'answer': phrase,
            'message_id': message.id,
            'started_at': datetime.datetime.now().timestamp()
        }
        
        # Set a timeout for the game
        self.bot.loop.create_task(self.game_timeout(channel.id, 60))
    
    async def spawn_emoji_game(self, channel):
        """Spawn an emoji sequence game in the specified channel."""
        # Generate a random sequence of 4-6 emojis
        emojis = ["😀", "😁", "😂", "🤣", "😃", "😄", "😅", "😆", "😉", "😊", 
                  "😋", "😎", "😍", "😘", "😗", "😙", "😚", "🙂", "🤗", "🤩",
                  "🤔", "🤨", "😐", "😑", "😶", "🙄", "😏", "😣", "😥", "😮",
                  "🤐", "😯", "😪", "😫", "😴", "😌", "😛", "😜", "😝", "🤤",
                  "😒", "😓", "😔", "😕", "🙃", "🤑", "😲", "☹️", "🙁", "😖"]
        
        sequence_length = random.randint(4, 6)
        emoji_sequence = " ".join(random.sample(emojis, sequence_length))
        
        # Create embed
        embed = discord.Embed(
            title="😎 Emoji Challenge",
            description="First to type the following emoji sequence correctly wins a reward!",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Type these emojis:", value=emoji_sequence, inline=False)
        embed.set_footer(text="Type exactly as shown (with spaces between emojis)")
        
        # Send the game message
        message = await channel.send(embed=embed)
        
        # Store the active game
        self.active_games[channel.id] = {
            'type': 'emoji',
            'answer': emoji_sequence,
            'message_id': message.id,
            'started_at': datetime.datetime.now().timestamp()
        }
        
        # Set a timeout for the game
        self.bot.loop.create_task(self.game_timeout(channel.id, 60))
    
    async def spawn_math_game(self, channel):
        """Spawn a math problem game in the specified channel."""
        # Generate a random math problem
        operations = ['+', '-', '*']
        operation = random.choice(operations)
        
        if operation == '+':
            num1 = random.randint(10, 100)
            num2 = random.randint(10, 100)
            answer = num1 + num2
            problem = f"{num1} + {num2}"
        elif operation == '-':
            num1 = random.randint(50, 100)
            num2 = random.randint(1, 49)
            answer = num1 - num2
            problem = f"{num1} - {num2}"
        else:  # multiplication
            num1 = random.randint(2, 12)
            num2 = random.randint(2, 12)
            answer = num1 * num2
            problem = f"{num1} × {num2}"
        
        # Create embed
        embed = discord.Embed(
            title="🧮 Math Challenge",
            description="First to solve this math problem correctly wins a reward!",
            color=discord.Color.red()
        )
        
        embed.add_field(name="Solve:", value=f"```{problem} = ?```", inline=False)
        embed.set_footer(text="Type just the number (answer)")
        
        # Send the game message
        message = await channel.send(embed=embed)
        
        # Store the active game
        self.active_games[channel.id] = {
            'type': 'math',
            'answer': str(answer),
            'message_id': message.id,
            'started_at': datetime.datetime.now().timestamp()
        }
        
        # Set a timeout for the game
        self.bot.loop.create_task(self.game_timeout(channel.id, 60))
    
    async def game_timeout(self, channel_id, seconds):
        """End a game after a timeout period if no one has won."""
        await asyncio.sleep(seconds)
        
        if channel_id in self.active_games:
            # Get the game info
            game_info = self.active_games[channel_id]
            
            # Get the channel
            channel = self.bot.get_channel(channel_id)
            if not channel:
                del self.active_games[channel_id]
                return
            
            # Get the message
            try:
                message = await channel.fetch_message(game_info['message_id'])
                
                # Update the embed
                embed = message.embeds[0]
                embed.title += " (Expired)"
                embed.color = discord.Color.light_grey()
                embed.add_field(name="Status", value="Game expired! No one answered in time.", inline=False)
                
                await message.edit(embed=embed)
                
                # Clean up
                del self.active_games[channel_id]
            except:
                # Message not found, just clean up
                del self.active_games[channel_id]
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Check if a message is the answer to an active game."""
        # Ignore messages from bots
        if message.author.bot:
            return
        
        # Check if there's an active game in this channel
        channel_id = message.channel.id
        if channel_id not in self.active_games:
            return
        
        # Get the game info
        game_info = self.active_games[channel_id]
        
        # Check if the message is the correct answer
        if message.content.strip() == game_info['answer']:
            # User won the game!
            
            # Calculate rewards
            xp_reward = random.randint(self.xp_rewards[0], self.xp_rewards[1])
            coin_reward = random.randint(self.coin_rewards[0], self.coin_rewards[1])
            
            # Award XP and coins
            from database import Database
            db = Database()
            
            # Get user data
            user_id = str(message.author.id)
            username = message.author.name
            user_data = db.get_or_create_user(user_id, username)
            
            # Add XP and coins
            db.add_xp(user_id, xp_reward)
            db.add_coins(user_id, coin_reward)
            
            try:
                # Get the game message
                game_message = await message.channel.fetch_message(game_info['message_id'])
                
                # Update the embed
                embed = game_message.embeds[0]
                embed.title += " (Completed)"
                embed.color = discord.Color.gold()
                embed.add_field(name="Winner", value=f"{message.author.mention} answered correctly!", inline=False)
                embed.add_field(name="Rewards", value=f"🪙 {coin_reward} Coins\n✨ {xp_reward} XP", inline=False)
                
                await game_message.edit(embed=embed)
                
                # Send a congratulatory message
                await message.reply(f"🎉 Congratulations! You earned **{coin_reward}** coins and **{xp_reward}** XP for winning the game!")
                
                # Clean up
                del self.active_games[channel_id]
            except Exception as e:
                self.logger.error(f"Error handling game win: {e}")
    
    # enablegames command removed
    
    # setgamecooldown command removed
    
    # setgamerewards command removed
    
    # addgamechannel command removed
    
    @app_commands.command(name="removegamechannel", description="Remove a channel from where mini-games can spawn (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def remove_game_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Remove a channel from where mini-games can spawn.
        
        Args:
            interaction: The interaction that triggered this command
            channel: The channel to remove
        """
        channel_id = str(channel.id)
        if channel_id not in self.allowed_channels:
            await interaction.response.send_message(
                f"{channel.mention} is not a game channel.",
                ephemeral=True
            )
            return
        
        self.allowed_channels.remove(channel_id)
        self.save_settings()
        
        await interaction.response.send_message(
            f"{channel.mention} has been removed as a game channel. Mini-games will no longer spawn there.",
            ephemeral=True
        )
    
    @app_commands.command(name="listgamechannels", description="List all channels where mini-games can spawn")
    async def list_game_channels(self, interaction: discord.Interaction):
        """List all channels where mini-games can spawn.
        
        Args:
            interaction: The interaction that triggered this command
        """
        if not self.allowed_channels:
            await interaction.response.send_message(
                "No game channels have been set up. Mini-games will not spawn automatically.",
                ephemeral=True
            )
            return
        
        channel_mentions = []
        for channel_id in self.allowed_channels:
            channel = interaction.guild.get_channel(int(channel_id))
            if channel:
                channel_mentions.append(channel.mention)
        
        embed = discord.Embed(
            title="Mini-Game Channels",
            description=f"Mini-games can spawn in the following channels:\n{', '.join(channel_mentions)}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Status", value=f"{'Enabled' if self.enabled else 'Disabled'}", inline=True)
        embed.add_field(name="Cooldown", value=f"{self.cooldown_minutes} minutes", inline=True)
        embed.add_field(name="Rewards", value=f"{self.xp_rewards[0]}-{self.xp_rewards[1]} XP\n{self.coin_rewards[0]}-{self.coin_rewards[1]} coins", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="forcegame", description="Force spawn a mini-game (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def force_game(self, interaction: discord.Interaction, game_type: str, channel: discord.TextChannel = None):
        """Force spawn a mini-game.
        
        Args:
            interaction: The interaction that triggered this command
            game_type: The type of game to spawn (typing, emoji, or math)
            channel: The channel to spawn the game in (defaults to the current channel)
        """
        target_channel = channel or interaction.channel
        
        if game_type not in ['typing', 'emoji', 'math']:
            await interaction.response.send_message(
                "Invalid game type. Choose from: typing, emoji, math",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            f"Spawning a {game_type} game in {target_channel.mention}...",
            ephemeral=True
        )
        
        if game_type == 'typing':
            await self.spawn_typing_game(target_channel)
        elif game_type == 'emoji':
            await self.spawn_emoji_game(target_channel)
        elif game_type == 'math':
            await self.spawn_math_game(target_channel)


async def setup(bot):
    """Add the games cog to the bot."""
    games_cog = GamesCog(bot)
    await bot.add_cog(games_cog)
    return games_cog