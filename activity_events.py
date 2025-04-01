import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
import asyncio
import sqlite3
import datetime
import random
import logging
from typing import Dict, List, Optional, Tuple
from logger import setup_logger
from permissions import has_admin_permissions

logger = setup_logger('activity_events')

# Custom permission check function
async def has_permissions(interaction, required_roles=None):
    """Check if a user has the required roles.
    
    Args:
        interaction: The Discord interaction
        required_roles: List of role IDs that are allowed to use the command
        
    Returns:
        bool: True if the user has any of the required roles, False otherwise
    """
    if not required_roles:
        return True
        
    # Admin check - they can do everything
    if await has_admin_permissions(interaction.user.id, interaction.guild_id):
        return True
        
    # Check if user has any of the required roles
    member_role_ids = [str(role.id) for role in interaction.user.roles]
    return any(role_id in member_role_ids for role_id in required_roles)

class ActivityEventSettings:
    """Class to store activity event settings and data."""
    def __init__(self):
        # Activity event settings
        self.active_events = {}  # Dict mapping server_id -> event_data
        self.event_tasks = {}  # Dict mapping event_id -> asyncio Task
        
    def to_dict(self):
        """Convert settings to a dictionary for storage."""
        return {
            "active_events": self.active_events
        }
    
    @classmethod
    def from_dict(cls, data_dict):
        """Create settings from a dictionary."""
        settings = cls()
        
        if not data_dict:
            return settings
        
        settings.active_events = data_dict.get("active_events", {})
        
        return settings

