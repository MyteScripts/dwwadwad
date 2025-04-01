import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import datetime
import json
import asyncio
import logging
import os

# Set up logging
logger = logging.getLogger('giveaway_system')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class GiveawaySystem(commands.Cog):
    """Cog for managing server giveaways."""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}
        self.giveaway_tasks = {}
        self.persistent_views_added = False
        
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Load active giveaways
        self.load_giveaways()
        
        # Start the background task for checking giveaways
        self.check_giveaways.start()
    
    def cog_unload(self):
        """Called when the cog is unloaded."""
        self.check_giveaways.cancel()
        for task in self.giveaway_tasks.values():
            task.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready. Sets up persistent views."""
        if not self.persistent_views_added:
            self.bot.add_view(GiveawayView(self))
            self.persistent_views_added = True
            logger.info("Added persistent views for giveaway system")
            
            # Resume active giveaways
            await self.resume_active_giveaways()
    
    async def resume_active_giveaways(self):
        """Resume all active giveaways when the bot starts."""
        current_time = datetime.datetime.now().timestamp()
        
        for giveaway_id, giveaway in list(self.active_giveaways.items()):
            end_time = giveaway.get('end_time', 0)
            
            if end_time > current_time:
                # Giveaway is still active, resume it
                channel_id = giveaway.get('channel_id')
                message_id = giveaway.get('message_id')
                
                if channel_id and message_id:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        try:
                            message = await channel.fetch_message(int(message_id))
                            # Recreate the view for this message
                            view = GiveawayView(self)
                            await message.edit(view=view)
                            
                            # Schedule the end task
                            self.schedule_giveaway_end(giveaway_id, end_time - current_time)
                            logger.info(f"Resumed giveaway {giveaway_id}")
                        except discord.NotFound:
                            logger.warning(f"Could not find message for giveaway {giveaway_id}, removing it")
                            del self.active_giveaways[giveaway_id]
                            self.save_giveaways()
                    else:
                        logger.warning(f"Could not find channel for giveaway {giveaway_id}, removing it")
                        del self.active_giveaways[giveaway_id]
                        self.save_giveaways()
            else:
                # Giveaway has ended, process it
                await self.end_giveaway(giveaway_id, announce=True)
    
    def load_giveaways(self):
        """Load active giveaways from JSON file."""
        try:
            if os.path.exists('data/giveaways.json'):
                with open('data/giveaways.json', 'r') as f:
                    self.active_giveaways = json.load(f)
                logger.info(f"Loaded {len(self.active_giveaways)} active giveaways")
            else:
                self.save_giveaways()
        except Exception as e:
            logger.error(f"Error loading giveaways: {e}")
            self.active_giveaways = {}
            self.save_giveaways()
    
    def save_giveaways(self):
        """Save active giveaways to JSON file."""
        try:
            with open('data/giveaways.json', 'w') as f:
                json.dump(self.active_giveaways, f, indent=4)
            logger.info(f"Saved {len(self.active_giveaways)} active giveaways")
        except Exception as e:
            logger.error(f"Error saving giveaways: {e}")
    
    def generate_giveaway_id(self):
        """Generate a unique ID for a giveaway."""
        return f"giveaway-{len(self.active_giveaways) + 1}-{random.randint(1000, 9999)}"
    
    def schedule_giveaway_end(self, giveaway_id, seconds):
        """Schedule a task to end a giveaway after the specified time."""
        if giveaway_id in self.giveaway_tasks:
            self.giveaway_tasks[giveaway_id].cancel()
        
        async def end_task():
            await asyncio.sleep(seconds)
            await self.end_giveaway(giveaway_id, announce=True)
        
        task = asyncio.create_task(end_task())
        self.giveaway_tasks[giveaway_id] = task
        logger.info(f"Scheduled giveaway {giveaway_id} to end in {seconds} seconds")
    
    @app_commands.command(
        name="giveaway",
        description="Create a new giveaway"
    )
    @app_commands.default_permissions(administrator=True)
    async def create_giveaway(self, interaction: discord.Interaction):
        """Create a new giveaway.
        
        Args:
            interaction: The interaction that triggered this command
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Open a modal for giveaway details
        await interaction.response.send_modal(GiveawayCreateModal(self))
    
    @app_commands.command(
        name="endgiveaway",
        description="End a giveaway immediately (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def end_giveaway_command(self, interaction: discord.Interaction, giveaway_id: str):
        """End a giveaway immediately.
        
        Args:
            interaction: The interaction that triggered this command
            giveaway_id: The ID of the giveaway to end
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if giveaway_id not in self.active_giveaways:
            await interaction.followup.send(
                f"No active giveaway found with ID: {giveaway_id}",
                ephemeral=True
            )
            return
        
        await self.end_giveaway(giveaway_id, announce=True, forced=True)
        
        await interaction.followup.send(
            f"Giveaway {giveaway_id} has been ended.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="cancelgiveaway",
        description="Cancel a giveaway without selecting winners (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def cancel_giveaway_command(self, interaction: discord.Interaction, giveaway_id: str):
        """Cancel a giveaway without selecting winners.
        
        Args:
            interaction: The interaction that triggered this command
            giveaway_id: The ID of the giveaway to cancel
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if giveaway_id not in self.active_giveaways:
            await interaction.followup.send(
                f"No active giveaway found with ID: {giveaway_id}",
                ephemeral=True
            )
            return
        
        # Get the giveaway details
        giveaway = self.active_giveaways[giveaway_id]
        channel_id = giveaway.get('channel_id')
        message_id = giveaway.get('message_id')
        prize = giveaway.get('prize')
        
        # Cancel task if it exists
        if giveaway_id in self.giveaway_tasks:
            self.giveaway_tasks[giveaway_id].cancel()
            del self.giveaway_tasks[giveaway_id]
        
        # Remove from active giveaways
        del self.active_giveaways[giveaway_id]
        self.save_giveaways()
        
        # Update the message
        channel = self.bot.get_channel(int(channel_id))
        if channel:
            try:
                message = await channel.fetch_message(int(message_id))
                embed = message.embeds[0]
                embed.color = discord.Color.red()
                embed.title = "Giveaway Cancelled"
                embed.set_footer(text=f"Giveaway ID: {giveaway_id} | Cancelled by {interaction.user.name}")
                
                await message.edit(embed=embed, view=None)
                
                # Send cancellation announcement
                await channel.send(
                    f"🚫 The giveaway for **{prize}** has been cancelled by {interaction.user.mention}.",
                    allowed_mentions=discord.AllowedMentions.none()
                )
            except discord.NotFound:
                logger.warning(f"Could not find message for giveaway {giveaway_id}")
        
        await interaction.followup.send(
            f"Giveaway {giveaway_id} has been cancelled.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="listgiveaways",
        description="List all active giveaways (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def list_giveaways_command(self, interaction: discord.Interaction):
        """List all active giveaways.
        
        Args:
            interaction: The interaction that triggered this command
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if not self.active_giveaways:
            await interaction.followup.send(
                "There are no active giveaways.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Active Giveaways",
            description="Here are all the currently active giveaways:",
            color=discord.Color.blue()
        )
        
        current_time = datetime.datetime.now().timestamp()
        
        for giveaway_id, giveaway in self.active_giveaways.items():
            prize = giveaway.get('prize', 'Unknown prize')
            end_time = giveaway.get('end_time', 0)
            winners_count = giveaway.get('winners_count', 1)
            
            # Calculate time remaining
            time_left = end_time - current_time
            if time_left > 0:
                days, remainder = divmod(time_left, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                time_str = ""
                if days > 0:
                    time_str += f"{int(days)}d "
                if hours > 0:
                    time_str += f"{int(hours)}h "
                if minutes > 0:
                    time_str += f"{int(minutes)}m "
                if seconds > 0 and days == 0 and hours == 0:
                    time_str += f"{int(seconds)}s"
                
                # Get the giveaway message link
                channel_id = giveaway.get('channel_id')
                message_id = giveaway.get('message_id')
                
                if channel_id and message_id:
                    message_link = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}"
                    embed.add_field(
                        name=f"ID: {giveaway_id}",
                        value=f"**Prize**: {prize}\n**Winners**: {winners_count}\n**Ends in**: {time_str}\n[Jump to Giveaway]({message_link})",
                        inline=True
                    )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="rerollgiveaway",
        description="Reroll a giveaway to select new winners (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def reroll_giveaway_command(self, interaction: discord.Interaction, giveaway_id: str, winners_count: int = 1):
        """Reroll a giveaway to select new winners.
        
        Args:
            interaction: The interaction that triggered this command
            giveaway_id: The ID of the giveaway to reroll
            winners_count: The number of new winners to select
        """
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Check if the giveaway exists (even if it's not active anymore)
        try:
            with open('data/giveaways.json', 'r') as f:
                all_giveaways = json.load(f)
        except:
            all_giveaways = {}
        
        if giveaway_id not in all_giveaways and giveaway_id not in self.active_giveaways:
            await interaction.followup.send(
                f"No giveaway found with ID: {giveaway_id}",
                ephemeral=True
            )
            return
        
        # Get the giveaway data
        if giveaway_id in self.active_giveaways:
            giveaway = self.active_giveaways[giveaway_id]
        else:
            giveaway = all_giveaways[giveaway_id]
        
        channel_id = giveaway.get('channel_id')
        message_id = giveaway.get('message_id')
        prize = giveaway.get('prize')
        
        if not channel_id or not message_id:
            await interaction.followup.send(
                "This giveaway does not have valid channel or message data.",
                ephemeral=True
            )
            return
        
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await interaction.followup.send(
                "The channel for this giveaway no longer exists.",
                ephemeral=True
            )
            return
        
        try:
            message = await channel.fetch_message(int(message_id))
            
            # Get participants by reaction
            reaction_users = []
            for reaction in message.reactions:
                async for user in reaction.users():
                    if not user.bot:
                        reaction_users.append(user)
            
            # Remove duplicates
            participants = list(set(reaction_users))
            
            if not participants:
                await interaction.followup.send(
                    "No participants found to reroll.",
                    ephemeral=True
                )
                return
            
            # Select new winners
            winners_count = min(winners_count, len(participants))
            winners = random.sample(participants, winners_count)
            
            # Announce reroll
            winners_mentions = ", ".join([winner.mention for winner in winners])
            await channel.send(
                f"🎉 **GIVEAWAY REROLL!** 🎉\n\nNew winner{'s' if winners_count > 1 else ''} for **{prize}**: {winners_mentions}\nCongratulations!",
                allowed_mentions=discord.AllowedMentions(users=winners)
            )
            
            await interaction.followup.send(
                f"Successfully rerolled giveaway {giveaway_id} with {winners_count} new winner{'s' if winners_count > 1 else ''}.",
                ephemeral=True
            )
            
        except discord.NotFound:
            await interaction.followup.send(
                "The message for this giveaway no longer exists.",
                ephemeral=True
            )
    
    async def start_giveaway(self, channel, prize, duration_hours, winners_count, host_user):
        """Start a new giveaway in the specified channel.
        
        Args:
            channel: The discord channel for the giveaway
            prize: The prize description
            duration_hours: Duration in hours
            winners_count: Number of winners
            host_user: The user hosting the giveaway
        
        Returns:
            str: The giveaway ID
        """
        # Generate unique ID
        giveaway_id = self.generate_giveaway_id()
        
        # Calculate end time
        duration_seconds = duration_hours * 3600
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
        end_timestamp = end_time.timestamp()
        
        # Create embed for giveaway
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**{prize}**\n\n"
                        f"React with 🎁 to enter!\n\n"
                        f"Hosted by: {host_user.mention}\n"
                        f"Winners: {winners_count}\n"
                        f"Ends: <t:{int(end_timestamp)}:R>",
            color=discord.Color.green(),
            timestamp=end_time
        )
        embed.set_footer(text=f"Giveaway ID: {giveaway_id} | Ends at")
        
        # Create view with enter button
        view = GiveawayView(self)
        
        # Send the giveaway message
        message = await channel.send(embed=embed, view=view)
        
        # Add a reaction for redundancy (some users may prefer reactions)
        await message.add_reaction("🎁")
        
        # Store giveaway data
        self.active_giveaways[giveaway_id] = {
            'channel_id': str(channel.id),
            'message_id': str(message.id),
            'prize': prize,
            'end_time': end_timestamp,
            'winners_count': winners_count,
            'host_user_id': str(host_user.id),
            'participants': []
        }
        self.save_giveaways()
        
        # Schedule the giveaway to end
        self.schedule_giveaway_end(giveaway_id, duration_seconds)
        
        return giveaway_id
    
    async def end_giveaway(self, giveaway_id, announce=True, forced=False):
        """End a giveaway and select winners.
        
        Args:
            giveaway_id: The ID of the giveaway to end
            announce: Whether to send an announcement message
            forced: Whether the giveaway was ended manually before its time
        """
        if giveaway_id not in self.active_giveaways:
            logger.warning(f"Attempted to end non-existent giveaway {giveaway_id}")
            return
        
        # Get giveaway data
        giveaway = self.active_giveaways[giveaway_id]
        channel_id = giveaway.get('channel_id')
        message_id = giveaway.get('message_id')
        prize = giveaway.get('prize')
        winners_count = giveaway.get('winners_count', 1)
        host_user_id = giveaway.get('host_user_id')
        
        # Cancel task if it exists
        if giveaway_id in self.giveaway_tasks:
            self.giveaway_tasks[giveaway_id].cancel()
            del self.giveaway_tasks[giveaway_id]
        
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                logger.warning(f"Channel {channel_id} not found for giveaway {giveaway_id}")
                del self.active_giveaways[giveaway_id]
                self.save_giveaways()
                return
            
            message = await channel.fetch_message(int(message_id))
            if not message:
                logger.warning(f"Message {message_id} not found for giveaway {giveaway_id}")
                del self.active_giveaways[giveaway_id]
                self.save_giveaways()
                return
            
            # Get participants by reaction
            reaction_users = []
            for reaction in message.reactions:
                async for user in reaction.users():
                    if not user.bot:
                        reaction_users.append(user)
            
            # Get participants from stored data as well (from button clicks)
            button_users = []
            stored_participants = giveaway.get('participants', [])
            for user_id in stored_participants:
                user = channel.guild.get_member(int(user_id))
                if user:
                    button_users.append(user)
            
            # Combine participants and remove duplicates
            all_participants = list(set(reaction_users + button_users))
            
            # Update giveaway embed
            embed = message.embeds[0]
            
            # Check if we have participants
            if not all_participants:
                # No participants
                embed.description = f"**{prize}**\n\n"
                embed.color = discord.Color.red()
                embed.title = "🎉 GIVEAWAY ENDED 🎉"
                embed.description += "No one entered the giveaway!"
                
                # Get the host user
                host_user = channel.guild.get_member(int(host_user_id)) if host_user_id else None
                if host_user:
                    embed.description += f"\n\nHosted by: {host_user.mention}"
                
                await message.edit(embed=embed, view=None)
                
                if announce:
                    await channel.send(
                        f"🎉 The giveaway for **{prize}** has ended, but no one entered!",
                        allowed_mentions=discord.AllowedMentions.none()
                    )
            else:
                # We have participants, select winners
                selected_winners = random.sample(all_participants, min(winners_count, len(all_participants)))
                winners_mentions = ", ".join([winner.mention for winner in selected_winners])
                
                embed.color = discord.Color.gold()
                embed.title = "🎉 GIVEAWAY ENDED 🎉"
                
                # Get the host user
                host_user = channel.guild.get_member(int(host_user_id)) if host_user_id else None
                host_mention = host_user.mention if host_user else "Unknown"
                
                embed.description = f"**{prize}**\n\n"
                embed.description += f"Winner{'s' if len(selected_winners) > 1 else ''}: {winners_mentions}\n\n"
                embed.description += f"Hosted by: {host_mention}\n"
                
                if forced:
                    embed.set_footer(text=f"Giveaway ID: {giveaway_id} | Ended early by admin")
                else:
                    embed.set_footer(text=f"Giveaway ID: {giveaway_id} | Ended at")
                
                await message.edit(embed=embed, view=None)
                
                if announce:
                    await channel.send(
                        f"🎉 **GIVEAWAY ENDED!** 🎉\n\nPrize: **{prize}**\nWinner{'s' if len(selected_winners) > 1 else ''}: {winners_mentions}\nHosted by: {host_mention}\n\nCongratulations!",
                        allowed_mentions=discord.AllowedMentions(users=selected_winners + ([host_user] if host_user else []))
                    )
            
            # Remove from active giveaways but keep in the file
            # We'll just mark it as ended so it can be rerolled if needed
            giveaway['ended'] = True
            giveaway['end_time'] = datetime.datetime.now().timestamp()
            self.save_giveaways()
            del self.active_giveaways[giveaway_id]
            
        except Exception as e:
            logger.error(f"Error ending giveaway {giveaway_id}: {e}")
            # Remove problematic giveaway
            if giveaway_id in self.active_giveaways:
                del self.active_giveaways[giveaway_id]
                self.save_giveaways()
    
    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        """Periodically check for ended giveaways."""
        current_time = datetime.datetime.now().timestamp()
        
        for giveaway_id, giveaway in list(self.active_giveaways.items()):
            end_time = giveaway.get('end_time', 0)
            
            if end_time <= current_time:
                logger.info(f"Giveaway {giveaway_id} has ended, processing it")
                await self.end_giveaway(giveaway_id)
    
    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        """Wait for the bot to be ready before starting the task."""
        await self.bot.wait_until_ready()


class GiveawayView(discord.ui.View):
    """View with buttons for giveaways."""
    
    def __init__(self, giveaway_system):
        super().__init__(timeout=None)  # Make the view persistent
        self.giveaway_system = giveaway_system
    
    @discord.ui.button(
        label="Enter Giveaway", 
        style=discord.ButtonStyle.primary, 
        emoji="🎁", 
        custom_id="giveaway:enter"
    )
    async def enter_giveaway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enter the giveaway when the button is clicked."""
        # Find which giveaway this is for
        message_id = str(interaction.message.id)
        giveaway_id = None
        
        for g_id, giveaway in self.giveaway_system.active_giveaways.items():
            if giveaway.get('message_id') == message_id:
                giveaway_id = g_id
                break
        
        if not giveaway_id:
            await interaction.response.send_message(
                "This giveaway no longer exists or has ended.",
                ephemeral=True
            )
            return
        
        # Add the user to participants
        user_id = str(interaction.user.id)
        
        if 'participants' not in self.giveaway_system.active_giveaways[giveaway_id]:
            self.giveaway_system.active_giveaways[giveaway_id]['participants'] = []
        
        if user_id not in self.giveaway_system.active_giveaways[giveaway_id]['participants']:
            self.giveaway_system.active_giveaways[giveaway_id]['participants'].append(user_id)
            self.giveaway_system.save_giveaways()
            
            await interaction.response.send_message(
                "You have entered the giveaway! Good luck! 🍀",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You have already entered this giveaway!",
                ephemeral=True
            )


class GiveawayCreateModal(discord.ui.Modal):
    """Modal for creating a new giveaway."""
    
    prize = discord.ui.TextInput(
        label="Prize",
        placeholder="What are you giving away?",
        required=True,
        max_length=100
    )
    
    winners_count = discord.ui.TextInput(
        label="Number of Winners",
        placeholder="Enter number of winners (default: 1)",
        required=False,
        default="1"
    )
    
    duration = discord.ui.TextInput(
        label="Duration (hours)",
        placeholder="How long should the giveaway last? (in hours)",
        required=True
    )
    
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="ID of the channel to host the giveaway in",
        required=True
    )
    
    def __init__(self, giveaway_system):
        super().__init__(title="Create a Giveaway")
        self.giveaway_system = giveaway_system
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse winners count
            winners_count = 1
            if self.winners_count.value:
                winners_count = int(self.winners_count.value)
                if winners_count < 1:
                    winners_count = 1
            
            # Parse duration
            duration_hours = float(self.duration.value)
            if duration_hours < 0.1:  # Minimum 6 minutes
                duration_hours = 0.1
            
            # Get the channel
            channel = interaction.guild.get_channel(int(self.channel_id.value))
            if not channel:
                await interaction.followup.send(
                    "Invalid channel ID. Please provide a valid text channel ID.",
                    ephemeral=True
                )
                return
            
            # Start the giveaway
            giveaway_id = await self.giveaway_system.start_giveaway(
                channel=channel,
                prize=self.prize.value,
                duration_hours=duration_hours,
                winners_count=winners_count,
                host_user=interaction.user
            )
            
            # Send confirmation
            await interaction.followup.send(
                f"Giveaway created successfully in {channel.mention}!\n"
                f"Prize: **{self.prize.value}**\n"
                f"Duration: {duration_hours} hours\n"
                f"Winners: {winners_count}\n"
                f"Giveaway ID: `{giveaway_id}`",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.followup.send(
                "Invalid input. Please ensure duration and winners count are valid numbers.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating giveaway: {e}")
            await interaction.followup.send(
                "An error occurred while creating the giveaway. Please try again later.",
                ephemeral=True
            )


async def setup(bot):
    """Add the giveaway system cog to the bot."""
    giveaway_cog = GiveawaySystem(bot)
    await bot.add_cog(giveaway_cog)
    logger.info("Giveaway system cog loaded")
    return giveaway_cog