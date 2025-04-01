import discord
from discord import app_commands
from discord.ext import commands
import logging
import random
import time
from logger import setup_logger

logger = setup_logger('embed_command', 'bot.log')

def get_rainbow_color():
    """Generate a random rainbow color."""

    rainbow_colors = [
        0xFF0000,  # Red
        0xFF7F00,  # Orange
        0xFFFF00,  # Yellow
        0x00FF00,  # Green
        0x0000FF,  # Blue
        0x4B0082,  # Indigo
        0x9400D3   # Violet
    ]

    rainbow_color = random.choice(rainbow_colors)

    variation = random.randint(-0x111111, 0x111111)
    rainbow_color = max(0, min(0xFFFFFF, rainbow_color + variation))
    
    return rainbow_color

class EmbedCommandCog(commands.Cog):
    """Cog for sending custom embeds via commands."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Embed command cog initialized")
    
    @app_commands.command(
        name="embed",
        description="Create and send a custom embed message (Admin only)"
    )
    @app_commands.describe(
        channel="The channel to send the embed to",
        title="The title of the embed",
        description="The description/content of the embed",
        color="The color of the embed (hex code like #FF0000 for red)",
        footer="Optional footer text for the embed",
        image_url="Optional URL to an image to add to the embed",
        thumbnail_url="Optional URL to a thumbnail image for the embed"
    )
    async def embed(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: str = "#5865F2",  # Default Discord blurple color
        footer: str = None,
        image_url: str = None,
        thumbnail_url: str = None
    ):
        """
        Create and send a custom embed to a channel.
        
        This command is restricted to administrators and staff with the same permissions
        as the /addlevel command.
        """

        try:

            rainbow_color = get_rainbow_color()
            embed_color = discord.Color(rainbow_color)
            logger.info(f"Using rainbow color: #{rainbow_color:06X}")

            embed = discord.Embed(
                title=title,
                description=description,
                color=embed_color
            )

            if footer:
                embed.set_footer(text=footer)

            if image_url:
                embed.set_image(url=image_url)

            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            await channel.send(embed=embed)

            await interaction.response.send_message(
                f"✅ Embed sent to {channel.mention} successfully!",
                ephemeral=True
            )
            
            logger.info(f"User {interaction.user.name} ({interaction.user.id}) sent an embed to channel {channel.name} ({channel.id})")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to send messages in that channel.",
                ephemeral=True
            )
            logger.error(f"Forbidden error sending embed to channel {channel.id}")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )
            logger.error(f"Error sending embed: {e}")

async def setup(bot):
    """Add the embed command cog to the bot."""
    await bot.add_cog(EmbedCommandCog(bot))
    logger.info("Embed command cog loaded")