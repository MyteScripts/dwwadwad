import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import os
import datetime
import asyncio
import random
from logger import setup_logger

logger = setup_logger('community_commands', 'bot.log')

CONFIG_FILE = "community_channels.json"

DEFAULT_CONFIG = {
    "suggestions_channel": None,
    "reports_channel": None,
    "bugs_channel": None,
    "feedback_channel": None,
    "giveaways_channel": None
}

def load_config():
    """Load community channels configuration."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading community config: {e}")
            return DEFAULT_CONFIG
    else:

        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    """Save community channels configuration."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving community config: {e}")
        return False

def parse_time(time_str):
    """Parse time string into seconds.
    
    Formats:
    - Xs: X seconds
    - Xm: X minutes
    - Xh: X hours
    - Xd: X days
    - Xw: X weeks
    """
    if not time_str:
        return None
    
    time_str = time_str.lower().strip()

    if not any(time_str.endswith(unit) for unit in ['s', 'm', 'h', 'd', 'w']):
        return None
    
    try:
        unit = time_str[-1]
        value = int(time_str[:-1])

        if unit == 's':
            return value
        elif unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 60 * 60
        elif unit == 'd':
            return value * 60 * 60 * 24
        elif unit == 'w':
            return value * 60 * 60 * 24 * 7
        else:
            return None
    except ValueError:
        return None

