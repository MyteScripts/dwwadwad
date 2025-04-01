import discord
from discord import app_commands
from discord.ext import commands
import logging
import datetime
import json
import asyncio
import os
import random

# Set up logging
logger = logging.getLogger('ticket_system')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class TicketSystem(commands.Cog):
    """Cog for managing support tickets."""
    
    def __init__(self, bot):
        self.bot = bot
        self.ticket_counter = 0
        self.active_tickets = {}
        self.tickets_category_id = None
        self.tickets_log_channel_id = None
        self.support_role_id = None
        self.reports_channel_id = None
        self.suggestions_channel_id = None
        self.persistent_views_added = False
        
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Load ticket counter and active tickets
        self.load_ticket_data()
        
        # Load configuration
        self.load_config()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready. Sets up persistent views."""
        if not self.persistent_views_added:
            # Add the persistent view for ticket panels
            self.bot.add_view(TicketPanelView(self))
            # Add persistent view for ticket controls
            self.bot.add_view(TicketControlsView(self, None))
            self.persistent_views_added = True
            logger.info("Added persistent views for ticket system")
    
    def load_ticket_data(self):
        """Load ticket counter and active tickets from file."""
        try:
            if os.path.exists('data/tickets.json'):
                with open('data/tickets.json', 'r') as f:
                    data = json.load(f)
                    self.ticket_counter = data.get('counter', 0)
                    self.active_tickets = data.get('active_tickets', {})
                logger.info(f"Loaded ticket data. Counter: {self.ticket_counter}, Active tickets: {len(self.active_tickets)}")
            else:
                self.save_ticket_data()
        except Exception as e:
            logger.error(f"Error loading ticket data: {e}")
            self.save_ticket_data()
    
    def save_ticket_data(self):
        """Save ticket counter and active tickets to file."""
        try:
            data = {
                'counter': self.ticket_counter,
                'active_tickets': self.active_tickets
            }
            with open('data/tickets.json', 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Saved ticket data. Counter: {self.ticket_counter}, Active tickets: {len(self.active_tickets)}")
        except Exception as e:
            logger.error(f"Error saving ticket data: {e}")
    
    def load_config(self):
        """Load ticket system configuration from settings.json."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                self.tickets_category_id = settings.get('tickets_category_id')
                self.tickets_log_channel_id = settings.get('tickets_log_channel_id')
                self.support_role_id = settings.get('support_role_id')
                self.reports_channel_id = settings.get('reports_channel_id')
                self.suggestions_channel_id = settings.get('suggestions_channel_id')
            logger.info(f"Loaded ticket configuration. Category ID: {self.tickets_category_id}, Log Channel ID: {self.tickets_log_channel_id}, Support Role ID: {self.support_role_id}, Reports Channel ID: {self.reports_channel_id}, Suggestions Channel ID: {self.suggestions_channel_id}")
        except Exception as e:
            logger.error(f"Error loading ticket configuration: {e}")
    
    def save_config(self):
        """Save ticket system configuration to settings.json."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
            
            settings['tickets_category_id'] = self.tickets_category_id
            settings['tickets_log_channel_id'] = self.tickets_log_channel_id
            settings['support_role_id'] = self.support_role_id
            settings['reports_channel_id'] = self.reports_channel_id
            settings['suggestions_channel_id'] = self.suggestions_channel_id
            
            with open('settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            logger.info(f"Saved ticket configuration. Category ID: {self.tickets_category_id}, Log Channel ID: {self.tickets_log_channel_id}, Support Role ID: {self.support_role_id}, Reports Channel ID: {self.reports_channel_id}, Suggestions Channel ID: {self.suggestions_channel_id}")
        except Exception as e:
            logger.error(f"Error saving ticket configuration: {e}")
    
    @app_commands.command(
        name="ticket",
        description="Create a support ticket"
    )
    async def create_ticket(self, interaction: discord.Interaction, subject: str, description: str):
        """Create a new support ticket.
        
        Args:
            interaction: The interaction that triggered this command
            subject: The subject of the ticket
            description: Detailed description of the issue
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if ticket category exists
            if not self.tickets_category_id:
                await interaction.followup.send(
                    "The ticket system has not been set up properly. Please ask an admin to set up the ticket category.",
                    ephemeral=True
                )
                return
            
            # Get the ticket category
            category = interaction.guild.get_channel(int(self.tickets_category_id))
            if not category:
                await interaction.followup.send(
                    "The ticket category could not be found. Please ask an admin to set up the ticket category.",
                    ephemeral=True
                )
                return
            
            # Check if user already has an active ticket
            user_id = str(interaction.user.id)
            for ticket_id, ticket_data in self.active_tickets.items():
                if ticket_data.get('user_id') == user_id:
                    channel = interaction.guild.get_channel(int(ticket_data.get('channel_id')))
                    if channel:
                        await interaction.followup.send(
                            f"You already have an active ticket: {channel.mention}. Please use that ticket instead.",
                            ephemeral=True
                        )
                        return
            
            # Increment ticket counter
            self.ticket_counter += 1
            ticket_id = f"TICKET-{self.ticket_counter:04d}"
            
            # Create a new channel for the ticket
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Add support role if configured
            if self.support_role_id:
                support_role = interaction.guild.get_role(int(self.support_role_id))
                if support_role:
                    overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel_name = f"ticket-{interaction.user.name}-{self.ticket_counter:04d}"
            ticket_channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Support ticket for {interaction.user.name} ({interaction.user.id})"
            )
            
            # Store ticket data
            self.active_tickets[ticket_id] = {
                'channel_id': str(ticket_channel.id),
                'user_id': user_id,
                'subject': subject,
                'created_at': datetime.datetime.now().isoformat(),
                'status': 'open'
            }
            self.save_ticket_data()
            
            # Create welcome message in the ticket channel
            embed = discord.Embed(
                title=f"Ticket: {ticket_id}",
                description="Thank you for creating a support ticket. A staff member will assist you shortly.",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Subject", value=subject, inline=False)
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="User", value=interaction.user.mention, inline=True)
            embed.set_footer(text=f"Ticket ID: {ticket_id}")
            
            # Create ticket controls
            view = TicketControlsView(self, ticket_id)
            
            message = await ticket_channel.send(
                content=f"{interaction.user.mention}",
                embed=embed,
                view=view
            )
            
            # Pin the welcome message
            await message.pin()
            
            # Notify logs channel if configured
            if self.tickets_log_channel_id:
                log_channel = interaction.guild.get_channel(int(self.tickets_log_channel_id))
                if log_channel:
                    log_embed = discord.Embed(
                        title="Ticket Created",
                        description=f"A new support ticket has been created by {interaction.user.mention}",
                        color=discord.Color.green(),
                        timestamp=datetime.datetime.now()
                    )
                    log_embed.add_field(name="Ticket ID", value=ticket_id, inline=True)
                    log_embed.add_field(name="Subject", value=subject, inline=True)
                    log_embed.add_field(name="Channel", value=ticket_channel.mention, inline=True)
                    log_embed.set_footer(text=f"User ID: {interaction.user.id}")
                    
                    await log_channel.send(embed=log_embed)
            
            # Send confirmation to the user
            await interaction.followup.send(
                f"Your ticket has been created: {ticket_channel.mention}",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.followup.send(
                "An error occurred while creating your ticket. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="ticket_setup",
        description="Set up the ticket system (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        """Set up the ticket system.
        
        This command sets up:
        1. A category for ticket channels
        2. A log channel for ticket actions
        3. The support role that can access tickets
        
        Args:
            interaction: The interaction that triggered this command
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_modal(TicketSetupModal(self))
    
    @app_commands.command(
        name="ticketpanel",
        description="Create a support ticket panel with buttons (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def create_ticket_panel(self, interaction: discord.Interaction, title: str = "Support Tickets", description: str = "Click the button below to create a support ticket"):
        """Create a ticket panel with buttons for users to create tickets.
        
        Args:
            interaction: The interaction that triggered this command
            title: The title for the ticket panel embed
            description: Description text for the panel
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Check if ticket system is set up
            if not self.tickets_category_id or not self.tickets_log_channel_id or not self.support_role_id:
                await interaction.followup.send(
                    "The ticket system has not been fully set up. Please use `/ticket_setup` first.",
                    ephemeral=True
                )
                return
            
            # Create ticket panel embed
            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            # Add instructions
            embed.add_field(
                name="How to create a ticket",
                value="Click the button below to open a ticket creation form. Fill in the required information and submit it to create your ticket.",
                inline=False
            )
            
            # Add support role mention
            support_role = interaction.guild.get_role(int(self.support_role_id))
            if support_role:
                embed.add_field(
                    name="Support Team",
                    value=f"Your ticket will be handled by the {support_role.mention} team.",
                    inline=False
                )
            
            # Add footer
            embed.set_footer(text=f"Ticket System | {interaction.guild.name}")
            
            # Create the view with buttons
            view = TicketPanelView(self)
            
            # Send the panel
            await interaction.followup.send(embed=embed, view=view)
            
            # Send confirmation to the admin (ephemeral)
            await interaction.followup.send(
                "Ticket panel created successfully! Users can now create tickets using the button.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating ticket panel: {e}")
            await interaction.followup.send(
                "An error occurred while creating the ticket panel. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="ticket_close",
        description="Close a ticket channel (Admin or ticket creator)"
    )
    async def close_ticket(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        """Close a ticket.
        
        Args:
            interaction: The interaction that triggered this command
            reason: The reason for closing the ticket
        """
        # Check if the channel is a ticket channel
        channel_id = str(interaction.channel.id)
        ticket_id = None
        
        for t_id, ticket_data in self.active_tickets.items():
            if ticket_data.get('channel_id') == channel_id:
                ticket_id = t_id
                break
        
        if not ticket_id:
            await interaction.response.send_message(
                "This command can only be used in ticket channels.",
                ephemeral=True
            )
            return
        
        # Check if the user has permission to close this ticket
        is_admin = await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id)
        is_support = False
        if self.support_role_id:
            support_role = interaction.guild.get_role(int(self.support_role_id))
            if support_role and support_role in interaction.user.roles:
                is_support = True
        
        is_ticket_creator = self.active_tickets[ticket_id].get('user_id') == str(interaction.user.id)
        
        if not (is_admin or is_support or is_ticket_creator):
            await interaction.response.send_message(
                "You don't have permission to close this ticket.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Create a transcript of the ticket
            messages = []
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                messages.append({
                    'author': message.author.display_name,
                    'content': message.content,
                    'attachments': [attachment.url for attachment in message.attachments],
                    'timestamp': message.created_at.isoformat()
                })
            
            # Generate a simple transcript file
            transcript_content = f"Ticket ID: {ticket_id}\n"
            transcript_content += f"Subject: {self.active_tickets[ticket_id].get('subject')}\n"
            transcript_content += f"User: {interaction.guild.get_member(int(self.active_tickets[ticket_id].get('user_id')))}\n"
            transcript_content += f"Created: {self.active_tickets[ticket_id].get('created_at')}\n"
            transcript_content += f"Closed by: {interaction.user.display_name} ({interaction.user.id})\n"
            transcript_content += f"Reason: {reason}\n\n"
            transcript_content += "-------------- TRANSCRIPT --------------\n\n"
            
            for msg in messages:
                transcript_content += f"[{msg['timestamp']}] {msg['author']}: {msg['content']}\n"
                if msg['attachments']:
                    transcript_content += f"Attachments: {', '.join(msg['attachments'])}\n"
                transcript_content += "\n"
            
            # Save the transcript to a file
            if not os.path.exists('data/transcripts'):
                os.makedirs('data/transcripts')
            
            transcript_filename = f"data/transcripts/ticket-{ticket_id}.txt"
            with open(transcript_filename, 'w', encoding='utf-8') as f:
                f.write(transcript_content)
            
            # Send a closing message
            embed = discord.Embed(
                title=f"Ticket Closed: {ticket_id}",
                description=f"This ticket has been closed by {interaction.user.mention}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Transcript", value="A transcript has been saved and sent to the logs channel.", inline=False)
            embed.set_footer(text="This channel will be deleted in 10 seconds.")
            
            await interaction.followup.send(embed=embed)
            
            # Send the transcript to the logs channel
            if self.tickets_log_channel_id:
                log_channel = interaction.guild.get_channel(int(self.tickets_log_channel_id))
                if log_channel:
                    log_embed = discord.Embed(
                        title=f"Ticket Closed: {ticket_id}",
                        description=f"Ticket closed by {interaction.user.mention}",
                        color=discord.Color.red(),
                        timestamp=datetime.datetime.now()
                    )
                    
                    user_id = self.active_tickets[ticket_id].get('user_id')
                    user = interaction.guild.get_member(int(user_id))
                    user_mention = user.mention if user else f"User ID: {user_id}"
                    
                    log_embed.add_field(name="User", value=user_mention, inline=True)
                    log_embed.add_field(name="Subject", value=self.active_tickets[ticket_id].get('subject'), inline=True)
                    log_embed.add_field(name="Reason", value=reason, inline=False)
                    log_embed.set_footer(text=f"Ticket ID: {ticket_id}")
                    
                    transcript_file = discord.File(transcript_filename, filename=f"ticket-{ticket_id}.txt")
                    await log_channel.send(embed=log_embed, file=transcript_file)
            
            # DM the user about ticket closure
            try:
                user_id = self.active_tickets[ticket_id].get('user_id')
                user = interaction.guild.get_member(int(user_id))
                if user:
                    user_embed = discord.Embed(
                        title=f"Your Ticket Has Been Closed: {ticket_id}",
                        description=f"Your support ticket in {interaction.guild.name} has been closed",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now()
                    )
                    
                    user_embed.add_field(name="Subject", value=self.active_tickets[ticket_id].get('subject'), inline=True)
                    user_embed.add_field(name="Closed By", value=interaction.user.display_name, inline=True)
                    user_embed.add_field(name="Reason", value=reason, inline=False)
                    user_embed.set_footer(text=f"If you need further assistance, please create a new ticket.")
                    
                    await user.send(embed=user_embed)
            except Exception as e:
                logger.error(f"Failed to DM user about ticket closure: {e}")
            
            # Remove ticket from active tickets
            del self.active_tickets[ticket_id]
            self.save_ticket_data()
            
            # Wait 10 seconds before deleting the channel
            await asyncio.sleep(10)
            await interaction.channel.delete(reason=f"Ticket {ticket_id} closed by {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            await interaction.followup.send(
                "An error occurred while closing the ticket. Please try again later.",
                ephemeral=True
            )
    
    # add_to_ticket command removed
    
    # remove_from_ticket command removed
    
    @app_commands.command(
        name="help",
        description="Show a list of available commands and their usage"
    )
    async def help_command(self, interaction: discord.Interaction):
        """Show a list of available commands and their usage.
        
        Args:
            interaction: The interaction that triggered this command
        """
        embed = discord.Embed(
            title="Bot Commands Help",
            description="Here's a list of available commands and their usage:",
            color=discord.Color.blue()
        )
        
        # Public commands section
        embed.add_field(
            name="__Public Commands__",
            value=(
                "• **/help** - Shows this help message with all commands and their purpose\n"
                "• **/report** - Report a user (Required: Who?, Why?, When?)\n"
                "• **/suggest** - Make a suggestion for the server (Required: Title, Suggestion)\n"
                "• **/ticket** - Create a support ticket (Required: Subject, Description)\n"
                "• **/ticket_close** - Close your support ticket (Required: Reason)\n"
                "• **/rank** - Display your current level, XP, and coins\n"
                "• **/leaderboard** - View the server's top users by level\n"
                "• **/mine** - Mine for resources to earn coins\n"
                "• **/balance** - Check your mining balance and resources\n"
                "• **/invest** - Browse and purchase luxury properties\n"
                "• **/business** - Manage your luxury property portfolio\n"
                "• **/tournament** - View tournament details\n"
                "• **/jointournament** - Join a tournament using its ID\n"
            ),
            inline=False
        )
        
        # Check if user is an admin or support
        is_admin = await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id)
        is_support = False
        if self.support_role_id:
            support_role = interaction.guild.get_role(int(self.support_role_id))
            if support_role and support_role in interaction.user.roles:
                is_support = True
        
        # Only show admin commands to admins
        if is_admin or is_support:
            embed.add_field(
                name="__Administration Commands__",
                value=(
                    "• **/ban** - Ban a user (Required: User, Reason, Duration)\n"
                    "• **/mute** - Mute a user (Required: User, Reason, Duration)\n"
                    "• **/kick** - Kick a user (Required: User, Reason)\n"
                    "• **/warn** - Warn a user (Required: User, Reason, Duration)\n"
                    "• **/givepermission** - Give permissions to a user\n"
                    "• **/purge** - Delete messages from a channel\n"
                    "• **/channellock** - Lock a channel to prevent messages\n"
                    "• **/channelunlock** - Unlock a previously locked channel\n"
                    "• **/embedsend** - Send a custom embed message\n"
                    "• **/giveawaystart** - Start a giveaway\n"
                    "• **/giveawayend** - End a giveaway by ID\n"
                    "• **/giveawayreroll** - Reroll a giveaway winner\n"
                    "• **/makestickynote** - Create a sticky message in a channel\n"
                ),
                inline=False
            )
            
            # Ticket-specific admin commands
            embed.add_field(
                name="__Ticket Management Commands__",
                value=(
                    "• **/ticket_setup** - Configure the ticket system\n"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Handle ticket channel deletion.
        
        Args:
            channel: The channel that was deleted
        """
        # Check if the deleted channel was a ticket channel
        channel_id = str(channel.id)
        ticket_id = None
        
        for t_id, ticket_data in self.active_tickets.items():
            if ticket_data.get('channel_id') == channel_id:
                ticket_id = t_id
                break
        
        if ticket_id:
            # Remove the ticket from active tickets
            del self.active_tickets[ticket_id]
            self.save_ticket_data()
            logger.info(f"Ticket {ticket_id} removed due to channel deletion.")


class TicketControlsView(discord.ui.View):
    """View for ticket control buttons."""
    
    def __init__(self, ticket_system, ticket_id=None):
        super().__init__(timeout=None)  # Persistent view
        self.ticket_system = ticket_system
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket:close")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket when the button is clicked."""
        # Verify this is a ticket channel
        channel_id = str(interaction.channel.id)
        ticket_id = None
        
        for t_id, ticket_data in self.ticket_system.active_tickets.items():
            if ticket_data.get('channel_id') == channel_id:
                ticket_id = t_id
                break
        
        if not ticket_id:
            await interaction.response.send_message(
                "This command can only be used in ticket channels.",
                ephemeral=True
            )
            return
        
        # Check if the user has permission to close this ticket
        is_admin = await self.ticket_system.bot.has_admin_permissions(interaction.user.id, interaction.guild.id)
        is_support = False
        if self.ticket_system.support_role_id:
            support_role = interaction.guild.get_role(int(self.ticket_system.support_role_id))
            if support_role and support_role in interaction.user.roles:
                is_support = True
        
        is_ticket_creator = self.ticket_system.active_tickets[ticket_id].get('user_id') == str(interaction.user.id)
        
        if not (is_admin or is_support or is_ticket_creator):
            await interaction.response.send_message(
                "You don't have permission to close this ticket.",
                ephemeral=True
            )
            return
            
        # Open a modal to get the close reason
        await interaction.response.send_modal(TicketCloseModal(self.ticket_system))


class TicketSetupModal(discord.ui.Modal):
    """Modal for setting up the ticket system."""
    
    category_id = discord.ui.TextInput(
        label="Tickets Category ID",
        placeholder="Enter the ID of the category for ticket channels",
        required=True
    )
    
    log_channel_id = discord.ui.TextInput(
        label="Log Channel ID",
        placeholder="Enter the ID of the channel for ticket logs",
        required=True
    )
    
    support_role_id = discord.ui.TextInput(
        label="Support Role ID",
        placeholder="Enter the ID of the role that can access tickets",
        required=True
    )
    
    def __init__(self, ticket_system):
        super().__init__(title="Ticket System Setup")
        self.ticket_system = ticket_system
        
        # Pre-fill current values if they exist
        if self.ticket_system.tickets_category_id:
            self.category_id.default = self.ticket_system.tickets_category_id
        
        if self.ticket_system.tickets_log_channel_id:
            self.log_channel_id.default = self.ticket_system.tickets_log_channel_id
        
        if self.ticket_system.support_role_id:
            self.support_role_id.default = self.ticket_system.support_role_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        try:
            # Update configuration
            self.ticket_system.tickets_category_id = self.category_id.value
            self.ticket_system.tickets_log_channel_id = self.log_channel_id.value
            self.ticket_system.support_role_id = self.support_role_id.value
            
            # Save configuration
            self.ticket_system.save_config()
            
            # Validate the channels and role
            category = interaction.guild.get_channel(int(self.category_id.value))
            log_channel = interaction.guild.get_channel(int(self.log_channel_id.value))
            support_role = interaction.guild.get_role(int(self.support_role_id.value))
            
            if not category or not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message(
                    "Invalid category ID. Please provide a valid category channel ID.",
                    ephemeral=True
                )
                return
            
            if not log_channel or not isinstance(log_channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Invalid log channel ID. Please provide a valid text channel ID.",
                    ephemeral=True
                )
                return
            
            if not support_role:
                await interaction.response.send_message(
                    "Invalid support role ID. Please provide a valid role ID.",
                    ephemeral=True
                )
                return
            
            # Confirm setup
            embed = discord.Embed(
                title="Ticket System Setup Complete",
                description="The ticket system has been successfully configured with the following settings:",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Tickets Category", value=f"{category.name} (`{category.id}`)", inline=False)
            embed.add_field(name="Log Channel", value=f"{log_channel.mention} (`{log_channel.id}`)", inline=False)
            embed.add_field(name="Support Role", value=f"{support_role.mention} (`{support_role.id}`)", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "Invalid input. Please ensure all IDs are valid numbers.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting up ticket system: {e}")
            await interaction.response.send_message(
                "An error occurred while setting up the ticket system. Please try again later.",
                ephemeral=True
            )


class TicketCloseModal(discord.ui.Modal):
    """Modal for closing a ticket."""
    
    reason = discord.ui.TextInput(
        label="Reason for Closing",
        placeholder="Please provide a reason for closing this ticket",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, ticket_system):
        super().__init__(title="Close Ticket")
        self.ticket_system = ticket_system
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await self.ticket_system.close_ticket(interaction, self.reason.value)


class TicketPanelView(discord.ui.View):
    """View with a button for creating tickets from a panel."""
    
    def __init__(self, ticket_system):
        super().__init__(timeout=None)  # Persistent view
        self.ticket_system = ticket_system
    
    @discord.ui.button(
        label="Create Ticket", 
        style=discord.ButtonStyle.primary, 
        emoji="🎫", 
        custom_id="ticket_panel:create"
    )
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a modal for creating a new ticket."""
        await interaction.response.send_modal(CreateTicketModal(self.ticket_system))


class CreateTicketModal(discord.ui.Modal):
    """Modal for creating a new ticket."""
    
    subject = discord.ui.TextInput(
        label="Subject",
        placeholder="Brief description of your issue",
        required=True,
        max_length=100
    )
    
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Please provide details about your issue",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, ticket_system):
        super().__init__(title="Create a Support Ticket")
        self.ticket_system = ticket_system
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await self.ticket_system.create_ticket(interaction, self.subject.value, self.description.value)


async def setup(bot):
    """Add the ticket system cog to the bot."""
    ticket_cog = TicketSystem(bot)
    await bot.add_cog(ticket_cog)
    logger.info("Ticket system cog loaded")
    return ticket_cog