import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import asyncio
import json
import os
import time
from logger import setup_logger
from database import Database

logger = setup_logger('random_drops')

class RandomDropsCog(commands.Cog):
    """Cog for random XP and coin drops."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.settings = self.load_settings()
        self.active_drops = {}
        self.drop_task.start()
        
    def cog_unload(self):
        self.drop_task.cancel()
        
    def load_settings(self):
        """Load random drop settings from JSON file."""
        try:
            if os.path.exists('data/drops_settings.json'):
                with open('data/drops_settings.json', 'r') as f:
                    return json.load(f)
            else:
                # Default settings
                settings = {
                    'enabled': True,
                    'interval_min': 45 * 60,  # 45 minutes minimum
                    'interval_max': 75 * 60,  # 75 minutes maximum
                    'drop_channels': [],  # List of channel IDs where drops can appear
                    'min_coins': 0,
                    'max_coins': 100,
                    'min_xp': 0,
                    'max_xp': 200,
                    'drop_duration': 120,  # How long drops stay active (seconds)
                    'last_drop_time': 0
                }
                self.save_settings(settings)
                return settings
        except Exception as e:
            logger.error(f"Error loading random drop settings: {e}")
            return {
                'enabled': True,
                'interval_min': 45 * 60,
                'interval_max': 75 * 60,
                'drop_channels': [],
                'min_coins': 0,
                'max_coins': 100,
                'min_xp': 0,
                'max_xp': 200,
                'drop_duration': 120,
                'last_drop_time': 0
            }
    
    def save_settings(self, settings=None):
        """Save random drop settings to JSON file."""
        try:
            if settings is None:
                settings = self.settings
                
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            
            with open('data/drops_settings.json', 'w') as f:
                json.dump(settings, f)
                
            self.settings = settings
            logger.info("Saved random drop settings")
            return True
        except Exception as e:
            logger.error(f"Error saving random drop settings: {e}")
            return False
    
    @tasks.loop(seconds=60)
    async def drop_task(self):
        """Task that periodically creates random drops."""
        if not self.settings.get('enabled', True):
            return
            
        current_time = int(time.time())
        last_drop_time = self.settings.get('last_drop_time', 0)
        
        # Calculate time since last drop
        time_since_last = current_time - last_drop_time
        
        # Get random interval for next drop
        interval_min = self.settings.get('interval_min', 45 * 60)  # Default 45 minutes
        interval_max = self.settings.get('interval_max', 75 * 60)  # Default 75 minutes
        
        # If it's time for a new drop
        if time_since_last >= interval_min:
            # Random chance to drop based on time passed
            chance = (time_since_last - interval_min) / (interval_max - interval_min)
            chance = min(1.0, max(0.0, chance))  # Clamp to 0-1 range
            
            # Random roll
            if random.random() <= chance:
                await self.create_random_drop()
                
                # Update last drop time
                self.settings['last_drop_time'] = current_time
                self.save_settings()
        
    @drop_task.before_loop
    async def before_drop_task(self):
        """Wait until the bot is ready before starting the drop task."""
        await self.bot.wait_until_ready()
        
    async def create_random_drop(self):
        """Create a random XP and coin drop in a random enabled channel."""
        # Check if there are any enabled channels
        enabled_channels = self.settings.get('drop_channels', [])
        if not enabled_channels:
            # If no specific channels are set, try to find a general channel
            for guild in self.bot.guilds:
                general_channels = [c for c in guild.text_channels if 'general' in c.name.lower()]
                if general_channels:
                    enabled_channels.append(general_channels[0].id)
                else:
                    # If no general channel, use the first text channel
                    text_channels = [c for c in guild.text_channels]
                    if text_channels:
                        enabled_channels.append(text_channels[0].id)
            
            # Save the identified channels
            if enabled_channels:
                self.settings['drop_channels'] = enabled_channels
                self.save_settings()
            else:
                logger.warning("No channels available for random drops")
                return
                
        # Pick a random channel from the enabled list
        channel_id = random.choice(enabled_channels)
        channel = self.bot.get_channel(channel_id)
        
        if not channel:
            logger.warning(f"Could not find channel with ID {channel_id}")
            return
            
        # Generate random coin and XP amounts
        min_coins = self.settings.get('min_coins', 0)
        max_coins = self.settings.get('max_coins', 100)
        min_xp = self.settings.get('min_xp', 0)
        max_xp = self.settings.get('max_xp', 200)
        
        coins = random.randint(min_coins, max_coins)
        xp = random.randint(min_xp, max_xp)
        
        # Create the drop message
        drop_id = f"drop_{int(time.time())}"
        
        embed = discord.Embed(
            title="🎁 Random Drop!",
            description=f"Quick! Click the button below to claim:\n\n<:activitycoin:1350889157676761088> **{coins}** coins\n⭐ **{xp}** XP",
            color=discord.Color.gold()
        )
        
        embed.set_footer(text=f"First to click gets the reward! • ID: {drop_id}")
        
        # Create view with button
        view = DropClaimView(self, drop_id, coins, xp)
        
        # Send the drop message
        try:
            drop_message = await channel.send(embed=embed, view=view)
            
            # Store drop info
            self.active_drops[drop_id] = {
                'message_id': drop_message.id,
                'channel_id': channel.id,
                'coins': coins,
                'xp': xp,
                'claimed_by': None,
                'created_at': int(time.time()),
                'expires_at': int(time.time()) + self.settings.get('drop_duration', 120)
            }
            
            logger.info(f"Created random drop in {channel.name} (ID: {channel.id}): {coins} coins, {xp} XP (ID: {drop_id})")
            
            # Set expiration for this drop
            await asyncio.sleep(self.settings.get('drop_duration', 120))
            
            # If drop still exists and is unclaimed, remove it
            if drop_id in self.active_drops and self.active_drops[drop_id]['claimed_by'] is None:
                self.active_drops.pop(drop_id, None)
                
                # Update the message if it still exists
                try:
                    message = await channel.fetch_message(drop_message.id)
                    if message:
                        embed = message.embeds[0]
                        embed.description = "This drop has expired! Better luck next time."
                        embed.color = discord.Color.darker_grey()
                        
                        await message.edit(embed=embed, view=None)
                        logger.info(f"Drop {drop_id} expired (unclaimed)")
                except:
                    logger.warning(f"Could not update expired drop message for {drop_id}")
                    
        except Exception as e:
            logger.error(f"Error creating random drop: {e}")
    
    @app_commands.command(name="drops_config", description="Configure random XP and coin drops (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def drops_config(self, interaction: discord.Interaction, 
                            enabled: bool = None,
                            min_interval: int = None, 
                            max_interval: int = None,
                            min_coins: int = None,
                            max_coins: int = None,
                            min_xp: int = None,
                            max_xp: int = None,
                            duration: int = None):
        """Configure random XP and coin drops."""
        
        settings_updated = False
        
        if enabled is not None:
            self.settings['enabled'] = enabled
            settings_updated = True
            
        if min_interval is not None:
            self.settings['interval_min'] = min_interval * 60  # Convert to seconds
            settings_updated = True
            
        if max_interval is not None:
            self.settings['interval_max'] = max_interval * 60  # Convert to seconds
            settings_updated = True
            
        if min_coins is not None:
            self.settings['min_coins'] = min_coins
            settings_updated = True
            
        if max_coins is not None:
            self.settings['max_coins'] = max_coins
            settings_updated = True
            
        if min_xp is not None:
            self.settings['min_xp'] = min_xp
            settings_updated = True
            
        if max_xp is not None:
            self.settings['max_xp'] = max_xp
            settings_updated = True
            
        if duration is not None:
            self.settings['drop_duration'] = duration
            settings_updated = True
            
        if settings_updated:
            self.save_settings()
            
        # Create settings embed
        embed = discord.Embed(
            title="Random Drops Configuration",
            description="Current settings for random XP and coin drops:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Status",
            value=f"{'Enabled' if self.settings.get('enabled', True) else 'Disabled'}",
            inline=True
        )
        
        embed.add_field(
            name="Drop Interval",
            value=f"{self.settings.get('interval_min', 45*60)//60}-{self.settings.get('interval_max', 75*60)//60} minutes",
            inline=True
        )
        
        embed.add_field(
            name="Duration",
            value=f"{self.settings.get('drop_duration', 120)} seconds",
            inline=True
        )
        
        embed.add_field(
            name="Coin Range",
            value=f"{self.settings.get('min_coins', 0)}-{self.settings.get('max_coins', 100)} coins",
            inline=True
        )
        
        embed.add_field(
            name="XP Range",
            value=f"{self.settings.get('min_xp', 0)}-{self.settings.get('max_xp', 200)} XP",
            inline=True
        )
        
        drop_channels = []
        for channel_id in self.settings.get('drop_channels', []):
            channel = self.bot.get_channel(channel_id)
            if channel:
                drop_channels.append(f"{channel.mention} ({channel.name})")
                
        embed.add_field(
            name="Drop Channels",
            value="\n".join(drop_channels) if drop_channels else "No specific channels set (will use general channel)",
            inline=False
        )
        
        if settings_updated:
            embed.set_footer(text="Settings updated successfully!")
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    # set_drop_channel command removed
                
    @app_commands.command(name="force_drop", description="Force a random drop to happen immediately (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def force_drop(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Force a random drop to happen immediately."""
        await interaction.response.send_message("Creating random drop...", ephemeral=True)
        
        # If channel is specified, temporarily set it as the only drop channel
        original_channels = None
        if channel:
            original_channels = self.settings.get('drop_channels', [])
            self.settings['drop_channels'] = [channel.id]
            
        # Create the drop
        await self.create_random_drop()
        
        # Restore original channels if needed
        if original_channels is not None:
            self.settings['drop_channels'] = original_channels

