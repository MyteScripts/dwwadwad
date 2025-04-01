import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
from datetime import datetime
from logger import setup_logger

logger = setup_logger('status_manager', 'bot.log')

class StatusSettings:
    """Class to store bot status settings."""
    def __init__(self):
        self.log_channel_id = None  # Channel to send status logs to
        self.current_status = "online"  # Current status: online, maintenance, off
        self.last_update = None  # When the status was last updated
        self.last_message_id = None  # ID of the last status message

class StatusManagerCog(commands.Cog):
    """Cog for managing the bot's status."""
    
    def __init__(self, bot):
        self.bot = bot
        self.settings = {}  # Guild ID -> StatusSettings
        logger.info("Status manager cog initialized")
    
    @app_commands.command(
        name="status", 
        description="Manage the bot's status (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        """
        Open a panel to manage the bot's status.
        """

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        if guild_id not in self.settings:
            self.settings[guild_id] = StatusSettings()

        embed = self._create_status_embed(interaction.guild)

        view = StatusView(self, interaction.guild)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Status panel opened by {interaction.user.id}")
    
    def _create_status_embed(self, guild):
        """Create a status embed with current bot status information."""
        guild_id = guild.id
        settings = self.settings.get(guild_id, StatusSettings())

        status_icon = "🟢" if settings.current_status == "online" else "🟠" if settings.current_status == "maintenance" else "🔴"
        
        embed = discord.Embed(
            title=f"{status_icon} Bot Status Manager",
            description="Use the buttons below to manage the bot's status.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Current Status",
            value=f"**{status_icon} {settings.current_status.upper()}**",
            inline=False
        )

        if settings.log_channel_id:
            channel = guild.get_channel(settings.log_channel_id)
            channel_name = channel.name if channel else f"Unknown (ID: {settings.log_channel_id})"
            embed.add_field(
                name="Status Log Channel",
                value=f"<#{settings.log_channel_id}> ({channel_name})",
                inline=False
            )
        else:
            embed.add_field(
                name="Status Log Channel",
                value="Not set. Use the 'Set Log Channel' button.",
                inline=False
            )

        if settings.last_update:
            time_str = settings.last_update.strftime("%Y-%m-%d %H:%M:%S UTC")
            embed.add_field(
                name="Last Update",
                value=f"**Time:** {time_str}",
                inline=False
            )
        
        return embed
    
    async def set_status(self, guild_id, status, reason=None, user=None):
        """Set the bot's status and update or send a status message."""
        if guild_id not in self.settings:
            self.settings[guild_id] = StatusSettings()
        
        settings = self.settings[guild_id]
        old_status = settings.current_status

        settings.current_status = status
        settings.last_update = datetime.utcnow()

        logger.info(f"Status changed from {old_status} to {status} for guild {guild_id}")

        if settings.log_channel_id:
            guild = self.bot.get_guild(guild_id)
            if guild:
                channel = guild.get_channel(settings.log_channel_id)
                if channel:

                    status_icon = "🟢" if status == "online" else "🟠" if status == "maintenance" else "🔴"

                    embed = discord.Embed(
                        title=f"{status_icon} Bot Status: {status.upper()}",
                        description=f"The bot is currently in **{status.upper()}** mode.",
                        color=discord.Color.green() if status == "online" else discord.Color.orange() if status == "maintenance" else discord.Color.red()
                    )

                    embed.add_field(
                        name="Last Updated",
                        value=settings.last_update.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        inline=False
                    )
                    
                    if user:
                        embed.set_footer(text=f"Updated by {user.name}")

                    if settings.last_message_id:
                        try:
                            last_message = await channel.fetch_message(settings.last_message_id)
                            await last_message.edit(embed=embed)
                            return True, f"Status updated to {status}."
                        except (discord.NotFound, discord.HTTPException, discord.Forbidden):

                            pass

                    message = await channel.send(embed=embed)
                    settings.last_message_id = message.id
        
        return True, f"Status updated to {status}."

class StatusView(discord.ui.View):
    """View with buttons for managing the bot's status."""
    
    def __init__(self, cog, guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild = guild
    
    @discord.ui.button(
        label="Set Log Channel", 
        style=discord.ButtonStyle.blurple,
        emoji="📝"
    )
    async def set_log_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set the status log channel."""
        modal = SetLogChannelModal(self.cog, self.guild.id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Set Online", 
        style=discord.ButtonStyle.green,
        emoji="🟢"
    )
    async def set_online_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set the bot status to online."""
        await interaction.response.defer(ephemeral=True)
        success, message = await self.cog.set_status(
            self.guild.id, 
            "online", 
            user=interaction.user
        )
        
        if success:

            status_embed = self.cog._create_status_embed(interaction.guild)
            await interaction.message.edit(embed=status_embed, view=interaction.message.view)

            if interaction.user.id == await self.cog.bot.is_owner(interaction.user):
                await self.cog.bot.change_presence(status=discord.Status.online)
            
            embed = discord.Embed(
                title="✅ Status Updated",
                description="Bot status changed to **ONLINE**.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=message,
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="Set Maintenance", 
        style=discord.ButtonStyle.secondary,
        emoji="🟠"
    )
    async def set_maintenance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set the bot status to maintenance."""
        await interaction.response.defer(ephemeral=True)
        success, message = await self.cog.set_status(
            self.guild.id, 
            "maintenance", 
            user=interaction.user
        )
        
        if success:

            status_embed = self.cog._create_status_embed(interaction.guild)
            await interaction.message.edit(embed=status_embed, view=interaction.message.view)

            if interaction.user.id == await self.cog.bot.is_owner(interaction.user):
                await self.cog.bot.change_presence(
                    status=discord.Status.idle,
                    activity=discord.Activity(
                        type=discord.ActivityType.playing,
                        name="Maintenance Mode"
                    )
                )
            
            embed = discord.Embed(
                title="✅ Status Updated",
                description="Bot status changed to **MAINTENANCE**.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=message,
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="Set Offline", 
        style=discord.ButtonStyle.red,
        emoji="🔴"
    )
    async def set_offline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set the bot status to offline."""
        await interaction.response.defer(ephemeral=True)
        success, message = await self.cog.set_status(
            self.guild.id, 
            "off", 
            user=interaction.user
        )
        
        if success:

            status_embed = self.cog._create_status_embed(interaction.guild)
            await interaction.message.edit(embed=status_embed, view=interaction.message.view)

            if interaction.user.id == await self.cog.bot.is_owner(interaction.user):
                await self.cog.bot.change_presence(status=discord.Status.dnd)
            
            embed = discord.Embed(
                title="✅ Status Updated",
                description="Bot status changed to **OFFLINE**.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=message,
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class SetLogChannelModal(discord.ui.Modal):
    """Modal for setting the status log channel."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID for status logs",
        required=True
    )
    
    def __init__(self, cog, guild_id):
        super().__init__(title="Set Status Log Channel")
        self.cog = cog
        self.guild_id = guild_id

        if guild_id in cog.settings and cog.settings[guild_id].log_channel_id:
            self.channel_id.default = str(cog.settings[guild_id].log_channel_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            channel_id = int(self.channel_id.value)

            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    f"❌ Could not find a channel with ID {channel_id}.",
                    ephemeral=True
                )
                return

            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    f"❌ The bot doesn't have permission to send messages in {channel.mention}.",
                    ephemeral=True
                )
                return

            if self.guild_id not in self.cog.settings:
                self.cog.settings[self.guild_id] = StatusSettings()
            
            self.cog.settings[self.guild_id].log_channel_id = channel_id

            embed = discord.Embed(
                title="✅ Status Log Channel Set",
                description=f"This channel will now receive bot status updates.",
                color=discord.Color.green()
            )
            
            await channel.send(embed=embed)

            status_embed = self.cog._create_status_embed(interaction.guild)
            await interaction.message.edit(embed=status_embed, view=interaction.message.view)
            
            await interaction.response.send_message(
                f"✅ Status log channel set to {channel.mention}.",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid channel ID.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in set log channel modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class StatusReasonModal(discord.ui.Modal):
    """Modal for providing a reason when changing the bot's status."""
    
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Enter the reason for this status change",
        required=False,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, cog, guild_id, status):
        super().__init__(title="Status Change Reason")
        self.cog = cog
        self.guild_id = guild_id
        self.status = status
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            success, message = await self.cog.set_status(
                self.guild_id, 
                self.status, 
                self.reason.value, 
                interaction.user
            )
            
            if success:

                status_embed = self.cog._create_status_embed(interaction.guild)
                await interaction.message.edit(embed=status_embed, view=interaction.message.view)

                if interaction.user.id == await self.cog.bot.is_owner(interaction.user):
                    if self.status == "online":
                        await self.cog.bot.change_presence(status=discord.Status.online)
                    elif self.status == "maintenance":
                        await self.cog.bot.change_presence(
                            status=discord.Status.idle,
                            activity=discord.Activity(
                                type=discord.ActivityType.playing,
                                name="Maintenance Mode"
                            )
                        )
                    elif self.status == "off":
                        await self.cog.bot.change_presence(status=discord.Status.dnd)
                
                embed = discord.Embed(
                    title="✅ Status Updated",
                    description=f"Bot status changed to **{self.status.upper()}**.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description=message,
                    color=discord.Color.red()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in status reason modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    """Add the status manager cog to the bot."""
    await bot.add_cog(StatusManagerCog(bot))
    logger.info("Status manager cog loaded")