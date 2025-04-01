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

logger = setup_logger('level_panel', 'bot.log')

class XPDropSettings:
    """Class to store XP drop settings."""
    def __init__(self):
        self.channel_id = None  # Channel to drop XP in
        self.min_xp = 20        # Minimum XP per drop
        self.max_xp = 100       # Maximum XP per drop
        self.duration = 1       # Duration value
        self.time_unit = "hour" # Time unit (minute, hour, day)
        self.is_active = False  # Whether XP drops are currently active
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

class LevelPanelCog(commands.Cog):
    """Cog for managing levels, XP, and XP drops through an admin panel."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.xp_drop_settings = {}  # Guild ID -> XPDropSettings
        self.load_settings()
        logger.info("Level panel cog initialized")
        
    async def cog_load(self):
        """Called when the cog is loaded."""

        self.bot.add_listener(self.on_ready_resume_xp_drops, 'on_ready')
        
    async def on_ready_resume_xp_drops(self):
        """Resume XP drops when the bot is ready."""
        logger.info("Bot is ready - resuming active XP drops")
        await self.resume_active_xp_drops()
        
    async def resume_active_xp_drops(self):
        """Resume active XP drops from saved settings."""

        for guild_id, settings in self.xp_drop_settings.items():

            if settings.is_active:
                logger.info(f"Resuming XP drops for guild {guild_id}")
                await self.toggle_xp_drops(guild_id, restart=True)
        
    def load_settings(self):
        """Load XP drop settings from persistent storage."""
        try:

            xp_settings = settings_storage.get_xp_drop_settings()

            for guild_id, settings in xp_settings.items():
                guild_id = int(guild_id)  # Convert back to int
                drop_settings = XPDropSettings()

                if "channel_id" in settings:
                    drop_settings.channel_id = settings["channel_id"]
                if "min_xp" in settings:
                    drop_settings.min_xp = settings["min_xp"]
                if "max_xp" in settings:
                    drop_settings.max_xp = settings["max_xp"]
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

                self.xp_drop_settings[guild_id] = drop_settings
                
            logger.info(f"Loaded XP drop settings for {len(self.xp_drop_settings)} guilds")
        except Exception as e:
            logger.error(f"Error loading XP drop settings: {e}")
            
    def save_settings(self, guild_id):
        """Save XP drop settings to persistent storage."""
        try:
            settings = self.xp_drop_settings.get(guild_id)
            if not settings:
                return

            settings_dict = {
                "channel_id": settings.channel_id,
                "min_xp": settings.min_xp,
                "max_xp": settings.max_xp,
                "duration": settings.duration,
                "time_unit": settings.time_unit,
                "is_active": settings.is_active,
                "last_drop_time": settings.last_drop_time.timestamp() if settings.last_drop_time else None,
                "next_drop_time": settings.next_drop_time.timestamp() if settings.next_drop_time else None
            }

            settings_storage.save_xp_drop_settings(guild_id, settings_dict)
            logger.info(f"Saved XP drop settings for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving XP drop settings: {e}")
    
    @app_commands.command(
        name="levelpanel", 
        description="Open a panel to manage levels, XP, and XP drops (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def level_panel(self, interaction: discord.Interaction):
        """
        Open a panel with buttons to manage levels, XP, and set up XP drops.
        """

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        if guild_id not in self.xp_drop_settings:
            self.xp_drop_settings[guild_id] = XPDropSettings()

        view = LevelManagementView(self, interaction.guild.id)
        
        embed = discord.Embed(
            title="📊 Level & XP Management Panel",
            description="Use the buttons below to manage levels, XP, and XP drops.",
            color=discord.Color.blue()
        )

        settings = self.xp_drop_settings[guild_id]
        if settings.channel_id:
            channel = interaction.guild.get_channel(settings.channel_id)
            channel_name = channel.name if channel else "Unknown"
            
            status = "✅ Active" if settings.is_active else "❌ Inactive"
            
            embed.add_field(
                name="Current XP Drop Settings",
                value=(
                    f"**Channel:** {channel_name} (ID: {settings.channel_id})\n"
                    f"**Amount:** {settings.min_xp}-{settings.max_xp} XP\n"
                    f"**Interval:** Every {settings.duration} {settings.time_unit}(s)\n"
                    f"**Status:** {status}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Level panel opened by {interaction.user.id}")
    
    async def add_xp(self, user_id, username, amount):
        """Add XP to a user."""
        if amount <= 0:
            return False, "Amount must be positive."
        
        try:

            user_data_before = self.db.get_user(user_id)
            
            if user_data_before is None:

                self.db.create_user(user_id, username)
                user_data_before = self.db.get_user(user_id)
                if user_data_before is None:
                    return False, f"Failed to create user {username} in database."

            level_before = 0
            if isinstance(user_data_before, (list, tuple)) and len(user_data_before) > 2:
                level_before = user_data_before[2]
            elif isinstance(user_data_before, dict) and 'level' in user_data_before:
                level_before = user_data_before['level']
            else:
                logger.error(f"Invalid user_data format: {user_data_before}")
                return False, f"Invalid user data format. Please report this to the administrator."

            self.db.add_xp(user_id, username, amount)

            user_data_after = self.db.get_user(user_id)
            
            if user_data_after is None:
                return False, f"User data could not be retrieved after adding XP."

            level_after = 0
            current_xp = 0
            if isinstance(user_data_after, (list, tuple)) and len(user_data_after) > 2:
                level_after = user_data_after[2]
                if len(user_data_after) > 1:
                    current_xp = user_data_after[1]
            elif isinstance(user_data_after, dict):
                if 'level' in user_data_after:
                    level_after = user_data_after['level']
                if 'xp' in user_data_after:
                    current_xp = user_data_after['xp']
            else:
                logger.error(f"Invalid user_data format after adding XP: {user_data_after}")
                return False, f"Error processing user data after adding XP. Please report this to the administrator."

            if level_after > level_before:
                return True, f"Added {amount} XP to {username}. They leveled up from {level_before} to {level_after}!"
            else:
                required_xp = self.db.calculate_required_xp(level_after)
                return True, f"Added {amount} XP to {username}. Current XP: {current_xp}/{required_xp}"
            
        except Exception as e:
            logger.error(f"Error adding XP: {e}")
            return False, f"Error adding XP: {str(e)}"
    
    async def set_level(self, user_id, username, level, xp=None):
        """Set a user's level and optionally XP."""
        if level <= 0:
            return False, "Level must be positive."
        
        try:

            user_data = self.db.get_user(user_id)

            if not user_data:
                self.db.create_user(user_id, username)
                user_data = self.db.get_user(user_id)

            if xp is None:
                xp = self.db.calculate_required_xp(level) // 2  # Middle of the level

            self.db.cursor.execute('''
                UPDATE users SET 
                    level = ?,
                    xp = ?
                WHERE user_id = ?
            ''', (level, xp, user_id))
            self.db.conn.commit()
            
            return True, f"Set {username}'s level to {level} with {xp} XP."
            
        except Exception as e:
            logger.error(f"Error setting level: {e}")
            return False, f"Error setting level: {str(e)}"
    
    async def set_xp_drop(self, guild_id, channel_id, min_xp, max_xp, duration, time_unit):
        """Set up XP drops in a channel."""
        try:

            if guild_id not in self.xp_drop_settings:
                self.xp_drop_settings[guild_id] = XPDropSettings()
            
            settings = self.xp_drop_settings[guild_id]

            settings.channel_id = channel_id
            settings.min_xp = min_xp
            settings.max_xp = max_xp
            settings.duration = duration
            settings.time_unit = time_unit

            self.save_settings(guild_id)

            if settings.is_active:
                await self.toggle_xp_drops(guild_id, restart=True)
            
            return True, (
                f"XP drop settings updated. Drops will occur every {duration} {time_unit}(s) "
                f"in <#{channel_id}> with {min_xp}-{max_xp} XP each."
            )
        except Exception as e:
            logger.error(f"Error setting XP drop: {e}")
            return False, f"Error setting XP drop: {str(e)}"
    
    async def toggle_xp_drops(self, guild_id, restart=False):
        """Start or stop XP drops for a guild."""
        try:

            if guild_id not in self.xp_drop_settings:
                return False, "No XP drop settings found. Please set up drops first."
            
            settings = self.xp_drop_settings[guild_id]

            if not settings.channel_id:
                return False, "No channel set for XP drops. Please set up drops first."

            if settings.task is not None and not settings.task.done():
                settings.task.cancel()
                settings.task = None
                
                if not restart:
                    settings.is_active = False

                    self.save_settings(guild_id)
                    return True, "XP drops have been stopped."

            if restart or not settings.is_active:
                settings.is_active = True
                settings.task = asyncio.create_task(self._run_xp_drops(guild_id))

                self.save_settings(guild_id)
                
                interval_text = f"{settings.duration} {settings.time_unit}"
                if settings.duration != 1:
                    interval_text += "s"
                    
                return True, f"XP drops have been started. XP will drop every {interval_text}."
                
        except Exception as e:
            logger.error(f"Error toggling XP drops: {e}")
            return False, f"Error toggling XP drops: {str(e)}"
    
    async def _run_xp_drops(self, guild_id):
        """Background task to handle XP drops at intervals."""
        try:
            settings = self.xp_drop_settings[guild_id]
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                logger.error(f"Could not find guild {guild_id}")
                settings.is_active = False
                self.save_settings(guild_id)
                return
            
            logger.info(f"Starting XP drops in guild {guild.name} ({guild_id})")

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
                        logger.info(f"Waiting {seconds_until_drop:.2f} seconds until next XP drop in guild {guild_id}")

                        if seconds_until_drop > 0:
                            await asyncio.sleep(seconds_until_drop)

                    channel = guild.get_channel(settings.channel_id)
                    if not channel:
                        logger.error(f"Could not find channel {settings.channel_id}")
                        settings.is_active = False
                        self.save_settings(guild_id)
                        break

                    xp_amount = random.randint(settings.min_xp, settings.max_xp)

                    emoji = "⭐"

                    embed = discord.Embed(
                        title="⭐ XP Drop!",
                        description=f"React with {emoji} to claim {xp_amount} XP!",
                        color=discord.Color.blue()
                    )

                    drop_message = await channel.send(embed=embed)

                    await drop_message.add_reaction(emoji)

                    settings.last_drop_time = datetime.datetime.now()
                    settings.next_drop_time = settings.last_drop_time + datetime.timedelta(seconds=interval_seconds)
                    next_drop_formatted = settings.next_drop_time.strftime("%I:%M %p")
                    self.save_settings(guild_id)
                    logger.info(f"XP drop sent in guild {guild_id}, next drop at {next_drop_formatted}")

                    def check(reaction, user):
                        return user != self.bot.user and str(reaction.emoji) == emoji and reaction.message.id == drop_message.id
                    
                    try:

                        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                        user_data_before = self.db.get_user(user.id)
                        level_before = 1
                        if isinstance(user_data_before, (list, tuple)) and len(user_data_before) > 2:
                            level_before = user_data_before[2]
                        elif isinstance(user_data_before, dict) and 'level' in user_data_before:
                            level_before = user_data_before['level']
                        
                        self.db.add_xp(user.id, user.display_name, xp_amount)

                        user_data_after = self.db.get_user(user.id)
                        level_after = 1
                        if isinstance(user_data_after, (list, tuple)) and len(user_data_after) > 2:
                            level_after = user_data_after[2]
                        elif isinstance(user_data_after, dict) and 'level' in user_data_after:
                            level_after = user_data_after['level']

                        level_message = ""
                        if level_after > level_before:
                            level_message = f"and **leveled up to {level_after}**! 🎊"

                        embed.title = "⭐ XP Drop Claimed!"
                        embed.description = f"🎉 **{user.display_name}** claimed {xp_amount} XP! {level_message}"
                        embed.color = discord.Color.green()
                        embed.set_footer(text=f"Next drop at {next_drop_formatted}")

                        await drop_message.edit(embed=embed)

                        await channel.send(f"🎉 Congratulations {user.mention}! You won {xp_amount} XP! {level_message} 🎉")
                        
                        logger.info(f"XP drop claimed by {user.id} ({user.display_name}) for {xp_amount} XP")
                    
                    except asyncio.TimeoutError:

                        embed.title = "⭐ XP Drop Expired!"
                        embed.description = "No one claimed the XP in time."
                        embed.color = discord.Color.red()
                        embed.set_footer(text=f"Next drop at {next_drop_formatted}")
                        
                        await drop_message.edit(embed=embed)
                        logger.info(f"XP drop expired with no claims")

                except asyncio.CancelledError:
                    logger.info(f"XP drop task cancelled for guild {guild_id}")
                    settings.is_active = False
                    self.save_settings(guild_id)
                    break
                except Exception as e:
                    logger.error(f"Error in XP drop cycle: {e}")
                    await asyncio.sleep(60)  # Wait a bit before retrying
            
            logger.info(f"XP drop task stopped for guild {guild_id}")
            
        except asyncio.CancelledError:
            logger.info(f"XP drop master task cancelled for guild {guild_id}")
            if guild_id in self.xp_drop_settings:
                self.xp_drop_settings[guild_id].is_active = False
                self.save_settings(guild_id)
        except Exception as e:
            logger.error(f"Error in XP drop task for guild {guild_id}: {e}")
            if guild_id in self.xp_drop_settings:
                self.xp_drop_settings[guild_id].is_active = False
                self.save_settings(guild_id)

