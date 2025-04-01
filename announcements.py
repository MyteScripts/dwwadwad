import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class AnnouncementsCog(commands.Cog):
    """Cog for managing announcements and how-to information."""
    
    def __init__(self, bot):
        self.bot = bot
        self.announcements_file = "data/announcements.json"
        self.howto_file = "data/howto.json"
        self.announcements_list = []
        self.howto_topics = {}
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Load existing data or create new files
        self.load_announcements()
        self.load_howto()
    
    def load_announcements(self):
        """Load announcements from JSON file."""
        try:
            if os.path.exists(self.announcements_file):
                with open(self.announcements_file, 'r') as f:
                    self.announcements_list = json.load(f)
            else:
                # Create empty file
                self.announcements_list = []
                self.save_announcements()
        except Exception as e:
            logger.error(f"Error loading announcements: {e}")
            self.announcements_list = []
    
    def save_announcements(self):
        """Save announcements to JSON file."""
        try:
            with open(self.announcements_file, 'w') as f:
                json.dump(self.announcements_list, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving announcements: {e}")
    
    def load_howto(self):
        """Load how-to guides from JSON file."""
        try:
            if os.path.exists(self.howto_file):
                with open(self.howto_file, 'r') as f:
                    self.howto_topics = json.load(f)
            else:
                # Create empty file with some default topics
                self.howto_topics = {
                    "level up": "To level up, be active in the server! You earn XP by chatting (with a 5-second cooldown). Every message gives you 5-15 XP randomly. Reach new levels to unlock special roles and perks!",
                    "mining": "Use the `/mine` command to gather resources. As you mine, you'll collect various resources of different rarities. You can sell these for coins or use them to craft items. Upgrade your pickaxe with `/upgrade` to mine more valuable resources!",
                    "investments": "Start with `/invest` to see available businesses. Buy one to earn passive income. Remember to regularly `/maintain` your investments to keep them generating coins. If maintenance drops too low, you'll need to `/repair` before collecting income."
                }
                self.save_howto()
        except Exception as e:
            logger.error(f"Error loading howto guides: {e}")
            self.howto_topics = {}
    
    def save_howto(self):
        """Save how-to guides to JSON file."""
        try:
            with open(self.howto_file, 'w') as f:
                json.dump(self.howto_topics, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving howto guides: {e}")
    
    @app_commands.command(name="announcements", description="📢 Shows the latest 3 announcements")
    async def announcements(self, interaction: discord.Interaction):
        """Shows the latest 3 announcements."""
        await interaction.response.defer(ephemeral=False)
        
        if not self.announcements_list:
            await interaction.followup.send("📢 There are no announcements at this time.")
            return
        
        embed = discord.Embed(
            title="📢 Server Announcements",
            description="The latest announcements from the server team",
            color=discord.Color.blue()
        )
        
        # Show the latest 3 announcements (or all if less than 3)
        for i, announcement in enumerate(self.announcements_list[-3:]):
            embed.add_field(
                name=f"{i+1}. {announcement['title']} ({announcement['date']})",
                value=announcement['content'],
                inline=False
            )
        
        embed.set_footer(text="Use /announcements to see this list anytime")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="addannouncement", description="📝 Add a new announcement (Admin only)")
    @app_commands.describe(
        title="The title of the announcement",
        content="The content of the announcement"
    )
    async def addannouncement(self, interaction: discord.Interaction, title: str, content: str):
        """Add a new announcement (Admin only)."""
        
        # Create new announcement
        new_announcement = {
            "title": title,
            "content": content,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "author_id": str(interaction.user.id),
            "author_name": interaction.user.name
        }
        
        # Add to list and save
        self.announcements_list.append(new_announcement)
        self.save_announcements()
        
        # Send confirmation
        embed = discord.Embed(
            title="✅ Announcement Added",
            description=f"Your announcement '{title}' has been added successfully.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Send to announcements channel if configured
        try:
            with open("community_channels.json", 'r') as f:
                channels = json.load(f)
                
            if "announcements" in channels:
                announcements_channel = self.bot.get_channel(int(channels["announcements"]))
                if announcements_channel:
                    announcement_embed = discord.Embed(
                        title=f"📢 {title}",
                        description=content,
                        color=discord.Color.blue()
                    )
                    announcement_embed.set_footer(text=f"Posted by {interaction.user.name} • {datetime.now().strftime('%Y-%m-%d')}")
                    
                    await announcements_channel.send(embed=announcement_embed)
        except Exception as e:
            logger.error(f"Failed to send announcement to channel: {e}")
    
    @app_commands.command(name="howto", description="❓ Get explanation for a specific feature")
    @app_commands.describe(
        topic="The feature or topic you want to learn about"
    )
    async def howto(self, interaction: discord.Interaction, topic: str):
        """Get explanation for a specific feature."""
        topic = topic.lower()
        
        if topic in self.howto_topics:
            embed = discord.Embed(
                title=f"❓ How to: {topic.title()}",
                description=self.howto_topics[topic],
                color=discord.Color.blue()
            )
            
            embed.set_footer(text="Have another question? Use /howto [topic]")
            
            await interaction.response.send_message(embed=embed)
        else:
            # Create a list of available topics
            available_topics = ", ".join([f"`{t}`" for t in self.howto_topics.keys()])
            
            embed = discord.Embed(
                title="❓ Topic Not Found",
                description=f"Sorry, I don't have information about '{topic}'.\n\nAvailable topics: {available_topics}",
                color=discord.Color.red()
            )
            
            embed.set_footer(text="If you need help with something else, contact a moderator!")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="addhowto", description="📝 Add or update a how-to topic (Admin only)")
    @app_commands.describe(
        topic="The topic name (e.g., 'level up')",
        explanation="The explanation or instructions for this topic"
    )
    async def addhowto(self, interaction: discord.Interaction, topic: str, explanation: str):
        """Add or update a how-to topic (Admin only)."""
        topic = topic.lower()
        
        # Add or update the topic
        is_new = topic not in self.howto_topics
        self.howto_topics[topic] = explanation
        self.save_howto()
        
        # Send confirmation
        embed = discord.Embed(
            title=f"✅ HowTo {'Added' if is_new else 'Updated'}",
            description=f"The topic '{topic}' has been {'added' if is_new else 'updated'} successfully.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="removehowto", description="🗑️ Remove a how-to topic (Admin only)")
    @app_commands.describe(
        topic="The topic to remove"
    )
    async def removehowto(self, interaction: discord.Interaction, topic: str):
        """Remove a how-to topic (Admin only)."""
        topic = topic.lower()
        
        if topic in self.howto_topics:
            del self.howto_topics[topic]
            self.save_howto()
            
            embed = discord.Embed(
                title="✅ HowTo Removed",
                description=f"The topic '{topic}' has been removed successfully.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Topic Not Found",
                description=f"The topic '{topic}' was not found.",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="listhowto", description="📋 List all available how-to topics (Admin only)")
    async def listhowto(self, interaction: discord.Interaction):
        """List all available how-to topics (Admin only)."""
        if not self.howto_topics:
            await interaction.response.send_message("No how-to topics have been added yet.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❓ Available How-To Topics",
            description="Here's a list of all topics with their explanations:",
            color=discord.Color.blue()
        )
        
        for topic, explanation in self.howto_topics.items():
            # Truncate long explanations
            if len(explanation) > 200:
                explanation = explanation[:197] + "..."
                
            embed.add_field(
                name=topic.title(),
                value=explanation,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    """Add the announcements cog to the bot."""
    await bot.add_cog(AnnouncementsCog(bot))