import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import asyncio
import datetime
import sqlite3
import time
import logging
from typing import Dict, List, Optional, Tuple, Union
from database import Database
from logger import setup_logger

logger = setup_logger('event_system')

class EventSettings:
    """Class to store event settings and data."""
    def __init__(self):

        self.x2_xp_active = False
        self.x2_xp_start_time = None
        self.x2_xp_end_time = None
        self.x2_xp_duration = 0
        self.x2_xp_time_unit = "hour"

        self.xp_race_active = False
        self.xp_race_start_time = None
        self.xp_race_end_time = None
        self.xp_race_duration = 0
        self.xp_race_time_unit = "hour"
        self.xp_race_prize = "25 DLS"
        self.xp_race_participants = {}  # Dict mapping user_id -> xp earned during race

        self.holiday_boost_active = False
        self.holiday_boost_start_time = None
        self.holiday_boost_end_time = None

        self.x2_xp_task = None
        self.xp_race_task = None
        self.holiday_boost_task = None
    
    def to_dict(self):
        """Convert settings to a dictionary for storage."""
        return {
            "x2_xp_active": self.x2_xp_active,
            "x2_xp_start_time": self.x2_xp_start_time,
            "x2_xp_end_time": self.x2_xp_end_time,
            "x2_xp_duration": self.x2_xp_duration,
            "x2_xp_time_unit": self.x2_xp_time_unit,
            
            "xp_race_active": self.xp_race_active,
            "xp_race_start_time": self.xp_race_start_time,
            "xp_race_end_time": self.xp_race_end_time,
            "xp_race_duration": self.xp_race_duration,
            "xp_race_time_unit": self.xp_race_time_unit,
            "xp_race_prize": self.xp_race_prize,
            "xp_race_participants": self.xp_race_participants,
            
            "holiday_boost_active": self.holiday_boost_active,
            "holiday_boost_start_time": self.holiday_boost_start_time,
            "holiday_boost_end_time": self.holiday_boost_end_time,
        }
    
    @classmethod
    def from_dict(cls, data_dict):
        """Create settings from a dictionary."""
        settings = cls()
        
        if not data_dict:
            return settings

        settings.x2_xp_active = data_dict.get("x2_xp_active", False)
        settings.x2_xp_start_time = data_dict.get("x2_xp_start_time")
        settings.x2_xp_end_time = data_dict.get("x2_xp_end_time")
        settings.x2_xp_duration = data_dict.get("x2_xp_duration", 0)
        settings.x2_xp_time_unit = data_dict.get("x2_xp_time_unit", "hour")

        settings.xp_race_active = data_dict.get("xp_race_active", False)
        settings.xp_race_start_time = data_dict.get("xp_race_start_time")
        settings.xp_race_end_time = data_dict.get("xp_race_end_time")
        settings.xp_race_duration = data_dict.get("xp_race_duration", 0)
        settings.xp_race_time_unit = data_dict.get("xp_race_time_unit", "hour")
        settings.xp_race_prize = data_dict.get("xp_race_prize", "25 DLS")
        settings.xp_race_participants = data_dict.get("xp_race_participants", {})

        settings.holiday_boost_active = data_dict.get("holiday_boost_active", False)
        settings.holiday_boost_start_time = data_dict.get("holiday_boost_start_time")
        settings.holiday_boost_end_time = data_dict.get("holiday_boost_end_time")
        
        return settings
    
    def get_x2_xp_seconds(self):
        """Convert duration and time unit to seconds for X2 XP event."""
        time_multipliers = {
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }
        return self.x2_xp_duration * time_multipliers.get(self.x2_xp_time_unit, 3600)
    
    def get_xp_race_seconds(self):
        """Convert duration and time unit to seconds for XP Race."""
        time_multipliers = {
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }
        return self.xp_race_duration * time_multipliers.get(self.xp_race_time_unit, 3600)