def format_time(seconds):
    """Format seconds into a readable time string."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"
    else:
        weeks = seconds // 604800
        return f"{weeks} week{'s' if weeks != 1 else ''}"

def get_color_from_name(color_name):
    """Convert color name to Discord color object."""
    color_map = {
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "blue": discord.Color.blue(),
        "yellow": discord.Color.yellow(),
        "orange": discord.Color(0xFFA500),
        "purple": discord.Color.purple(),
        "pink": discord.Color(0xFFC0CB),
        "black": discord.Color(0x000000),
        "white": discord.Color(0xFFFFFF),
        "gray": discord.Color.light_grey(),
        "gold": discord.Color.gold(),
        "random": discord.Color.random()
    }
    
    color_name = color_name.lower() if color_name else "random"
    return color_map.get(color_name, discord.Color.random())

active_giveaways = {}

class GiveawayModal(discord.ui.Modal, title="Create Giveaway"):
    """Modal for creating a new giveaway."""
    
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="Enter the giveaway title",
        required=True,
        max_length=100
    )
    
    body = discord.ui.TextInput(
        label="Body (optional)",
        placeholder="Enter additional details for the giveaway",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )
    
    amount = discord.ui.TextInput(
        label="Prize Amount",
        placeholder="Enter the prize (e.g., '50 DLS', '1 Premium Role')",
        required=True,
        max_length=100
    )
    
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="Enter duration (e.g., 1h, 1d, 1w)",
        required=True,
        max_length=10
    )
    
    color = discord.ui.TextInput(
        label="Color",
        placeholder="red, green, blue, yellow, orange, purple, pink, random",
        required=False,
        max_length=20,
        default="random"
    )
    
    def __init__(self, bot, config):
        super().__init__()
        self.bot = bot
        self.config = config
    
    async def on_submit(self, interaction: discord.Interaction):

        duration_seconds = parse_time(self.duration.value)
        if duration_seconds is None:
            await interaction.response.send_message(
                "Invalid duration format. Please use formats like 1s, 1m, 1h, 1d, 1w.",
                ephemeral=True
            )
            return

        channel_id = self.config.get("giveaways_channel")
        if not channel_id:
            await interaction.response.send_message(
                "Giveaway channel not set. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Giveaway channel not found. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return

        await interaction.response.send_message("Creating your giveaway...", ephemeral=True)

        color = get_color_from_name(self.color.value)
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
        
        embed = discord.Embed(
            title=self.title_input.value,
            description=self.body.value if self.body.value else "",
            color=color
        )
        
        embed.add_field(name="Prize", value=self.amount.value, inline=False)
        embed.add_field(name="Duration", value=format_time(duration_seconds), inline=True)
        embed.add_field(name="Ends At", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"Started by {interaction.user.name}")

        view = GiveawayView(duration_seconds, self.amount.value, interaction.user.id)

        giveaway_msg = await channel.send(embed=embed, view=view)

        giveaway_id = str(giveaway_msg.id)
        active_giveaways[giveaway_id] = {
            "message_id": giveaway_msg.id,
            "channel_id": channel.id,
            "end_time": end_time.timestamp(),
            "prize": self.amount.value,
            "host_id": interaction.user.id,
            "title": self.title_input.value,
            "participants": []
        }

        self.bot.loop.create_task(self.end_giveaway_after(giveaway_msg, duration_seconds, view))
    
    async def end_giveaway_after(self, message, duration, view):
        """End the giveaway after the specified duration."""
        await asyncio.sleep(duration)

        giveaway_id = str(message.id)
        if giveaway_id not in active_giveaways:
            return
        
        giveaway_data = active_giveaways[giveaway_id]
        participants = giveaway_data.get("participants", [])

        view.children[0].disabled = True
        await message.edit(view=view)

        if participants:
            winner_id = random.choice(participants)
            winner = self.bot.get_user(winner_id) or await self.bot.fetch_user(winner_id)

            embed = message.embeds[0]
            embed.add_field(name="Winner", value=f"{winner.mention} ({winner.name})", inline=False)
            embed.color = discord.Color.green()
            
            await message.edit(embed=embed)

            channel = message.channel
            await channel.send(
                f"🎉 Congratulations {winner.mention}! You won the giveaway for **{giveaway_data['prize']}**!"
            )

            try:
                dm_embed = discord.Embed(
                    title="🎉 You Won a Giveaway!",
                    description=f"You won the giveaway for **{giveaway_data['prize']}**!\n\nPlease contact the server staff to claim your prize.",
                    color=discord.Color.green()
                )
                await winner.send(embed=dm_embed)
            except:
                logger.warning(f"Failed to send DM to giveaway winner {winner.id}")
        else:

            embed = message.embeds[0]
            embed.add_field(name="Winner", value="No participants", inline=False)
            embed.color = discord.Color.red()
            
            await message.edit(embed=embed)
            await message.channel.send(f"No one participated in the giveaway for **{giveaway_data['prize']}**.")

        del active_giveaways[giveaway_id]

class GiveawayView(discord.ui.View):
    """View with a button to join the giveaway."""
    
    def __init__(self, duration, prize, host_id):
        super().__init__(timeout=duration)
        self.prize = prize
        self.host_id = host_id
        self.participants = []
    
    @discord.ui.button(label="Join Giveaway (0)", style=discord.ButtonStyle.primary, emoji="🎉")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        if user_id == self.host_id:
            await interaction.response.send_message("You cannot join your own giveaway!", ephemeral=True)
            return

        giveaway_id = str(interaction.message.id)
        if giveaway_id not in active_giveaways:
            await interaction.response.send_message("This giveaway has ended or doesn't exist.", ephemeral=True)
            return
        
        giveaway_data = active_giveaways[giveaway_id]

        if user_id in giveaway_data["participants"]:
            await interaction.response.send_message("You have already joined this giveaway!", ephemeral=True)
            return

        giveaway_data["participants"].append(user_id)
        active_giveaways[giveaway_id] = giveaway_data

        participants_count = len(giveaway_data["participants"])
        button.label = f"Join Giveaway ({participants_count})"
        
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"You have joined the giveaway for **{self.prize}**!", ephemeral=True)

class SuggestionModal(discord.ui.Modal, title="Create Suggestion"):
    """Modal for creating a new suggestion."""
    
    title = discord.ui.TextInput(
        label="Title",
        placeholder="Enter the suggestion title",
        required=True,
        max_length=100
    )
    
    body = discord.ui.TextInput(
        label="Body",
        placeholder="Enter your suggestion details",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, bot, config):
        super().__init__()
        self.bot = bot
        self.config = config
    
    async def on_submit(self, interaction: discord.Interaction):

        channel_id = self.config.get("suggestions_channel")
        if not channel_id:
            await interaction.response.send_message(
                "Suggestions channel not set. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Suggestions channel not found. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Thank you for your suggestion! The server staff will review it soon.",
            ephemeral=True
        )

        embed = discord.Embed(
            title=f"Suggestion: {self.title.value}",
            description=self.body.value,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        view = SuggestionView()

        await channel.send(embed=embed, view=view)

class SuggestionView(discord.ui.View):
    """View with buttons to act on or pass a suggestion."""
    
    def __init__(self):
        super().__init__(timeout=None)  # No timeout for suggestion buttons
    
    @discord.ui.button(label="Act on it", style=discord.ButtonStyle.success)
    async def act_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value="✅ Accepted", inline=False)
        embed.add_field(name="Acted on by", value=f"{interaction.user.name}", inline=False)

        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("Suggestion marked as 'Act on it'.", ephemeral=True)
    
    @discord.ui.button(label="Pass", style=discord.ButtonStyle.danger)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
            return

        await interaction.message.delete()
        await interaction.response.send_message("Suggestion has been passed/declined.", ephemeral=True)

class ReportModal(discord.ui.Modal, title="Report User"):
    """Modal for reporting a user."""
    
    user = discord.ui.TextInput(
        label="User",
        placeholder="@user or user ID",
        required=True,
        max_length=100
    )
    
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Why are you reporting this user?",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, bot, config):
        super().__init__()
        self.bot = bot
        self.config = config
    
    async def on_submit(self, interaction: discord.Interaction):

        channel_id = self.config.get("reports_channel")
        if not channel_id:
            await interaction.response.send_message(
                "Reports channel not set. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Reports channel not found. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return

        reported_user = None
        try:

            if self.user.value.startswith('<@') and self.user.value.endswith('>'):
                user_id = self.user.value.strip('<@!>')
                reported_user = await self.bot.fetch_user(int(user_id))
            else:

                try:
                    reported_user = await self.bot.fetch_user(int(self.user.value.strip()))
                except ValueError:

                    members = interaction.guild.members
                    for member in members:
                        if self.user.value.lower() in member.name.lower() or \
                           (member.nick and self.user.value.lower() in member.nick.lower()):
                            reported_user = member
                            break
        except Exception as e:
            logger.error(f"Error finding reported user: {e}")

        await interaction.response.send_message(
            "Thank you for your report. The server staff will review it soon.",
            ephemeral=True
        )

        embed = discord.Embed(
            title="User Report",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        
        if reported_user:
            embed.add_field(name="Reported User", value=f"{reported_user.mention} ({reported_user.name})", inline=False)
            embed.add_field(name="Reported User ID", value=reported_user.id, inline=False)
        else:
            embed.add_field(name="Reported User", value=f"Unable to identify: {self.user.value}", inline=False)
        
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        embed.set_footer(text=f"Reporter ID: {interaction.user.id}")

        await channel.send(embed=embed)

class BugModal(discord.ui.Modal, title="Report a Bug"):
    """Modal for reporting a bug."""
    
    title = discord.ui.TextInput(
        label="Bug Title",
        placeholder="Brief description of the bug",
        required=True,
        max_length=100
    )
    
    description = discord.ui.TextInput(
        label="Bug Description",
        placeholder="Detailed description of the bug",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    steps = discord.ui.TextInput(
        label="Steps to Reproduce",
        placeholder="Step-by-step instructions to reproduce the bug",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    expected = discord.ui.TextInput(
        label="Expected Behavior",
        placeholder="What should happen when working correctly",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, bot, config):
        super().__init__()
        self.bot = bot
        self.config = config
    
    async def on_submit(self, interaction: discord.Interaction):

        channel_id = self.config.get("bugs_channel")
        if not channel_id:
            await interaction.response.send_message(
                "Bugs channel not set. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Bugs channel not found. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Thank you for reporting this bug! The development team will review it soon.",
            ephemeral=True
        )

        embed = discord.Embed(
            title=f"Bug Report: {self.title.value}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        
        embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.add_field(name="Steps to Reproduce", value=self.steps.value, inline=False)
        
        if self.expected.value:
            embed.add_field(name="Expected Behavior", value=self.expected.value, inline=False)
        
        embed.set_footer(text=f"Reporter ID: {interaction.user.id}")

        await channel.send(embed=embed)

class FeedbackModal(discord.ui.Modal, title="Provide Feedback"):
    """Modal for providing feedback."""
    
    feedback = discord.ui.TextInput(
        label="Feedback",
        placeholder="Share your thoughts, suggestions, or feedback",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, bot, config):
        super().__init__()
        self.bot = bot
        self.config = config
    
    async def on_submit(self, interaction: discord.Interaction):

        channel_id = self.config.get("feedback_channel")
        if not channel_id:
            await interaction.response.send_message(
                "Feedback channel not set. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Feedback channel not found. Please ask an admin to set it with /set_channel.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Thank you for your feedback! We appreciate your input.",
            ephemeral=True
        )

        embed = discord.Embed(
            title="User Feedback",
            description=self.feedback.value,
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        await channel.send(embed=embed)

class SetChannelModal(discord.ui.Modal, title="Set Community Channel"):
    """Modal for setting a community channel."""
    
    channel_type = discord.ui.TextInput(
        label="Channel Type",
        placeholder="suggestions, reports, bugs, feedback, giveaways",
        required=True,
        max_length=20
    )
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID",
        required=True,
        max_length=20
    )
    
    def __init__(self, config):
        super().__init__()
        self.config = config
    
    async def on_submit(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return

        channel_type = self.channel_type.value.lower().strip()
        valid_types = ["suggestions", "reports", "bugs", "feedback", "giveaways"]
        
        if channel_type not in valid_types:
            await interaction.response.send_message(
                f"Invalid channel type. Please use one of: {', '.join(valid_types)}",
                ephemeral=True
            )
            return

        try:
            channel_id = int(self.channel_id.value.strip())
        except ValueError:
            await interaction.response.send_message("Invalid channel ID. Please provide a valid number.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Channel not found. Please provide a valid channel ID.", ephemeral=True)
            return

        config_key = f"{channel_type}_channel"
        self.config[config_key] = channel_id
        save_config(self.config)
        
        await interaction.response.send_message(
            f"✅ {channel_type.capitalize()} channel set to {channel.mention}",
            ephemeral=True
        )

class CommunityCommandsCog(commands.Cog):
    """Cog for community interaction commands."""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
    
    @app_commands.command(name="giveaway", description="Start a new giveaway")
    async def giveaway(self, interaction: discord.Interaction):
        """Create a new giveaway."""

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to create giveaways.", ephemeral=True)
            return

        await interaction.response.send_modal(GiveawayModal(self.bot, self.config))
    
    @app_commands.command(name="community_suggestion", description="Submit a suggestion for the server")
    async def suggest(self, interaction: discord.Interaction):
        """Submit a server suggestion."""
        await interaction.response.send_modal(SuggestionModal(self.bot, self.config))
    
    @app_commands.command(name="community_report", description="Report a user")
    async def report(self, interaction: discord.Interaction):
        """Report a user for breaking rules."""
        await interaction.response.send_modal(ReportModal(self.bot, self.config))
    
    @app_commands.command(name="bug", description="Report a bug")
    async def bug(self, interaction: discord.Interaction):
        """Report a bug in the bot or server features."""
        await interaction.response.send_modal(BugModal(self.bot, self.config))
    
    @app_commands.command(name="feedback", description="Provide feedback")
    async def feedback(self, interaction: discord.Interaction):
        """Provide general feedback about the server or bot."""
        await interaction.response.send_modal(FeedbackModal(self.bot, self.config))
    
    @app_commands.command(name="rules", description="Get the server rules")
    async def rules(self, interaction: discord.Interaction):
        """Send the server rules via DM."""
        try:

            embed = discord.Embed(
                title="Server Rules",
                description="Here are the rules of our server. Please follow them to ensure a positive experience for everyone.",
                color=discord.Color.blue()
            )

            embed.add_field(name="Rule 1", value="Be respectful to all members", inline=False)
            embed.add_field(name="Rule 2", value="No spamming or flooding the chat", inline=False)
            embed.add_field(name="Rule 3", value="No advertising without permission", inline=False)
            embed.add_field(name="Rule 4", value="No NSFW content", inline=False)
            embed.add_field(name="Rule 5", value="Use appropriate channels for your messages", inline=False)
            
            embed.set_footer(text="These rules are subject to change. Check announcements for updates.")

            await interaction.user.send(embed=embed)

            await interaction.response.send_message("I've sent you the server rules via DM!", ephemeral=True)
        except discord.Forbidden:

            await interaction.response.send_message(
                "I couldn't send you a DM. Please enable direct messages from server members in your privacy settings.",
                ephemeral=True
            )
    
    @app_commands.command(name="set_channel", description="Set a channel for community features")
    async def set_channel(self, interaction: discord.Interaction):
        """Set channels for suggestions, reports, bugs, etc."""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return

        await interaction.response.send_modal(SetChannelModal(self.config))
    
    @app_commands.command(name="view_channels", description="View current channel settings")
    async def view_channels(self, interaction: discord.Interaction):
        """View current channel settings for community features."""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Community Channel Settings",
            color=discord.Color.blue(),
            description="Current channel settings for community features:"
        )
        
        for feature, channel_id in self.config.items():
            feature_name = feature.replace("_channel", "").capitalize()
            
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                value = f"{channel.mention} (ID: {channel_id})" if channel else f"Invalid Channel (ID: {channel_id})"
            else:
                value = "Not set"
            
            embed.add_field(name=feature_name, value=value, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    """Add the community commands cog to the bot."""
    await bot.add_cog(CommunityCommandsCog(bot))
    logger.info("Community Commands cog loaded")