class DataManager:
    """Class to manage activity event data and user statistics."""
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.user_stats_file = os.path.join(self.data_dir, "user_activity.json")
        self.event_settings_file = os.path.join(self.data_dir, "event_settings.json")
        
        self.user_stats = {}
        self.events = ActivityEventSettings()
        self.activity_settings = {}  # Server settings for activity tracking
        
        self._load_data()
        logger.info("Data manager initialized")
        
    def _load_data(self):
        """Load user stats and event settings from JSON files."""
        try:
            if os.path.exists(self.user_stats_file):
                with open(self.user_stats_file, 'r') as f:
                    self.user_stats = json.load(f)
            else:
                self._save_data()
                
            if os.path.exists(self.event_settings_file):
                with open(self.event_settings_file, 'r') as f:
                    data = json.load(f)
                    self.events = ActivityEventSettings.from_dict(data)
            else:
                with open(self.event_settings_file, 'w') as f:
                    json.dump(self.events.to_dict(), f, indent=4)
                    
            # Load activity settings
            activity_settings_file = os.path.join(self.data_dir, "activity_settings.json")
            if os.path.exists(activity_settings_file):
                with open(activity_settings_file, 'r') as f:
                    self.activity_settings = json.load(f)
            else:
                # Create default settings
                with open(activity_settings_file, 'w') as f:
                    json.dump({}, f, indent=4)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            
    def _save_data(self):
        """Save user stats and event settings to JSON files."""
        try:
            with open(self.user_stats_file, 'w') as f:
                json.dump(self.user_stats, f, indent=4)
                
            with open(self.event_settings_file, 'w') as f:
                json.dump(self.events.to_dict(), f, indent=4, default=str)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            
    def get_user_stats(self, user_id):
        """Get activity stats for a user."""
        return self.user_stats.get(user_id, {})
        
    def get_all_user_stats(self):
        """Get stats for all users."""
        return self.user_stats
        
    def update_user_stats(self, user_id, field, value=1, operation="add"):
        """Update stats for a user."""
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {}
            
        user = self.user_stats[user_id]
        
        if operation == "add":
            user[field] = user.get(field, 0) + value
        elif operation == "set":
            user[field] = value
            
        # Update last active time
        user["last_active"] = time.time()
        
        self._save_data()
        return user[field]
        
    def reset_user_stats(self, user_id):
        """Reset activity stats for a user."""
        if user_id in self.user_stats:
            default_stats = {
                "messages": 0,
                "reactions_added": 0, 
                "reactions_received": 0,
                "voice_minutes": 0,
                "invites": 0,
                "last_active": time.time()
            }
            
            # Keep user profile data but reset activity stats
            profile_data = {}
            if "join_date" in self.user_stats[user_id]:
                profile_data["join_date"] = self.user_stats[user_id]["join_date"]
                
            self.user_stats[user_id] = {**default_stats, **profile_data}
            self._save_data()
            
    def create_activity_event(self, server_id, creator_id, duration, duration_type, prize, winners_count):
        """Create a new activity event."""
        event_id = f"event_{int(time.time())}"
        
        # Calculate event end time
        seconds = self._get_seconds(duration, duration_type)
        start_time = time.time()
        end_time = start_time + seconds
        
        event_data = {
            "event_id": event_id,
            "server_id": server_id,
            "creator_id": creator_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "duration_type": duration_type,
            "prize": prize,
            "winners_count": winners_count,
            "active": True
        }
        
        # Store the event
        self.events.active_events[server_id] = event_data
        self._save_data()
        
        return event_id
        
    def end_activity_event(self, server_id):
        """End an activity event and get the winners."""
        if server_id not in self.events.active_events:
            return None, []
            
        event_data = self.events.active_events[server_id]
        event_data["active"] = False
        self._save_data()
        
        # Get top users
        winners_count = event_data.get("winners_count", 1)
        winners = self._get_top_users(winners_count)
        
        return event_data, winners
        
    def get_active_event(self, server_id):
        """Get the active event for a server."""
        if server_id in self.events.active_events:
            event_data = self.events.active_events[server_id]
            if event_data.get("active", False):
                return event_data["event_id"], event_data
        return None, None
        
    def get_activity_settings(self, server_id):
        """Get activity tracking settings for a server."""
        return self.activity_settings.get(server_id, {})
        
    def update_activity_settings(self, server_id, settings):
        """Update activity tracking settings for a server."""
        self.activity_settings[server_id] = settings
        # Save to file
        settings_file = os.path.join(self.data_dir, "activity_settings.json")
        try:
            with open(settings_file, 'w') as f:
                json.dump(self.activity_settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving activity settings: {e}")
        
    def _get_seconds(self, duration, duration_type):
        """Convert duration and time unit to seconds."""
        time_multipliers = {
            "min": 60,
            "hour": 3600,
            "day": 86400
        }
        return duration * time_multipliers.get(duration_type, 3600)
        
    def _get_top_users(self, count=3):
        """Get the top users with the most activity points."""
        from collections import defaultdict
        
        # Calculate total points for each user
        point_values = {
            "messages": 1,
            "reactions_added": 0.5,
            "reactions_received": 0.5,
            "voice_minutes": 0.1,
            "invites": 5
        }
        
        user_points = defaultdict(float)
        
        for user_id, stats in self.user_stats.items():
            total_points = 0
            for stat, value in stats.items():
                if stat in point_values:
                    total_points += value * point_values[stat]
            user_points[user_id] = total_points
            
        # Sort users by points
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        
        # Return top users
        return sorted_users[:count]
        
class ActivityEventCog(commands.Cog):
    """Cog for managing activity events."""
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        
    async def cog_load(self):
        """Called when the cog is loaded."""
        # We'll use on_ready event to resume events instead of creating a task here
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info("ActivityEventCog: Bot is ready, resuming events")
        await self.resume_events()
        
    @app_commands.command(name="activityevent", description="📊 Show the current activity event status")
    async def activity_event_command(self, interaction: discord.Interaction):
        """Show the current activity event status."""
        # This command is public, so we don't need permission checks
        server_id = str(interaction.guild.id)
        event_id, active_event = self.data_manager.get_active_event(server_id)
        
        if not active_event:
            await interaction.response.send_message(
                "⚠️ There is no active event running in this server.",
                ephemeral=True
            )
            return
            
        # Calculate remaining time
        remaining_seconds = active_event["end_time"] - time.time()
        remaining_hours = int(remaining_seconds // 3600)
        remaining_minutes = int((remaining_seconds % 3600) // 60)
        
        # Get the top users so far
        winners_count = active_event.get("winners_count", 1)
        top_users = self.data_manager._get_top_users(winners_count)
        
        # Create embed
        embed = discord.Embed(
            title="🎮 Activity Event Status",
            description="Here's the current status of the activity event:",
            color=discord.Color.blue()
        )
        
        # Add event details
        embed.add_field(
            name="⏱️ Time Remaining", 
            value=f"{remaining_hours}h {remaining_minutes}m", 
            inline=True
        )
        embed.add_field(
            name="🏆 Winners Count", 
            value=str(active_event["winners_count"]), 
            inline=True
        )
        embed.add_field(
            name="🎁 Prize", 
            value=active_event["prize"], 
            inline=True
        )
        
        # Add current top participants
        if top_users:
            top_users_text = ""
            for i, (user_id, points) in enumerate(top_users):
                user = interaction.guild.get_member(int(user_id))
                username = user.display_name if user else f"User {user_id}"
                
                if i == 0:
                    medal = "🥇"
                elif i == 1:
                    medal = "🥈"
                elif i == 2:
                    medal = "🥉"
                else:
                    medal = f"{i+1}."
                    
                top_users_text += f"{medal} **{username}** - {int(points)} <:activitycoin:1350889157676761088>\n"
            
            embed.add_field(
                name="📊 Current Leaders",
                value=top_users_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📊 Current Leaders",
                value="No participants yet!",
                inline=False
            )
            
        # Add how to earn points
        embed.add_field(
            name="How to Earn Coins",
            value="💬 Send messages\n🔄 Add reactions\n⭐ Receive reactions\n🎙️ Spend time in voice channels\n📨 Create invites",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
    async def resume_events(self):
        """Resume any active events after bot restart."""
        await self.bot.wait_until_ready()
        
        for server_id, event_data in self.data_manager.events.active_events.items():
            if event_data.get("active", False):
                event_id = event_data["event_id"]
                end_time = event_data["end_time"]
                
                now = time.time()
                if end_time > now:
                    remaining_seconds = end_time - now
                    logger.info(f"Resuming activity event {event_id} with {remaining_seconds} seconds remaining")
                    
                    task = self.bot.loop.create_task(
                        self._run_event(event_id, server_id, remaining_seconds)
                    )
                    self.data_manager.events.event_tasks[event_id] = task
                else:
                    # Event already ended, clean up
                    logger.info(f"Cleaning up expired event {event_id}")
                    await self._end_event(server_id)
                    
    async def _run_event(self, event_id, server_id, seconds):
        """Run an activity event for the specified duration."""
        try:
            await asyncio.sleep(seconds)
            await self._end_event(server_id)
        except asyncio.CancelledError:
            logger.info(f"Event {event_id} was cancelled")
        except Exception as e:
            logger.error(f"Error running event {event_id}: {e}")
            
    async def _end_event(self, server_id):
        """End an activity event and announce the winners."""
        try:
            event_data, winners = self.data_manager.end_activity_event(server_id)
            
            if not event_data:
                return
                
            # Get the server
            guild = self.bot.get_guild(int(server_id))
            if not guild:
                return
                
            # Find an appropriate channel to announce the results
            announcement_channel = None
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    if "general" in channel.name.lower() or "activity" in channel.name.lower():
                        announcement_channel = channel
                        break
                        
            if not announcement_channel:
                # Use the first channel with send permissions
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        announcement_channel = channel
                        break
                        
            if not announcement_channel:
                logger.error(f"Could not find a channel to announce event results in server {server_id}")
                return
                
            # Create an announcement embed
            embed = discord.Embed(
                title="🏆 Activity Event Ended!",
                description=f"The activity event has ended! Here are the winners:",
                color=discord.Color.gold()
            )
            
            # Add winners to the embed
            if winners:
                winners_text = ""
                for i, (user_id, points) in enumerate(winners):
                    user = guild.get_member(int(user_id))
                    username = user.display_name if user else f"User {user_id}"
                    
                    if i == 0:
                        medal = "🥇"
                    elif i == 1:
                        medal = "🥈"
                    elif i == 2:
                        medal = "🥉"
                    else:
                        medal = f"{i+1}."
                        
                    winners_text += f"{medal} **{username}** - {int(points)} <:activitycoin:1350889157676761088>\n"
                
                embed.add_field(
                    name="Winners",
                    value=winners_text,
                    inline=False
                )
                
                embed.add_field(
                    name="Prize",
                    value=event_data.get("prize", "25 DLS"),
                    inline=False
                )
            else:
                embed.add_field(
                    name="No Winners",
                    value="No one participated in the event!",
                    inline=False
                )
                
            embed.set_footer(text=f"Event ID: {event_data['event_id']}")
            
            # Send the announcement
            await announcement_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error ending event: {e}")
            
    @app_commands.command(name="activity_settings", description="🔄 Manage activity event settings")
    async def manage_events(self, interaction: discord.Interaction):
        """Manage activity event settings with toggle buttons."""
        # Check permissions first
        if not await has_permissions(interaction, required_roles=['1338482857974169683', '1339687502121795584']):
            embed = discord.Embed(
                title="⚠️ Permission Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        server_id = str(interaction.guild.id)
        event_id, active_event = self.data_manager.get_active_event(server_id)
        
        # Create the main embed
        embed = discord.Embed(
            title="🎮 Activity Events Settings",
            description="Toggle specific activity tracking methods or view the current event status.",
            color=discord.Color.blue()
        )
        
        # If there's an active event, show its details
        if active_event:
            # Calculate remaining time
            remaining_seconds = active_event["end_time"] - time.time()
            remaining_hours = int(remaining_seconds // 3600)
            remaining_minutes = int((remaining_seconds % 3600) // 60)
            
            embed.add_field(
                name="🏆 Current Event",
                value=f"⏱️ Time Remaining: {remaining_hours}h {remaining_minutes}m\n"
                      f"🎁 Prize: {active_event['prize']}\n"
                      f"👥 Winners: {active_event['winners_count']}",
                inline=False
            )
        else:
            embed.add_field(
                name="🏆 Current Event",
                value="No active event currently running",
                inline=False
            )
            
        # Load current settings
        settings = self.data_manager.get_activity_settings(server_id) or {}
        
        # Create the view with toggle buttons
        view = EventSettingsView(self.data_manager, server_id, settings)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    """Add the activity events cog to the bot."""
    await bot.add_cog(ActivityEventCog(bot))

class EventSettingsView(discord.ui.View):
    """View with toggle buttons for activity event settings."""
    
    def __init__(self, data_manager, server_id, settings):
        super().__init__(timeout=180)
        self.data_manager = data_manager
        self.server_id = server_id
        self.settings = settings
        
        # Add toggle buttons for each activity type
        self.add_toggle_button("messages", "💬 Messages", settings.get("track_messages", True))
        self.add_toggle_button("reactions", "🔄 Reactions", settings.get("track_reactions", True)) 
        self.add_toggle_button("voice", "🎙️ Voice Time", settings.get("track_voice", True))
        self.add_toggle_button("invites", "📨 Invites", settings.get("track_invites", True))
    
    def add_toggle_button(self, setting_id, label, is_enabled):
        """Add a toggle button for a specific setting."""
        button = discord.ui.Button(
            label=label,
            custom_id=f"toggle_{setting_id}",
            style=discord.ButtonStyle.success if is_enabled else discord.ButtonStyle.danger,
            emoji="✅" if is_enabled else "❌"
        )
        
        async def toggle_callback(interaction: discord.Interaction):
            # Toggle the setting
            setting_key = f"track_{setting_id}"
            current_value = self.settings.get(setting_key, True)
            self.settings[setting_key] = not current_value
            
            # Update the button style
            button.style = discord.ButtonStyle.success if self.settings[setting_key] else discord.ButtonStyle.danger
            button.emoji = "✅" if self.settings[setting_key] else "❌"
            
            # Save settings
            self.data_manager.update_activity_settings(self.server_id, self.settings)
            
            # Update the view
            await interaction.response.edit_message(view=self)
            
        button.callback = toggle_callback
        self.add_item(button)