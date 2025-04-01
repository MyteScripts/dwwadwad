import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import datetime
import logging
import json
from logger import setup_logger
from database import Database
from settings_storage import settings_storage

logger = setup_logger('coin_panel', 'bot.log')

class CoinDropSettings:
    """Class to store coin drop settings."""
    def __init__(self):
        self.channel_id = None  # Channel to drop coins in
        self.min_coins = 10     # Minimum coins per drop
        self.max_coins = 50     # Maximum coins per drop
        self.duration = 1       # Duration value
        self.time_unit = "hour" # Time unit (minute, hour, day)
        self.is_active = False  # Whether coin drops are currently active
        self.task = None        # The scheduled task
        self.last_drop_time = None  # Timestamp of the last drop
        self.next_drop_time = None  # Timestamp for the next scheduled drop
        
    def get_seconds(self):
        """Convert duration and time unit to seconds."""
        if self.time_unit == "minute":
            return self.duration * 60
        elif self.time_unit == "hour":
            return self.duration * 60 * 60
        elif self.time_unit == "day":
            return self.duration * 24 * 60 * 60
        else:
            return self.duration * 60 * 60  # Default to hours

class CoinPanelCog(commands.Cog):
    """Cog for managing coins and coin drops through an admin panel."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.coin_drop_settings = {}  # Guild ID -> CoinDropSettings
        self.load_settings()
        logger.info("Coin panel cog initialized")
        
    async def cog_load(self):
        """Called when the cog is loaded."""

        self.bot.add_listener(self.on_ready_resume_coin_drops, 'on_ready')
        
    async def on_ready_resume_coin_drops(self):
        """Resume coin drops when the bot is ready."""
        logger.info("Bot is ready - resuming active coin drops")
        await self.resume_active_coin_drops()
        
    async def resume_active_coin_drops(self):
        """Resume active coin drops from saved settings."""

        for guild_id, settings in self.coin_drop_settings.items():

            if settings.is_active:
                logger.info(f"Resuming coin drops for guild {guild_id}")
                await self.toggle_coin_drops(guild_id, restart=True)
        
    def load_settings(self):
        """Load coin drop settings from persistent storage."""
        try:

            coin_settings = settings_storage.get_coin_drop_settings()

            for guild_id, settings in coin_settings.items():
                guild_id = int(guild_id)  # Convert back to int
                drop_settings = CoinDropSettings()

                if "channel_id" in settings:
                    drop_settings.channel_id = settings["channel_id"]
                if "min_coins" in settings:
                    drop_settings.min_coins = settings["min_coins"]
                if "max_coins" in settings:
                    drop_settings.max_coins = settings["max_coins"]
                if "duration" in settings:
                    drop_settings.duration = settings["duration"]
                if "time_unit" in settings:
                    drop_settings.time_unit = settings["time_unit"]
                if "is_active" in settings:
                    drop_settings.is_active = settings["is_active"]
                if "last_drop_time" in settings and settings["last_drop_time"] is not None:
                    drop_settings.last_drop_time = datetime.datetime.fromtimestamp(settings["last_drop_time"])
                if "next_drop_time" in settings and settings["next_drop_time"] is not None:
                    drop_settings.next_drop_time = datetime.datetime.fromtimestamp(settings["next_drop_time"])

                self.coin_drop_settings[guild_id] = drop_settings
                
            logger.info(f"Loaded coin drop settings for {len(self.coin_drop_settings)} guilds")
        except Exception as e:
            logger.error(f"Error loading coin drop settings: {e}")
            
    def save_settings(self, guild_id):
        """Save coin drop settings to persistent storage."""
        try:
            settings = self.coin_drop_settings.get(guild_id)
            if not settings:
                return

            settings_dict = {
                "channel_id": settings.channel_id,
                "min_coins": settings.min_coins,
                "max_coins": settings.max_coins,
                "duration": settings.duration,
                "time_unit": settings.time_unit,
                "is_active": settings.is_active,
                "last_drop_time": settings.last_drop_time.timestamp() if settings.last_drop_time else None,
                "next_drop_time": settings.next_drop_time.timestamp() if settings.next_drop_time else None
            }

            settings_storage.save_coin_drop_settings(guild_id, settings_dict)
            logger.info(f"Saved coin drop settings for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving coin drop settings: {e}")
    
    @app_commands.command(
        name="coinpanel", 
        description="Open a panel to manage coins and coin drops (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def coin_panel(self, interaction: discord.Interaction):
        """
        Open a panel with buttons to manage coins and set up coin drops.
        """

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        if guild_id not in self.coin_drop_settings:
            self.coin_drop_settings[guild_id] = CoinDropSettings()

        view = CoinManagementView(self, interaction.guild.id)
        
        embed = discord.Embed(
            title="🪙 Coin Management Panel",
            description="Use the buttons below to manage coins and coin drops.",
            color=discord.Color.gold()
        )

        settings = self.coin_drop_settings[guild_id]
        if settings.channel_id:
            channel = interaction.guild.get_channel(settings.channel_id)
            channel_name = channel.name if channel else "Unknown"
            
            status = "✅ Active" if settings.is_active else "❌ Inactive"
            
            embed.add_field(
                name="Current Coin Drop Settings",
                value=(
                    f"**Channel:** {channel_name} (ID: {settings.channel_id})\n"
                    f"**Amount:** {settings.min_coins}-{settings.max_coins} coins\n"
                    f"**Interval:** Every {settings.duration} {settings.time_unit}(s)\n"
                    f"**Status:** {status}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Coin panel opened by {interaction.user.id}")
    
    async def add_coins(self, user_id, username, amount):
        """Add coins to a user."""
        if amount <= 0:
            return False, "Amount must be positive."
        
        try:

            self.db.add_coins(user_id, username, amount)

            user_data = self.db.get_user(user_id)
            
            if user_data is None:
                return False, f"User data could not be retrieved after adding coins."

            coins = 0
            if isinstance(user_data, (list, tuple)) and len(user_data) > 4:
                coins = user_data[4]
            elif isinstance(user_data, dict) and 'coins' in user_data:
                coins = user_data['coins']
            else:
                logger.error(f"Invalid user_data format: {user_data}")
                
            return True, f"Added {amount} coins to {username}. New balance: {coins} coins."
        except Exception as e:
            logger.error(f"Error adding coins: {e}")
            return False, f"Error adding coins: {str(e)}"
    
    async def remove_coins(self, user_id, username, amount):
        """Remove coins from a user."""
        if amount <= 0:
            return False, "Amount must be positive."
        
        try:

            user_data = self.db.get_user(user_id)
            
            if user_data is None:
                return False, f"User data not found for {username}."

            current_coins = 0
            if isinstance(user_data, (list, tuple)) and len(user_data) > 4:
                current_coins = user_data[4]
            elif isinstance(user_data, dict) and 'coins' in user_data:
                current_coins = user_data['coins']
            else:
                logger.error(f"Invalid user_data format: {user_data}")
                return False, f"Invalid user data format. Please report this to the administrator."

            if current_coins < amount:
                return False, f"{username} only has {current_coins} coins. Cannot remove {amount}."

            self.db.add_coins(user_id, username, -amount)

            user_data = self.db.get_user(user_id)
            
            if user_data is None:
                return False, f"User data could not be retrieved after removing coins."

            coins = 0
            if isinstance(user_data, (list, tuple)) and len(user_data) > 4:
                coins = user_data[4]
            elif isinstance(user_data, dict) and 'coins' in user_data:
                coins = user_data['coins']
            else:
                logger.error(f"Invalid user_data format after removing coins: {user_data}")
                
            return True, f"Removed {amount} coins from {username}. New balance: {coins} coins."
        except Exception as e:
            logger.error(f"Error removing coins: {e}")
            return False, f"Error removing coins: {str(e)}"
    
    async def set_coin_drop(self, guild_id, channel_id, min_coins, max_coins, duration, time_unit):
        """Set up coin drops in a channel."""
        try:

            if guild_id not in self.coin_drop_settings:
                self.coin_drop_settings[guild_id] = CoinDropSettings()
            
            settings = self.coin_drop_settings[guild_id]

            settings.channel_id = channel_id
            settings.min_coins = min_coins
            settings.max_coins = max_coins
            settings.duration = duration
            settings.time_unit = time_unit

            self.save_settings(guild_id)

            if settings.is_active:
                await self.toggle_coin_drops(guild_id, restart=True)
            
            return True, (
                f"Coin drop settings updated. Drops will occur every {duration} {time_unit}(s) "
                f"in <#{channel_id}> with {min_coins}-{max_coins} coins each."
            )
        except Exception as e:
            logger.error(f"Error setting coin drop: {e}")
            return False, f"Error setting coin drop: {str(e)}"
    
    async def toggle_coin_drops(self, guild_id, restart=False):
        """Start or stop coin drops for a guild."""
        try:

            if guild_id not in self.coin_drop_settings:
                return False, "No coin drop settings found. Please set up drops first."
            
            settings = self.coin_drop_settings[guild_id]

            if not settings.channel_id:
                return False, "No channel set for coin drops. Please set up drops first."

            if settings.task is not None and not settings.task.done():
                settings.task.cancel()
                settings.task = None
                
                if not restart:
                    settings.is_active = False
                    self.save_settings(guild_id)
                    return True, "Coin drops have been stopped."

            if restart or not settings.is_active:
                settings.is_active = True
                self.save_settings(guild_id)
                settings.task = asyncio.create_task(self._run_coin_drops(guild_id))
                
                interval_text = f"{settings.duration} {settings.time_unit}"
                if settings.duration != 1:
                    interval_text += "s"
                    
                return True, f"Coin drops have been started. Coins will drop every {interval_text}."
                
        except Exception as e:
            logger.error(f"Error toggling coin drops: {e}")
            return False, f"Error toggling coin drops: {str(e)}"
    
    async def _run_coin_drops(self, guild_id):
        """Background task to handle coin drops at intervals."""
        try:
            settings = self.coin_drop_settings[guild_id]
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                logger.error(f"Could not find guild {guild_id}")
                settings.is_active = False
                self.save_settings(guild_id)
                return
            
            logger.info(f"Starting coin drops in guild {guild.name} ({guild_id})")

            now = datetime.datetime.now()
            interval_seconds = settings.get_seconds()

            if settings.last_drop_time is None:
                settings.last_drop_time = now

            if settings.next_drop_time is None or settings.next_drop_time < now:

                if settings.next_drop_time is not None and settings.next_drop_time < now:

                    time_diff = (now - settings.next_drop_time).total_seconds()
                    intervals_passed = int(time_diff // interval_seconds) + 1

                    settings.next_drop_time = settings.next_drop_time + datetime.timedelta(seconds=interval_seconds * intervals_passed)
                    logger.info(f"Calculated next drop time: {settings.next_drop_time} after {intervals_passed} missed intervals")
                else:

                    settings.next_drop_time = now + datetime.timedelta(seconds=interval_seconds)
                    logger.info(f"Set initial next drop time: {settings.next_drop_time}")

                self.save_settings(guild_id)
            
            while settings.is_active:
                try:

                    now = datetime.datetime.now()
                    if settings.next_drop_time > now:
                        seconds_until_drop = (settings.next_drop_time - now).total_seconds()
                        logger.info(f"Waiting {seconds_until_drop:.2f} seconds until next coin drop in guild {guild_id}")

                        if seconds_until_drop > 0:
                            await asyncio.sleep(seconds_until_drop)

                    channel = guild.get_channel(settings.channel_id)
                    if not channel:
                        logger.error(f"Could not find channel {settings.channel_id}")
                        settings.is_active = False
                        self.save_settings(guild_id)
                        break

                    coin_amount = random.randint(settings.min_coins, settings.max_coins)

                    emoji = "💰"

                    embed = discord.Embed(
                        title="💰 Coin Drop!",
                        description=f"React with {emoji} to claim {coin_amount} coins!",
                        color=discord.Color.gold()
                    )

                    drop_message = await channel.send(embed=embed)

                    await drop_message.add_reaction(emoji)

                    settings.last_drop_time = datetime.datetime.now()
                    settings.next_drop_time = settings.last_drop_time + datetime.timedelta(seconds=interval_seconds)
                    next_drop_formatted = settings.next_drop_time.strftime("%I:%M %p")
                    self.save_settings(guild_id)
                    logger.info(f"Coin drop sent in guild {guild_id}, next drop at {next_drop_formatted}")

                    def check(reaction, user):
                        return user != self.bot.user and str(reaction.emoji) == emoji and reaction.message.id == drop_message.id
                    
                    try:

                        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                        self.db.add_coins(user.id, user.display_name, coin_amount)

                        embed.title = "💰 Coin Drop Claimed!"
                        embed.description = f"🎉 **{user.display_name}** claimed {coin_amount} coins!"
                        embed.color = discord.Color.green()
                        embed.set_footer(text=f"Next drop at {next_drop_formatted}")

                        await drop_message.edit(embed=embed)

                        await channel.send(f"🎉 Congratulations {user.mention}! You won {coin_amount} coins! 🎉")
                        
                        logger.info(f"Coin drop claimed by {user.id} ({user.display_name}) for {coin_amount} coins")
                    
                    except asyncio.TimeoutError:

                        embed.title = "💰 Coin Drop Expired!"
                        embed.description = "No one claimed the coins in time."
                        embed.color = discord.Color.red()
                        embed.set_footer(text=f"Next drop at {next_drop_formatted}")
                        
                        await drop_message.edit(embed=embed)
                        logger.info(f"Coin drop expired with no claims")

                except asyncio.CancelledError:
                    logger.info(f"Coin drop task cancelled for guild {guild_id}")
                    settings.is_active = False
                    self.save_settings(guild_id)
                    break
                except Exception as e:
                    logger.error(f"Error in coin drop cycle: {e}")
                    await asyncio.sleep(60)  # Wait a bit before retrying
            
            logger.info(f"Coin drop task stopped for guild {guild_id}")
            
        except asyncio.CancelledError:
            logger.info(f"Coin drop master task cancelled for guild {guild_id}")
            if guild_id in self.coin_drop_settings:
                self.coin_drop_settings[guild_id].is_active = False
                self.save_settings(guild_id)
        except Exception as e:
            logger.error(f"Error in coin drop task for guild {guild_id}: {e}")
            if guild_id in self.coin_drop_settings:
                self.coin_drop_settings[guild_id].is_active = False
                self.save_settings(guild_id)

class CoinManagementView(discord.ui.View):
    """View with buttons for managing coins."""
    
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(
        label="Add Coins", 
        style=discord.ButtonStyle.green,
        emoji="➕"
    )
    async def add_coins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for adding coins."""
        modal = AddCoinsModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Remove Coins", 
        style=discord.ButtonStyle.red,
        emoji="➖"
    )
    async def remove_coins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for removing coins."""
        modal = RemoveCoinsModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Set Up Drops", 
        style=discord.ButtonStyle.blurple,
        emoji="⚙️"
    )
    async def setup_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for setting up coin drops."""
        modal = SetupCoinDropsModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Toggle Drops", 
        style=discord.ButtonStyle.gray,
        emoji="🔄"
    )
    async def toggle_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to toggle coin drops on or off."""

        if self.guild_id not in self.cog.coin_drop_settings or not self.cog.coin_drop_settings[self.guild_id].channel_id:
            await interaction.response.send_message(
                "⚠️ Please set up coin drops first using the 'Set Up Drops' button.",
                ephemeral=True
            )
            return

        settings = self.cog.coin_drop_settings[self.guild_id]
        if settings.is_active:
            success, message = await self.cog.toggle_coin_drops(self.guild_id)
            if success:
                await interaction.response.send_message(
                    f"✅ {message}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
        else:

            view = CoinDropToggleView(self.cog, self.guild_id)
            
            channel = interaction.guild.get_channel(settings.channel_id)
            channel_name = channel.name if channel else f"Unknown (ID: {settings.channel_id})"
            
            embed = discord.Embed(
                title="Start Coin Drops?",
                description=(
                    f"Would you like to start coin drops with these settings?\n\n"
                    f"**Channel:** {channel_name}\n"
                    f"**Amount:** {settings.min_coins}-{settings.max_coins} coins\n"
                    f"**Interval:** Every {settings.duration} {settings.time_unit}(s)"
                ),
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class CoinDropToggleView(discord.ui.View):
    """View with buttons for toggling coin drops."""
    
    def __init__(self, cog, guild_id):
        super().__init__(timeout=120)  # 2 minute timeout
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(
        label="Start Drops", 
        style=discord.ButtonStyle.green,
        emoji="▶️"
    )
    async def start_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to start coin drops."""
        success, message = await self.cog.toggle_coin_drops(self.guild_id)
        
        if success:
            embed = discord.Embed(
                title="✅ Coin Drops Started",
                description=message,
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=message,
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
    
    @discord.ui.button(
        label="Cancel", 
        style=discord.ButtonStyle.gray,
        emoji="⏱️"
    )
    async def dont_start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to not start drops yet."""
        await interaction.response.send_message(
            "Coin drops have not been started.",
            ephemeral=True
        )
        self.stop()

class AddCoinsModal(discord.ui.Modal, title="Add Coins"):
    """Modal for adding coins to a user."""
    
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user's ID (right-click user & Copy ID)",
        required=True
    )
    
    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="Enter the amount of coins to add",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            user_id = int(self.user_id.value)
            amount = int(self.amount.value)

            member = interaction.guild.get_member(user_id)
            if not member:
                await interaction.response.send_message(
                    f"❌ Could not find a member with ID {user_id}.",
                    ephemeral=True
                )
                return

            success, message = await self.cog.add_coins(user_id, member.display_name, amount)
            
            if success:
                embed = discord.Embed(
                    title="✅ Coins Added",
                    description=message,
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description=message,
                    color=discord.Color.red()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers for User ID and Amount.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in add coins modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class RemoveCoinsModal(discord.ui.Modal, title="Remove Coins"):
    """Modal for removing coins from a user."""
    
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user's ID (right-click user & Copy ID)",
        required=True
    )
    
    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="Enter the amount of coins to remove",
        required=True
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            user_id = int(self.user_id.value)
            amount = int(self.amount.value)

            member = interaction.guild.get_member(user_id)
            if not member:
                await interaction.response.send_message(
                    f"❌ Could not find a member with ID {user_id}.",
                    ephemeral=True
                )
                return

            success, message = await self.cog.remove_coins(user_id, member.display_name, amount)
            
            if success:
                embed = discord.Embed(
                    title="✅ Coins Removed",
                    description=message,
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description=message,
                    color=discord.Color.red()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers for User ID and Amount.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in remove coins modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class SetupCoinDropsModal(discord.ui.Modal, title="Set Up Coin Drops"):
    """Modal for setting up coin drops."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID for drops",
        required=True
    )
    
    min_coins = discord.ui.TextInput(
        label="Minimum Coins",
        placeholder="Enter the minimum coins per drop (default: 10)",
        required=False,
        default="10"
    )
    
    max_coins = discord.ui.TextInput(
        label="Maximum Coins",
        placeholder="Enter the maximum coins per drop (default: 50)",
        required=False,
        default="50"
    )
    
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="How often drops occur (default: 1)",
        required=False,
        default="1"
    )
    
    time_unit = discord.ui.TextInput(
        label="Time Unit",
        placeholder="minute, hour, or day (default: hour)",
        required=False,
        default="hour"
    )
    
    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

        if guild_id in cog.coin_drop_settings:
            settings = cog.coin_drop_settings[guild_id]
            if settings.channel_id:
                self.channel_id.default = str(settings.channel_id)
            if settings.min_coins:
                self.min_coins.default = str(settings.min_coins)
            if settings.max_coins:
                self.max_coins.default = str(settings.max_coins)
            if settings.duration:
                self.duration.default = str(settings.duration)
            if settings.time_unit:
                self.time_unit.default = settings.time_unit
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            channel_id = int(self.channel_id.value)
            min_coins = int(self.min_coins.value or 10)
            max_coins = int(self.max_coins.value or 50)
            duration = int(self.duration.value or 1)
            time_unit = self.time_unit.value.lower() or "hour"

            if time_unit not in ["minute", "hour", "day"]:
                await interaction.response.send_message(
                    "❌ Time unit must be 'minute', 'hour', or 'day'.",
                    ephemeral=True
                )
                return

            if min_coins < 1:
                await interaction.response.send_message(
                    "❌ Minimum coins must be at least 1.",
                    ephemeral=True
                )
                return
            
            if max_coins < min_coins:
                await interaction.response.send_message(
                    "❌ Maximum coins must be greater than minimum coins.",
                    ephemeral=True
                )
                return
            
            if duration < 1:
                await interaction.response.send_message(
                    "❌ Duration must be at least 1.",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    f"❌ Could not find a channel with ID {channel_id}.",
                    ephemeral=True
                )
                return

            success, message = await self.cog.set_coin_drop(
                self.guild_id, channel_id, min_coins, max_coins, duration, time_unit
            )
            
            if success:

                view = CoinDropToggleView(self.cog, self.guild_id)
                
                embed = discord.Embed(
                    title="✅ Coin Drops Set Up",
                    description=(
                        f"{message}\n\n"
                        f"Would you like to start coin drops now?"
                    ),
                    color=discord.Color.green()
                )
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description=message,
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers for Channel ID, Min/Max Coins, and Duration.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in setup coin drops modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    """Add the coin panel cog to the bot."""
    await bot.add_cog(CoinPanelCog(bot))
    logger.info("Coin panel cog loaded")