import discord
import random
from discord.ext import commands, tasks
from datetime import datetime
from logger import setup_logger

logger = setup_logger('events')

def register_events(bot):
    """Register all event handlers for the bot."""
    
    @bot.event
    async def on_ready():
        """Called when the bot has connected to Discord and is ready."""
        logger.info(f'Bot connected as {bot.user.name} (ID: {bot.user.id})')

        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for server events"
            )
        )

        status_changer.start()
        logger.info("Background tasks started")

    @tasks.loop(minutes=30)
    async def status_changer():
        """Changes the bot's status message periodically."""
        status_messages = [
            ("watching", "your XP grow"),
            ("listening", "to level up sounds"),
            ("playing", "with leveling systems"),
            ("watching", "the leaderboard"),
            ("playing", "rank /rank to see stats")
        ]
        
        activity_type, message = random.choice(status_messages)
        
        if activity_type == "watching":
            activity = discord.Activity(type=discord.ActivityType.watching, name=message)
        elif activity_type == "listening":
            activity = discord.Activity(type=discord.ActivityType.listening, name=message)
        elif activity_type == "playing":
            activity = discord.Game(name=message)
        
        await bot.change_presence(status=discord.Status.online, activity=activity)
        logger.debug(f"Changed status to {activity_type} {message}")

    @bot.event
    async def on_member_join(member):
        """Called when a member joins the server."""
        logger.info(f'New member joined: {member.name}#{member.discriminator} (ID: {member.id})')

    @bot.event
    async def on_member_remove(member):
        """Called when a member leaves the server."""
        logger.info(f'Member left: {member.name}#{member.discriminator} (ID: {member.id})')

        system_channel = member.guild.system_channel

        excluded_channel_id = 1348388847758872616
        
        if system_channel and system_channel.id != excluded_channel_id:
            goodbye_messages = [
                f"{member.name} has left the server. We'll miss you!",
                f"Farewell, {member.name}. It was nice having you!",
                f"{member.name} just left... Was it something I said?",
                f"Goodbye {member.name}. Come back soon!"
            ]
            
            goodbye_message = random.choice(goodbye_messages)
            await system_channel.send(goodbye_message)

    @bot.event
    async def on_message(message):
        """Called when a message is sent in a channel the bot can see."""

        if message.author == bot.user:
            return

        logger.debug(f'Message from {message.author}: {message.content[:50]}{"..." if len(message.content) > 50 else ""}')

        if bot.user.mentioned_in(message):
            logger.info(f'Bot was mentioned by {message.author}')

    @bot.event
    async def on_reaction_add(reaction, user):
        """Called when a reaction is added to a message."""

        if user == bot.user:
            return
            
        logger.debug(f'Reaction {reaction.emoji} added by {user} to message ID {reaction.message.id}')

    @bot.event
    async def on_guild_channel_create(channel):
        """Called when a new channel is created."""
        logger.info(f'New channel created: {channel.name} (ID: {channel.id})')

    @bot.event
    async def on_error(event, *args, **kwargs):
        """Called when an error is raised during an event."""
        logger.error(f'Error in event {event}: {args} {kwargs}')

    @bot.event
    async def on_disconnect():
        """Called when the bot disconnects from Discord."""
        logger.warning('Bot disconnected from Discord')

    @bot.event
    async def on_resumed():
        """Called when the bot resumes a session after disconnecting."""
        logger.info('Bot resumed session')
        
    @bot.event
    async def on_voice_state_update(member, before, after):
        """Called when a member changes voice state."""

        if before.channel is None and after.channel is not None:
            logger.info(f'{member} joined voice channel {after.channel.name}')

        elif before.channel is not None and after.channel is None:
            logger.info(f'{member} left voice channel {before.channel.name}')

        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            logger.info(f'{member} moved from voice channel {before.channel.name} to {after.channel.name}')

    @bot.event
    async def on_guild_join(guild):
        """Called when the bot joins a guild (server)."""
        logger.info(f'Bot joined new guild: {guild.name} (ID: {guild.id})')

        if guild.system_channel:
            await guild.system_channel.send(
                f"Hello, {guild.name}! I'm GridBot Beta, a leveling system bot. "
                f"Use `/rank` to check your stats, `/leaderboard` to see top members, "
                f"and admins can use `/editleveling` to configure the system!"
            )

    return bot
