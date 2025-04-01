import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
import random
from typing import List, Dict, Optional, Union
import datetime

# Set up logging
logger = logging.getLogger('mass_messaging')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

def get_rainbow_color():
    """Generate a random rainbow color."""
    hue = random.random()
    # Convert HSV to RGB (S and V are at 100%)
    h = hue
    s = 0.8  # A bit desaturated for better readability
    v = 0.9  # Not too bright
    
    # HSV to RGB conversion
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    
    if i % 6 == 0:
        r, g, b = v, t, p
    elif i % 6 == 1:
        r, g, b = q, v, p
    elif i % 6 == 2:
        r, g, b = p, v, t
    elif i % 6 == 3:
        r, g, b = p, q, v
    elif i % 6 == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    
    # Convert to int color
    return int(r * 255) << 16 | int(g * 255) << 8 | int(b * 255)

class MassMessagingCog(commands.Cog):
    """Cog for sending mass messages to all members in a guild."""
    
    def __init__(self, bot):
        self.bot = bot
        self.pending_messages = {}  # {user_id: {guild_id: MessageData}}
        logger.info("Mass Messaging cog initialized")
    
    class MessageData:
        """Class to store message data during creation/editing."""
        def __init__(self):
            self.title = ""
            self.description = ""
            self.color = 0x5865F2  # Discord blue
            self.fields = []  # List of (name, value, inline) tuples
            self.footer = ""
            self.image_url = ""
            self.thumbnail_url = ""
            self.timestamp = True
            # Additional options
            self.include_roles = []  # List of role IDs to include
            self.exclude_roles = []  # List of role IDs to exclude
            self.target_role_id = None  # Single role ID to target specifically (priority over include/exclude)
            self.dry_run = False  # If True, just show preview without sending
    
    def get_user_message_data(self, user_id, guild_id):
        """Get a user's pending message data for a specific guild."""
        user_id = str(user_id)
        guild_id = str(guild_id)
        
        if user_id not in self.pending_messages:
            self.pending_messages[user_id] = {}
        
        if guild_id not in self.pending_messages[user_id]:
            self.pending_messages[user_id][guild_id] = self.MessageData()
        
        return self.pending_messages[user_id][guild_id]
    
    def create_embed_from_data(self, message_data):
        """Create a Discord embed from the message data."""
        embed = discord.Embed(
            title=message_data.title,
            description=message_data.description,
            color=message_data.color
        )
        
        # Add fields
        for name, value, inline in message_data.fields:
            embed.add_field(name=name, value=value, inline=inline)
        
        # Set footer
        if message_data.footer:
            embed.set_footer(text=message_data.footer)
        
        # Set images
        if message_data.image_url:
            embed.set_image(url=message_data.image_url)
        
        if message_data.thumbnail_url:
            embed.set_thumbnail(url=message_data.thumbnail_url)
        
        # Set timestamp
        if message_data.timestamp:
            embed.timestamp = datetime.datetime.now()
        
        return embed
    
    async def is_admin(self, interaction: discord.Interaction):
        """Check if the user has admin permissions (same as /addlevel)."""
        return await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id)
    
    @app_commands.command(
        name="sendtoall",
        description="Send an embedded message to all server members via DM (Admin only)"
    )
    async def sendtoall(self, interaction: discord.Interaction):
        """
        Send an embedded message to all members in the server.
        This command has the same permission requirements as /addlevel.
        """
        # Check admin permissions like /addlevel
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", 
                ephemeral=True
            )
            return
        
        # Initialize message data
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        message_data = self.get_user_message_data(user_id, guild_id)
        
        # Create the base embed for preview
        embed = discord.Embed(
            title="Mass Message Creator",
            description="Use the buttons below to customize your message that will be sent to all members.",
            color=discord.Color.blue()
        )
        
        # Add instructions
        embed.add_field(
            name="How to use",
            value="1. Click 'Set Content' to add title and description\n"
                  "2. Customize with fields, footer, or images\n"
                  "3. Use filter options to target specific roles\n"
                  "4. Preview when ready\n"
                  "5. Send to all members",
            inline=False
        )
        
        # Create view with buttons
        view = MassMessageBuilderView(self, user_id, guild_id)
        
        # Send the initial message
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"User {interaction.user.id} opened the mass message creator")


