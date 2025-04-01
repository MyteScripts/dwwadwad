import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import datetime
import logging
from logger import setup_logger

logger = setup_logger('countdown', 'bot.log')

class CountdownCog(commands.Cog):
    """Cog for creating and managing countdown timers."""
    
    def __init__(self, bot):
        self.bot = bot
        self.countdowns = {}  # Dictionary to store active countdowns
        self.check_countdowns.start()  # Start the task
        logger.info("Countdown cog initialized")
    
    def cog_unload(self):
        """Called when the cog is unloaded."""
        self.check_countdowns.cancel()
    
    @tasks.loop(seconds=30)
    async def check_countdowns(self):
        """Check active countdowns and send updates."""
        if not self.countdowns:
            return  # No countdowns to check
        
        now = datetime.datetime.now()
        to_remove = []
        
        for channel_id, countdown_info in self.countdowns.items():
            end_time = countdown_info['end_time']
            update_interval = countdown_info['update_interval']
            last_update = countdown_info.get('last_update')

            if now >= end_time:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(f"🎯 **{countdown_info['title']} Countdown Complete!** ⏰")
                        logger.info(f"Countdown '{countdown_info['title']}' completed in channel {channel_id}")
                    except Exception as e:
                        logger.error(f"Error sending countdown completion message: {e}")
                to_remove.append(channel_id)
                continue

            if not last_update or (now - last_update).total_seconds() >= update_interval.total_seconds():
                channel = self.bot.get_channel(channel_id)
                if channel:
                    remaining = end_time - now
                    days, seconds = remaining.days, remaining.seconds
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    seconds = seconds % 60
                    
                    time_str = []
                    if days > 0:
                        time_str.append(f"{days} day{'s' if days != 1 else ''}")
                    if hours > 0:
                        time_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
                    if minutes > 0:
                        time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                    if seconds > 0 and days == 0 and hours == 0:  # Only show seconds if less than an hour left
                        time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                    
                    time_remaining = ", ".join(time_str)
                    
                    try:
                        await channel.send(f"⏳ **{countdown_info['title']}** - Time remaining: **{time_remaining}**")
                        countdown_info['last_update'] = now
                        logger.info(f"Sent update for countdown '{countdown_info['title']}' in channel {channel_id}")
                    except Exception as e:
                        logger.error(f"Error sending countdown update message: {e}")

        for channel_id in to_remove:
            del self.countdowns[channel_id]
    
    @check_countdowns.before_loop
    async def before_check_countdowns(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="countdown", description="Create a countdown timer or manage existing ones")
    async def countdown(self, interaction: discord.Interaction):
        """Opens a panel to create or manage countdown timers."""

        view = CountdownView(self)

        embed = discord.Embed(
            title="⏱️ Countdown Timer",
            description="Create a new countdown or remove the latest one.",
            color=discord.Color.blue()
        )

        if interaction.channel_id in self.countdowns:
            countdown_info = self.countdowns[interaction.channel_id]
            end_time = countdown_info['end_time']
            now = datetime.datetime.now()

            if now < end_time:
                remaining = end_time - now
                days, seconds = remaining.days, remaining.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                
                time_str = []
                if days > 0:
                    time_str.append(f"{days} day{'s' if days != 1 else ''}")
                if hours > 0:
                    time_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes > 0:
                    time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds > 0 and days == 0 and hours == 0:
                    time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
                time_remaining = ", ".join(time_str)
                
                embed.add_field(
                    name="Current Countdown",
                    value=f"**{countdown_info['title']}**\nTime Remaining: **{time_remaining}**\nUpdates every: **{self._format_interval(countdown_info['update_interval'])}**",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Countdown command used by {interaction.user}")
    
    def _format_interval(self, interval):
        """Format a timedelta into a readable string."""
        total_seconds = interval.total_seconds()
        
        if total_seconds < 60:
            return f"{int(total_seconds)} seconds"
        elif total_seconds < 3600:
            minutes = int(total_seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif total_seconds < 86400:
            hours = int(total_seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = int(total_seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''}"

class CountdownModal(discord.ui.Modal):
    """Modal for creating a new countdown timer."""
    
    def __init__(self, cog):
        super().__init__(title="Create Countdown Timer")
        self.cog = cog
        
        self.title_input = discord.ui.TextInput(
            label="Countdown Title",
            placeholder="Enter a title for your countdown",
            required=True,
            max_length=100
        )
        self.add_item(self.title_input)
        
        self.duration_input = discord.ui.TextInput(
            label="Duration (number)",
            placeholder="Enter a number",
            required=True,
            max_length=10
        )
        self.add_item(self.duration_input)
        
        self.unit_input = discord.ui.TextInput(
            label="Time Unit",
            placeholder="minutes, hours, or days",
            required=True,
            max_length=10
        )
        self.add_item(self.unit_input)
        
        self.update_interval_input = discord.ui.TextInput(
            label="Update Interval (number)",
            placeholder="How often to send updates (in same units)",
            required=True,
            max_length=10
        )
        self.add_item(self.update_interval_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            duration = int(self.duration_input.value)
            unit = self.unit_input.value.lower().strip()

            update_interval = int(self.update_interval_input.value)

            if unit in ["minute", "minutes", "min", "mins", "m"]:
                duration_td = datetime.timedelta(minutes=duration)
                update_interval_td = datetime.timedelta(minutes=update_interval)
                unit_name = "minute(s)"
            elif unit in ["hour", "hours", "hr", "hrs", "h"]:
                duration_td = datetime.timedelta(hours=duration)
                update_interval_td = datetime.timedelta(hours=update_interval)
                unit_name = "hour(s)"
            elif unit in ["day", "days", "d"]:
                duration_td = datetime.timedelta(days=duration)
                update_interval_td = datetime.timedelta(days=update_interval)
                unit_name = "day(s)"
            else:
                await interaction.response.send_message("Invalid time unit! Please use minutes, hours, or days.", ephemeral=True)
                return

            if duration <= 0:
                await interaction.response.send_message("Duration must be greater than 0!", ephemeral=True)
                return
            
            if update_interval <= 0:
                await interaction.response.send_message("Update interval must be greater than 0!", ephemeral=True)
                return
            
            if update_interval > duration:
                await interaction.response.send_message("Update interval cannot be larger than the total duration!", ephemeral=True)
                return

            end_time = datetime.datetime.now() + duration_td

            self.cog.countdowns[interaction.channel_id] = {
                'title': self.title_input.value,
                'end_time': end_time,
                'update_interval': update_interval_td,
                'created_by': interaction.user.id,
                'last_update': None  # Will be set on first update
            }

            await interaction.response.send_message(
                f"✅ Countdown **{self.title_input.value}** created!\n"
                f"⏱️ Duration: **{duration} {unit_name}**\n"
                f"🔄 Updates every: **{update_interval} {unit_name}**\n"
                f"⏳ Ends at: <t:{int(end_time.timestamp())}:f>"
            )
            
            logger.info(f"New countdown '{self.title_input.value}' created by {interaction.user} in channel {interaction.channel_id}")
            
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers for duration and update interval!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error creating countdown: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class CountdownView(discord.ui.View):
    """View with buttons for creating and managing countdowns."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
    
    @discord.ui.button(label="Create Countdown", style=discord.ButtonStyle.primary, emoji="⏱️")
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to create a new countdown."""
        modal = CountdownModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remove Countdown", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to remove the current countdown."""
        if interaction.channel_id in self.cog.countdowns:
            countdown_info = self.cog.countdowns[interaction.channel_id]
            title = countdown_info['title']

            is_creator = countdown_info['created_by'] == interaction.user.id
            has_manage_permission = interaction.user.guild_permissions.manage_messages
            
            if is_creator or has_manage_permission:
                del self.cog.countdowns[interaction.channel_id]
                await interaction.response.send_message(f"✅ Countdown **{title}** has been removed!")
                logger.info(f"Countdown '{title}' removed by {interaction.user} in channel {interaction.channel_id}")
            else:
                await interaction.response.send_message("You don't have permission to remove this countdown!", ephemeral=True)
        else:
            await interaction.response.send_message("There is no active countdown in this channel!", ephemeral=True)

async def setup(bot):
    """Add the countdown cog to the bot."""
    await bot.add_cog(CountdownCog(bot))
    logger.info("Countdown cog loaded")