class DropClaimView(discord.ui.View):
    """View with button to claim a random drop."""
    
    def __init__(self, cog, drop_id, coins, xp):
        super().__init__(timeout=cog.settings.get('drop_duration', 120))
        self.cog = cog
        self.drop_id = drop_id
        self.coins = coins
        self.xp = xp
        
    @discord.ui.button(label="Claim Reward!", style=discord.ButtonStyle.success, emoji="🎁", custom_id="claim_drop")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle claim button press."""
        
        # Check if drop exists and is not already claimed
        if self.drop_id not in self.cog.active_drops:
            await interaction.response.send_message("This drop no longer exists!", ephemeral=True)
            return
            
        drop_info = self.cog.active_drops[self.drop_id]
        
        if drop_info['claimed_by'] is not None:
            await interaction.response.send_message("This drop has already been claimed!", ephemeral=True)
            return
            
        # Mark as claimed
        drop_info['claimed_by'] = interaction.user.id
        
        # Add coins and XP to the user
        user_id = str(interaction.user.id)
        username = str(interaction.user)
        
        try:
            # Add coins
            user = self.cog.db.add_coins(user_id, username, self.coins)
            if user is None:
                logger.error(f"Failed to add coins to user {username} ({user_id})")
                await interaction.response.send_message("Error claiming reward. Please try again later.", ephemeral=True)
                return
                
            # Add XP (using a simplified version since we don't need coin calculation from level ups)
            xp_result = self.cog.db.add_xp(user_id, username, self.xp)
            if xp_result[0] is None:
                logger.error(f"Failed to add XP to user {username} ({user_id})")
            
            # Get final user data
            final_user = self.cog.db.get_user(user_id)
            
            # Check if a level up happened
            level_up = xp_result[1]
            new_level = final_user['level'] if final_user else None
            
            # Update the message
            message = interaction.message
            embed = message.embeds[0]
            
            embed.title = "🎁 Drop Claimed!"
            embed.description = f"{interaction.user.mention} claimed this drop and received:\n\n<:activitycoin:1350889157676761088> **{self.coins}** coins\n⭐ **{self.xp}** XP"
            embed.color = discord.Color.green()
            
            if level_up:
                embed.description += f"\n\n**LEVEL UP!** 🎉 {interaction.user.mention} reached level **{new_level}**!"
                
            await message.edit(embed=embed, view=None)
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
                
            # Create claim confirmation embed
            claim_embed = discord.Embed(
                title="🎁 Reward Claimed!",
                description=f"You successfully claimed the random drop and received:\n\n<:activitycoin:1350889157676761088> **{self.coins}** coins\n⭐ **{self.xp}** XP",
                color=discord.Color.green()
            )
            
            if level_up:
                claim_embed.description += f"\n\n**LEVEL UP!** 🎉 You reached level **{new_level}**!"
                
            claim_embed.add_field(
                name="Your New Balance",
                value=f"<:activitycoin:1350889157676761088> **{int(final_user['coins']):,}** coins\n⭐ **{final_user['xp']}** / **{self.cog.db.calculate_required_xp(final_user['level'])}** XP",
                inline=False
            )
            
            await interaction.response.send_message(embed=claim_embed, ephemeral=True)
            
            # Log the claim
            logger.info(f"Drop {self.drop_id} claimed by {username} ({user_id}): {self.coins} coins, {self.xp} XP")
            
        except Exception as e:
            logger.error(f"Error processing drop claim: {e}")
            await interaction.response.send_message("An error occurred while claiming the reward. Please try again later.", ephemeral=True)

async def setup(bot):
    """Add the random drops cog to the bot."""
    await bot.add_cog(RandomDropsCog(bot))
    logger.info("Random drops cog loaded")