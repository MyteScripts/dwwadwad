import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import datetime
import logging
import sqlite3
import json
from logger import setup_logger
from activity_events import has_permissions

logger = setup_logger('chat_activity', 'bot.log')

def get_rainbow_color():
    """Generate a random rainbow color."""

    rainbow_colors = [
        0xFF0000,  # Red
        0xFF7F00,  # Orange
        0xFFFF00,  # Yellow
        0x00FF00,  # Green
        0x0000FF,  # Blue
        0x4B0082,  # Indigo
        0x9400D3   # Violet
    ]

    rainbow_color = random.choice(rainbow_colors)

    variation = random.randint(-0x111111, 0x111111)
    rainbow_color = max(0, min(0xFFFFFF, rainbow_color + variation))
    
    return rainbow_color

class ActivityEvent:
    """Class to store activity event settings and data."""
    def __init__(self):
        self.channel_id = None    # Channel to monitor activity in
        self.prize = "25DLS"      # Default prize
        self.duration = 2         # Duration value
        self.time_unit = "hour"   # Time unit (minute, hour, day)
        self.is_active = False    # Whether activity tracking is active
        self.start_time = None    # When the activity started
        self.end_time = None      # When the activity will end
        self.participants = {}    # {user_id: coins_count}
        self.task = None          # The scheduled task

    @property
    def channel_id(self) -> int:
        return self._channel_id
        
    @channel_id.setter
    def channel_id(self, value):
        self._channel_id = value
        
    @property
    def prize(self) -> str:
        return self._prize
        
    @prize.setter
    def prize(self, value):
        self._prize = value
        
    @property
    def duration(self) -> int:
        return self._duration
        
    @duration.setter
    def duration(self, value):
        self._duration = value
        
    @property
    def time_unit(self) -> str:
        return self._time_unit
        
    @time_unit.setter
    def time_unit(self, value):
        self._time_unit = value
        
    @property
    def is_active(self) -> bool:
        return self._is_active
        
    @is_active.setter
    def is_active(self, value):
        self._is_active = value
        
    @property
    def start_time(self):
        return self._start_time
        
    @start_time.setter
    def start_time(self, value):
        self._start_time = value
        
    @property
    def end_time(self):
        return self._end_time
        
    @end_time.setter
    def end_time(self, value):
        self._end_time = value
        
    @property
    def participants(self):
        return self._participants
        
    @participants.setter
    def participants(self, value):
        self._participants = value
        
    @property
    def task(self):
        return self._task
        
    @task.setter
    def task(self, value):
        self._task = value
        
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
            
    def get_reminder_times(self):
        """Get reminder times for the activity (in seconds before end).
        Returns times to send reminders before the event ends.
        """
        total_seconds = self.get_seconds()
        reminders = []

        if self.time_unit == "minute":

            if self.duration >= 2:

                reminders.append(60)

                if self.duration >= 5:
                    reminders.append(total_seconds // 2)

        elif self.time_unit == "hour":

            reminders.append(5 * 60)

            if self.duration >= 2:
                reminders.append(30 * 60)

            if self.duration >= 3:
                reminders.append(60 * 60)

        elif self.time_unit == "day":

            reminders.append(60 * 60)

            reminders.append(6 * 60 * 60)

            if self.duration >= 2:
                reminders.append(24 * 60 * 60)

        reminders = [r for r in reminders if r < total_seconds]

        reminders.sort(reverse=True)
        
        return reminders

class ChatActivityCog(commands.Cog):
    """Cog for managing chat activity events."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_name = 'data/leveling.db'
        self.activity_event = None  # Current activity event
        self.setup_database()
        logger.info("Chat activity cog initialized")
        
    async def cog_load(self):
        """Called when the cog is loaded. Used to initialize async tasks."""

        event = self.load_active_event()
        if event and event.is_active:
            self.activity_event = event
            logger.info("Loaded active chat activity event, will resume after bot is ready")

        self.bot.add_listener(self.on_ready_resume_activity, 'on_ready')
        
    async def on_ready_resume_activity(self):
        """Resume activity event when the bot is ready."""
        logger.info("Bot is ready - resuming any active chat activity events")
        await self.load_and_resume_activity()
        
    async def load_and_resume_activity(self):
        """Load active event from database and resume it if applicable."""

        event = self.load_active_event()
        if not event or not event.is_active:
            logger.info("No active chat activity event to resume")
            return

        now = datetime.datetime.now()
        if now >= event.end_time:

            event.is_active = False
            self.activity_event = event
            self.save_event()
            logger.info("Found expired chat activity event, marked as inactive")
            return

        self.activity_event = event

        remaining_seconds = (event.end_time - now).total_seconds()
        if remaining_seconds > 0:

            self.activity_event.task = asyncio.create_task(self._run_activity_event(remaining_seconds, is_resuming=True))
            logger.info(f"Silently resumed chat activity event with {remaining_seconds:.1f} seconds remaining")
    
    def setup_database(self):
        """Set up the database tables needed for activity tracking."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                prize TEXT,
                duration INTEGER,
                time_unit TEXT,
                start_time TEXT,
                end_time TEXT,
                is_active INTEGER
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_participants (
                event_id INTEGER,
                user_id INTEGER,
                username TEXT,
                coins INTEGER,
                PRIMARY KEY (event_id, user_id),
                FOREIGN KEY (event_id) REFERENCES activity_events(id)
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Activity database tables created")
        except Exception as e:
            logger.error(f"Error setting up activity database: {e}")
    
    def save_event(self):
        """Save current activity event to database."""
        if not self.activity_event:
            return None
            
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            start_time_str = self.activity_event.start_time.isoformat() if self.activity_event.start_time else None
            end_time_str = self.activity_event.end_time.isoformat() if self.activity_event.end_time else None

            cursor.execute("SELECT id FROM activity_events WHERE is_active = 1")
            result = cursor.fetchone()
            
            if result:

                event_id = result[0]
                cursor.execute('''
                UPDATE activity_events 
                SET channel_id = ?, prize = ?, duration = ?, time_unit = ?, 
                    start_time = ?, end_time = ?, is_active = ?
                WHERE id = ?
                ''', (
                    self.activity_event.channel_id,
                    self.activity_event.prize,
                    self.activity_event.duration,
                    self.activity_event.time_unit,
                    start_time_str,
                    end_time_str,
                    1 if self.activity_event.is_active else 0,
                    event_id
                ))

                cursor.execute("DELETE FROM activity_participants WHERE event_id = ?", (event_id,))

                for user_id, coins in self.activity_event.participants.items():

                    username = "Unknown"
                    user = self.bot.get_user(user_id)
                    if user:
                        username = user.display_name
                    
                    cursor.execute('''
                    INSERT INTO activity_participants (event_id, user_id, username, coins)
                    VALUES (?, ?, ?, ?)
                    ''', (event_id, user_id, username, coins))
            else:

                cursor.execute('''
                INSERT INTO activity_events 
                (channel_id, prize, duration, time_unit, start_time, end_time, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    self.activity_event.channel_id,
                    self.activity_event.prize,
                    self.activity_event.duration,
                    self.activity_event.time_unit,
                    start_time_str,
                    end_time_str,
                    1 if self.activity_event.is_active else 0
                ))
                
                event_id = cursor.lastrowid

                for user_id, coins in self.activity_event.participants.items():

                    username = "Unknown"
                    user = self.bot.get_user(user_id)
                    if user:
                        username = user.display_name
                    
                    cursor.execute('''
                    INSERT INTO activity_participants (event_id, user_id, username, coins)
                    VALUES (?, ?, ?, ?)
                    ''', (event_id, user_id, username, coins))
            
            conn.commit()
            conn.close()
            logger.info(f"Activity event saved with ID {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Error saving activity event: {e}")
            return None
    
    def load_active_event(self):
        """Load active event from database if exists."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, channel_id, prize, duration, time_unit, start_time, end_time 
            FROM activity_events WHERE is_active = 1
            ''')
            event_data = cursor.fetchone()
            
            if not event_data:
                conn.close()
                return None
                
            event_id, channel_id, prize, duration, time_unit, start_time_str, end_time_str = event_data

            event = ActivityEvent()
            event.channel_id = channel_id
            event.prize = prize
            event.duration = duration
            event.time_unit = time_unit
            event.is_active = True

            if start_time_str:
                event.start_time = datetime.datetime.fromisoformat(start_time_str)
            if end_time_str:
                event.end_time = datetime.datetime.fromisoformat(end_time_str)

            cursor.execute('''
            SELECT user_id, coins FROM activity_participants WHERE event_id = ?
            ''', (event_id,))
            participants = cursor.fetchall()
            
            for user_id, coins in participants:
                event.participants[user_id] = coins
            
            conn.close()
            logger.info(f"Loaded active event ID {event_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error loading active event: {e}")
            return None
    
    def get_latest_event(self):
        """Get the latest event, active or not."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, channel_id, prize, duration, time_unit, start_time, end_time, is_active
            FROM activity_events ORDER BY id DESC LIMIT 1
            ''')
            event_data = cursor.fetchone()
            
            if not event_data:
                conn.close()
                return None
                
            event_id, channel_id, prize, duration, time_unit, start_time_str, end_time_str, is_active = event_data

            event = ActivityEvent()
            event.channel_id = channel_id
            event.prize = prize
            event.duration = duration
            event.time_unit = time_unit
            event.is_active = is_active == 1

            if start_time_str:
                event.start_time = datetime.datetime.fromisoformat(start_time_str)
            if end_time_str:
                event.end_time = datetime.datetime.fromisoformat(end_time_str)

            cursor.execute('''
            SELECT user_id, coins FROM activity_participants WHERE event_id = ?
            ''', (event_id,))
            participants = cursor.fetchall()
            
            for user_id, coins in participants:
                event.participants[user_id] = coins
            
            conn.close()
            logger.info(f"Retrieved latest event ID {event_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error getting latest event: {e}")
            return None
    
    @app_commands.command(
        name="chatactivity", 
        description="🎮 Start or end a chat activity event (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def chat_activity(self, interaction: discord.Interaction):
        """
        Open a panel to start or end a chat activity event.
        """

        if not await has_permissions(interaction, required_roles=['1338482857974169683', '1339687502121795584']):
            embed = discord.Embed(
                title="⚠️ Permission Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not self.activity_event:
            self.activity_event = self.load_active_event()

        view = ActivityManagementView(self)
        
        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="🎯 Chat Activity Management",
            description="Manage chat activity events that reward users with activity coins for messaging.",
            color=discord.Color(rainbow_color)
        )

        if self.activity_event and self.activity_event.is_active:
            channel = interaction.guild.get_channel(self.activity_event.channel_id)
            channel_name = channel.name if channel else f"Unknown (ID: {self.activity_event.channel_id})"
            
            time_remaining = ""
            if self.activity_event.end_time:
                now = datetime.datetime.now()
                if now < self.activity_event.end_time:
                    remaining = self.activity_event.end_time - now
                    hours, remainder = divmod(remaining.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_remaining = f"\n**Time Remaining:** {hours}h {minutes}m"

            top_participant = None
            if self.activity_event.participants:
                top_user_id = max(self.activity_event.participants, key=self.activity_event.participants.get)
                top_user = interaction.guild.get_member(top_user_id)
                top_coins = self.activity_event.participants[top_user_id]
                top_participant = f"\n**Current Leader:** {top_user.display_name if top_user else 'Unknown'} ({top_coins} coins)"
            
            embed.add_field(
                name="Current Activity Event",
                value=(
                    f"**Channel:** {channel_name}\n"
                    f"**Prize:** {self.activity_event.prize}\n"
                    f"**Duration:** {self.activity_event.duration} {self.activity_event.time_unit}(s)\n"
                    f"**Status:** ✅ Active"
                    f"{time_remaining}"
                    f"{top_participant if top_participant else ''}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Chat activity panel opened by {interaction.user.id}")
    
    @app_commands.command(
        name="activityleaderboard", 
        description="🏆 Show the current activity event leaderboard"
    )
    async def activity_leaderboard(self, interaction: discord.Interaction):
        """
        Show the leaderboard for the current activity event.
        This command is available to @everyone - no permission check needed
        """

        if not self.activity_event:
            self.activity_event = self.load_active_event()

        if not self.activity_event or not self.activity_event.is_active:
            await interaction.response.send_message(
                "⚠️ There is no active chat activity event currently running.",
                ephemeral=True
            )
            return

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="🏆 Activity Leaderboard",
            description="Current standings in the ongoing chat activity event:",
            color=discord.Color(rainbow_color)
        )

        channel = interaction.guild.get_channel(self.activity_event.channel_id)
        channel_mention = f"<#{self.activity_event.channel_id}>" if channel else "Unknown channel"

        coin_multiplier = 1.0
        event_system_cog = self.bot.get_cog("EventSystemCog")
        if event_system_cog:
            coin_multiplier = await event_system_cog.get_coin_multiplier()

        multiplier_text = ""
        if coin_multiplier > 1.0:
            multiplier_text = f"**Coin Bonus:** {coin_multiplier}x ✨\n"
        
        time_remaining = ""
        if self.activity_event.end_time:
            now = datetime.datetime.now()
            if now < self.activity_event.end_time:
                remaining = self.activity_event.end_time - now
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_remaining = f"**Time Remaining:** {hours}h {minutes}m\n"
        
        embed.add_field(
            name="Event Info",
            value=(
                f"**Prize:** {self.activity_event.prize}\n"
                f"**Channel:** {channel_mention}\n"
                f"{multiplier_text}"
                f"{time_remaining}"
            ),
            inline=False
        )

        if self.activity_event.participants:
            sorted_participants = sorted(
                self.activity_event.participants.items(), 
                key=lambda x: x[1], 
                reverse=True
            )

            top_participants = sorted_participants[:10]
            
            leaderboard_text = ""
            for i, (user_id, coins) in enumerate(top_participants, 1):
                member = interaction.guild.get_member(user_id)
                username = member.display_name if member else "Unknown User"
                
                if i == 1:
                    leaderboard_text += f"👑 **1. {username}** - {coins} coins\n"
                elif i == 2:
                    leaderboard_text += f"🥈 **2. {username}** - {coins} coins\n"
                elif i == 3:
                    leaderboard_text += f"🥉 **3. {username}** - {coins} coins\n"
                else:
                    leaderboard_text += f"**{i}.** {username} - {coins} coins\n"

            user_id = interaction.user.id
            if user_id in self.activity_event.participants and user_id not in [uid for uid, _ in top_participants]:

                user_position = next(i for i, (uid, _) in enumerate(sorted_participants, 1) if uid == user_id)
                user_coins = self.activity_event.participants[user_id]
                leaderboard_text += f"\n**Your Position:** #{user_position} - {user_coins} coins"
            
            embed.add_field(
                name="Top Participants",
                value=leaderboard_text if leaderboard_text else "No participants yet!",
                inline=False
            )
        else:
            embed.add_field(
                name="Top Participants",
                value="No participants yet! Start chatting to earn activity coins.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Activity leaderboard viewed by {interaction.user.id}")
    
    async def start_activity(self, channel_id, prize, duration, time_unit, is_resuming=False):
        """Start a new activity event.
        
        Args:
            channel_id: The channel ID to track activity in
            prize: The prize description
            duration: The duration of the event
            time_unit: minute, hour, or day
            is_resuming: If True, don't announce the start (silent resume)
        """
        try:

            if self.activity_event and self.activity_event.is_active and self.activity_event.task:
                self.activity_event.task.cancel()

            self.activity_event = ActivityEvent()
            self.activity_event.channel_id = channel_id
            self.activity_event.prize = prize
            self.activity_event.duration = duration
            self.activity_event.time_unit = time_unit
            self.activity_event.is_active = True
            self.activity_event.start_time = datetime.datetime.now()

            seconds = self.activity_event.get_seconds()
            self.activity_event.end_time = self.activity_event.start_time + datetime.timedelta(seconds=seconds)

            event_id = self.save_event()
            
            if not event_id:
                return False, "Failed to save activity event to database."

            self.activity_event.task = asyncio.create_task(self._run_activity_event(seconds, is_resuming=is_resuming))
            
            return True, "Activity event started successfully!"
            
        except Exception as e:
            logger.error(f"Error starting activity: {e}")
            return False, f"Error starting activity: {str(e)}"
    
    async def end_activity(self, announce=True):
        """End the current activity event and announce results."""
        try:
            if not self.activity_event:
                return False, "No activity event to end."

            if self.activity_event.task and not self.activity_event.task.done():
                self.activity_event.task.cancel()
                self.activity_event.task = None

            winner_id = None
            winner_coins = 0
            
            if self.activity_event.participants:
                winner_id = max(self.activity_event.participants, key=self.activity_event.participants.get)
                winner_coins = self.activity_event.participants[winner_id]

            self.activity_event.is_active = False
            self.activity_event.end_time = datetime.datetime.now()

            self.save_event()

            if announce and self.activity_event.channel_id:
                channel = self.bot.get_channel(self.activity_event.channel_id)
                if channel:
                    await self._announce_activity_results(channel, winner_id, winner_coins)
            
            return True, "Activity event ended successfully!"
            
        except Exception as e:
            logger.error(f"Error ending activity: {e}")
            return False, f"Error ending activity: {str(e)}"
    
    async def _run_activity_event(self, seconds, is_resuming=False):
        """Run the activity event for the specified duration.
        
        Args:
            seconds: Duration in seconds
            is_resuming: If True, don't announce start (silent resume)
        """
        try:

            if not is_resuming:
                channel = self.bot.get_channel(self.activity_event.channel_id)
                if channel:
                    await self._announce_activity_start(channel)

            reminder_times = self.activity_event.get_reminder_times()

            remaining_seconds = seconds
            for reminder_seconds in reminder_times:

                sleep_time = remaining_seconds - reminder_seconds

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    remaining_seconds -= sleep_time

                    channel = self.bot.get_channel(self.activity_event.channel_id)
                    if channel:
                        await self._send_time_reminder(channel, reminder_seconds)

            if remaining_seconds > 0:
                await asyncio.sleep(remaining_seconds)

            await self.end_activity()
            
        except asyncio.CancelledError:
            logger.info("Activity event task cancelled")
        except Exception as e:
            logger.error(f"Error in activity event task: {e}")
            
    async def _send_time_reminder(self, channel, seconds_remaining):
        """Send a reminder about time left in the activity event.
        
        Args:
            channel: The Discord channel to send the reminder to
            seconds_remaining: The number of seconds remaining in the event
        """
        try:

            if seconds_remaining >= 86400:  # 1 day
                time_str = f"{seconds_remaining // 86400} day{'s' if seconds_remaining // 86400 != 1 else ''}"
            elif seconds_remaining >= 3600:  # 1 hour
                time_str = f"{seconds_remaining // 3600} hour{'s' if seconds_remaining // 3600 != 1 else ''}"
            elif seconds_remaining >= 60:  # 1 minute
                time_str = f"{seconds_remaining // 60} minute{'s' if seconds_remaining // 60 != 1 else ''}"
            else:
                time_str = f"{seconds_remaining} second{'s' if seconds_remaining != 1 else ''}"

            top_user_id = None
            top_coins = 0
            
            if self.activity_event.participants:
                top_user_id = max(self.activity_event.participants, key=self.activity_event.participants.get)
                top_coins = self.activity_event.participants[top_user_id]

            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title=f"⏰ ACTIVITY EVENT REMINDER",
                description=f"**{time_str} remaining** in the current activity event!\n\nKeep chatting to earn activity coins and win the prize.",
                color=discord.Color(rainbow_color)
            )

            embed.add_field(
                name="Prize",
                value=self.activity_event.prize,
                inline=True
            )

            if top_user_id:
                top_user = self.bot.get_user(top_user_id)
                top_username = top_user.display_name if top_user else "Unknown User"
                
                embed.add_field(
                    name="Current Leader",
                    value=f"{top_username} with {top_coins} coins",
                    inline=True
                )

            embed.add_field(
                name="Participants",
                value=f"{len(self.activity_event.participants)} users",
                inline=True
            )

            embed.set_footer(text=f"Use /activityleaderboard to see the full rankings")
            
            await channel.send(embed=embed)
            logger.info(f"Sent activity reminder for {time_str} remaining")
            
        except Exception as e:
            logger.error(f"Error sending activity reminder: {e}")
    
    async def _announce_activity_start(self, channel):
        """Announce the start of an activity event."""
        try:

            duration_text = f"{self.activity_event.duration} {self.activity_event.time_unit}"
            if self.activity_event.duration != 1:
                duration_text += "s"

            coin_multiplier = 1.0
            event_system_cog = self.bot.get_cog("EventSystemCog")
            if event_system_cog:
                coin_multiplier = await event_system_cog.get_coin_multiplier()

            title = "🎯 ACTIVITY EVENT STARTED"
            if coin_multiplier > 1.0:
                title = f"🎯✨ ACTIVITY EVENT STARTED ({coin_multiplier}x BONUS)"
                
            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title=title,
                description=f"+ A new activity event has begun!",
                color=discord.Color(rainbow_color)
            )
            
            embed.add_field(
                name="🎁 Prize",
                value=self.activity_event.prize,
                inline=True
            )
            
            embed.add_field(
                name="⏰ Duration",
                value=duration_text,
                inline=True
            )

            embed.add_field(
                name="✨ Start chatting to earn activity coins!",
                value=f"Event is now active",
                inline=False
            )

            coins_per_msg = int(1 * coin_multiplier)
            if coin_multiplier > 1.0:
                value = f"> • {coins_per_msg} coins per message ✨ ({coin_multiplier}x Event Bonus Active!)"
            else:
                value = f"> • 1 coin per message"
                
            embed.add_field(
                name="📝 How to earn coins",
                value=value,
                inline=False
            )
            
            embed.add_field(
                name="🔄 Leaderboard has been reset!",
                value="Everyone starts from 0.",
                inline=False
            )
            
            embed.add_field(
                name="💫 Good luck everyone!",
                value="\u200b",  # Zero-width space
                inline=False
            )
            
            await channel.send(embed=embed)
            logger.info(f"Activity start announced in channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Error announcing activity start: {e}")
    
    async def _announce_activity_results(self, channel, winner_id, winner_coins):
        """Announce the results of an activity event."""
        try:

            coin_multiplier = 1.0
            event_system_cog = self.bot.get_cog("EventSystemCog")
            if event_system_cog:
                coin_multiplier = await event_system_cog.get_coin_multiplier()

            title = "🎊 ACTIVITY EVENT ENDED!"
            if coin_multiplier > 1.0:
                title = f"🎊✨ ACTIVITY EVENT ENDED! ({coin_multiplier}x BONUS)"
                
            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title=title,
                description="+ Congratulations to our winner!",
                color=discord.Color(rainbow_color)
            )

            winner_text = "No participants" if not winner_id else f"<@{winner_id}>"
            embed.add_field(
                name="👑 Winner",
                value=winner_text,
                inline=False
            )
            
            embed.add_field(
                name="🎁 Prize",
                value=self.activity_event.prize,
                inline=True
            )
            
            coins_text = f"{winner_coins}" if winner_coins > 0 else "0"

            if coin_multiplier > 1.0:
                coins_text = f"{winner_coins} ✨ ({coin_multiplier}x Event Bonus was active!)"
            
            embed.add_field(
                name="💰 Coins Earned",
                value=coins_text,
                inline=True
            )

            current_time = datetime.datetime.now().strftime("%H:%M")
            embed.set_footer(text=f"{current_time}")
            
            await channel.send(embed=embed)

            if winner_id:

                congrats_msg = f"🎉 Congratulations <@{winner_id}>! You won the activity event and earned {winner_coins} activity coins! 🎉"
                if coin_multiplier > 1.0:
                    congrats_msg = f"🎉 Congratulations <@{winner_id}>! You won the activity event and earned {winner_coins} activity coins with a {coin_multiplier}x event bonus! 🎉"
                
                await channel.send(congrats_msg)
            
            logger.info(f"Activity results announced in channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Error announcing activity results: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages to track activity coins."""

        if message.author.bot:
            return

        if not self.activity_event or not self.activity_event.is_active:
            return

        if message.channel.id != self.activity_event.channel_id:
            return

        coin_multiplier = 1.0
        event_system_cog = self.bot.get_cog("EventSystemCog")
        if event_system_cog:

            coin_multiplier = await event_system_cog.get_coin_multiplier()

        coins_to_add = 1
        if coin_multiplier > 1.0:
            coins_to_add = int(coins_to_add * coin_multiplier)
        
        user_id = message.author.id
        self.activity_event.participants[user_id] = self.activity_event.participants.get(user_id, 0) + coins_to_add

        self.save_event()

        logger.debug(f"Added {coins_to_add} coin(s) for {message.author} in activity event. Total: {self.activity_event.participants[user_id]}")

        if coin_multiplier > 1.0:
            logger.debug(f"Applied {coin_multiplier}x multiplier for {message.author} in activity event. Added {coins_to_add} coins.")

class ActivityManagementView(discord.ui.View):
    """View with buttons for managing activity events."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
    
    @discord.ui.button(
        label="Start Activity Event", 
        style=discord.ButtonStyle.green,
        emoji="🎯"
    )
    async def start_activity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open a modal for starting an activity event."""

        if self.cog.activity_event and self.cog.activity_event.is_active:
            await interaction.response.send_message(
                "⚠️ There is already an active chat activity event. Please end it before starting a new one.",
                ephemeral=True
            )
            return
        
        modal = StartActivityModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="End Latest Activity", 
        style=discord.ButtonStyle.red,
        emoji="🛑"
    )
    async def end_activity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to end the latest activity event."""

        if not self.cog.activity_event or not self.cog.activity_event.is_active:

            latest_event = self.cog.get_latest_event()
            if not latest_event:
                await interaction.response.send_message(
                    "⚠️ There are no chat activity events in the database.",
                    ephemeral=True
                )
                return

            self.cog.activity_event = latest_event

        view = EndActivityConfirmView(self.cog)

        coin_multiplier = 1.0
        event_system_cog = self.bot.get_cog("EventSystemCog")
        if event_system_cog:
            coin_multiplier = await event_system_cog.get_coin_multiplier()
        
        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="⚠️ End Activity Event?",
            description="Are you sure you want to end the current activity event? This will announce the results immediately.",
            color=discord.Color(rainbow_color)
        )

        channel = interaction.guild.get_channel(self.cog.activity_event.channel_id)
        channel_name = channel.name if channel else f"Unknown (ID: {self.cog.activity_event.channel_id})"

        top_participant = "No participants yet"
        if self.cog.activity_event.participants:
            top_user_id = max(self.cog.activity_event.participants, key=self.cog.activity_event.participants.get)
            top_user = interaction.guild.get_member(top_user_id)
            top_coins = self.cog.activity_event.participants[top_user_id]
            top_participant = f"{top_user.display_name if top_user else 'Unknown'} ({top_coins} coins)"

        multiplier_info = ""
        if coin_multiplier > 1.0:
            multiplier_info = f"**Event Bonus:** {coin_multiplier}x Multiplier Active! ✨\n"
        
        embed.add_field(
            name="Current Activity Details",
            value=(
                f"**Channel:** {channel_name}\n"
                f"**Prize:** {self.cog.activity_event.prize}\n"
                f"{multiplier_info}"
                f"**Current Leader:** {top_participant}"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class EndActivityConfirmView(discord.ui.View):
    """View with buttons for confirming activity event end."""
    
    def __init__(self, cog):
        super().__init__(timeout=60)  # 1 minute timeout
        self.cog = cog
    
    @discord.ui.button(
        label="Yes, End Now", 
        style=discord.ButtonStyle.danger,
        emoji="✓"
    )
    async def confirm_end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to confirm ending the activity."""
        success, message = await self.cog.end_activity()
        
        if success:
            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title="✅ Activity Ended",
                description="The activity event has been ended and results have been announced.",
                color=discord.Color(rainbow_color)
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
        style=discord.ButtonStyle.secondary,
        emoji="✗"
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to cancel ending the activity."""
        await interaction.response.send_message(
            "Activity event end cancelled.",
            ephemeral=True
        )
        self.stop()

class StartActivityModal(discord.ui.Modal):
    """Modal for starting a new activity event."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID to track activity in",
        required=True
    )
    
    prize = discord.ui.TextInput(
        label="Prize",
        placeholder="Enter the prize description (default: 25DLS)",
        required=False,
        default="25DLS"
    )
    
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="How long the activity will run (default: 2)",
        required=False,
        default="2"
    )
    
    time_unit = discord.ui.TextInput(
        label="Time Unit",
        placeholder="minute, hour, or day (default: hour)",
        required=False,
        default="hour"
    )
    
    def __init__(self, cog):
        super().__init__(title="Start Activity Event")
        self.cog = cog
        # Access bot through cog only when needed, not during initialization
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            channel_id = int(self.channel_id.value)
            prize = self.prize.value or "25DLS"
            duration = int(self.duration.value or 2)
            time_unit = self.time_unit.value.lower() or "hour"

            if time_unit not in ["minute", "hour", "day"]:
                await interaction.response.send_message(
                    "❌ Time unit must be 'minute', 'hour', or 'day'.",
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

            success, message = await self.cog.start_activity(channel_id, prize, duration, time_unit)
            
            if success:

                coin_multiplier = 1.0
                # Access bot through the cog
                event_system_cog = self.cog.bot.get_cog("EventSystemCog")
                if event_system_cog:
                    coin_multiplier = await event_system_cog.get_coin_multiplier()

                multiplier_info = ""
                if coin_multiplier > 1.0:
                    multiplier_info = f"**Event Bonus:** {coin_multiplier}x Coin Multiplier Active! ✨\n"
                
                rainbow_color = get_rainbow_color()
                embed = discord.Embed(
                    title="✅ Activity Started",
                    description=(
                        f"Chat activity event has been started in <#{channel_id}>!\n\n"
                        f"**Prize:** {prize}\n"
                        f"**Duration:** {duration} {time_unit}(s)\n"
                        f"{multiplier_info}\n"
                        f"Users can now earn activity coins by sending messages in that channel."
                    ),
                    color=discord.Color(rainbow_color)
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
                "❌ Please enter valid numbers for Channel ID and Duration.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in start activity modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    """Add the chat activity cog to the bot."""
    await bot.add_cog(ChatActivityCog(bot))
    logger.info("Chat activity cog loaded")