import discord
from discord import app_commands
from discord.ext import commands
import logging
import datetime
import json
import os

class WelcomeGoodbyeSystem(commands.Cog):
    """Cog for handling welcome and goodbye messages."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('welcome_goodbye')
        
        # Default settings
        self.welcome_channel_id = None
        self.goodbye_channel_id = None
        self.welcome_message = "Welcome to {server}, {user}! 🎉\nWe're glad to have you here!"
        self.goodbye_message = "Goodbye, {user}! We hope to see you again soon!"
        
        # Custom messages per guild
        self.custom_messages = {}
        
        # Load settings
        self.load_settings()
    
    def load_settings(self):
        """Load welcome/goodbye settings from settings.json."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                self.welcome_channel_id = settings.get('welcome_channel_id')
                self.goodbye_channel_id = settings.get('goodbye_channel_id')
                
                if 'welcome_message' in settings:
                    self.welcome_message = settings['welcome_message']
                if 'goodbye_message' in settings:
                    self.goodbye_message = settings['goodbye_message']
                    
                self.custom_messages = settings.get('custom_welcome_messages', {})
        except Exception as e:
            self.logger.error(f"Failed to load welcome/goodbye settings: {e}")
    
    def save_settings(self):
        """Save welcome/goodbye settings to settings.json."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
            
            settings['welcome_channel_id'] = self.welcome_channel_id
            settings['goodbye_channel_id'] = self.goodbye_channel_id
            settings['welcome_message'] = self.welcome_message
            settings['goodbye_message'] = self.goodbye_message
            settings['custom_welcome_messages'] = self.custom_messages
            
            with open('settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save welcome/goodbye settings: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send a welcome message when a member joins."""
        if not self.welcome_channel_id:
            return
        
        try:
            channel = self.bot.get_channel(int(self.welcome_channel_id))
            if not channel:
                self.logger.error(f"Welcome channel not found: {self.welcome_channel_id}")
                return
            
            # Get the invite that was used
            invite_used = "Direct join or unknown invite"
            guild = member.guild
            
            # Get a list of the guild's invites before the user joined
            try:
                invites_before = getattr(self.bot, 'invites_before', {}).get(guild.id, {})
                invites_after = await guild.invites()
                
                # Find which invite count decreased
                for invite in invites_after:
                    if invite.code in invites_before and invite.uses > invites_before[invite.code]:
                        invite_used = f"Used invite '{invite.code}' created by {invite.inviter.name if invite.inviter else 'Unknown'}"
                        break
                
                # Update the invites
                self.bot.invites_before[guild.id] = {i.code: i.uses for i in invites_after}
            except:
                # If we can't get the invites, just continue with the default message
                pass
            
            # Check if there's a custom message for this guild
            guild_id = str(member.guild.id)
            message = self.custom_messages.get(guild_id, self.welcome_message)
            
            # Format the message
            formatted_message = message.format(
                user=member.mention,
                username=member.name,
                server=member.guild.name,
                invite=invite_used,
                membercount=member.guild.member_count
            )
            
            # Create an embed
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=formatted_message,
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            
            # Add the user's avatar to the embed
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Add footer with join date and other information
            embed.set_footer(text=f"User ID: {member.id} | Account Created: {member.created_at.strftime('%Y-%m-%d')}")
            
            # Add field for the invite used
            embed.add_field(name="Invite Information", value=invite_used, inline=False)
            
            # Send the welcome message
            await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to send welcome message: {e}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Send a goodbye message when a member leaves."""
        if not self.goodbye_channel_id:
            return
        
        try:
            channel = self.bot.get_channel(int(self.goodbye_channel_id))
            if not channel:
                self.logger.error(f"Goodbye channel not found: {self.goodbye_channel_id}")
                return
            
            # Format the goodbye message
            formatted_message = self.goodbye_message.format(
                user=member.name,
                username=member.name,
                server=member.guild.name,
                membercount=member.guild.member_count
            )
            
            # Create an embed
            embed = discord.Embed(
                title="Member Left",
                description=formatted_message,
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            
            # Add the user's avatar to the embed
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Add footer with join date and other information
            joined_at = member.joined_at.strftime('%Y-%m-%d') if member.joined_at else "Unknown"
            embed.set_footer(text=f"User ID: {member.id} | Joined: {joined_at}")
            
            # Add field for how long they were a member
            if member.joined_at:
                time_in_server = datetime.datetime.now() - member.joined_at.replace(tzinfo=None)
                days = time_in_server.days
                hours, remainder = divmod(time_in_server.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                time_str = f"{days} days, {hours} hours, {minutes} minutes"
                embed.add_field(name="Time in Server", value=time_str, inline=False)
            
            # Send the goodbye message
            await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to send goodbye message: {e}")
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Track invites when they are created."""
        try:
            if not hasattr(self.bot, 'invites_before'):
                self.bot.invites_before = {}
            
            guild_id = invite.guild.id
            if guild_id not in self.bot.invites_before:
                self.bot.invites_before[guild_id] = {}
            
            self.bot.invites_before[guild_id][invite.code] = invite.uses
        except Exception as e:
            self.logger.error(f"Failed to track invite creation: {e}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Cache all invites when the bot starts up."""
        try:
            self.bot.invites_before = {}
            for guild in self.bot.guilds:
                try:
                    self.bot.invites_before[guild.id] = {i.code: i.uses for i in await guild.invites()}
                except:
                    # If we can't access invites for this guild, skip it
                    pass
        except Exception as e:
            self.logger.error(f"Failed to cache invites on startup: {e}")
    
    @app_commands.command(name="setwelcomechannel", description="Set the channel for welcome messages (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def set_welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel for welcome messages.
        
        Args:
            interaction: The interaction that triggered this command
            channel: The channel to set as the welcome channel
        """
        self.welcome_channel_id = channel.id
        self.save_settings()
        
        await interaction.response.send_message(
            f"Welcome channel set to {channel.mention}.",
            ephemeral=True
        )
    
    @app_commands.command(name="setgoodbyechannel", description="Set the channel for goodbye messages (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def set_goodbye_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel for goodbye messages.
        
        Args:
            interaction: The interaction that triggered this command
            channel: The channel to set as the goodbye channel
        """
        self.goodbye_channel_id = channel.id
        self.save_settings()
        
        await interaction.response.send_message(
            f"Goodbye channel set to {channel.mention}.",
            ephemeral=True
        )
    
    @app_commands.command(name="setwelcomemessage", description="Set the welcome message format (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def set_welcome_message(self, interaction: discord.Interaction, message: str):
        """Set the welcome message format.
        
        Args:
            interaction: The interaction that triggered this command
            message: The message format (can include {user}, {server}, {invite}, {membercount})
        """
        guild_id = str(interaction.guild.id)
        self.custom_messages[guild_id] = message
        self.save_settings()
        
        # Show a preview of the message
        formatted_message = message.format(
            user=interaction.user.mention,
            username=interaction.user.name,
            server=interaction.guild.name,
            invite="example-invite",
            membercount=interaction.guild.member_count
        )
        
        await interaction.response.send_message(
            f"Welcome message set. Preview:\n\n{formatted_message}",
            ephemeral=True
        )
    
    @app_commands.command(name="setgoodbyemessage", description="Set the goodbye message format (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def set_goodbye_message(self, interaction: discord.Interaction, message: str):
        """Set the goodbye message format.
        
        Args:
            interaction: The interaction that triggered this command
            message: The message format (can include {user}, {server}, {membercount})
        """
        self.goodbye_message = message
        self.save_settings()
        
        # Show a preview of the message
        formatted_message = message.format(
            user=interaction.user.name,
            username=interaction.user.name,
            server=interaction.guild.name,
            membercount=interaction.guild.member_count
        )
        
        await interaction.response.send_message(
            f"Goodbye message set. Preview:\n\n{formatted_message}",
            ephemeral=True
        )
    
    @app_commands.command(name="testwelcome", description="Test the welcome message (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def test_welcome(self, interaction: discord.Interaction):
        """Test the welcome message.
        
        Args:
            interaction: The interaction that triggered this command
        """
        if not self.welcome_channel_id:
            await interaction.response.send_message(
                "No welcome channel has been set. Use /setwelcomechannel first.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "Sending a test welcome message...",
            ephemeral=True
        )
        
        # Simulate a member join
        await self.on_member_join(interaction.user)
    
    @app_commands.command(name="testgoodbye", description="Test the goodbye message (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def test_goodbye(self, interaction: discord.Interaction):
        """Test the goodbye message.
        
        Args:
            interaction: The interaction that triggered this command
        """
        if not self.goodbye_channel_id:
            await interaction.response.send_message(
                "No goodbye channel has been set. Use /setgoodbyechannel first.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "Sending a test goodbye message...",
            ephemeral=True
        )
        
        # Simulate a member leave
        await self.on_member_remove(interaction.user)


async def setup(bot):
    """Add the welcome/goodbye system cog to the bot."""
    welcome_goodbye_cog = WelcomeGoodbyeSystem(bot)
    await bot.add_cog(welcome_goodbye_cog)
    return welcome_goodbye_cog