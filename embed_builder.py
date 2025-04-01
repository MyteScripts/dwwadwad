import discord
from discord import app_commands
from discord.ext import commands
import logging
import datetime
import json
import asyncio
import re

class EmbedBuilderCog(commands.Cog):
    """Cog for creating and sending customized embeds"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('embed_builder')
        
        # Store pending embeds being edited by users
        # Structure: {user_id: {guild_id: EmbedData}}
        self.pending_embeds = {}
    
    class EmbedData:
        """Class to store embed data during creation/editing."""
        def __init__(self):
            self.title = ""
            self.description = ""
            self.color = 0x5865F2  # Discord blue
            self.fields = []  # List of (name, value, inline) tuples
            self.footer = ""
            self.image_url = ""
            self.thumbnail_url = ""
            self.author_name = ""
            self.author_icon_url = ""
            self.timestamp = True
    
    def get_user_embed_data(self, user_id, guild_id):
        """Get a user's pending embed data for a specific guild."""
        user_id = str(user_id)
        guild_id = str(guild_id)
        
        if user_id not in self.pending_embeds:
            self.pending_embeds[user_id] = {}
        
        if guild_id not in self.pending_embeds[user_id]:
            self.pending_embeds[user_id][guild_id] = self.EmbedData()
        
        return self.pending_embeds[user_id][guild_id]
    
    def color_from_string(self, color_str):
        """Convert a color string to a Discord color.
        
        Args:
            color_str: A color string (e.g., "red", "blue", "gold", "#FF0000")
        
        Returns:
            discord.Color or int: The color value
        """
        color_str = color_str.lower()
        
        # Check for hex code
        if color_str.startswith('#'):
            try:
                return int(color_str[1:], 16)
            except ValueError:
                pass
        
        # Check for named colors
        color_map = {
            'red': discord.Color.red(),
            'green': discord.Color.green(),
            'blue': discord.Color.blue(),
            'yellow': discord.Color.yellow(),
            'orange': discord.Color.orange(),
            'purple': discord.Color.purple(),
            'gold': discord.Color.gold(),
            'black': 0x000000,
            'white': 0xFFFFFF,
            'pink': 0xFFC0CB,
            'teal': 0x008080,
            'navy': 0x000080,
            'lime': 0x00FF00,
            'magenta': 0xFF00FF,
            'cyan': 0x00FFFF,
            'brown': 0x8B4513,
            'gray': 0x808080,
            'grey': 0x808080,
            'default': 0x5865F2  # Discord blue
        }
        
        return color_map.get(color_str, 0x5865F2)
    
    @app_commands.command(name="embedsend", description="Create and send an embed message")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_send(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Create and send an embed message.
        
        Args:
            interaction: The interaction that triggered this command
            channel: The channel to send the embed to (defaults to current channel)
        """
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        # Check permissions
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"I don't have permission to send messages in {target_channel.mention}.",
                ephemeral=True
            )
            return
        
        # Get the user's embed data
        embed_data = self.get_user_embed_data(interaction.user.id, interaction.guild.id)
        
        # Create the embed builder view
        view = EmbedBuilderView(self, interaction.user.id, interaction.guild.id, target_channel)
        
        # Create the preview embed
        embed = self.create_embed_from_data(embed_data, interaction.user)
        
        # Send the initial response
        await interaction.response.send_message(
            "Use the buttons below to customize your embed, then click Send when ready:",
            embed=embed,
            view=view,
            ephemeral=True
        )
    
    def create_embed_from_data(self, embed_data, user=None):
        """Create a Discord embed from the provided embed data.
        
        Args:
            embed_data: The EmbedData object
            user: The user creating the embed (for author info if needed)
            
        Returns:
            discord.Embed: The created embed
        """
        embed = discord.Embed(
            title=embed_data.title or None,
            description=embed_data.description or None,
            color=embed_data.color
        )
        
        # Add fields
        for name, value, inline in embed_data.fields:
            if name and value:
                embed.add_field(name=name, value=value, inline=inline)
        
        # Add footer
        if embed_data.footer:
            embed.set_footer(text=embed_data.footer)
        
        # Add image
        if embed_data.image_url:
            embed.set_image(url=embed_data.image_url)
        
        # Add thumbnail
        if embed_data.thumbnail_url:
            embed.set_thumbnail(url=embed_data.thumbnail_url)
        
        # Add author
        if embed_data.author_name:
            embed.set_author(
                name=embed_data.author_name,
                icon_url=embed_data.author_icon_url or None
            )
        elif user:
            # Default to the user's name and avatar if no author is specified
            embed.set_author(
                name=user.display_name,
                icon_url=user.display_avatar.url
            )
        
        # Add timestamp
        if embed_data.timestamp:
            embed.timestamp = datetime.datetime.now()
        
        return embed


class EmbedBuilderView(discord.ui.View):
    """View with buttons for building embeds."""
    
    def __init__(self, cog, user_id, guild_id, target_channel):
        super().__init__(timeout=600)  # 10 minute timeout
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.target_channel = target_channel
    
    @discord.ui.button(label="Set Title", style=discord.ButtonStyle.primary, row=0)
    async def set_title_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the embed title."""
        await interaction.response.send_modal(EmbedTitleModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Description", style=discord.ButtonStyle.primary, row=0)
    async def set_description_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the embed description."""
        await interaction.response.send_modal(EmbedDescriptionModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Color", style=discord.ButtonStyle.primary, row=0)
    async def set_color_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the embed color."""
        await interaction.response.send_modal(EmbedColorModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.secondary, row=1)
    async def add_field_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to add a field to the embed."""
        await interaction.response.send_modal(EmbedFieldModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Footer", style=discord.ButtonStyle.secondary, row=1)
    async def set_footer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the embed footer."""
        await interaction.response.send_modal(EmbedFooterModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Images", style=discord.ButtonStyle.secondary, row=1)
    async def set_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the embed image and thumbnail."""
        await interaction.response.send_modal(EmbedImageModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Author", style=discord.ButtonStyle.secondary, row=2)
    async def set_author_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the embed author information."""
        await interaction.response.send_modal(EmbedAuthorModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Toggle Timestamp", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_timestamp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle whether to include a timestamp in the embed."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Toggle timestamp
        embed_data.timestamp = not embed_data.timestamp
        
        # Update the preview
        embed = self.cog.create_embed_from_data(embed_data)
        
        await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, row=2)
    async def clear_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear all embed settings."""
        # Reset the user's embed data
        self.cog.pending_embeds[str(self.user_id)][str(self.guild_id)] = self.cog.EmbedData()
        
        # Get the new embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the preview
        embed = self.cog.create_embed_from_data(embed_data)
        
        await interaction.response.edit_message(content="All embed settings have been cleared. Use the buttons to customize your embed:", embed=embed)
    
    @discord.ui.button(label="Send Embed", style=discord.ButtonStyle.success, row=3)
    async def send_embed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send the customized embed to the target channel."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Create the embed
        embed = self.cog.create_embed_from_data(embed_data)
        
        try:
            # Send the embed to the target channel
            await self.target_channel.send(embed=embed)
            
            # Confirm success
            await interaction.response.edit_message(
                content=f"✅ Embed sent to {self.target_channel.mention}!",
                embed=None,
                view=None
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"I don't have permission to send messages in {self.target_channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to send embed: {e}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel embed creation."""
        # Clean up
        if str(self.user_id) in self.cog.pending_embeds:
            if str(self.guild_id) in self.cog.pending_embeds[str(self.user_id)]:
                del self.cog.pending_embeds[str(self.user_id)][str(self.guild_id)]
        
        await interaction.response.edit_message(
            content="Embed creation cancelled.",
            embed=None,
            view=None
        )
    
    async def on_timeout(self):
        """Handle view timeout."""
        # Clean up
        if str(self.user_id) in self.cog.pending_embeds:
            if str(self.guild_id) in self.cog.pending_embeds[str(self.user_id)]:
                del self.cog.pending_embeds[str(self.user_id)][str(self.guild_id)]


class EmbedTitleModal(discord.ui.Modal, title="Set Embed Title"):
    """Modal for setting the embed title."""
    
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="Enter the title for your embed",
        required=False,
        max_length=256
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Pre-fill the field with current value
        embed_data = self.cog.get_user_embed_data(user_id, guild_id)
        if embed_data.title:
            self.title_input.default = embed_data.title
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the title
        embed_data.title = self.title_input.value
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


class EmbedDescriptionModal(discord.ui.Modal, title="Set Embed Description"):
    """Modal for setting the embed description."""
    
    description_input = discord.ui.TextInput(
        label="Description",
        placeholder="Enter the description for your embed",
        required=False,
        max_length=4000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Pre-fill the field with current value
        embed_data = self.cog.get_user_embed_data(user_id, guild_id)
        if embed_data.description:
            self.description_input.default = embed_data.description
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the description
        embed_data.description = self.description_input.value
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


class EmbedColorModal(discord.ui.Modal, title="Set Embed Color"):
    """Modal for setting the embed color."""
    
    color_input = discord.ui.TextInput(
        label="Color",
        placeholder="Enter a color name (e.g., red, blue) or hex code (e.g., #FF0000)",
        required=False
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Pre-fill the field with current value
        embed_data = self.cog.get_user_embed_data(user_id, guild_id)
        if embed_data.color:
            # Convert the color value to hex string
            hex_color = f"#{embed_data.color:06X}"
            self.color_input.default = hex_color
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the color
        if self.color_input.value:
            embed_data.color = self.cog.color_from_string(self.color_input.value)
        else:
            embed_data.color = 0x5865F2  # Default Discord blue
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


class EmbedFieldModal(discord.ui.Modal, title="Add Embed Field"):
    """Modal for adding a field to the embed."""
    
    field_name = discord.ui.TextInput(
        label="Field Name",
        placeholder="Enter the name/title for this field",
        required=True,
        max_length=256
    )
    
    field_value = discord.ui.TextInput(
        label="Field Value",
        placeholder="Enter the content for this field",
        required=True,
        max_length=1024,
        style=discord.TextStyle.paragraph
    )
    
    field_inline = discord.ui.TextInput(
        label="Inline (yes/no)",
        placeholder="Should this field be displayed inline? (yes/no)",
        required=False,
        default="yes"
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Determine if the field should be inline
        inline = self.field_inline.value.lower() in ['yes', 'y', 'true', 't', '1']
        
        # Add the field
        if len(embed_data.fields) < 25:  # Discord limits embeds to 25 fields
            embed_data.fields.append((self.field_name.value, self.field_value.value, inline))
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


class EmbedFooterModal(discord.ui.Modal, title="Set Embed Footer"):
    """Modal for setting the embed footer."""
    
    footer_text = discord.ui.TextInput(
        label="Footer Text",
        placeholder="Enter the text for the footer",
        required=False,
        max_length=2048
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Pre-fill the field with current value
        embed_data = self.cog.get_user_embed_data(user_id, guild_id)
        if embed_data.footer:
            self.footer_text.default = embed_data.footer
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the footer
        embed_data.footer = self.footer_text.value
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


class EmbedImageModal(discord.ui.Modal, title="Set Embed Images"):
    """Modal for setting the embed image and thumbnail."""
    
    image_url = discord.ui.TextInput(
        label="Image URL",
        placeholder="Enter the URL for the main image",
        required=False
    )
    
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL",
        placeholder="Enter the URL for the thumbnail image",
        required=False
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Pre-fill the fields with current values
        embed_data = self.cog.get_user_embed_data(user_id, guild_id)
        if embed_data.image_url:
            self.image_url.default = embed_data.image_url
        if embed_data.thumbnail_url:
            self.thumbnail_url.default = embed_data.thumbnail_url
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the image and thumbnail
        embed_data.image_url = self.image_url.value
        embed_data.thumbnail_url = self.thumbnail_url.value
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


class EmbedAuthorModal(discord.ui.Modal, title="Set Embed Author"):
    """Modal for setting the embed author information."""
    
    author_name = discord.ui.TextInput(
        label="Author Name",
        placeholder="Enter the name for the author",
        required=False,
        max_length=256
    )
    
    author_icon_url = discord.ui.TextInput(
        label="Author Icon URL",
        placeholder="Enter the URL for the author icon",
        required=False
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Pre-fill the fields with current values
        embed_data = self.cog.get_user_embed_data(user_id, guild_id)
        if embed_data.author_name:
            self.author_name.default = embed_data.author_name
        if embed_data.author_icon_url:
            self.author_icon_url.default = embed_data.author_icon_url
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        # Get the user's embed data
        embed_data = self.cog.get_user_embed_data(self.user_id, self.guild_id)
        
        # Update the author information
        embed_data.author_name = self.author_name.value
        embed_data.author_icon_url = self.author_icon_url.value
        
        # Create the updated embed
        embed = self.cog.create_embed_from_data(embed_data, interaction.user)
        
        # Update the message
        await interaction.response.edit_message(embed=embed)


async def setup(bot):
    """Add the embed builder cog to the bot."""
    embed_builder_cog = EmbedBuilderCog(bot)
    await bot.add_cog(embed_builder_cog)
    return embed_builder_cog