class MassMessageBuilderView(discord.ui.View):
    """View with buttons for building a mass message."""
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=600)  # 10 minute timeout
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
    
    @discord.ui.button(label="Set Content", style=discord.ButtonStyle.primary, row=0)
    async def set_content_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the message title and description."""
        await interaction.response.send_modal(MassMessageContentModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.secondary, row=0)
    async def add_field_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to add a field to the message."""
        await interaction.response.send_modal(MassMessageFieldModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Footer", style=discord.ButtonStyle.secondary, row=0)
    async def set_footer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the message footer."""
        await interaction.response.send_modal(MassMessageFooterModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Set Images", style=discord.ButtonStyle.secondary, row=1)
    async def set_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set the message images."""
        await interaction.response.send_modal(MassMessageImageModal(self.cog, self.user_id, self.guild_id))
    
    @discord.ui.button(label="Toggle Timestamp", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_timestamp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle whether to include a timestamp in the message."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        message_data.timestamp = not message_data.timestamp
        
        await interaction.response.edit_message(
            content=f"Timestamp {'enabled' if message_data.timestamp else 'disabled'}. Use 'Preview' to see the changes.",
            view=self
        )
    
    @discord.ui.button(label="Set Filters", style=discord.ButtonStyle.secondary, row=1)
    async def set_filters_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a separate UI to filter which members receive the message."""
        guild = self.cog.bot.get_guild(int(self.guild_id))
        if not guild:
            await interaction.response.send_message("Guild not found.", ephemeral=True)
            return
        
        # Get current filter settings
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Create embed with current filters
        embed = discord.Embed(
            title="Message Recipient Filters",
            description="Choose which members should receive this message.\n\n"
                       "Note: Users with DMs disabled will not receive the message.",
            color=discord.Color.gold()
        )
        
        # Show current include/exclude roles
        include_role_mentions = []
        for role_id in message_data.include_roles:
            role = guild.get_role(int(role_id))
            if role:
                include_role_mentions.append(role.mention)
        
        exclude_role_mentions = []
        for role_id in message_data.exclude_roles:
            role = guild.get_role(int(role_id))
            if role:
                exclude_role_mentions.append(role.mention)
        
        embed.add_field(
            name="Include Roles",
            value=", ".join(include_role_mentions) if include_role_mentions else "All roles (no filter)",
            inline=False
        )
        
        embed.add_field(
            name="Exclude Roles",
            value=", ".join(exclude_role_mentions) if exclude_role_mentions else "No roles excluded",
            inline=False
        )
        
        # Show target role if set (this takes priority over include/exclude)
        if message_data.target_role_id:
            target_role = guild.get_role(int(message_data.target_role_id))
            if target_role:
                embed.add_field(
                    name="🎯 Target Role",
                    value=f"Only sending to: {target_role.mention}\n(This overrides include/exclude settings)",
                    inline=False
                )
                embed.color = discord.Color.green()  # Change color to indicate targeting mode
        
        # Calculate estimated recipients
        member_count = 0
        for member in guild.members:
            if self._should_send_to_member(member, message_data):
                member_count += 1
        
        embed.add_field(
            name="Estimated Recipients",
            value=f"Approximately {member_count} members will receive this message",
            inline=False
        )
        
        # Create view with role filter options
        view = MassMessageFilterView(self.cog, self.user_id, self.guild_id, self)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Target", style=discord.ButtonStyle.blurple, row=1)
    async def target_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a modal to select a specific target role for the message."""
        await interaction.response.send_modal(MassMessageTargetModal(
            self.cog, self.user_id, self.guild_id, parent_view=self
        ))
    
    @discord.ui.button(label="Preview", style=discord.ButtonStyle.primary, row=2)
    async def preview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show a preview of the message."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        if not message_data.title and not message_data.description:
            await interaction.response.send_message(
                "Please set at least a title or description first.", 
                ephemeral=True
            )
            return
        
        # Create embed from data
        embed = self.cog.create_embed_from_data(message_data)
        
        # Create a preview view
        view = MassMessagePreviewView(self.cog, self.user_id, self.guild_id, self)
        
        await interaction.response.edit_message(
            content="📬 **Here's how your message will look:**",
            embed=embed,
            view=view
        )
    
    @discord.ui.button(label="Send to All", style=discord.ButtonStyle.danger, row=2)
    async def send_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send the message to all members after confirmation."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        if not message_data.title and not message_data.description:
            await interaction.response.send_message(
                "Please set at least a title or description first.", 
                ephemeral=True
            )
            return
        
        # Create confirmation view
        view = MassMessageConfirmView(self.cog, self.user_id, self.guild_id, self)
        
        await interaction.response.edit_message(
            content="⚠️ **Are you sure you want to send this message to all members?**\n"
                   "This action cannot be undone and will send DMs to all members who have DMs enabled.",
            view=view
        )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the message creation process."""
        user_id = str(self.user_id)
        guild_id = str(self.guild_id)
        
        # Clean up
        if user_id in self.cog.pending_messages:
            if guild_id in self.cog.pending_messages[user_id]:
                del self.cog.pending_messages[user_id][guild_id]
        
        await interaction.response.edit_message(
            content="Mass message creation cancelled.",
            embed=None,
            view=None
        )
    
    def _should_send_to_member(self, member, message_data):
        """Check if a message should be sent to this member based on filters."""
        # Skip bots
        if member.bot:
            return False
        
        # Target role filter (takes priority over include/exclude)
        if message_data.target_role_id:
            # Only send to members with this specific role
            for role in member.roles:
                if str(role.id) == message_data.target_role_id:
                    return True
            # If we get here, member doesn't have the target role
            return False
        
        # Include filter
        if message_data.include_roles:
            # Only include members with at least one of the specified roles
            has_included_role = False
            for role in member.roles:
                if str(role.id) in message_data.include_roles:
                    has_included_role = True
                    break
            
            if not has_included_role:
                return False
        
        # Exclude filter
        if message_data.exclude_roles:
            # Exclude members with any of the specified roles
            for role in member.roles:
                if str(role.id) in message_data.exclude_roles:
                    return False
        
        return True


class MassMessageContentModal(discord.ui.Modal, title="Set Message Content"):
    """Modal for setting the title and description of a mass message."""
    
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="Enter the title for your message",
        required=False,
        max_length=256
    )
    
    description_input = discord.ui.TextInput(
        label="Message Content",
        placeholder="Enter the main content of your message",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Set initial values
        message_data = self.cog.get_user_message_data(user_id, guild_id)
        if message_data.title:
            self.title_input.default = message_data.title
        if message_data.description:
            self.description_input.default = message_data.description
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Update message data
        message_data.title = self.title_input.value
        message_data.description = self.description_input.value
        
        # Create a fresh color for the message
        message_data.color = get_rainbow_color()
        
        # Create view
        view = MassMessageBuilderView(self.cog, self.user_id, self.guild_id)
        
        # Create preview embed
        embed = self.cog.create_embed_from_data(message_data)
        
        await interaction.response.edit_message(
            content="✅ Content updated! Preview:",
            embed=embed,
            view=view
        )


class MassMessageFieldModal(discord.ui.Modal, title="Add Message Field"):
    """Modal for adding a field to a mass message."""
    
    field_name = discord.ui.TextInput(
        label="Field Name",
        placeholder="Enter the field name",
        required=True,
        max_length=256
    )
    
    field_value = discord.ui.TextInput(
        label="Field Value",
        placeholder="Enter the field content",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1024
    )
    
    field_inline = discord.ui.TextInput(
        label="Inline? (yes/no)",
        placeholder="Type 'yes' for inline fields or 'no' for full-width",
        required=True,
        default="yes",
        max_length=3
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Process inline option
        is_inline = self.field_inline.value.lower() in ('yes', 'y', 'true')
        
        # Add field to the message data
        message_data.fields.append((self.field_name.value, self.field_value.value, is_inline))
        
        # Create view
        view = MassMessageBuilderView(self.cog, self.user_id, self.guild_id)
        
        # Create preview embed
        embed = self.cog.create_embed_from_data(message_data)
        
        await interaction.response.edit_message(
            content="✅ Field added! Preview:",
            embed=embed,
            view=view
        )


class MassMessageFooterModal(discord.ui.Modal, title="Set Message Footer"):
    """Modal for setting the footer of a mass message."""
    
    footer_text = discord.ui.TextInput(
        label="Footer Text",
        placeholder="Enter the footer text for your message",
        required=True,
        max_length=2048
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Set initial value
        message_data = self.cog.get_user_message_data(user_id, guild_id)
        if message_data.footer:
            self.footer_text.default = message_data.footer
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Update message data
        message_data.footer = self.footer_text.value
        
        # Create view
        view = MassMessageBuilderView(self.cog, self.user_id, self.guild_id)
        
        # Create preview embed
        embed = self.cog.create_embed_from_data(message_data)
        
        await interaction.response.edit_message(
            content="✅ Footer updated! Preview:",
            embed=embed,
            view=view
        )


class MassMessageImageModal(discord.ui.Modal, title="Set Message Images"):
    """Modal for setting the images of a mass message."""
    
    image_url = discord.ui.TextInput(
        label="Main Image URL",
        placeholder="Enter URL for the main image (leave empty to remove)",
        required=False
    )
    
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail Image URL",
        placeholder="Enter URL for the thumbnail image (leave empty to remove)",
        required=False
    )
    
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        # Set initial values
        message_data = self.cog.get_user_message_data(user_id, guild_id)
        if message_data.image_url:
            self.image_url.default = message_data.image_url
        if message_data.thumbnail_url:
            self.thumbnail_url.default = message_data.thumbnail_url
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Update message data
        message_data.image_url = self.image_url.value
        message_data.thumbnail_url = self.thumbnail_url.value
        
        # Create view
        view = MassMessageBuilderView(self.cog, self.user_id, self.guild_id)
        
        # Create preview embed
        embed = self.cog.create_embed_from_data(message_data)
        
        await interaction.response.edit_message(
            content="✅ Images updated! Preview:",
            embed=embed,
            view=view
        )


class MassMessageFilterView(discord.ui.View):
    """View for setting role filters for mass messages."""
    
    def __init__(self, cog, user_id, guild_id, parent_view):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.parent_view = parent_view
    
    @discord.ui.button(label="Include Role", style=discord.ButtonStyle.primary, row=0)
    async def include_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a modal to select roles to include."""
        await interaction.response.send_modal(MassMessageRoleModal(
            self.cog, self.user_id, self.guild_id, is_include=True, parent_view=self
        ))
    
    @discord.ui.button(label="Exclude Role", style=discord.ButtonStyle.secondary, row=0)
    async def exclude_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a modal to select roles to exclude."""
        await interaction.response.send_modal(MassMessageRoleModal(
            self.cog, self.user_id, self.guild_id, is_include=False, parent_view=self
        ))
    
    @discord.ui.button(label="Target Role", style=discord.ButtonStyle.success, row=1)
    async def target_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a modal to select a specific target role (overrides include/exclude)."""
        await interaction.response.send_modal(MassMessageTargetModal(
            self.cog, self.user_id, self.guild_id, parent_view=self
        ))
    
    @discord.ui.button(label="Clear Filters", style=discord.ButtonStyle.danger, row=0)
    async def clear_filters_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear all role filters."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        message_data.include_roles = []
        message_data.exclude_roles = []
        message_data.target_role_id = None
        
        # Return to parent view
        await interaction.response.edit_message(
            content="All filters cleared! Message will be sent to all members.",
            view=self.parent_view
        )
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main message builder view."""
        # Create preview embed
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        embed = self.cog.create_embed_from_data(message_data)
        
        await interaction.response.edit_message(
            content="Filters updated! Preview:",
            embed=embed,
            view=self.parent_view
        )


class MassMessageTargetModal(discord.ui.Modal, title="Target Specific Role"):
    """Modal for selecting a single target role."""
    
    role_id = discord.ui.TextInput(
        label="Role ID",
        placeholder="Enter a single role ID (e.g. 123456789012)",
        required=True
    )
    
    def __init__(self, cog, user_id, guild_id, parent_view):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.parent_view = parent_view
        
        # Set initial value if already set
        message_data = self.cog.get_user_message_data(user_id, guild_id)
        if message_data.target_role_id:
            self.role_id.default = message_data.target_role_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Set target role ID (this overrides include/exclude filters)
        target_role_id = self.role_id.value.strip()
        message_data.target_role_id = target_role_id
        
        # Get guild
        guild = self.cog.bot.get_guild(int(self.guild_id))
        if not guild:
            await interaction.response.send_message("Guild not found.", ephemeral=True)
            return
        
        # Check if role exists
        target_role = None
        try:
            target_role = guild.get_role(int(target_role_id))
        except ValueError:
            pass
        
        if not target_role:
            await interaction.response.send_message(
                f"Role with ID {target_role_id} not found. Please try again with a valid role ID.", 
                ephemeral=True
            )
            return
        
        # Create embed with updated filters
        embed = discord.Embed(
            title="Message Recipient Filters",
            description="Choose which members should receive this message.\n\n"
                       "Note: Users with DMs disabled will not receive the message.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Target Role Set",
            value=f"Message will be sent **only** to members with the {target_role.mention} role.",
            inline=False
        )
        
        # Calculate estimated recipients
        member_count = 0
        for member in guild.members:
            if target_role in member.roles and not member.bot:
                member_count += 1
        
        embed.add_field(
            name="Estimated Recipients",
            value=f"Approximately {member_count} members will receive this message",
            inline=False
        )
        
        embed.set_footer(text="Note: Target role overrides include/exclude filters")
        
        await interaction.response.edit_message(
            embed=embed,
            view=self.parent_view
        )


class MassMessageRoleModal(discord.ui.Modal, title="Select Roles"):
    """Modal for selecting roles to include or exclude."""
    
    role_ids = discord.ui.TextInput(
        label="Role IDs",
        placeholder="Enter role IDs separated by commas (e.g. 123456,789012)",
        required=False,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, cog, user_id, guild_id, is_include, parent_view):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.is_include = is_include
        self.parent_view = parent_view
        
        # Set modal title
        self.title = "Select Roles to Include" if is_include else "Select Roles to Exclude"
        
        # Set initial values
        message_data = self.cog.get_user_message_data(user_id, guild_id)
        role_list = message_data.include_roles if is_include else message_data.exclude_roles
        if role_list:
            self.role_ids.default = ",".join(role_list)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        
        # Process role IDs
        if self.role_ids.value.strip():
            role_ids = [role_id.strip() for role_id in self.role_ids.value.split(',')]
        else:
            role_ids = []
        
        # Update message data
        if self.is_include:
            message_data.include_roles = role_ids
        else:
            message_data.exclude_roles = role_ids
        
        # Get guild
        guild = self.cog.bot.get_guild(int(self.guild_id))
        if not guild:
            await interaction.response.send_message("Guild not found.", ephemeral=True)
            return
        
        # Create embed with current filters
        embed = discord.Embed(
            title="Message Recipient Filters",
            description="Choose which members should receive this message.\n\n"
                       "Note: Users with DMs disabled will not receive the message.",
            color=discord.Color.gold()
        )
        
        # Show current include/exclude roles
        include_role_mentions = []
        for role_id in message_data.include_roles:
            try:
                role = guild.get_role(int(role_id))
                if role:
                    include_role_mentions.append(role.mention)
            except ValueError:
                # Skip invalid role IDs
                pass
        
        exclude_role_mentions = []
        for role_id in message_data.exclude_roles:
            try:
                role = guild.get_role(int(role_id))
                if role:
                    exclude_role_mentions.append(role.mention)
            except ValueError:
                # Skip invalid role IDs
                pass
        
        embed.add_field(
            name="Include Roles",
            value=", ".join(include_role_mentions) if include_role_mentions else "All roles (no filter)",
            inline=False
        )
        
        embed.add_field(
            name="Exclude Roles",
            value=", ".join(exclude_role_mentions) if exclude_role_mentions else "No roles excluded",
            inline=False
        )
        
        # Calculate estimated recipients
        member_count = 0
        for member in guild.members:
            if self.parent_view.parent_view._should_send_to_member(member, message_data):
                member_count += 1
        
        embed.add_field(
            name="Estimated Recipients",
            value=f"Approximately {member_count} members will receive this message",
            inline=False
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=self.parent_view
        )


class MassMessagePreviewView(discord.ui.View):
    """View for previewing a mass message before sending."""
    
    def __init__(self, cog, user_id, guild_id, parent_view):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.parent_view = parent_view
    
    @discord.ui.button(label="Back to Editor", style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main message builder view."""
        # Create empty embed for the builder
        embed = discord.Embed(
            title="Mass Message Creator",
            description="Use the buttons below to customize your message that will be sent to all members.",
            color=discord.Color.blue()
        )
        
        # Add instructions
        embed.add_field(
            name="How to use",
            value="1. Click 'Set Content' to add title and description\n"
                  "2. Customize with fields, footer, or images\n"
                  "3. Use filter options to target specific roles\n"
                  "4. Preview when ready\n"
                  "5. Send to all members",
            inline=False
        )
        
        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=self.parent_view
        )
    
    @discord.ui.button(label="Send to All", style=discord.ButtonStyle.danger, row=0)
    async def send_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send the message to all members after confirmation."""
        # Create confirmation view
        view = MassMessageConfirmView(self.cog, self.user_id, self.guild_id, self.parent_view)
        
        await interaction.response.edit_message(
            content="⚠️ **Are you sure you want to send this message to all members?**\n"
                   "This action cannot be undone and will send DMs to all members who have DMs enabled.",
            view=view
        )


class MassMessageConfirmView(discord.ui.View):
    """View for confirming before sending a mass message."""
    
    def __init__(self, cog, user_id, guild_id, parent_view):
        super().__init__(timeout=180)  # 3 minute timeout
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.parent_view = parent_view
    
    @discord.ui.button(label="Yes, Send to All", style=discord.ButtonStyle.danger, row=0)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm and begin sending the message to all members."""
        guild = self.cog.bot.get_guild(int(self.guild_id))
        if not guild:
            await interaction.response.send_message("Guild not found.", ephemeral=True)
            return
        
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        embed = self.cog.create_embed_from_data(message_data)
        
        # Acknowledge the action is starting
        progress_embed = discord.Embed(
            title="Mass Message Sending",
            description="Starting to send your message to all members...",
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(
            content="",
            embed=progress_embed,
            view=None
        )
        
        # Count how many we'll try to send to
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        target_members = []
        
        for member in guild.members:
            if self.parent_view._should_send_to_member(member, message_data):
                target_members.append(member)
        
        # Start a background task to send the messages
        self.cog.bot.loop.create_task(
            self._send_mass_message(interaction, guild, target_members, embed, message_data)
        )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel sending and return to the builder."""
        # Create preview embed
        message_data = self.cog.get_user_message_data(self.user_id, self.guild_id)
        embed = self.cog.create_embed_from_data(message_data)
        
        await interaction.response.edit_message(
            content="Sending cancelled. Preview:",
            embed=embed,
            view=MassMessagePreviewView(self.cog, self.user_id, self.guild_id, self.parent_view)
        )
    
    async def _send_mass_message(self, interaction, guild, target_members, embed, message_data):
        """Send the message to all target members and update progress."""
        total_members = len(target_members)
        success_count = 0
        fail_count = 0
        
        # Start time for tracking
        start_time = datetime.datetime.now()
        
        # Create progress embed
        progress_embed = discord.Embed(
            title="Mass Message Sending",
            description=f"Sending message to {total_members} members...",
            color=discord.Color.blue()
        )
        
        progress_embed.add_field(
            name="Progress",
            value=f"0% complete (0/{total_members})",
            inline=False
        )
        
        progress_embed.add_field(
            name="Statistics",
            value=f"✅ Successfully sent: 0\n❌ Failed to send: 0",
            inline=False
        )
        
        await interaction.edit_original_response(embed=progress_embed)
        
        # Process members in batches to avoid rate limits
        for index, member in enumerate(target_members):
            try:
                await member.send(embed=embed)
                success_count += 1
                logger.info(f"Successfully sent mass message to {member.name} ({member.id})")
                
            except (discord.Forbidden, discord.HTTPException) as e:
                fail_count += 1
                logger.warning(f"Failed to send mass message to {member.name} ({member.id}): {e}")
                
            except Exception as e:
                fail_count += 1
                logger.error(f"Unexpected error sending message to {member.name} ({member.id}): {e}")
            
            # Update progress every 10 members or at the end
            if (index + 1) % 10 == 0 or index + 1 == total_members:
                progress_percent = int((index + 1) / total_members * 100)
                elapsed = (datetime.datetime.now() - start_time).total_seconds()
                
                progress_embed = discord.Embed(
                    title="Mass Message Sending",
                    description=f"Sending message to {total_members} members...",
                    color=discord.Color.blue()
                )
                
                progress_embed.add_field(
                    name="Progress",
                    value=f"{progress_percent}% complete ({index + 1}/{total_members})",
                    inline=False
                )
                
                progress_embed.add_field(
                    name="Statistics",
                    value=f"✅ Successfully sent: {success_count}\n❌ Failed to send: {fail_count}",
                    inline=False
                )
                
                if index + 1 < total_members:
                    # Calculate estimated time remaining
                    if index + 1 > 0:
                        time_per_member = elapsed / (index + 1)
                        remaining_members = total_members - (index + 1)
                        time_remaining = time_per_member * remaining_members
                        
                        minutes, seconds = divmod(int(time_remaining), 60)
                        time_str = f"{minutes}m {seconds}s"
                        
                        progress_embed.add_field(
                            name="Estimated Time Remaining",
                            value=f"~{time_str}",
                            inline=False
                        )
                
                await interaction.edit_original_response(embed=progress_embed)
                
                # Sleep briefly to avoid rate limits
                await asyncio.sleep(0.5)
        
        # Final update
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        minutes, seconds = divmod(int(elapsed_time), 60)
        
        complete_embed = discord.Embed(
            title="Mass Message Sending Complete",
            description=f"Finished sending messages to {total_members} members.",
            color=discord.Color.green()
        )
        
        complete_embed.add_field(
            name="Results",
            value=f"✅ Successfully sent: {success_count}\n❌ Failed to send: {fail_count}",
            inline=False
        )
        
        complete_embed.add_field(
            name="Time Taken",
            value=f"{minutes}m {seconds}s",
            inline=False
        )
        
        complete_embed.set_footer(text="Note: Failed sends are usually due to users having DMs disabled")
        
        await interaction.edit_original_response(embed=complete_embed)


async def setup(bot):
    """Add the mass messaging cog to the bot."""
    await bot.add_cog(MassMessagingCog(bot))
    logger.info("Mass Messaging cog loaded")