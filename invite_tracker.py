import discord
from discord import app_commands
from discord.ext import commands
import logging
import datetime
import json
import os

class InviteTracker(commands.Cog):
    """Cog for tracking server invites and displaying statistics."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('invite_tracker')
        
        # Dictionary to store invite data for each guild
        # Structure: {guild_id: {invite_code: {'uses': 0, 'inviter_id': '123', 'created_at': timestamp}}}
        self.invite_data = {}
        
        # Tracking of invites before a user joins
        if not hasattr(bot, 'invites_before'):
            bot.invites_before = {}
        
        # Dictionary to track which invite each user used to join
        # Structure: {guild_id: {user_id: {'invite_code': 'abc123', 'inviter_id': '123', 'joined_at': timestamp}}}
        self.user_invites = {}
        
        # Load data
        self.load_data()
    
    def load_data(self):
        """Load invite tracking data from file."""
        try:
            # Ensure the data directory exists
            os.makedirs('data', exist_ok=True)
            
            # Load invite data
            try:
                with open('data/invite_data.json', 'r') as f:
                    self.invite_data = json.load(f)
            except FileNotFoundError:
                self.logger.info("No invite data found. Creating new file.")
                self.invite_data = {}
            
            # Load user invites data
            try:
                with open('data/user_invites.json', 'r') as f:
                    self.user_invites = json.load(f)
            except FileNotFoundError:
                self.logger.info("No user invites data found. Creating new file.")
                self.user_invites = {}
        except Exception as e:
            self.logger.error(f"Failed to load invite data: {e}")
    
    def save_data(self):
        """Save invite tracking data to file."""
        try:
            # Ensure the data directory exists
            os.makedirs('data', exist_ok=True)
            
            # Save invite data
            with open('data/invite_data.json', 'w') as f:
                json.dump(self.invite_data, f, indent=4)
            
            # Save user invites data
            with open('data/user_invites.json', 'w') as f:
                json.dump(self.user_invites, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save invite data: {e}")
    
    def cog_unload(self):
        """Clean up when the cog is unloaded."""
        self.save_data()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Cache all invites when the bot starts up."""
        try:
            self.bot.invites_before = {}
            for guild in self.bot.guilds:
                try:
                    invites = await guild.invites()
                    self.bot.invites_before[guild.id] = {i.code: i.uses for i in invites}
                    
                    # Update our tracking data
                    guild_id = str(guild.id)
                    if guild_id not in self.invite_data:
                        self.invite_data[guild_id] = {}
                    
                    for invite in invites:
                        self.invite_data[guild_id][invite.code] = {
                            'uses': invite.uses,
                            'inviter_id': str(invite.inviter.id) if invite.inviter else None,
                            'created_at': invite.created_at.timestamp() if invite.created_at else datetime.datetime.now().timestamp()
                        }
                except:
                    # If we can't access invites for this guild, skip it
                    pass
            
            # Save the data
            self.save_data()
        except Exception as e:
            self.logger.error(f"Failed to cache invites on startup: {e}")
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Track invites when they are created."""
        try:
            # Update our cached invites
            guild_id = invite.guild.id
            if guild_id not in self.bot.invites_before:
                self.bot.invites_before[guild_id] = {}
            
            self.bot.invites_before[guild_id][invite.code] = invite.uses
            
            # Update our tracking data
            guild_id_str = str(guild_id)
            if guild_id_str not in self.invite_data:
                self.invite_data[guild_id_str] = {}
            
            self.invite_data[guild_id_str][invite.code] = {
                'uses': invite.uses,
                'inviter_id': str(invite.inviter.id) if invite.inviter else None,
                'created_at': invite.created_at.timestamp() if invite.created_at else datetime.datetime.now().timestamp()
            }
            
            # Save the data
            self.save_data()
        except Exception as e:
            self.logger.error(f"Failed to track invite creation: {e}")
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """Track invites when they are deleted."""
        try:
            # Update our cached invites
            guild_id = invite.guild.id
            if guild_id in self.bot.invites_before and invite.code in self.bot.invites_before[guild_id]:
                del self.bot.invites_before[guild_id][invite.code]
            
            # Update our tracking data
            guild_id_str = str(guild_id)
            if guild_id_str in self.invite_data and invite.code in self.invite_data[guild_id_str]:
                # We don't delete it completely to maintain history
                self.invite_data[guild_id_str][invite.code]['deleted'] = True
            
            # Save the data
            self.save_data()
        except Exception as e:
            self.logger.error(f"Failed to track invite deletion: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track which invite a member used to join."""
        guild = member.guild
        guild_id = guild.id
        guild_id_str = str(guild_id)
        
        try:
            # Get invites before the user joined
            invites_before = self.bot.invites_before.get(guild_id, {})
            
            # Get the current invites
            invites_after = await guild.invites()
            
            # Find which invite count increased
            invite_used = None
            inviter_id = None
            
            for invite in invites_after:
                if invite.code in invites_before:
                    # If the uses increased, this invite was used
                    if invite.uses > invites_before[invite.code]:
                        invite_used = invite.code
                        inviter_id = str(invite.inviter.id) if invite.inviter else None
                        break
            
            # Update our cached invites
            self.bot.invites_before[guild_id] = {i.code: i.uses for i in invites_after}
            
            # Update our tracking data
            if guild_id_str not in self.invite_data:
                self.invite_data[guild_id_str] = {}
            
            for invite in invites_after:
                if invite.code not in self.invite_data[guild_id_str]:
                    self.invite_data[guild_id_str][invite.code] = {
                        'uses': invite.uses,
                        'inviter_id': str(invite.inviter.id) if invite.inviter else None,
                        'created_at': invite.created_at.timestamp() if invite.created_at else datetime.datetime.now().timestamp()
                    }
                else:
                    self.invite_data[guild_id_str][invite.code]['uses'] = invite.uses
            
            # Record which invite the user used
            if guild_id_str not in self.user_invites:
                self.user_invites[guild_id_str] = {}
            
            self.user_invites[guild_id_str][str(member.id)] = {
                'invite_code': invite_used,
                'inviter_id': inviter_id,
                'joined_at': datetime.datetime.now().timestamp()
            }
            
            # Save the data
            self.save_data()
        except Exception as e:
            self.logger.error(f"Failed to track invite usage: {e}")
    
    @app_commands.command(name="invites", description="Show your invite statistics")
    async def invites(self, interaction: discord.Interaction, user: discord.User = None):
        """Show invite statistics for yourself or another user.
        
        Args:
            interaction: The interaction that triggered this command
            user: The user to check invites for (defaults to the command user)
        """
        target_user = user or interaction.user
        guild_id = str(interaction.guild.id)
        
        # Count the invites
        regular_invites = 0
        left_invites = 0
        fake_invites = 0
        
        # Loop through all user joins in this guild
        if guild_id in self.user_invites:
            for user_id, invite_data in self.user_invites[guild_id].items():
                if invite_data.get('inviter_id') == str(target_user.id):
                    # Count this invite
                    regular_invites += 1
                    
                    # Check if the user is still in the guild
                    member = interaction.guild.get_member(int(user_id))
                    if not member:
                        left_invites += 1
                    
                    # Check if it's a fake invite (joined and left quickly)
                    joined_at = invite_data.get('joined_at', 0)
                    if (not member) and (datetime.datetime.now().timestamp() - joined_at < 24 * 60 * 60):  # Left within 24 hours
                        fake_invites += 1
        
        # Create embed
        embed = discord.Embed(
            title=f"Invite Statistics for {target_user.name}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(name="Total Invites", value=str(regular_invites), inline=True)
        embed.add_field(name="Active Invites", value=str(regular_invites - left_invites), inline=True)
        embed.add_field(name="Left Members", value=str(left_invites), inline=True)
        embed.add_field(name="Fake Invites", value=str(fake_invites), inline=True)
        
        # Add a field for the user's active invite codes
        active_invite_codes = []
        if guild_id in self.invite_data:
            for code, data in self.invite_data[guild_id].items():
                if data.get('inviter_id') == str(target_user.id) and not data.get('deleted', False):
                    active_invite_codes.append(f"`{code}` - {data.get('uses', 0)} uses")
        
        invite_codes_text = "\n".join(active_invite_codes) if active_invite_codes else "No active invites"
        embed.add_field(name="Active Invite Codes", value=invite_codes_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="inviteleaderboard", description="Show the invite leaderboard")
    async def invite_leaderboard(self, interaction: discord.Interaction):
        """Show the invite leaderboard for the server.
        
        Args:
            interaction: The interaction that triggered this command
        """
        guild_id = str(interaction.guild.id)
        
        # Count invites for each user
        invite_counts = {}
        
        # Loop through all user joins in this guild
        if guild_id in self.user_invites:
            for user_id, invite_data in self.user_invites[guild_id].items():
                inviter_id = invite_data.get('inviter_id')
                if not inviter_id:
                    continue
                
                if inviter_id not in invite_counts:
                    invite_counts[inviter_id] = {
                        'total': 0,
                        'active': 0,
                        'left': 0,
                        'fake': 0
                    }
                
                # Count this invite
                invite_counts[inviter_id]['total'] += 1
                
                # Check if the user is still in the guild
                member = interaction.guild.get_member(int(user_id))
                if member:
                    invite_counts[inviter_id]['active'] += 1
                else:
                    invite_counts[inviter_id]['left'] += 1
                
                # Check if it's a fake invite (joined and left quickly)
                joined_at = invite_data.get('joined_at', 0)
                if (not member) and (datetime.datetime.now().timestamp() - joined_at < 24 * 60 * 60):  # Left within 24 hours
                    invite_counts[inviter_id]['fake'] += 1
        
        # Sort by total invites
        sorted_inviters = sorted(invite_counts.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Create embed
        embed = discord.Embed(
            title=f"Invite Leaderboard for {interaction.guild.name}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        
        # Add the top 10 inviters
        leaderboard_text = ""
        for i, (inviter_id, counts) in enumerate(sorted_inviters[:10], 1):
            try:
                user = await self.bot.fetch_user(int(inviter_id))
                username = user.name
            except:
                username = f"Unknown User ({inviter_id})"
            
            leaderboard_text += f"{i}. **{username}** - {counts['total']} invites ({counts['active']} active, {counts['left']} left)\n"
        
        if not leaderboard_text:
            leaderboard_text = "No invites tracked yet."
        
        embed.description = leaderboard_text
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="whoinvited", description="Show who invited a specific user")
    @app_commands.default_permissions(manage_guild=True)
    async def who_invited(self, interaction: discord.Interaction, user: discord.User):
        """Show who invited a specific user to the server.
        
        Args:
            interaction: The interaction that triggered this command
            user: The user to check who invited them
        """
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)
        
        if guild_id not in self.user_invites or user_id not in self.user_invites[guild_id]:
            await interaction.response.send_message(
                f"I don't have any record of who invited {user.mention} to the server.",
                ephemeral=True
            )
            return
        
        invite_data = self.user_invites[guild_id][user_id]
        inviter_id = invite_data.get('inviter_id')
        invite_code = invite_data.get('invite_code', 'Unknown')
        joined_at = invite_data.get('joined_at')
        
        if not inviter_id:
            await interaction.response.send_message(
                f"{user.mention} joined the server, but I couldn't determine who invited them.",
                ephemeral=True
            )
            return
        
        try:
            inviter = await self.bot.fetch_user(int(inviter_id))
            inviter_name = inviter.name
            inviter_mention = inviter.mention
        except:
            inviter_name = f"Unknown User ({inviter_id})"
            inviter_mention = f"Unknown User ({inviter_id})"
        
        embed = discord.Embed(
            title=f"Invite Information for {user.name}",
            description=f"{user.mention} was invited by {inviter_mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(name="Inviter", value=inviter_name, inline=True)
        embed.add_field(name="Invite Code", value=invite_code, inline=True)
        
        if joined_at:
            join_date = datetime.datetime.fromtimestamp(joined_at)
            embed.add_field(name="Joined At", value=discord.utils.format_dt(join_date), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="resetinvites", description="Reset invite tracking data (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def reset_invites(self, interaction: discord.Interaction, user: discord.User = None):
        """Reset invite tracking data for a user or the entire server.
        
        Args:
            interaction: The interaction that triggered this command
            user: The user to reset invites for (if None, reset for all users)
        """
        guild_id = str(interaction.guild.id)
        
        if user:
            # Reset for a specific user
            user_id = str(user.id)
            
            # Remove them as an inviter from user_invites
            if guild_id in self.user_invites:
                for invited_id, invite_data in list(self.user_invites[guild_id].items()):
                    if invite_data.get('inviter_id') == user_id:
                        self.user_invites[guild_id][invited_id]['inviter_id'] = None
            
            # Save the data
            self.save_data()
            
            await interaction.response.send_message(
                f"Invite tracking data has been reset for {user.mention}.",
                ephemeral=True
            )
        else:
            # Reset for the entire server
            if guild_id in self.user_invites:
                del self.user_invites[guild_id]
            
            if guild_id in self.invite_data:
                del self.invite_data[guild_id]
            
            # Save the data
            self.save_data()
            
            await interaction.response.send_message(
                "Invite tracking data has been reset for the entire server.",
                ephemeral=True
            )


async def setup(bot):
    """Add the invite tracker cog to the bot."""
    invite_tracker_cog = InviteTracker(bot)
    await bot.add_cog(invite_tracker_cog)
    return invite_tracker_cog