class EventSystemCog(commands.Cog):
    """Cog for managing special server events like XP boosts and races."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.settings_file = "data/event_settings.json"
        self.settings = EventSettings()

        os.makedirs("data", exist_ok=True)

        self.load_settings()
        logger.info("Event system initialized")
    
    async def cog_load(self):
        """Called when the cog is loaded."""

        pass
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready. Used to resume events."""
        await self.resume_events()
    
    def load_settings(self):
        """Load event settings from the JSON file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    self.settings = EventSettings.from_dict(data)
                    logger.info("Loaded event settings from file")
            else:

                self.save_settings()
                logger.info("Created new event settings file")
        except Exception as e:
            logger.error(f"Error loading event settings: {e}")
            self.settings = EventSettings()
    
    def save_settings(self):
        """Save event settings to the JSON file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings.to_dict(), f, indent=4, default=str)
            logger.info("Saved event settings to file")
        except Exception as e:
            logger.error(f"Error saving event settings: {e}")
    
    async def resume_events(self):
        """Resume any active events after bot restart."""

        if self.settings.x2_xp_active and self.settings.x2_xp_end_time:

            if isinstance(self.settings.x2_xp_end_time, str):
                end_time = datetime.datetime.fromisoformat(self.settings.x2_xp_end_time)
            else:
                end_time = self.settings.x2_xp_end_time
                
            now = datetime.datetime.now()
            if end_time > now:

                remaining_seconds = (end_time - now).total_seconds()
                logger.info(f"Resuming X2 XP event with {remaining_seconds} seconds remaining")

                self.settings.x2_xp_task = asyncio.create_task(self._run_x2_xp_event(remaining_seconds))

        if self.settings.xp_race_active and self.settings.xp_race_end_time:

            if isinstance(self.settings.xp_race_end_time, str):
                end_time = datetime.datetime.fromisoformat(self.settings.xp_race_end_time)
            else:
                end_time = self.settings.xp_race_end_time
                
            now = datetime.datetime.now()
            if end_time > now:

                remaining_seconds = (end_time - now).total_seconds()
                logger.info(f"Resuming XP Race with {remaining_seconds} seconds remaining")

                self.settings.xp_race_task = asyncio.create_task(self._run_xp_race_event(remaining_seconds))

        if self.settings.holiday_boost_active and self.settings.holiday_boost_end_time:

            if isinstance(self.settings.holiday_boost_end_time, str):
                end_time = datetime.datetime.fromisoformat(self.settings.holiday_boost_end_time)
            else:
                end_time = self.settings.holiday_boost_end_time
                
            now = datetime.datetime.now()
            if end_time > now:

                remaining_seconds = (end_time - now).total_seconds()
                logger.info(f"Resuming Holiday Boost with {remaining_seconds} seconds remaining")

                self.settings.holiday_boost_task = asyncio.create_task(self._run_holiday_boost_event(remaining_seconds))
    
    @app_commands.command(
        name="server_events",
        description="🎉 Open a panel to manage server-wide events and boosts"
    )
    async def events(self, interaction: discord.Interaction):
        """Open a panel with buttons to manage server events."""

        allowed_user_ids = ["1308527904497340467", "479711321399623681"]
        if str(interaction.user.id) in allowed_user_ids:

            status_text = "**Current Event Status:**\n"

            if self.settings.x2_xp_active:
                end_time = self.settings.x2_xp_end_time
                if isinstance(end_time, str):
                    end_time = datetime.datetime.fromisoformat(end_time)
                time_left = end_time - datetime.datetime.now()
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                status_text += f"✅ **X2 XP**: Active - {hours}h {minutes}m remaining\n"
            else:
                status_text += "❌ **X2 XP**: Inactive\n"

            if self.settings.xp_race_active:
                end_time = self.settings.xp_race_end_time
                if isinstance(end_time, str):
                    end_time = datetime.datetime.fromisoformat(end_time)
                time_left = end_time - datetime.datetime.now()
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                status_text += f"✅ **XP Race Challenge**: Active - {hours}h {minutes}m remaining\n"
                status_text += f"    Prize: {self.settings.xp_race_prize}\n"
                status_text += f"    Participants: {len(self.settings.xp_race_participants)}\n"
            else:
                status_text += "❌ **XP Race Challenge**: Inactive\n"

            if self.settings.holiday_boost_active:
                end_time = self.settings.holiday_boost_end_time
                if isinstance(end_time, str):
                    end_time = datetime.datetime.fromisoformat(end_time)
                time_left = end_time - datetime.datetime.now()
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                status_text += f"✅ **Holiday XP Boost**: Active - {hours}h {minutes}m remaining\n"
            else:
                status_text += "❌ **Holiday XP Boost**: Inactive\n"

            embed = discord.Embed(
                title="🎉 Server Events Manager",
                description=status_text,
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="Event Types",
                value=(
                    "**X2 XP**: Doubles all XP gain from messages\n"
                    "**XP Race Challenge**: Users compete to gain the most XP\n"
                    "**Holiday XP Boost**: 1.5x XP (no coin boost) for 1 hour"
                ),
                inline=False
            )

            view = EventManagementView(self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ You don't have permission to manage events.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="xpleaderboard",
        description="📊 View the current XP Race Challenge leaderboard"
    )
    async def xpleaderboard(self, interaction: discord.Interaction):
        """Display the current XP Race Challenge leaderboard."""

        await interaction.response.defer(ephemeral=False)  # Make this visible to everyone
        
        if not self.settings.xp_race_active:
            embed = discord.Embed(
                title="❌ XP Race Challenge Inactive",
                description="There is no active XP Race Challenge at the moment. Check back later!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        participants = self.settings.xp_race_participants
        
        if not participants:
            embed = discord.Embed(
                title="📊 XP Race Challenge Leaderboard",
                description="No participants yet! Start sending messages to earn XP.",
                color=discord.Color.blue()
            )

            end_time = self.settings.xp_race_end_time
            if isinstance(end_time, str):
                end_time = datetime.datetime.fromisoformat(end_time)
            time_left = end_time - datetime.datetime.now()
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            embed.add_field(
                name="Event Info",
                value=f"Prize: {self.settings.xp_race_prize}\nTime Remaining: {hours}h {minutes}m",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            return

        sorted_participants = sorted(participants.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="📊 XP Race Challenge Leaderboard",
            description=f"Top participants in the current XP Race Challenge",
            color=discord.Color.blue()
        )

        end_time = self.settings.xp_race_end_time
        if isinstance(end_time, str):
            end_time = datetime.datetime.fromisoformat(end_time)
        time_left = end_time - datetime.datetime.now()
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed.add_field(
            name="Event Info",
            value=f"Prize: {self.settings.xp_race_prize}\nTime Remaining: {hours}h {minutes}m",
            inline=False
        )

        leaderboard_text = ""
        for index, (user_id, xp) in enumerate(sorted_participants[:10], 1):

            user = self.bot.get_user(int(user_id))
            username = user.name if user else f"User {user_id}"

            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"{index}."
            
            leaderboard_text += f"{medal} **{username}** - {xp} XP\n"
        
        embed.add_field(
            name="Current Standings",
            value=leaderboard_text if leaderboard_text else "No participants yet!",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    
    async def start_x2_xp_event(self, duration, time_unit):
        """Start a double XP event."""

        if self.settings.x2_xp_task and not self.settings.x2_xp_task.done():
            self.settings.x2_xp_task.cancel()

        self.settings.x2_xp_active = True
        self.settings.x2_xp_duration = duration
        self.settings.x2_xp_time_unit = time_unit
        self.settings.x2_xp_start_time = datetime.datetime.now().isoformat()

        seconds = self.settings.get_x2_xp_seconds()
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        self.settings.x2_xp_end_time = end_time.isoformat()

        self.save_settings()

        self.settings.x2_xp_task = asyncio.create_task(self._run_x2_xp_event(seconds))
        
        return True, f"✅ Double XP event started for {duration} {time_unit}(s)!"
    
    async def end_x2_xp_event(self):
        """End the double XP event early."""
        if not self.settings.x2_xp_active:
            return False, "❌ No active Double XP event to end."

        if self.settings.x2_xp_task and not self.settings.x2_xp_task.done():
            self.settings.x2_xp_task.cancel()

        self.settings.x2_xp_active = False
        self.settings.x2_xp_start_time = None
        self.settings.x2_xp_end_time = None

        self.save_settings()

        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        await channel.send("🔔 **The Double XP event has ended!** XP gain has returned to normal.")
                        break  # Only send to the first available channel
                    except Exception as e:
                        logger.error(f"Error announcing end of X2 XP event: {e}")
        
        return True, "✅ Double XP event ended successfully."
    
    async def _run_x2_xp_event(self, seconds):
        """Run the double XP event for the specified duration."""
        try:

            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        try:
                            duration_text = f"{self.settings.x2_xp_duration} {self.settings.x2_xp_time_unit}"
                            if self.settings.x2_xp_duration > 1:
                                duration_text += "s"
                                
                            await channel.send(
                                f"🔔 **Double XP Event Started!** All members will receive 2x XP from messages for the next {duration_text}!"
                            )
                            break  # Only send to the first available channel
                        except Exception as e:
                            logger.error(f"Error announcing X2 XP event: {e}")

            await asyncio.sleep(seconds)

            if self.settings.x2_xp_active:
                await self.end_x2_xp_event()
        
        except asyncio.CancelledError:
            logger.info("X2 XP event task was cancelled")
        except Exception as e:
            logger.error(f"Error in X2 XP event task: {e}")

            self.settings.x2_xp_active = False
            self.save_settings()
    
    async def start_xp_race_event(self, duration, time_unit, prize):
        """Start an XP race challenge event."""

        if self.settings.xp_race_task and not self.settings.xp_race_task.done():
            self.settings.xp_race_task.cancel()

        self.settings.xp_race_active = True
        self.settings.xp_race_duration = duration
        self.settings.xp_race_time_unit = time_unit
        self.settings.xp_race_prize = prize
        self.settings.xp_race_start_time = datetime.datetime.now().isoformat()

        self.settings.xp_race_participants = {}

        seconds = self.settings.get_xp_race_seconds()
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        self.settings.xp_race_end_time = end_time.isoformat()

        self.save_settings()

        self.settings.xp_race_task = asyncio.create_task(self._run_xp_race_event(seconds))
        
        return True, f"✅ XP Race Challenge started for {duration} {time_unit}(s) with prize: {prize}!"
    
    async def end_xp_race_event(self):
        """End the XP race challenge early."""
        if not self.settings.xp_race_active:
            return False, "❌ No active XP Race Challenge to end."

        if self.settings.xp_race_task and not self.settings.xp_race_task.done():
            self.settings.xp_race_task.cancel()

        winner_id = None
        winner_xp = 0
        
        participants = self.settings.xp_race_participants
        if participants:

            winner_id, winner_xp = max(participants.items(), key=lambda x: x[1])

        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        if winner_id:
                            user = self.bot.get_user(int(winner_id))
                            winner_name = user.mention if user else f"<@{winner_id}>"
                            await channel.send(
                                f"🏆 **XP Race Challenge has ended!**\n"
                                f"Winner: {winner_name} with {winner_xp} XP!\n"
                                f"Prize: {self.settings.xp_race_prize}"
                            )
                        else:
                            await channel.send(
                                "🏆 **XP Race Challenge has ended!**\n"
                                "There were no participants, so no winner was determined."
                            )
                        break  # Only send to the first available channel
                    except Exception as e:
                        logger.error(f"Error announcing end of XP Race: {e}")

        self.settings.xp_race_active = False
        self.settings.xp_race_start_time = None
        self.settings.xp_race_end_time = None
        self.settings.xp_race_participants = {}

        self.save_settings()
        
        return True, "✅ XP Race Challenge ended successfully."
    
    async def _run_xp_race_event(self, seconds):
        """Run the XP race challenge for the specified duration."""
        try:

            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        try:
                            duration_text = f"{self.settings.xp_race_duration} {self.settings.xp_race_time_unit}"
                            if self.settings.xp_race_duration > 1:
                                duration_text += "s"
                                
                            await channel.send(
                                f"🏁 **XP Race Challenge Started!**\n"
                                f"Compete to earn the most XP in the next {duration_text}!\n"
                                f"Prize: {self.settings.xp_race_prize}\n"
                                f"Use `/xpleaderboard` to check the standings!\n"
                                f"XP is earned by sending messages only (not voice activity)."
                            )
                            break  # Only send to the first available channel
                        except Exception as e:
                            logger.error(f"Error announcing XP Race event: {e}")

            await asyncio.sleep(seconds)

            if self.settings.xp_race_active:
                await self.end_xp_race_event()
        
        except asyncio.CancelledError:
            logger.info("XP Race event task was cancelled")
        except Exception as e:
            logger.error(f"Error in XP Race event task: {e}")

            self.settings.xp_race_active = False
            self.save_settings()
    
    async def start_holiday_boost_event(self):
        """Start a holiday boost event (1.5x XP only for 1 hour)."""

        if self.settings.holiday_boost_task and not self.settings.holiday_boost_task.done():
            self.settings.holiday_boost_task.cancel()

        self.settings.holiday_boost_active = True
        self.settings.holiday_boost_start_time = datetime.datetime.now().isoformat()

        end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
        self.settings.holiday_boost_end_time = end_time.isoformat()

        self.save_settings()

        self.settings.holiday_boost_task = asyncio.create_task(self._run_holiday_boost_event(3600))  # 1 hour = 3600 seconds
        
        return True, "✅ Holiday XP Boost (1.5x XP only) started for 1 hour!"
    
    async def end_holiday_boost_event(self):
        """End the holiday boost event early."""
        if not self.settings.holiday_boost_active:
            return False, "❌ No active Holiday XP Boost to end."

        if self.settings.holiday_boost_task and not self.settings.holiday_boost_task.done():
            self.settings.holiday_boost_task.cancel()

        self.settings.holiday_boost_active = False
        self.settings.holiday_boost_start_time = None
        self.settings.holiday_boost_end_time = None

        self.save_settings()

        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        await channel.send("🔔 **The Holiday XP Boost has ended!** XP gain has returned to normal.")
                        break  # Only send to the first available channel
                    except Exception as e:
                        logger.error(f"Error announcing end of Holiday Boost: {e}")
        
        return True, "✅ Holiday XP Boost ended successfully."
    
    async def _run_holiday_boost_event(self, seconds):
        """Run the holiday boost event for the specified duration."""
        try:

            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        try:
                            await channel.send(
                                "🎉 **Holiday XP Boost Started!** All members will receive 1.5x XP (no coin boost) from messages for the next hour!"
                            )
                            break  # Only send to the first available channel
                        except Exception as e:
                            logger.error(f"Error announcing Holiday Boost event: {e}")

            await asyncio.sleep(seconds)

            if self.settings.holiday_boost_active:
                await self.end_holiday_boost_event()
        
        except asyncio.CancelledError:
            logger.info("Holiday Boost event task was cancelled")
        except Exception as e:
            logger.error(f"Error in Holiday Boost event task: {e}")

            self.settings.holiday_boost_active = False
            self.save_settings()
    
    async def add_xp_race_points(self, user_id, username, xp_amount):
        """Add XP points to a user in the XP Race Challenge."""
        if not self.settings.xp_race_active:
            return False
        
        user_id = str(user_id)

        if user_id not in self.settings.xp_race_participants:
            self.settings.xp_race_participants[user_id] = 0

        self.settings.xp_race_participants[user_id] += xp_amount

        self.save_settings()
        
        return True
    
    async def get_xp_multiplier(self):
        """Get the current XP multiplier based on active events."""
        multiplier = 1.0

        if self.settings.x2_xp_active:
            multiplier *= 2.0

        if self.settings.holiday_boost_active:
            multiplier *= 1.5
        
        return multiplier
    
    async def get_coin_multiplier(self):
        """Get the current coin multiplier based on active events."""
        multiplier = 1.0

        return multiplier
    
    async def on_message(self, message):
        """Listen for messages to track XP race points."""

        if message.author.bot:
            return

        if self.settings.xp_race_active:

            await self.add_xp_race_points(message.author.id, message.author.name, 1)

class EventManagementView(discord.ui.View):
    """View with buttons for managing events."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
    
    @discord.ui.button(
        label="X2 XP",
        style=discord.ButtonStyle.primary,
        emoji="✨",
        row=0
    )
    async def x2_xp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to start or end X2 XP event."""
        if self.cog.settings.x2_xp_active:

            view = EndEventConfirmView(self.cog, "x2_xp")
            await interaction.response.send_message(
                "Do you want to end the X2 XP event early?",
                view=view,
                ephemeral=True
            )
        else:

            modal = X2XPEventModal(self.cog)
            await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="XP Race Challenge",
        style=discord.ButtonStyle.success,
        emoji="🏁",
        row=0
    )
    async def xp_race_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to start or end XP Race Challenge."""
        if self.cog.settings.xp_race_active:

            view = EndEventConfirmView(self.cog, "xp_race")
            await interaction.response.send_message(
                "Do you want to end the XP Race Challenge early?",
                view=view,
                ephemeral=True
            )
        else:

            modal = XPRaceEventModal(self.cog)
            await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Holiday XP Boost",
        style=discord.ButtonStyle.danger,
        emoji="🎉",
        row=0
    )
    async def holiday_boost_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to start or end Holiday XP Boost."""
        if self.cog.settings.holiday_boost_active:

            view = EndEventConfirmView(self.cog, "holiday_boost")
            await interaction.response.send_message(
                "Do you want to end the Holiday XP Boost early?",
                view=view,
                ephemeral=True
            )
        else:

            success, message = await self.cog.start_holiday_boost_event()
            
            if success:
                await interaction.response.send_message(
                    f"{message} The event will automatically end in 1 hour.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Error starting Holiday XP Boost: {message}",
                    ephemeral=True
                )

class X2XPEventModal(discord.ui.Modal, title="X2 XP Event Settings"):
    """Modal for setting up X2 XP event."""
    
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="How long the event will run (default: 1)",
        required=False,
        default="1"
    )
    
    time_unit = discord.ui.TextInput(
        label="Time Unit",
        placeholder="minute, hour, or day (default: hour)",
        required=False,
        default="hour"
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            duration_str = self.duration.value.strip()
            try:
                duration = int(duration_str) if duration_str else 1
            except ValueError:
                duration = 1

            time_unit = self.time_unit.value.strip().lower()
            if time_unit not in ["minute", "hour", "day"]:
                time_unit = "hour"

            success, message = await self.cog.start_x2_xp_event(duration, time_unit)
            
            if success:
                await interaction.response.send_message(
                    f"{message} The event will automatically end after the specified duration.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Error starting X2 XP event: {message}",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"Error in X2XPEventModal submission: {e}")
            await interaction.response.send_message(
                f"❌ Error setting up X2 XP event: {e}",
                ephemeral=True
            )

class XPRaceEventModal(discord.ui.Modal, title="XP Race Challenge Settings"):
    """Modal for setting up XP Race Challenge."""
    
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="How long the event will run (default: 1)",
        required=False,
        default="1"
    )
    
    time_unit = discord.ui.TextInput(
        label="Time Unit",
        placeholder="minute, hour, or day (default: hour)",
        required=False,
        default="hour"
    )
    
    prize = discord.ui.TextInput(
        label="Prize",
        placeholder="What the winner will receive (default: 25 DLS)",
        required=False,
        default="25 DLS"
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            duration_str = self.duration.value.strip()
            try:
                duration = int(duration_str) if duration_str else 1
            except ValueError:
                duration = 1

            time_unit = self.time_unit.value.strip().lower()
            if time_unit not in ["minute", "hour", "day"]:
                time_unit = "hour"

            prize = self.prize.value.strip()
            if not prize:
                prize = "25 DLS"

            success, message = await self.cog.start_xp_race_event(duration, time_unit, prize)
            
            if success:
                await interaction.response.send_message(
                    f"{message} The event will automatically end after the specified duration.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Error starting XP Race Challenge: {message}",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"Error in XPRaceEventModal submission: {e}")
            await interaction.response.send_message(
                f"❌ Error setting up XP Race Challenge: {e}",
                ephemeral=True
            )

class EndEventConfirmView(discord.ui.View):
    """View with buttons for confirming event end."""
    
    def __init__(self, cog, event_type):
        super().__init__(timeout=60)  # 1 minute timeout
        self.cog = cog
        self.event_type = event_type  # "x2_xp", "xp_race", or "holiday_boost"
    
    @discord.ui.button(
        label="Confirm End",
        style=discord.ButtonStyle.danger,
        emoji="✅"
    )
    async def confirm_end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to confirm ending the event."""
        if self.event_type == "x2_xp":
            success, message = await self.cog.end_x2_xp_event()
        elif self.event_type == "xp_race":
            success, message = await self.cog.end_xp_race_event()
        elif self.event_type == "holiday_boost":
            success, message = await self.cog.end_holiday_boost_event()
        else:
            success = False
            message = "Unknown event type."
        
        if success:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Error ending event: {message}",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="❌"
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to cancel ending the event."""
        await interaction.response.send_message(
            "Event end cancelled. The event will continue.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(EventSystemCog(bot))
    logger.info("Event system cog loaded")