class LevelManagementView(discord.ui.View):
    """View with buttons for managing levels and XP."""
    
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(
        label="Add XP", 
        style=discord.ButtonStyle.green,
        emoji="➕"
    )
    async def add_xp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for adding XP."""
        modal = AddXPModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Set Level", 
        style=discord.ButtonStyle.blurple,
        emoji="🔝"
    )
    async def set_level_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for setting a user's level."""
        modal = SetLevelModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Set Up Drops", 
        style=discord.ButtonStyle.blurple,
        emoji="⚙️"
    )
    async def setup_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for setting up XP drops."""
        modal = SetupXPDropsModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Toggle Drops", 
        style=discord.ButtonStyle.gray,
        emoji="🔄"
    )
    async def toggle_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to toggle XP drops on or off."""

        if self.guild_id not in self.cog.xp_drop_settings or not self.cog.xp_drop_settings[self.guild_id].channel_id:
            await interaction.response.send_message(
                "⚠️ Please set up XP drops first using the 'Set Up Drops' button.",
                ephemeral=True
            )
            return

        settings = self.cog.xp_drop_settings[self.guild_id]
        if settings.is_active:
            success, message = await self.cog.toggle_xp_drops(self.guild_id)
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

            view = XPDropToggleView(self.cog, self.guild_id)
            
            channel = interaction.guild.get_channel(settings.channel_id)
            channel_name = channel.name if channel else f"Unknown (ID: {settings.channel_id})"
            
            embed = discord.Embed(
                title="Start XP Drops?",
                description=(
                    f"Would you like to start XP drops with these settings?\n\n"
                    f"**Channel:** {channel_name}\n"
                    f"**Amount:** {settings.min_xp}-{settings.max_xp} XP\n"
                    f"**Interval:** Every {settings.duration} {settings.time_unit}(s)"
                ),
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class XPDropToggleView(discord.ui.View):
    """View with buttons for toggling XP drops."""
    
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
        """Button to start XP drops."""
        success, message = await self.cog.toggle_xp_drops(self.guild_id)
        
        if success:
            embed = discord.Embed(
                title="✅ XP Drops Started",
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
            "XP drops have not been started.",
            ephemeral=True
        )
        self.stop()

class AddXPModal(discord.ui.Modal, title="Add XP"):
    """Modal for adding XP to a user."""
    
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user's ID (right-click user & Copy ID)",
        required=True
    )
    
    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="Enter the amount of XP to add",
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

            success, message = await self.cog.add_xp(user_id, member.display_name, amount)
            
            if success:
                embed = discord.Embed(
                    title="✅ XP Added",
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
            logger.error(f"Error in add XP modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class SetLevelModal(discord.ui.Modal, title="Set User Level"):
    """Modal for setting a user's level."""
    
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user's ID (right-click user & Copy ID)",
        required=True
    )
    
    level = discord.ui.TextInput(
        label="Level",
        placeholder="Enter the level to set",
        required=True
    )
    
    xp = discord.ui.TextInput(
        label="XP (Optional)",
        placeholder="Enter XP amount (leave blank for default)",
        required=False
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            user_id = int(self.user_id.value)
            level = int(self.level.value)
            xp = int(self.xp.value) if self.xp.value else None

            member = interaction.guild.get_member(user_id)
            if not member:
                await interaction.response.send_message(
                    f"❌ Could not find a member with ID {user_id}.",
                    ephemeral=True
                )
                return

            success, message = await self.cog.set_level(user_id, member.display_name, level, xp)
            
            if success:
                embed = discord.Embed(
                    title="✅ Level Set",
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
                "❌ Please enter valid numbers for User ID, Level, and XP.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in set level modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class SetupXPDropsModal(discord.ui.Modal, title="Set Up XP Drops"):
    """Modal for setting up XP drops."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID for drops",
        required=True
    )
    
    min_xp = discord.ui.TextInput(
        label="Minimum XP",
        placeholder="Enter the minimum XP per drop (default: 20)",
        required=False,
        default="20"
    )
    
    max_xp = discord.ui.TextInput(
        label="Maximum XP",
        placeholder="Enter the maximum XP per drop (default: 100)",
        required=False,
        default="100"
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

        if guild_id in cog.xp_drop_settings:
            settings = cog.xp_drop_settings[guild_id]
            if settings.channel_id:
                self.channel_id.default = str(settings.channel_id)
            if settings.min_xp:
                self.min_xp.default = str(settings.min_xp)
            if settings.max_xp:
                self.max_xp.default = str(settings.max_xp)
            if settings.duration:
                self.duration.default = str(settings.duration)
            if settings.time_unit:
                self.time_unit.default = settings.time_unit
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            channel_id = int(self.channel_id.value)
            min_xp = int(self.min_xp.value or 20)
            max_xp = int(self.max_xp.value or 100)
            duration = int(self.duration.value or 1)
            time_unit = self.time_unit.value.lower() or "hour"

            if time_unit not in ["minute", "hour", "day"]:
                await interaction.response.send_message(
                    "❌ Time unit must be 'minute', 'hour', or 'day'.",
                    ephemeral=True
                )
                return

            if min_xp <= 0 or max_xp <= 0 or duration <= 0:
                await interaction.response.send_message(
                    "❌ All numerical values must be positive.",
                    ephemeral=True
                )
                return
            
            if min_xp > max_xp:
                await interaction.response.send_message(
                    "❌ Minimum XP cannot be greater than maximum XP.",
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

            success, message = await self.cog.set_xp_drop(
                self.guild_id, channel_id, min_xp, max_xp, duration, time_unit
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ XP Drops Set Up",
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
                "❌ Please enter valid numbers for Channel ID, Min XP, Max XP, and Duration.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in set up XP drops modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    """Add the level panel cog to the bot."""
    await bot.add_cog(LevelPanelCog(bot))
    logger.info("Level panel cog loaded")
