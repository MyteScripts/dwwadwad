import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from logger import setup_logger
from events import register_events
from config import BotConfig
from leveling import setup as setup_leveling
from permissions import is_admin
from countdown import setup as setup_countdown
from gamevote import setup as setup_gamevote
from invites import setup as setup_invites
from migration import setup as setup_migration
from legacy_data_finder import setup as setup_legacy_finder
from db_sync import setup as setup_db_sync
from coin_panel import setup as setup_coin_panel
from level_panel import setup as setup_level_panel
from drop_edit import setup as setup_drop_edit
from status_manager import setup as setup_status_manager
# Removed old investment system
from chat_activity import setup as setup_chat_activity
from permissions import setup as setup_permissions
from moderation import setup as setup_moderation
from grumbleteeth import setup as setup_grumbleteeth
from event_system import setup as setup_event_system
from level_roles import setup as setup_level_roles
from work import setup as setup_work
from web_auth import setup as setup_web_auth
from embed_command import setup as setup_embed_command
from community_commands import setup as setup_community_commands
from mining import setup as setup_mining
from announcements import setup as setup_announcements
from profile_system import setup as setup_profile_system
from mini_games import setup as setup_mini_games
from activity_events import setup as setup_activity_events
from random_drops import setup as setup_random_drops
# New luxury property investment system
from investment_system_new import setup as setup_investment_system_new
# New cogs
from reporting import setup as setup_reporting
from welcome_goodbye import setup as setup_welcome_goodbye
from invite_tracker import setup as setup_invite_tracker 
from games import setup as setup_games
from tournaments import setup as setup_tournaments
from embed_builder import setup as setup_embed_builder

logger = setup_logger('bot')

async def initialize_bot():
    """Initialize and run the Discord bot."""

    load_dotenv()

    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logger.critical("No Discord token found! Please set the DISCORD_TOKEN environment variable.")
        return

    intents = discord.Intents.default()
    intents.members = True  # Enable member events
    intents.message_content = True  # Enable message content

    bot = commands.Bot(command_prefix="G9x#7!@Kp$", intents=intents)

    async def has_admin_permissions(user_id, guild_id):
        """Check if a user has admin permissions.
        
        Args:
            user_id: The ID of the user to check
            guild_id: The ID of the guild where the check is being performed
            
        Returns:
            bool: True if the user has admin permissions, False otherwise
        """

        admin_user_ids = ["1308527904497340467", "479711321399623681", "1063511383397892256"]

        if str(user_id) in admin_user_ids:
            return True

        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                admin_role_id = "1338482857974169683"
                for role in member.roles:
                    if str(role.id) == admin_role_id:
                        return True

        return False

    bot.has_admin_permissions = has_admin_permissions

    config = BotConfig()

    register_events(bot)

    await setup_leveling(bot)

    await setup_countdown(bot)

    await setup_gamevote(bot)

    await setup_invites(bot)

    await setup_migration(bot)

    await setup_legacy_finder(bot)

    await setup_db_sync(bot)

    await setup_coin_panel(bot)

    await setup_level_panel(bot)

    await setup_drop_edit(bot)

    await setup_status_manager(bot)

    # Using the new luxury property investment system
    await setup_investment_system_new(bot)

    await setup_chat_activity(bot)

    await setup_permissions(bot)

    await setup_work(bot)

    await setup_moderation(bot)

    await setup_grumbleteeth(bot)

    await setup_event_system(bot)

    await setup_level_roles(bot)

    await setup_web_auth(bot)

    await setup_embed_command(bot)

    await setup_community_commands(bot)

    await setup_mining(bot)
    
    await setup_announcements(bot)
    
    await setup_profile_system(bot)
    
    await setup_mini_games(bot)
    
    await setup_activity_events(bot)
    
    await setup_random_drops(bot)
    
    # Setup new cogs
    await setup_reporting(bot)
    await setup_welcome_goodbye(bot)
    await setup_invite_tracker(bot)
    await setup_games(bot)
    await setup_tournaments(bot)
    await setup_embed_builder(bot)
    
    @bot.event
    async def on_ready():
        """Called when the bot has successfully connected to Discord."""

        logger.info(f"Bot connected as {bot.user.name} (ID: {bot.user.id})")
        logger.info(f"Connected to {len(bot.guilds)} guilds")

        try:
            # Get all guild IDs where the bot is a member
            guild_ids = [guild.id for guild in bot.guilds]
            
            # Print registered commands before syncing
            logger.info("Commands registered in the command tree:")
            for cmd in bot.tree.get_commands():
                logger.info(f"Command: {cmd.name}")
            
            # Force sync the commands globally first
            try:
                # Get all commands before syncing
                all_commands = bot.tree.get_commands()
                
                # Sync up to 95 global commands
                bot.tree._global_commands = bot.tree._global_commands[:95]
                logger.info(f"Syncing up to 95 global commands")
                
                global_commands = await bot.tree.sync()
                logger.info(f"Synced {len(global_commands)} commands globally")
                total_synced = len(global_commands)
            except Exception as e:
                logger.error(f"Failed to sync commands globally: {e}")
                total_synced = 0
                
            # Now sync to each guild separately for guild-specific commands
            for guild_id in guild_ids:
                try:
                    guild_commands = await bot.tree.sync(guild=discord.Object(id=guild_id))
                    total_synced += len(guild_commands)
                    logger.info(f"Synced {len(guild_commands)} commands to guild ID: {guild_id}")
                except Exception as e:
                    logger.error(f"Failed to sync commands to guild ID {guild_id}: {e}")
            
            print(f"Synced {total_synced} total command(s) across {len(guild_ids)} guild(s)")
            print(f"Bot is online as {bot.user.name}")
            
            # Log the registered commands
            for guild_id in guild_ids:
                guild_commands = bot.tree.get_commands(guild=discord.Object(id=guild_id))
                for cmd in guild_commands:
                    logger.info(f"Registered command: {cmd.name} in guild ID: {guild_id}")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    max_retries = 5
    retry_count = 0
    
    try:
        while retry_count < max_retries:
            try:
                logger.info("Attempting to connect to Discord...")
                async with bot:
                    await bot.start(TOKEN)
                break
            except discord.errors.LoginFailure:
                logger.critical("Improper token has been passed. Please check your token and try again.")
                break
            except Exception as e:
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.error(f"Failed to connect: {e}. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
                
        if retry_count >= max_retries:
            logger.critical(f"Failed to connect after {max_retries} attempts. Please check your internet connection and try again later.")
    finally:
        # Ensure all connections are properly closed
        await bot.close()
async def remove_excess_commands(bot):
    """Remove excess commands if we're over Discord's 100 command limit"""
    commands = bot.tree.get_commands()
    if len(commands) > 100:
        logger.warning(f"Bot has {len(commands)} commands, exceeding Discord's 100 command limit")
        # Keep core commands, remove excess
        bot.tree._global_commands = bot.tree._global_commands[:95]
        logger.info("Reduced to 95 global commands to allow for guild-specific commands")
