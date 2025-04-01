import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
from logger import setup_logger
import datetime
from invite_modals import InviteAddModal, InviteRemoveModal, InviteResetModal

logger = setup_logger('invites', 'bot.log')

class InviteTracker:
    """Class for tracking and managing invites."""
    
    def __init__(self, db_name='data/leveling.db'):
        """Initialize the invite tracker with database connection."""
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        logger.info("Invite tracker initialized")

        self.guild_invites = {}
    
    def _create_tables(self):
        """Create necessary tables for invite tracking if they don't exist."""

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invites (
                user_id INTEGER PRIMARY KEY,
                regular_invites INTEGER DEFAULT 0,
                fake_invites INTEGER DEFAULT 0,
                bonus_invites INTEGER DEFAULT 0,
                left_invites INTEGER DEFAULT 0
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invite_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invite_uses (
                invited_user_id INTEGER PRIMARY KEY,
                inviter_id INTEGER,
                invite_code TEXT,
                join_time TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def get_invite_settings(self, guild_id):
        """Get settings for a guild."""
        self.cursor.execute(
            "SELECT * FROM invite_settings WHERE guild_id = ?",
            (guild_id,)
        )
        settings = self.cursor.fetchone()
        
        if not settings:

            self.cursor.execute(
                "INSERT INTO invite_settings (guild_id, log_channel_id) VALUES (?, ?)",
                (guild_id, None)
            )
            self.conn.commit()
            return {"guild_id": guild_id, "log_channel_id": None}
        
        return dict(settings)
    
    def set_log_channel(self, guild_id, channel_id):
        """Set the channel for invite logs."""
        self.cursor.execute(
            "INSERT OR REPLACE INTO invite_settings (guild_id, log_channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        self.conn.commit()
        return True
    
    def get_user_invites(self, user_id):
        """Get invite counts for a user."""
        self.cursor.execute(
            "SELECT * FROM invites WHERE user_id = ?",
            (user_id,)
        )
        invites = self.cursor.fetchone()
        
        if not invites:

            self.cursor.execute(
                "INSERT INTO invites (user_id, regular_invites, fake_invites, bonus_invites, left_invites) VALUES (?, 0, 0, 0, 0)",
                (user_id,)
            )
            self.conn.commit()
            return {"user_id": user_id, "regular_invites": 0, "fake_invites": 0, "bonus_invites": 0, "left_invites": 0}
        
        return dict(invites)
    
    def add_invites(self, user_id, regular=0, fake=0, bonus=0, left=0):
        """Add invites to a user's counts."""
        invites = self.get_user_invites(user_id)
        
        self.cursor.execute(
            """
            UPDATE invites SET 
                regular_invites = ?,
                fake_invites = ?,
                bonus_invites = ?,
                left_invites = ?
            WHERE user_id = ?
            """,
            (
                invites["regular_invites"] + regular,
                invites["fake_invites"] + fake,
                invites["bonus_invites"] + bonus,
                invites["left_invites"] + left,
                user_id
            )
        )
        self.conn.commit()
        return self.get_user_invites(user_id)
    
    def reset_user_invites(self, user_id):
        """Reset a user's invite counts to zero."""
        self.cursor.execute(
            "UPDATE invites SET regular_invites = 0, fake_invites = 0, bonus_invites = 0, left_invites = 0 WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()
        return True
        
    def reset_all_invites(self):
        """Reset all users' invite counts to zero."""
        self.cursor.execute(
            "UPDATE invites SET regular_invites = 0, fake_invites = 0, bonus_invites = 0, left_invites = 0"
        )
        self.conn.commit()
        return True
    
    def get_invite_leaderboard(self, limit=10):
        """Get top inviters by total invites."""
        self.cursor.execute(
            """
            SELECT 
                user_id, 
                regular_invites, 
                fake_invites, 
                bonus_invites, 
                left_invites,
                (regular_invites + bonus_invites - fake_invites - left_invites) as total_invites
            FROM invites
            ORDER BY total_invites DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in self.cursor.fetchall()]
    
    def track_invite_use(self, invited_user_id, inviter_id, invite_code):
        """Record which invite was used by a user."""
        current_time = datetime.datetime.now()
        self.cursor.execute(
            "INSERT OR REPLACE INTO invite_uses (invited_user_id, inviter_id, invite_code, join_time) VALUES (?, ?, ?, ?)",
            (invited_user_id, inviter_id, invite_code, current_time)
        )
        self.conn.commit()

        self.add_invites(inviter_id, regular=1)
        return True
    
    def get_user_inviter(self, user_id):
        """Get the user who invited another user."""
        self.cursor.execute(
            "SELECT inviter_id, invite_code, join_time FROM invite_uses WHERE invited_user_id = ?",
            (user_id,)
        )
        invite_use = self.cursor.fetchone()
        return dict(invite_use) if invite_use else None
    
    def handle_member_leave(self, user_id):
        """Handle when a member leaves, updating inviter stats."""
        invite_use = self.get_user_inviter(user_id)
        if invite_use:
            inviter_id = invite_use["inviter_id"]

            self.add_invites(inviter_id, left=1)
            return inviter_id
        return None
    
    def handle_fake_invite(self, inviter_id):
        """Mark an invite as fake (user left too quickly)."""
        self.add_invites(inviter_id, fake=1)

        self.add_invites(inviter_id, regular=-1)
        return True
    
    def close(self):
        """Close the database connection."""
        self.conn.close()

class InvitesCog(commands.Cog):
    """Cog for handling invite tracking and commands."""
    
    def __init__(self, bot):
        self.bot = bot
        self.invite_tracker = InviteTracker()
        self.log_messages = {}  # Store message IDs for later editing
        logger.info("Invites cog initialized")
    
    async def cache_invites(self):
        """Cache invites for all guilds."""
        for guild in self.bot.guilds:
            try:

                invites = await guild.invites()
                self.invite_tracker.guild_invites[guild.id] = {
                    invite.code: invite.uses for invite in invites
                }
                logger.info(f"Cached {len(invites)} invites for guild {guild.id}")
            except discord.errors.Forbidden:
                logger.warning(f"Missing permissions to fetch invites for guild {guild.id}")
                self.invite_tracker.guild_invites[guild.id] = {}
    
    @app_commands.command(name="invitepanel", description="Open the invites management panel (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def invite_panel(self, interaction: discord.Interaction):
        """Send a panel with invite management buttons."""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎟️ Invite Management",
            description="Manage your server invites with the buttons below.",
            color=discord.Color.blue()
        )

        settings = self.invite_tracker.get_invite_settings(interaction.guild.id)
        log_channel_id = settings.get("log_channel_id")

        log_channel_text = "Not set"
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                log_channel_text = log_channel.mention
            else:
                try:
                    log_channel = await interaction.guild.fetch_channel(log_channel_id)
                    if log_channel:
                        log_channel_text = log_channel.mention
                except:
                    log_channel_text = f"Unknown channel (ID: {log_channel_id})"
        
        embed.add_field(
            name="Current Settings",
            value=f"Log Channel: {log_channel_text}",
            inline=False
        )
        
        view = InviteManagementView(self)
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Invite panel opened by {interaction.user.id}")
    
    @app_commands.command(name="invites", description="Check invite counts for yourself or another user")
    async def check_invites(self, interaction: discord.Interaction, member: discord.Member = None):
        """Display invite counts for a user."""
        if member is None:
            member = interaction.user
        
        invites = self.invite_tracker.get_user_invites(member.id)

        total_invites = invites["regular_invites"] + invites["bonus_invites"] - invites["fake_invites"] - invites["left_invites"]
        
        embed = discord.Embed(
            title=f"🎟️ Invite Stats for {member.display_name}",
            color=discord.Color.blue()
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(
            name="✅ Regular Invites",
            value=f"{invites['regular_invites']}",
            inline=True
        )
        
        embed.add_field(
            name="🎁 Bonus Invites",
            value=f"{invites['bonus_invites']}",
            inline=True
        )
        
        embed.add_field(
            name="⚠️ Fake Invites",
            value=f"{invites['fake_invites']}",
            inline=True
        )
        
        embed.add_field(
            name="👋 Left Members",
            value=f"{invites['left_invites']}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Total Invites",
            value=f"**{total_invites}**",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Invites checked for {member.id} by {interaction.user.id}")
    
    @app_commands.command(name="inviteleaderboard", description="Show the server's top inviters")
    async def invite_leaderboard(self, interaction: discord.Interaction, limit: int = 10):
        """Display the leaderboard of top inviters."""
        if limit < 1:
            limit = 10
        if limit > 25:
            limit = 25  # Prevent abuse with huge numbers
        
        leaderboard = self.invite_tracker.get_invite_leaderboard(limit)
        
        if not leaderboard:
            await interaction.response.send_message("No invite data found yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏆 Invite Leaderboard",
            description=f"Top {len(leaderboard)} inviters in the server",
            color=discord.Color.gold()
        )
        
        for i, invite_data in enumerate(leaderboard, 1):

            try:
                member = await interaction.guild.fetch_member(invite_data['user_id'])
                name = member.display_name
            except:

                name = f"User {invite_data['user_id']}"
            
            total = invite_data['total_invites']

            details = (
                f"Regular: {invite_data['regular_invites']} | "
                f"Bonus: {invite_data['bonus_invites']} | "
                f"Fake: {invite_data['fake_invites']} | "
                f"Left: {invite_data['left_invites']}"
            )
            
            embed.add_field(
                name=f"{i}. {name} - {total} invites",
                value=details,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Invite leaderboard displayed by {interaction.user.id}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """When bot is ready, cache all guild invites and set default invite log channel."""
        await self.cache_invites()

        default_channel_id = 1354491891579752448
        for guild in self.bot.guilds:
            self.invite_tracker.set_log_channel(guild.id, default_channel_id)
            logger.info(f"Set default invite log channel to {default_channel_id} for guild {guild.id}")
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """When an invite is created, add it to the cache."""
        guild_id = invite.guild.id
        if guild_id not in self.invite_tracker.guild_invites:
            self.invite_tracker.guild_invites[guild_id] = {}
        self.invite_tracker.guild_invites[guild_id][invite.code] = 0
        logger.info(f"New invite {invite.code} created in guild {guild_id}")
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """When an invite is deleted, remove it from the cache."""
        guild_id = invite.guild.id
        if guild_id in self.invite_tracker.guild_invites and invite.code in self.invite_tracker.guild_invites[guild_id]:
            del self.invite_tracker.guild_invites[guild_id][invite.code]
            logger.info(f"Invite {invite.code} deleted from guild {guild_id}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """When a member joins, determine which invite they used."""
        guild = member.guild
        inviter_id = None
        invite_code = None
        is_vanity = False

        if guild.id not in self.invite_tracker.guild_invites:
            return

        old_invite_counts = self.invite_tracker.guild_invites[guild.id].copy()

        try:
            new_invites = await guild.invites()

            self.invite_tracker.guild_invites[guild.id] = {
                invite.code: invite.uses for invite in new_invites
            }

            for invite in new_invites:
                if invite.code in old_invite_counts:
                    if invite.uses > old_invite_counts[invite.code]:
                        inviter_id = invite.inviter.id
                        invite_code = invite.code
                        break
                else:

                    if invite.uses > 0:
                        inviter_id = invite.inviter.id
                        invite_code = invite.code
                        break

            settings = self.invite_tracker.get_invite_settings(guild.id)
            log_channel_id = settings["log_channel_id"]

            if inviter_id and invite_code:

                self.invite_tracker.track_invite_use(member.id, inviter_id, invite_code)

                excluded_channel_id = 1348388847758872616
                if log_channel_id and log_channel_id != excluded_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        try:
                            inviter = await guild.fetch_member(inviter_id)
                            inviter_mention = inviter.mention
                        except discord.NotFound:
                            # Handle the case where inviter is not in the guild anymore
                            inviter_mention = f"User (ID: {inviter_id})"
                            logger.warning(f"Inviter {inviter_id} is not in the guild anymore")

                        embed = discord.Embed(
                            title="Member Joined",
                            description=f"{member.mention} joined using {inviter_mention}'s invite `{invite_code}`",
                            color=discord.Color.green(),
                            timestamp=datetime.datetime.now()
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text=f"Member ID: {member.id}")
                        
                        message = await log_channel.send(embed=embed)
                        self.log_messages[member.id] = message.id

            elif log_channel_id:
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:

                    try:
                        vanity_invite = await guild.vanity_invite()
                        if vanity_invite:
                            is_vanity = True
                            embed = discord.Embed(
                                title="Member Joined",
                                description=f"{member.mention} joined using the server's vanity URL (`{vanity_invite.code}`)",
                                color=discord.Color.purple(),
                                timestamp=datetime.datetime.now()
                            )
                            embed.set_thumbnail(url=member.display_avatar.url)
                            embed.set_footer(text=f"Member ID: {member.id}")
                            
                            message = await log_channel.send(embed=embed)
                            self.log_messages[member.id] = message.id
                    except (discord.HTTPException, discord.Forbidden):

                        embed = discord.Embed(
                            title="Member Joined",
                            description=f"{member.mention} joined, but their invite source couldn't be determined (could be vanity, direct join, or Discovery)",
                            color=discord.Color.blue(),
                            timestamp=datetime.datetime.now()
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text=f"Member ID: {member.id}")
                        
                        message = await log_channel.send(embed=embed)
                        self.log_messages[member.id] = message.id
                
                logger.info(f"Member {member.id} joined using invite {invite_code} from {inviter_id}")
        except Exception as e:
            logger.error(f"Error tracking invite use: {e}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """When a member leaves, update invite stats."""

        inviter_id = self.invite_tracker.handle_member_leave(member.id)
        
        if inviter_id:

            guild = member.guild
            settings = self.invite_tracker.get_invite_settings(guild.id)
            log_channel_id = settings["log_channel_id"]

            excluded_channel_id = 1348388847758872616
            if log_channel_id and log_channel_id != excluded_channel_id:
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:
                    try:
                        inviter = await guild.fetch_member(inviter_id)
                        inviter_name = inviter.mention
                    except discord.NotFound:
                        # Handle the case where inviter is not in the guild anymore
                        inviter_name = f"User (ID: {inviter_id})"
                        logger.warning(f"Inviter {inviter_id} is not in the guild anymore")
                    except Exception as e:
                        inviter_name = f"User {inviter_id}"
                        logger.error(f"Error fetching inviter: {e}")
                    
                    embed = discord.Embed(
                        title="Member Left",
                        description=f"{member.display_name} left the server. They were invited by {inviter_name}.",
                        color=discord.Color.red(),
                        timestamp=datetime.datetime.now()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=f"Member ID: {member.id}")

                    if member.id in self.log_messages:
                        try:

                            old_msg_id = self.log_messages[member.id]
                            old_msg = await log_channel.fetch_message(old_msg_id)

                            old_embed = old_msg.embeds[0]
                            old_embed.add_field(
                                name="⚠️ Update",
                                value="This member has left the server.",
                                inline=False
                            )
                            await old_msg.edit(embed=old_embed)
                        except:

                            await log_channel.send(embed=embed)
                    else:
                        await log_channel.send(embed=embed)
            
            logger.info(f"Member {member.id} left, who was invited by {inviter_id}")

class UserSelectModal(discord.ui.Modal):
    """Modal for selecting a user by ID."""
    
    def __init__(self, title, callback):
        super().__init__(title=title)
        self.callback_func = callback
        
        self.user_id_input = discord.ui.TextInput(
            label="Member ID",
            placeholder="Right-click user, select 'Copy ID', paste here",
            required=True,
            min_length=17,
            max_length=19
        )
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            user_id = int(self.user_id_input.value)
            await self.callback_func(interaction, user_id)
        except ValueError:
            await interaction.response.send_message("Please enter a valid user ID!", ephemeral=True)

class InviteCountModal(discord.ui.Modal):
    """Modal for adding or removing invites."""
    
    def __init__(self, title, user_id, callback, is_add=True):
        super().__init__(title=title)
        self.user_id = user_id
        self.callback_func = callback
        self.is_add = is_add
        
        action = "Add" if is_add else "Remove"
        
        self.regular_input = discord.ui.TextInput(
            label=f"{action} Regular Invites Count",
            placeholder="Enter count (e.g. 5)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.regular_input)
        
        self.bonus_input = discord.ui.TextInput(
            label=f"{action} Bonus Invites Count",
            placeholder="Enter count (e.g. 3)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.bonus_input)
        
        self.fake_input = discord.ui.TextInput(
            label=f"{action} Fake Invites Count",
            placeholder="Enter count (e.g. 2)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.fake_input)
        
        self.left_input = discord.ui.TextInput(
            label=f"{action} Left Invites Count",
            placeholder="Enter count (e.g. 1)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.left_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            regular = int(self.regular_input.value or 0)
            bonus = int(self.bonus_input.value or 0)
            fake = int(self.fake_input.value or 0)
            left = int(self.left_input.value or 0)

            if not self.is_add:
                regular = -regular
                bonus = -bonus
                fake = -fake
                left = -left
            
            await self.callback_func(interaction, self.user_id, regular, bonus, fake, left)
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers!", ephemeral=True)

class ChannelSelectModal(discord.ui.Modal):
    """Modal for selecting a channel by ID."""
    
    def __init__(self, cog, title="Set Invites Log Channel"):
        super().__init__(title=title)
        self.cog = cog
        self.callback_func = cog.set_log_channel
        
        self.channel_id_input = discord.ui.TextInput(
            label="Channel ID",
            placeholder="Right-click channel, select 'Copy ID', paste here",
            required=True,
            min_length=17,
            max_length=19
        )
        self.add_item(self.channel_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            channel_id = int(self.channel_id_input.value)

            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                try:
                    channel = await interaction.guild.fetch_channel(channel_id)
                except discord.errors.NotFound:
                    await interaction.response.send_message("Could not find that channel in this server.", ephemeral=True)
                    return
                except Exception as e:
                    logger.error(f"Error fetching channel: {e}")
                    await interaction.response.send_message(f"Error fetching channel: {e}", ephemeral=True)
                    return

            await self.callback_func(interaction, channel_id)
            
        except ValueError:
            await interaction.response.send_message("Please enter a valid channel ID!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in ChannelSelectModal: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class ConfirmationView(discord.ui.View):
    """View with confirm/cancel buttons for dangerous actions."""
    
    def __init__(self, callback, user_id, timeout=60):
        super().__init__(timeout=timeout)
        self.callback = callback
        self.user_id = user_id
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm button"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You are not authorized to use these buttons.", ephemeral=True)
            return
        
        await self.callback(interaction)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel button"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You are not authorized to use these buttons.", ephemeral=True)
            return
        
        await interaction.response.send_message("Action cancelled.", ephemeral=True)
        self.stop()

class InviteManagementView(discord.ui.View):
    """View with buttons for managing invites."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        
    async def reset_all_invites_confirmed(self, interaction):
        """Reset all invite counts after confirmation."""
        try:

            self.cog.invite_tracker.reset_all_invites()

            embed = discord.Embed(
                title="✅ All Invites Reset",
                description="All invite counts have been reset to zero for all server members.",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"All invites reset by {interaction.user.id} in guild {interaction.guild_id}")
        except Exception as e:
            logger.error(f"Error resetting all invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Reset All Invites", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reset_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to reset all server invites."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this button.", ephemeral=True)
            return

        confirm_embed = discord.Embed(
            title="⚠️ Reset ALL Invites?",
            description="This will reset invite counts for ALL members in the server. This action cannot be undone.\n\nAre you sure?",
            color=discord.Color.red()
        )

        view = ConfirmationView(self.reset_all_invites_confirmed, interaction.user.id)
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Add Member Invites", style=discord.ButtonStyle.success, emoji="➕")
    async def add_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to add invites to a member."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this button.", ephemeral=True)
            return
        
        modal = InviteAddModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remove Member Invites", style=discord.ButtonStyle.secondary, emoji="➖")
    async def remove_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to remove invites from a member."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this button.", ephemeral=True)
            return
        
        modal = InviteRemoveModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Invites Logs Channel", style=discord.ButtonStyle.primary, emoji="📝")
    async def set_log_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set the channel for invite logs."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this button.", ephemeral=True)
            return

        manual_modal = discord.ui.Modal(title="Set Invite Logs Channel")

        channel_id_input = discord.ui.TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID (right-click channel, Copy ID)",
            default="1354491891579752448",
            required=True
        )
        
        manual_modal.add_item(channel_id_input)
        
        async def modal_submit(modal_interaction):
            try:
                entered_id = int(channel_id_input.value.strip())
                await self.set_log_channel(modal_interaction, entered_id)
            except ValueError:
                await modal_interaction.response.send_message("Invalid channel ID format. Please enter a numeric ID.", ephemeral=True)
        
        manual_modal.on_submit = modal_submit
        await interaction.response.send_modal(manual_modal)
        logger.info(f"Channel ID input modal shown to {interaction.user.id}")
    
    async def reset_user_invites(self, interaction, user_id):
        """Reset a user's invites to zero."""
        try:

            member = await interaction.guild.fetch_member(user_id)

            self.cog.invite_tracker.reset_user_invites(user_id)
            
            await interaction.response.send_message(f"Reset all invites for {member.mention}!", ephemeral=True)
            logger.info(f"Invites reset for user {user_id} by {interaction.user.id}")
        except discord.errors.NotFound:
            await interaction.response.send_message("Could not find that user in this server.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error resetting invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    async def select_user_for_add(self, interaction, user_id):
        """Show modal to add invites for a user."""
        try:

            member = await interaction.guild.fetch_member(user_id)

            await interaction.response.send_modal(
                InviteCountModal(f"Add Invites for {member.display_name}", user_id, self.add_invites, is_add=True)
            )
        except discord.errors.NotFound:
            await interaction.response.send_message("Could not find that user in this server.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error preparing to add invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    async def select_user_for_remove(self, interaction, user_id):
        """Show modal to remove invites from a user."""
        try:

            member = await interaction.guild.fetch_member(user_id)

            await interaction.response.send_modal(
                InviteCountModal(f"Remove Invites from {member.display_name}", user_id, self.add_invites, is_add=False)
            )
        except discord.errors.NotFound:
            await interaction.response.send_message("Could not find that user in this server.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error preparing to remove invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    async def add_invites(self, interaction, user_id, regular, bonus, fake, left):
        """Add or remove invites for a user."""
        try:

            new_invites = self.cog.invite_tracker.add_invites(
                user_id, regular=regular, bonus=bonus, fake=fake, left=left
            )
            
            member = await interaction.guild.fetch_member(user_id)

            action = "Added" if regular >= 0 else "Removed"
            change_details = []
            if regular != 0:
                change_details.append(f"{abs(regular)} regular")
            if bonus != 0:
                change_details.append(f"{abs(bonus)} bonus")
            if fake != 0:
                change_details.append(f"{abs(fake)} fake")
            if left != 0:
                change_details.append(f"{abs(left)} left")
            
            change_text = ", ".join(change_details)

            embed = discord.Embed(
                title=f"Invite Changes for {member.display_name}",
                description=f"{action} {change_text} invites.",
                color=discord.Color.green() if regular >= 0 else discord.Color.orange()
            )
            
            embed.add_field(
                name="New Invite Counts",
                value=(
                    f"Regular: {new_invites['regular_invites']}\n"
                    f"Bonus: {new_invites['bonus_invites']}\n"
                    f"Fake: {new_invites['fake_invites']}\n"
                    f"Left: {new_invites['left_invites']}"
                ),
                inline=False
            )
            
            total = (
                new_invites["regular_invites"] + 
                new_invites["bonus_invites"] - 
                new_invites["fake_invites"] - 
                new_invites["left_invites"]
            )
            
            embed.add_field(
                name="Total Invites",
                value=f"**{total}**",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Invites modified for user {user_id} by {interaction.user.id}")
        except Exception as e:
            logger.error(f"Error modifying invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    async def set_log_channel(self, interaction, channel_id):
        """Set the channel for invite logs."""
        try:

            if channel_id == 1354491891579752448:

                self.cog.invite_tracker.set_log_channel(interaction.guild.id, channel_id)

                try:
                    channel = interaction.guild.get_channel(channel_id)
                    if not channel:
                        channel = await interaction.guild.fetch_channel(channel_id)
                    channel_mention = channel.mention
                except:

                    channel_mention = f"<#{channel_id}>"
                
                await interaction.response.send_message(
                    f"Successfully set invite logs channel to {channel_mention}! (ID: {channel_id})", 
                    ephemeral=True
                )
                logger.info(f"Invite log channel set to the specified ID {channel_id} by {interaction.user.id}")
                return

            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                channel = await interaction.guild.fetch_channel(channel_id)

            self.cog.invite_tracker.set_log_channel(interaction.guild.id, channel_id)
            
            await interaction.response.send_message(f"Set invite logs channel to {channel.mention}!", ephemeral=True)
            logger.info(f"Invite log channel set to {channel_id} by {interaction.user.id}")
        except discord.errors.NotFound:

            if channel_id == 1354491891579752448:
                self.cog.invite_tracker.set_log_channel(interaction.guild.id, channel_id)
                await interaction.response.send_message(
                    f"Channel with ID {channel_id} couldn't be verified but has been set as the invite logs channel.", 
                    ephemeral=True
                )
                logger.info(f"Invite log channel set to unverified ID {channel_id} by {interaction.user.id}")
                return
            await interaction.response.send_message("Could not find that channel in this server.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error setting log channel: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

async def setup(bot):
    """Add the invites cog to the bot."""
    await bot.add_cog(InvitesCog(bot))
    logger.info("Invites cog loaded")