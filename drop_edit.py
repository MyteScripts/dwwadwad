import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
from datetime import datetime
from logger import setup_logger

logger = setup_logger('drop_edit', 'bot.log')

class DropEditCog(commands.Cog):
    """Cog for managing XP and coin drops through a unified panel."""
    
    def __init__(self, bot):
        self.bot = bot
        self.level_cog = None
        self.coin_cog = None
        logger.info("Drop edit cog initialized")
    
    async def cog_load(self):
        """Called when the cog is loaded."""

        self.level_cog = self.bot.get_cog("LevelPanelCog")
        self.coin_cog = self.bot.get_cog("CoinPanelCog")
        logger.info("Drop edit cog loaded")
    
    @app_commands.command(
        name="dropedit", 
        description="Manage XP and coin drops in one place (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def drop_edit(self, interaction: discord.Interaction):
        """
        Open a panel to manage XP and coin drops with status indicators.
        """

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return

        embed = await self._create_status_embed(interaction.guild)

        view = DropEditView(self, interaction.guild)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Drop edit panel opened by {interaction.user.id}")
    
    async def _create_status_embed(self, guild):
        """Create a status embed with both XP and coin drop information."""
        guild_id = guild.id

        xp_status = "❌ Not Set Up"
        xp_details = "Use the 'Edit XP Drops' button to set up XP drops."
        xp_active = "❌ Inactive"
        
        if self.level_cog and hasattr(self.level_cog, 'xp_drop_settings') and guild_id in self.level_cog.xp_drop_settings:
            settings = self.level_cog.xp_drop_settings[guild_id]
            if settings.channel_id:
                channel = guild.get_channel(settings.channel_id)
                channel_mention = f"<#{settings.channel_id}>" if channel else f"Unknown (ID: {settings.channel_id})"
                
                xp_status = "✅ Set Up"
                xp_details = (
                    f"**Channel:** {channel_mention}\n"
                    f"**Range:** {settings.min_xp} - {settings.max_xp} XP\n"
                    f"**Frequency:** Every {settings.duration} {settings.time_unit}(s)"
                )
                
                if settings.is_active:
                    xp_active = "✅ Active"
                else:
                    xp_active = "❌ Inactive"

        coin_status = "❌ Not Set Up"
        coin_details = "Use the 'Edit Coin Drops' button to set up coin drops."
        coin_active = "❌ Inactive"
        
        if self.coin_cog and hasattr(self.coin_cog, 'coin_drop_settings') and guild_id in self.coin_cog.coin_drop_settings:
            settings = self.coin_cog.coin_drop_settings[guild_id]
            if settings.channel_id:
                channel = guild.get_channel(settings.channel_id)
                channel_mention = f"<#{settings.channel_id}>" if channel else f"Unknown (ID: {settings.channel_id})"
                
                coin_status = "✅ Set Up"
                coin_details = (
                    f"**Channel:** {channel_mention}\n"
                    f"**Range:** {settings.min_coins} - {settings.max_coins} coins\n"
                    f"**Frequency:** Every {settings.duration} {settings.time_unit}(s)"
                )
                
                if settings.is_active:
                    coin_active = "✅ Active"
                else:
                    coin_active = "❌ Inactive"

        embed = discord.Embed(
            title="Drop Management Panel",
            description="Manage XP and Coin drops from this panel.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="💫 XP Drop Status",
            value=xp_status,
            inline=True
        )
        
        embed.add_field(
            name="💫 XP Drops",
            value=xp_active,
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for spacing
        
        embed.add_field(
            name="💫 XP Drop Settings",
            value=xp_details,
            inline=False
        )

        embed.add_field(
            name="💰 Coin Drop Status",
            value=coin_status,
            inline=True
        )
        
        embed.add_field(
            name="💰 Coin Drops",
            value=coin_active,
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for spacing
        
        embed.add_field(
            name="💰 Coin Drop Settings",
            value=coin_details,
            inline=False
        )
        
        return embed

class DropEditView(discord.ui.View):
    """View with buttons for editing XP and coin drops."""
    
    def __init__(self, cog, guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild = guild
    
    @discord.ui.button(
        label="Edit XP Drops", 
        style=discord.ButtonStyle.primary,
        emoji="💫"
    )
    async def edit_xp_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit XP drop settings."""
        modal = EditXPDropsModal(self.cog, self.guild.id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Edit Coin Drops", 
        style=discord.ButtonStyle.primary,
        emoji="💰"
    )
    async def edit_coin_drops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit coin drop settings."""
        modal = EditCoinDropsModal(self.cog, self.guild.id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="XP Drops Active", 
        style=discord.ButtonStyle.green,
        emoji="✅",
        row=1
    )
    async def xp_drops_active_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to activate XP drops."""

        guild_id = self.guild.id
        level_cog = self.cog.level_cog
        
        if not hasattr(level_cog, 'xp_drop_settings') or guild_id not in level_cog.xp_drop_settings:
            await interaction.response.send_message(
                "❌ XP drops are not set up yet. Please use the 'Edit XP Drops' button first.",
                ephemeral=True
            )
            return
        
        settings = level_cog.xp_drop_settings[guild_id]
        if not settings.channel_id:
            await interaction.response.send_message(
                "❌ XP drops are not set up yet. Please use the 'Edit XP Drops' button first.",
                ephemeral=True
            )
            return

        if settings.is_active:
            await interaction.response.send_message(
                "✅ XP drops are already active.",
                ephemeral=True
            )
            return

        success, message = await level_cog.toggle_xp_drops(guild_id, restart=False)
        
        if success:
            embed = discord.Embed(
                title="✅ XP Drops Started",
                description=message,
                color=discord.Color.green()
            )

            status_embed = await self.cog._create_status_embed(self.guild)
            await interaction.message.edit(embed=status_embed, view=self)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=message,
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="XP Drops Inactive", 
        style=discord.ButtonStyle.red,
        emoji="❌",
        row=1
    )
    async def xp_drops_inactive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to deactivate XP drops."""

        guild_id = self.guild.id
        level_cog = self.cog.level_cog
        
        if not hasattr(level_cog, 'xp_drop_settings') or guild_id not in level_cog.xp_drop_settings:
            await interaction.response.send_message(
                "❌ XP drops are not set up yet.",
                ephemeral=True
            )
            return
        
        settings = level_cog.xp_drop_settings[guild_id]
        if not settings.is_active:
            await interaction.response.send_message(
                "❌ XP drops are already inactive.",
                ephemeral=True
            )
            return

        if settings.task is not None and not settings.task.done():
            settings.task.cancel()
            settings.task = None
        settings.is_active = False
        
        embed = discord.Embed(
            title="✅ XP Drops Stopped",
            description="XP drops have been stopped.",
            color=discord.Color.green()
        )

        status_embed = await self.cog._create_status_embed(self.guild)
        await interaction.message.edit(embed=status_embed, view=self)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="Coin Drops Active", 
        style=discord.ButtonStyle.green,
        emoji="✅",
        row=2
    )
    async def coin_drops_active_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to activate coin drops."""

        guild_id = self.guild.id
        coin_cog = self.cog.coin_cog
        
        if not hasattr(coin_cog, 'coin_drop_settings') or guild_id not in coin_cog.coin_drop_settings:
            await interaction.response.send_message(
                "❌ Coin drops are not set up yet. Please use the 'Edit Coin Drops' button first.",
                ephemeral=True
            )
            return
        
        settings = coin_cog.coin_drop_settings[guild_id]
        if not settings.channel_id:
            await interaction.response.send_message(
                "❌ Coin drops are not set up yet. Please use the 'Edit Coin Drops' button first.",
                ephemeral=True
            )
            return

        if settings.is_active:
            await interaction.response.send_message(
                "✅ Coin drops are already active.",
                ephemeral=True
            )
            return

        success, message = await coin_cog.toggle_coin_drops(guild_id, restart=False)
        
        if success:
            embed = discord.Embed(
                title="✅ Coin Drops Started",
                description=message,
                color=discord.Color.green()
            )

            status_embed = await self.cog._create_status_embed(self.guild)
            await interaction.message.edit(embed=status_embed, view=self)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=message,
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="Coin Drops Inactive", 
        style=discord.ButtonStyle.red,
        emoji="❌",
        row=2
    )
    async def coin_drops_inactive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to deactivate coin drops."""

        guild_id = self.guild.id
        coin_cog = self.cog.coin_cog
        
        if not hasattr(coin_cog, 'coin_drop_settings') or guild_id not in coin_cog.coin_drop_settings:
            await interaction.response.send_message(
                "❌ Coin drops are not set up yet.",
                ephemeral=True
            )
            return
        
        settings = coin_cog.coin_drop_settings[guild_id]
        if not settings.is_active:
            await interaction.response.send_message(
                "❌ Coin drops are already inactive.",
                ephemeral=True
            )
            return

        if settings.task is not None and not settings.task.done():
            settings.task.cancel()
            settings.task = None
        settings.is_active = False
        
        embed = discord.Embed(
            title="✅ Coin Drops Stopped",
            description="Coin drops have been stopped.",
            color=discord.Color.green()
        )

        status_embed = await self.cog._create_status_embed(self.guild)
        await interaction.message.edit(embed=status_embed, view=self)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="Refresh Status", 
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        row=3
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to refresh the status."""

        embed = await self.cog._create_status_embed(self.guild)
        await interaction.message.edit(embed=embed, view=self)
        
        await interaction.response.send_message(
            "✅ Status refreshed.",
            ephemeral=True
        )

class EditXPDropsModal(discord.ui.Modal, title="Edit XP Drops"):
    """Modal for editing XP drop settings."""
    
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

        level_cog = cog.level_cog
        if level_cog and hasattr(level_cog, 'xp_drop_settings') and guild_id in level_cog.xp_drop_settings:
            settings = level_cog.xp_drop_settings[guild_id]
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

            if min_xp < 1:
                await interaction.response.send_message(
                    "❌ Minimum XP must be at least 1.",
                    ephemeral=True
                )
                return
            
            if max_xp < min_xp:
                await interaction.response.send_message(
                    "❌ Maximum XP must be greater than minimum XP.",
                    ephemeral=True
                )
                return
            
            if duration < 1:
                await interaction.response.send_message(
                    "❌ Duration must be at least 1.",
                    ephemeral=True
                )
                return

            success, message = await self.cog.level_cog.set_xp_drop(
                self.guild_id,
                channel_id,
                min_xp,
                max_xp,
                duration,
                time_unit
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ XP Drops Updated",
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
                "❌ Please enter valid numbers for Channel ID, Min/Max XP, and Duration.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in edit XP drops modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class EditCoinDropsModal(discord.ui.Modal, title="Edit Coin Drops"):
    """Modal for editing coin drop settings."""
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID for drops",
        required=True
    )
    
    min_coins = discord.ui.TextInput(
        label="Minimum Coins",
        placeholder="Enter the minimum coins per drop (default: 5)",
        required=False,
        default="5"
    )
    
    max_coins = discord.ui.TextInput(
        label="Maximum Coins",
        placeholder="Enter the maximum coins per drop (default: 25)",
        required=False,
        default="25"
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

        coin_cog = cog.coin_cog
        if coin_cog and hasattr(coin_cog, 'coin_drop_settings') and guild_id in coin_cog.coin_drop_settings:
            settings = coin_cog.coin_drop_settings[guild_id]
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
            min_coins = float(self.min_coins.value or 5)
            max_coins = float(self.max_coins.value or 25)
            duration = int(self.duration.value or 1)
            time_unit = self.time_unit.value.lower() or "hour"

            if time_unit not in ["minute", "hour", "day"]:
                await interaction.response.send_message(
                    "❌ Time unit must be 'minute', 'hour', or 'day'.",
                    ephemeral=True
                )
                return

            if min_coins < 0.1:
                await interaction.response.send_message(
                    "❌ Minimum coins must be at least 0.1.",
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

            success, message = await self.cog.coin_cog.set_coin_drop(
                self.guild_id,
                channel_id,
                min_coins,
                max_coins,
                duration,
                time_unit
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Coin Drops Updated",
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
                "❌ Please enter valid numbers for Channel ID, Min/Max Coins, and Duration.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in edit coin drops modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    """Add the drop edit cog to the bot."""
    await bot.add_cog(DropEditCog(bot))