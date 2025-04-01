import discord
from discord import app_commands
from discord.ext import commands
import time
import asyncio
import random
from logger import setup_logger
from database import Database
import os
from typing import Optional, Union

logger = setup_logger('leveling')

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

class LevelingCog(commands.Cog):
    """Cog for handling all leveling-related commands and functionality."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.xp_cooldowns = {}  # Memory cache of cooldowns
        logger.info("Leveling system initialized")
    
    async def create_rank_embed(self, user_data, member):
        """Create a cool, visually appealing rank card with all details."""
        next_level_xp = self.db.calculate_required_xp(user_data['level'])

        progress = user_data['xp'] / next_level_xp
        progress_bar = self.get_cool_progress_bar(progress)
        percent = int(progress * 100)

        max_prestige = 5  # Maximum prestige level
        prestige_level = min(user_data['prestige'], max_prestige)
        
        # Cool prestige display with custom icons
        prestige_icons = ["👑", "💎", "🔮", "⚜️", "🏆"]
        if prestige_level > 0:
            prestige_display = f"{prestige_icons[prestige_level-1]} **PRESTIGE {prestige_level}** {prestige_icons[prestige_level-1]}"
        else:
            prestige_display = "⭐ **NOVICE** ⭐"

        leaderboard = self.db.get_leaderboard(100)  # Get top 100 to find position
        rank_position = next((i for i, user in enumerate(leaderboard, 1) if user['user_id'] == user_data['user_id']), "???")
        
        # Cooler rank display with badges
        try:
            rank_pos = int(rank_position) if isinstance(rank_position, str) else rank_position
            if rank_pos == 1:
                rank_display = "🥇 **SERVER CHAMPION**"
            elif rank_pos == 2:
                rank_display = "🥈 **ELITE CHALLENGER**"
            elif rank_pos == 3:
                rank_display = "🥉 **BRONZE CONTENDER**"
            elif isinstance(rank_pos, int) and rank_pos <= 10:
                rank_display = f"🏅 **TOP {rank_pos}**"
            else:
                rank_display = f"🔹 **RANK #{rank_pos}**"
        except (ValueError, TypeError):
            rank_display = f"⚪ **RANK #{rank_position}**"

        formatted_xp = f"{user_data['xp']:,}"
        formatted_next_level = f"{next_level_xp:,}"

        coins_int = int(user_data['coins'])
        formatted_coins = f"{coins_int:,}"

        message_count = user_data.get('message_count', 0)
        formatted_msg_count = f"{message_count:,}"
        
        # Calculate XP needed for next level
        xp_needed = next_level_xp - user_data['xp']
        formatted_xp_needed = f"{xp_needed:,}"
        
        # Generate a color based on level/prestige
        rainbow_color = self.get_level_color(user_data['level'], user_data['prestige'])
        
        # Create a cool embed with title
        embed = discord.Embed(
            title=f"⚡ {member.display_name}'s Profile ⚡",
            color=discord.Color(rainbow_color)
        )
        
        # Add level banner - this is the coolest part!
        level_display = f"```fix\n⚜️ LEVEL {user_data['level']} ⚜️```"
        
        # Structured display with all details
        embed.description = (
            f"{level_display}\n"
            f"{prestige_display}\n"
            f"{rank_display}\n\n"
            f"**Progress:** {progress_bar}\n"
            f"**XP:** {formatted_xp} / {formatted_next_level} ({percent}%)\n"
            f"**Needed for Next Level:** {formatted_xp_needed} XP\n"
            f"**<:activitycoin:1350889157676761088> Coins:** {formatted_coins}\n"
            f"**💬 Messages:** {formatted_msg_count}\n"
        )
        
        # Add a motivational footer based on level
        if user_data['level'] < 10:
            footer = "Just getting started! Keep it up!"
        elif user_data['level'] < 25:
            footer = "Making great progress! You're becoming a regular!"
        elif user_data['level'] < 50:
            footer = "Impressive dedication! You're a vital community member!"
        else:
            footer = "Amazing commitment! You're a server legend!"
            
        embed.set_footer(text=footer)

        # Add user avatar
        embed.set_thumbnail(url=member.display_avatar.url)
        
        return embed
        
    def get_cool_progress_bar(self, progress, length=15):
        """Create a cool, visually distinctive progress bar."""
        filled_length = int(length * progress)
        empty_length = length - filled_length
        
        # Use more visually distinct characters for better appearance
        fill_char = "■"
        empty_char = "□"
        
        # Create a more visually appealing progress bar
        bar = fill_char * filled_length + empty_char * empty_length
        
        # Return formatted bar
        return f"`{bar}`"
        
    def get_advanced_progress_bar(self, progress, length=10):
        """Create an advanced text-based progress bar with more visual appeal."""
        filled_length = int(length * progress)
        empty_length = length - filled_length
        
        # Use more visually distinct characters for better appearance
        fill_chars = ["▰", "▰", "▰"]  # Multiple options for variety
        empty_char = "▱"
        
        # Create a more visually appealing progress bar
        filled_section = "".join(random.choice(fill_chars) for _ in range(filled_length))
        empty_section = empty_char * empty_length
        
        # Add visual indicators at start/end for better framing
        return f"`{filled_section}{empty_section}`"
        
    def get_level_color(self, level, prestige):
        """Generate a color based on user level and prestige for consistent visual identity."""
        # Base colors for different prestige tiers
        prestige_colors = [
            0x3498db,  # Blue (Prestige 0)
            0xe74c3c,  # Red (Prestige 1)
            0x9b59b6,  # Purple (Prestige 2)
            0xf1c40f,  # Gold (Prestige 3)
            0x2ecc71,  # Green (Prestige 4)
            0xe67e22,  # Orange (Prestige 5)
        ]
        
        base_color = prestige_colors[min(prestige, len(prestige_colors)-1)]
        
        # Add a slight variation based on level
        level_variation = (level % 10) * 0x030303
        color = base_color + level_variation
        
        # Ensure color is within valid range
        return max(0, min(0xFFFFFF, color))
    
    def get_progress_bar(self, progress, length=10):
        """Create a text-based progress bar."""
        filled_length = int(length * progress)
        empty_length = length - filled_length
        
        fill_char = "█"
        empty_char = "░"
        
        bar = fill_char * filled_length + empty_char * empty_length
        percent = int(progress * 100)
        
        return f"`{bar}` {percent}%"
    
    @app_commands.command(name="rank", description="✨ Check your or another user's advanced rank card")
    @app_commands.describe(
        member="The member whose rank you want to check (optional)"
    )
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Display enhanced rank information with a modern design."""

        # Show typing indicator for a better user experience
        await interaction.response.defer(thinking=True)
        
        # Ensure member is valid, default to interaction.user if None
        if member is None:
            member = interaction.user
            
        # Safety check to ensure member is not None after our attempt to set it
        if member is None:
            await interaction.followup.send("Error: Cannot display rank card. Please try again later.", ephemeral=True)
            logger.error("Member is None in rank command even after fallback to interaction.user")
            return
        
        try:
            user_id = str(member.id)
            username = str(member)
            
            # Fetch user's data
            user_data = self.db.get_or_create_user(user_id, username)
            
            if not user_data:
                await interaction.followup.send(f"Couldn't find user data for {member.display_name}. They might need to chat first!", ephemeral=True)
                return

            # Generate the enhanced rank embed
            embed = await self.create_rank_embed(user_data, member)
            
            # Send the fancy rank card without introductory text
            await interaction.followup.send(embed=embed)
            logger.info(f"Enhanced rank command used by {interaction.user} for {member}")
            
        except Exception as e:
            logger.error(f"Error in rank command: {e}")
            await interaction.followup.send("An error occurred while creating your rank card. Please try again.", ephemeral=True)
    
    @app_commands.command(name="editleveling", description="Configure the leveling system (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def edit_leveling(self, interaction: discord.Interaction):
        """Open a panel to edit leveling system settings."""

        settings = self.db.get_settings()

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="Leveling System Settings",
            description="Use the buttons below to adjust the leveling system settings.",
            color=discord.Color(rainbow_color)
        )

        xp_status = settings.get('xp_enabled', 1)
        status_text = "✅ **Enabled**" if xp_status else "❌ **Disabled**"
        status_note = "" if xp_status else "\n*Use /xpstart to enable XP gain*"
        
        embed.add_field(
            name="XP Status",
            value=f"{status_text}{status_note}",
            inline=False
        )

        min_xp = settings.get('min_xp_per_message', 0)
        max_xp = settings.get('max_xp_per_message', 0)
        
        if min_xp > 0 and max_xp > 0 and min_xp != max_xp:

            embed.add_field(
                name="XP Per Message",
                value=f"🎲 **{min_xp}-{max_xp}** (random)",
                inline=True
            )
        else:

            embed.add_field(
                name="XP Per Message",
                value=f"🔢 **{settings['xp_per_message']}**",
                inline=True
            )
        
        embed.add_field(
            name="Coins Per Level Up",
            value=f"💰 **{settings['coins_per_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="XP Cooldown",
            value=f"⏱️ **{settings['xp_cooldown']}** seconds",
            inline=True
        )
        
        embed.add_field(
            name="Base XP Required",
            value=f"📊 **{settings['base_xp_required']}** XP\n*(Level 1: {settings['base_xp_required']}, Level 2: {settings['base_xp_required']*2}, etc.)*",
            inline=False
        )

        view = LevelingSettingsView(self.db, self.bot)
        
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Edit leveling settings panel opened by {interaction.user}")
    
    @app_commands.command(name="xpstop", description="Stop all users from gaining XP and coins (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def xpstop(self, interaction: discord.Interaction):
        """Stop all users from gaining XP and coins in the server."""

        if not self.db.get_xp_status():
            await interaction.response.send_message("XP and coin gain is already disabled.", ephemeral=True)
            return

        self.db.toggle_xp(enable=False)

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="⚠️ XP AND COIN GAIN DISABLED ⚠️",
            description="Users will no longer earn XP or coins from any activity.",
            color=discord.Color(rainbow_color)
        )

        await interaction.response.send_message(embed=embed, ephemeral=False)
        logger.info(f"XP and coin gain disabled by {interaction.user}")
    
    @app_commands.command(name="xpstart", description="Allow users to gain XP and coins again (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def xpstart(self, interaction: discord.Interaction):
        """Re-enable XP and coin gain for all users in the server."""

        if self.db.get_xp_status():
            await interaction.response.send_message("XP and coin gain is already enabled.", ephemeral=True)
            return

        self.db.toggle_xp(enable=True)

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="✅ XP AND COIN GAIN ENABLED ✅",
            description="Users will now earn XP and coins from activity again.",
            color=discord.Color(rainbow_color)
        )

        await interaction.response.send_message(embed=embed, ephemeral=False)
        logger.info(f"XP and coin gain enabled by {interaction.user}")
    
    @app_commands.command(name="leaderboard", description="Display the server's top members")
    async def leaderboard(self, interaction: discord.Interaction, limit: int = 10):
        """Display the leaderboard of top users."""

        if limit < 1:
            limit = 10
        if limit > 25:
            limit = 25  # Prevent abuse with huge numbers

        leaderboard_data = self.db.get_leaderboard(limit)
        
        if not leaderboard_data:
            await interaction.response.send_message("No users found in the leaderboard yet!", ephemeral=True)
            return

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="🏆 Server Leaderboard",
            description=f"Top {len(leaderboard_data)} members by level and experience",
            color=discord.Color(rainbow_color)
        )
        
        for i, user_data in enumerate(leaderboard_data, 1):

            try:
                member = await interaction.guild.fetch_member(user_data['user_id'])
                name = member.display_name
            except:

                name = user_data['username']

            prestige_str = f"P{user_data['prestige']} " if user_data['prestige'] > 0 else ""

            coins_int = int(user_data['coins'])
            
            value = f"Level: **{user_data['level']}** {prestige_str}| XP: **{user_data['xp']}** | Coins: **{coins_int:,}**"
            
            embed.add_field(
                name=f"{i}. {name}",
                value=value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Leaderboard command used by {interaction.user}")
    
    @app_commands.command(name="addlevel", description="Add levels to a user (Admin only)")
    @app_commands.describe(
        member="The member to add levels to",
        amount="The number of levels to add"
    )
    async def addlevel(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        """Add levels to a user (Admin only)."""

        if amount <= 0:
            await interaction.response.send_message("❌ Please provide a positive number of levels to add.", ephemeral=True)
            return

        user_id = member.id
        username = member.name
        user_data = self.db.get_or_create_user(user_id, username)
        
        if user_data is None:
            await interaction.response.send_message("❌ Failed to retrieve user data. Please try again later.", ephemeral=True)
            return

        initial_level = user_data['level']

        new_level = initial_level + amount

        settings = self.db.get_settings()
        base_xp = settings['base_xp_required']

        current_xp = user_data['xp']

        next_level_xp = base_xp * new_level

        self.db.update_user(user_id, {'level': new_level, 'xp': current_xp})

        updated_user = self.db.get_user(user_id)

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="✅ Level Added",
            description=f"Successfully added {amount} levels to {member.mention}.",
            color=discord.Color(rainbow_color)
        )

        embed.add_field(
            name="Level",
            value=f"{initial_level} → {new_level}",
            inline=True
        )
        
        embed.add_field(
            name="XP Progress",
            value=f"{current_xp:,}/{next_level_xp:,} XP required for next level",
            inline=True
        )

        level_roles_cog = self.bot.get_cog("LevelRolesCog")
        if level_roles_cog:

            role_success, role_message = await level_roles_cog.update_member_roles(member, new_level)
            if role_success:
                embed.add_field(
                    name="Roles Updated",
                    value=role_message,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Roles Not Updated",
                    value=f"Could not update roles: {role_message}",
                    inline=False
                )
        else:
            logger.warning(f"LevelRolesCog not found when updating roles for {member.name} via addlevel command")

        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="removelevel", description="Remove levels from a user (Admin only)")
    @app_commands.describe(
        member="The member to remove levels from",
        amount="The number of levels to remove"
    )
    async def removelevel(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        """Remove levels from a user (Admin only)."""

        if amount <= 0:
            await interaction.response.send_message("❌ Please provide a positive number of levels to remove.", ephemeral=True)
            return

        user_id = member.id
        username = member.name
        user_data = self.db.get_or_create_user(user_id, username)
        
        if user_data is None:
            await interaction.response.send_message("❌ Failed to retrieve user data. Please try again later.", ephemeral=True)
            return

        initial_level = user_data['level']

        new_level = max(1, initial_level - amount)

        settings = self.db.get_settings()
        base_xp = settings['base_xp_required']

        current_xp = user_data['xp']

        next_level_xp = base_xp * new_level

        self.db.update_user(user_id, {'level': new_level, 'xp': current_xp})

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="✅ Level Removed",
            description=f"Successfully removed {amount} levels from {member.mention}.",
            color=discord.Color(rainbow_color)
        )

        embed.add_field(
            name="Level",
            value=f"{initial_level} → {new_level}",
            inline=True
        )
        
        embed.add_field(
            name="XP Progress",
            value=f"{current_xp:,}/{next_level_xp:,} XP required for next level",
            inline=True
        )

        level_roles_cog = self.bot.get_cog("LevelRolesCog")
        if level_roles_cog:

            role_success, role_message = await level_roles_cog.update_member_roles(member, new_level)
            if role_success:
                embed.add_field(
                    name="Roles Updated",
                    value=role_message,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Roles Not Updated",
                    value=f"Could not update roles: {role_message}",
                    inline=False
                )
        else:
            logger.warning(f"LevelRolesCog not found when updating roles for {member.name} via removelevel command")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="addcoin", description="Add coins to a user (Admin only)")
    @app_commands.describe(
        member="The member to add coins to",
        amount="The number of coins to add"
    )
    async def addcoin(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        """Add coins to a user (Admin only)."""

        if amount <= 0:

            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Please provide a positive number of coins to add.",
                color=discord.Color(rainbow_color)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_id = member.id
        username = member.name

        self.db.add_coins(user_id, username, amount)

        user_data = self.db.get_or_create_user(user_id, username)

        coins = int(user_data['coins'])

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="✅ Coins Added",
            description=f"Successfully added {amount:,} coins to {member.mention}.",
            color=discord.Color(rainbow_color)
        )

        embed.add_field(
            name="Current Balance",
            value=f"💰 {coins:,} coins",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="removecoin", description="Remove coins from a user (Admin only)")
    @app_commands.describe(
        member="The member to remove coins from",
        amount="The number of coins to remove"
    )
    async def removecoin(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        """Remove coins from a user (Admin only)."""

        if amount <= 0:

            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Please provide a positive number of coins to remove.",
                color=discord.Color(rainbow_color)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_id = member.id
        username = member.name
        user_data = self.db.get_or_create_user(user_id, username)
        
        if user_data is None:
            await interaction.response.send_message("❌ Failed to retrieve user data. Please try again later.", ephemeral=True)
            return

        coins = int(user_data['coins'])  # Convert to integer to remove all decimals
        if user_data['coins'] < amount:

            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title="⚠️ Insufficient Coins",
                description=f"{member.mention} only has {coins:,} coins. Cannot remove {amount:,} coins.",
                color=discord.Color(rainbow_color)
            )
            
            embed.add_field(
                name="Suggestion",
                value=f"Use `/removecoin {member.mention} {coins}` to remove all their coins.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.db.add_coins(user_id, username, -amount)

        user_data = self.db.get_or_create_user(user_id, username)

        coins = int(user_data['coins'])

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="✅ Coins Removed",
            description=f"Successfully removed {amount:,} coins from {member.mention}.",
            color=discord.Color(rainbow_color)
        )

        embed.add_field(
            name="Current Balance",
            value=f"💰 {coins:,} coins",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP when users send messages."""

        if message.author.bot:
            return

        if not message.guild:
            return

        user_id = message.author.id
        username = str(message.author)
        
        logger.info(f"Processing message from {username} (ID: {user_id}) for XP")

        xp_multiplier = 1.0
        coin_multiplier = 1.0
        
        event_system_cog = self.bot.get_cog("EventSystemCog")
        if event_system_cog:

            xp_multiplier = await event_system_cog.get_xp_multiplier()
            coin_multiplier = await event_system_cog.get_coin_multiplier()

            if event_system_cog.settings.xp_race_active:
                await event_system_cog.add_xp_race_points(user_id, username, 1)
        
        logger.info(f"Multipliers - XP: {xp_multiplier}x, Coins: {coin_multiplier}x")

        settings = self.db.get_settings()
        logger.info(f"XP Enabled: {settings.get('xp_enabled', 1)}")

        updated_user, leveled_up, xp_earned = self.db.add_xp(user_id, username, xp_multiplier=xp_multiplier, coin_multiplier=coin_multiplier)
        
        logger.info(f"XP add result: User updated: {updated_user is not None}, Leveled up: {leveled_up}, XP earned: {xp_earned}")

        if leveled_up and updated_user:

            settings = self.db.get_settings()
            coins_earned = int(settings['coins_per_level'] * coin_multiplier)

            multiplier_text = ""
            if xp_multiplier > 1.0 or coin_multiplier > 1.0:
                if xp_multiplier == coin_multiplier:
                    multiplier_text = f" (with {xp_multiplier}x event bonus!)"
                else:
                    multiplier_text = f" (with XP: {xp_multiplier}x, Coins: {coin_multiplier}x event bonus!)"

            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title="🎉 LEVEL UP! 🎉",
                description=f"{message.author.mention} has reached level **{updated_user['level']}**!\n"
                           f"💰 You earned **{coins_earned}** coins{multiplier_text}!",
                color=discord.Color(rainbow_color)
            )

            try:
                await message.channel.send(embed=embed)
                logger.info(f"User {message.author} leveled up to level {updated_user['level']}")

                self.bot.dispatch('level_up', message.author, updated_user['level'])
                logger.info(f"Dispatched level_up event for {message.author.name} (Level {updated_user['level']})")
            except Exception as e:
                logger.error(f"Failed to send level up message: {e}")

class SettingModal(discord.ui.Modal):
    """Modal for changing a leveling system setting."""
    
    def __init__(self, title, setting_name, current_value, callback):
        super().__init__(title=title)
        self.setting_name = setting_name
        self.callback_func = callback

        self.value_input = discord.ui.TextInput(
            label=f"Enter new value (current: {current_value})",
            placeholder=f"Enter a number...",
            default=str(current_value),
            required=True,
            min_length=1,
            max_length=10
        )
        self.add_item(self.value_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            if self.setting_name in ['xp_multiplier']:
                new_value = float(self.value_input.value)
            else:
                new_value = int(self.value_input.value)

            await self.callback_func(interaction, self.setting_name, new_value)
            
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number!",
                ephemeral=True
            )

class MinMaxXPModal(discord.ui.Modal):
    """Modal for setting min and max XP per message."""
    
    min_xp = discord.ui.TextInput(
        label="Minimum XP",
        placeholder="Enter the minimum XP per message",
        required=True
    )
    
    max_xp = discord.ui.TextInput(
        label="Maximum XP",
        placeholder="Enter the maximum XP per message",
        required=True
    )
    
    def __init__(self, db, current_min=1, current_max=10):
        super().__init__(title="Set Min-Max XP Range")
        self.db = db
        self.min_xp.default = str(current_min)
        self.max_xp.default = str(current_max)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            min_xp = int(self.min_xp.value)
            max_xp = int(self.max_xp.value)

            if min_xp < 1:
                await interaction.response.send_message("Minimum XP must be at least 1!", ephemeral=True)
                return
                
            if max_xp < min_xp:
                await interaction.response.send_message("Maximum XP must be greater than or equal to Minimum XP!", ephemeral=True)
                return

            settings = self.db.get_settings()
            settings['min_xp_per_message'] = min_xp
            settings['max_xp_per_message'] = max_xp
            self.db.update_settings(settings)

            rainbow_color = get_rainbow_color()
            embed = discord.Embed(
                title="Leveling System Settings",
                description="Random XP range updated successfully!",
                color=discord.Color(rainbow_color)
            )

            xp_status = settings.get('xp_enabled', 1)
            status_text = "✅ **Enabled**" if xp_status else "❌ **Disabled**"
            status_note = "" if xp_status else "\n*Use /xpstart to enable XP gain*"
            
            embed.add_field(
                name="XP Status",
                value=f"{status_text}{status_note}",
                inline=False
            )

            embed.add_field(
                name="XP Per Message",
                value=f"🎲 **{min_xp}-{max_xp}** (random)",
                inline=True
            )
            
            embed.add_field(
                name="Coins Per Level Up",
                value=f"💰 **{settings['coins_per_level']}**",
                inline=True
            )
            
            embed.add_field(
                name="XP Cooldown",
                value=f"⏱️ **{settings['xp_cooldown']}** seconds",
                inline=True
            )
            
            embed.add_field(
                name="Base XP Required",
                value=f"📊 **{settings['base_xp_required']}** XP\n*(Level 1: {settings['base_xp_required']}, Level 2: {settings['base_xp_required']*2}, etc.)*",
                inline=False
            )

            await interaction.response.edit_message(embed=embed)
            
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid numbers!",
                ephemeral=True
            )

class LevelingSettingsView(discord.ui.View):
    """View with buttons for editing leveling system settings."""
    
    def __init__(self, db, bot):
        super().__init__(timeout=300)  # 5 minute timeout
        self.db = db
        self.bot = bot
    
    @discord.ui.button(label="XP Per Message", style=discord.ButtonStyle.primary, emoji="📝")
    async def xp_per_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit XP awarded per message."""
        settings = self.db.get_settings()
        modal = SettingModal(
            "Edit XP Per Message",
            "xp_per_message",
            settings['xp_per_message'],
            self.update_setting
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Random XP Range", style=discord.ButtonStyle.primary, emoji="🎲", row=1)
    async def random_xp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set random XP range (min-max)."""
        settings = self.db.get_settings()
        min_xp = settings.get('min_xp_per_message', 1)
        max_xp = settings.get('max_xp_per_message', settings['xp_per_message'])
        
        modal = MinMaxXPModal(self.db, min_xp, max_xp)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Coins Per Level", style=discord.ButtonStyle.primary, emoji="💰")
    async def coins_per_level_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit coins awarded per level up."""
        settings = self.db.get_settings()
        modal = SettingModal(
            "Edit Coins Per Level",
            "coins_per_level",
            settings['coins_per_level'],
            self.update_setting
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="XP Cooldown", style=discord.ButtonStyle.primary, emoji="⏱️")
    async def xp_cooldown_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit XP cooldown in seconds."""
        settings = self.db.get_settings()
        modal = SettingModal(
            "Edit XP Cooldown",
            "xp_cooldown",
            settings['xp_cooldown'],
            self.update_setting
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Base XP Required", style=discord.ButtonStyle.primary, emoji="📊")
    async def base_xp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit base XP required for level up."""
        settings = self.db.get_settings()
        modal = SettingModal(
            "Edit Base XP Required",
            "base_xp_required",
            settings['base_xp_required'],
            self.update_setting
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Save & Close", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to save settings and close the panel."""
        await interaction.response.edit_message(
            content="Settings saved successfully!",
            embed=None,
            view=None
        )
        self.stop()
    
    async def update_setting(self, interaction, setting_name, new_value):
        """Update a setting in the database."""
        settings = self.db.get_settings()

        if setting_name == "xp_per_message" and new_value < 1:
            await interaction.response.send_message("XP per message must be at least 1!", ephemeral=True)
            return
        
        if setting_name == "coins_per_level" and new_value < 0:
            await interaction.response.send_message("Coins per level cannot be negative!", ephemeral=True)
            return
        
        if setting_name == "xp_cooldown" and new_value < 0:
            await interaction.response.send_message("XP cooldown cannot be negative!", ephemeral=True)
            return
        
        if setting_name == "base_xp_required" and new_value < 1:
            await interaction.response.send_message("Base XP required must be at least 1!", ephemeral=True)
            return

        settings[setting_name] = new_value
        self.db.update_settings(settings)

        rainbow_color = get_rainbow_color()
        embed = discord.Embed(
            title="Leveling System Settings",
            description="Settings updated successfully!",
            color=discord.Color(rainbow_color)
        )

        xp_status = settings.get('xp_enabled', 1)
        status_text = "✅ **Enabled**" if xp_status else "❌ **Disabled**"
        status_note = "" if xp_status else "\n*Use /xpstart to enable XP gain*"
        
        embed.add_field(
            name="XP Status",
            value=f"{status_text}{status_note}",
            inline=False
        )

        min_xp = settings.get('min_xp_per_message', 0)
        max_xp = settings.get('max_xp_per_message', 0)
        
        if min_xp > 0 and max_xp > 0 and min_xp != max_xp:

            embed.add_field(
                name="XP Per Message",
                value=f"🎲 **{min_xp}-{max_xp}** (random)",
                inline=True
            )
        else:

            embed.add_field(
                name="XP Per Message",
                value=f"🔢 **{settings['xp_per_message']}**",
                inline=True
            )
        
        embed.add_field(
            name="Coins Per Level Up",
            value=f"💰 **{settings['coins_per_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="XP Cooldown",
            value=f"⏱️ **{settings['xp_cooldown']}** seconds",
            inline=True
        )
        
        embed.add_field(
            name="Base XP Required",
            value=f"📊 **{settings['base_xp_required']}** XP\n*(Level 1: {settings['base_xp_required']}, Level 2: {settings['base_xp_required']*2}, etc.)*",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @app_commands.command(name="edit_message_xp", description="Edit message XP settings (Admin only)")
    @app_commands.describe(
        min_xp="Minimum XP gained per message",
        max_xp="Maximum XP gained per message",
        cooldown_min="Minimum cooldown between messages in seconds",
        cooldown_max="Maximum cooldown between messages in seconds"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_message_xp(self, interaction: discord.Interaction, min_xp: int = None, max_xp: int = None, 
                             cooldown_min: int = None, cooldown_max: int = None):
        """Edit message XP settings."""
        settings = self.db.get_settings()
        updated = False
        
        if min_xp is not None and min_xp >= 0:
            settings['min_xp_per_message'] = min_xp
            updated = True
            
        if max_xp is not None and max_xp >= 0:
            settings['max_xp_per_message'] = max_xp
            updated = True
            
        if cooldown_min is not None and cooldown_min >= 0:
            settings['xp_cooldown_min'] = cooldown_min
            updated = True
            
        if cooldown_max is not None and cooldown_max >= 0:
            settings['xp_cooldown_max'] = cooldown_max
            updated = True
        
        if updated:
            # Ensure min_xp doesn't exceed max_xp
            if settings['min_xp_per_message'] > settings['max_xp_per_message']:
                settings['min_xp_per_message'] = settings['max_xp_per_message']
                
            # Ensure cooldown_min doesn't exceed cooldown_max
            if settings['xp_cooldown_min'] > settings['xp_cooldown_max']:
                settings['xp_cooldown_min'] = settings['xp_cooldown_max']
                
            self.db.update_settings(settings)
            
            embed = discord.Embed(
                title="Message XP Settings Updated",
                description="The message XP settings have been updated:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="XP Per Message",
                value=f"🎲 **{settings['min_xp_per_message']}-{settings['max_xp_per_message']}** (random)",
                inline=True
            )
            
            embed.add_field(
                name="Cooldown",
                value=f"⏱️ **{settings['xp_cooldown_min']}-{settings['xp_cooldown_max']}** seconds",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Message XP settings updated by {interaction.user}")
        else:
            await interaction.response.send_message("No valid settings provided. Please specify at least one setting to update.", ephemeral=True)
    
    @app_commands.command(name="edit_voice_rewards", description="Edit voice channel reward settings (Admin only)")
    @app_commands.describe(
        active_xp="XP per active minute in voice channels",
        inactive_xp="XP per inactive minute in voice channels",
        active_coins="Coins per active minute in voice channels",
        inactive_coins="Coins per inactive minute in voice channels"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_voice_rewards(self, interaction: discord.Interaction, active_xp: int = None, inactive_xp: int = None,
                               active_coins: float = None, inactive_coins: float = None):
        """Edit voice channel reward settings."""
        settings = self.db.get_settings()
        updated = False
        
        if active_xp is not None and active_xp >= 0:
            settings['voice_active_xp'] = active_xp
            updated = True
            
        if inactive_xp is not None and inactive_xp >= 0:
            settings['voice_inactive_xp'] = inactive_xp
            updated = True
            
        if active_coins is not None and active_coins >= 0:
            settings['voice_active_coins'] = active_coins
            updated = True
            
        if inactive_coins is not None and inactive_coins >= 0:
            settings['voice_inactive_coins'] = inactive_coins
            updated = True
        
        if updated:
            self.db.update_settings(settings)
            
            embed = discord.Embed(
                title="Voice Channel Rewards Updated",
                description="The voice channel reward settings have been updated:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Active Voice",
                value=f"⭐ **{settings['voice_active_xp']}** XP per minute\n💰 **{settings['voice_active_coins']}** coins per minute",
                inline=True
            )
            
            embed.add_field(
                name="Inactive Voice",
                value=f"⭐ **{settings['voice_inactive_xp']}** XP per minute\n💰 **{settings['voice_inactive_coins']}** coins per minute",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Voice channel reward settings updated by {interaction.user}")
        else:
            await interaction.response.send_message("No valid settings provided. Please specify at least one setting to update.", ephemeral=True)
    
    @app_commands.command(name="edit_image_rewards", description="Edit image reward settings (Admin only)")
    @app_commands.describe(
        image_xp="XP gained per image posted"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_image_rewards(self, interaction: discord.Interaction, image_xp: int):
        """Edit image reward settings."""
        if image_xp < 0:
            await interaction.response.send_message("Image XP cannot be negative!", ephemeral=True)
            return
            
        settings = self.db.get_settings()
        settings['image_xp'] = image_xp
        self.db.update_settings(settings)
        
        embed = discord.Embed(
            title="Image Rewards Updated",
            description="The image reward settings have been updated:",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="XP Per Image",
            value=f"📸 **{settings['image_xp']}** XP per image",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        logger.info(f"Image reward settings updated by {interaction.user}")
    
    @app_commands.command(name="edit_streaming_rewards", description="Edit streaming reward settings (Admin only)")
    @app_commands.describe(
        streaming_xp="XP per minute of streaming",
        streaming_coins="Coins per minute of streaming"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_streaming_rewards(self, interaction: discord.Interaction, streaming_xp: int = None, streaming_coins: float = None):
        """Edit streaming reward settings."""
        settings = self.db.get_settings()
        updated = False
        
        if streaming_xp is not None and streaming_xp >= 0:
            settings['streaming_xp'] = streaming_xp
            updated = True
            
        if streaming_coins is not None and streaming_coins >= 0:
            settings['streaming_coins'] = streaming_coins
            updated = True
        
        if updated:
            self.db.update_settings(settings)
            
            embed = discord.Embed(
                title="Streaming Rewards Updated",
                description="The streaming reward settings have been updated:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Streaming Rewards",
                value=f"⭐ **{settings['streaming_xp']}** XP per minute\n💰 **{settings['streaming_coins']}** coins per minute",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Streaming reward settings updated by {interaction.user}")
        else:
            await interaction.response.send_message("No valid settings provided. Please specify at least one setting to update.", ephemeral=True)
    
    @app_commands.command(name="edit_leveling_progression", description="Edit leveling progression settings (Admin only)")
    @app_commands.describe(
        base_xp="Base XP required for level ups",
        coins_per_level="Coins awarded per level up",
        levels_per_prestige="Levels required to prestige",
        max_prestige="Maximum prestige level"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_leveling_progression(self, interaction: discord.Interaction, base_xp: int = None, 
                                      coins_per_level: int = None, levels_per_prestige: int = None, 
                                      max_prestige: int = None):
        """Edit leveling progression settings."""
        settings = self.db.get_settings()
        updated = False
        
        if base_xp is not None and base_xp > 0:
            settings['base_xp_required'] = base_xp
            updated = True
            
        if coins_per_level is not None and coins_per_level >= 0:
            settings['coins_per_level'] = coins_per_level
            updated = True
            
        if levels_per_prestige is not None and levels_per_prestige > 0:
            settings['levels_per_prestige'] = levels_per_prestige
            updated = True
            
        if max_prestige is not None and max_prestige >= 0:
            settings['max_prestige'] = max_prestige
            updated = True
        
        if updated:
            self.db.update_settings(settings)
            
            embed = discord.Embed(
                title="Leveling Progression Updated",
                description="The leveling progression settings have been updated:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="XP Requirements",
                value=f"📊 **{settings['base_xp_required']}** Base XP\n(increases with each level)",
                inline=True
            )
            
            embed.add_field(
                name="Level Rewards",
                value=f"💰 **{settings['coins_per_level']}** coins per level",
                inline=True
            )
            
            embed.add_field(
                name="Prestige Settings",
                value=f"🌟 **{settings['levels_per_prestige']}** levels per prestige\n👑 **{settings['max_prestige']}** maximum prestige",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Leveling progression settings updated by {interaction.user}")
        else:
            await interaction.response.send_message("No valid settings provided. Please specify at least one setting to update.", ephemeral=True)
    
    @app_commands.command(name="edit_prestige_rewards", description="Edit prestige reward settings (Admin only)")
    @app_commands.describe(
        prestige_coins="Coins awarded when prestiging",
        boost_multiplier="XP boost multiplier for prestiging",
        boost_duration="Duration of XP boost in hours"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_prestige_rewards(self, interaction: discord.Interaction, prestige_coins: int = None,
                                  boost_multiplier: float = None, boost_duration: int = None):
        """Edit prestige reward settings."""
        settings = self.db.get_settings()
        updated = False
        
        if prestige_coins is not None and prestige_coins >= 0:
            settings['prestige_coins'] = prestige_coins
            updated = True
            
        if boost_multiplier is not None and boost_multiplier >= 1.0:
            settings['prestige_boost_multiplier'] = boost_multiplier
            updated = True
            
        if boost_duration is not None and boost_duration > 0:
            # Convert hours to seconds
            settings['prestige_boost_duration'] = boost_duration * 3600
            updated = True
        
        if updated:
            self.db.update_settings(settings)
            
            # Convert seconds back to hours for display
            boost_hours = settings['prestige_boost_duration'] // 3600
            
            embed = discord.Embed(
                title="Prestige Rewards Updated",
                description="The prestige rewards settings have been updated:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Prestige Rewards",
                value=f"💰 **{settings['prestige_coins']}** coins per prestige\n🚀 **{settings['prestige_boost_multiplier']}x** XP boost for **{boost_hours}** hours",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Prestige reward settings updated by {interaction.user}")
        else:
            await interaction.response.send_message("No valid settings provided. Please specify at least one setting to update.", ephemeral=True)

async def setup(bot):
    """Add the leveling cog to the bot."""
    await bot.add_cog(LevelingCog(bot))
    logger.info("Leveling cog loaded")