import discord
import logging
from logger import setup_logger

logger = setup_logger('invite_modals')

class InviteAddModal(discord.ui.Modal):
    """Modal for adding invites with member ID and count all at once."""
    
    def __init__(self, cog):
        super().__init__(title="Add Member Invites")
        self.cog = cog
        
        self.user_id_input = discord.ui.TextInput(
            label="Member ID",
            placeholder="Right-click user, select 'Copy ID', paste here",
            required=True,
            min_length=17,
            max_length=19
        )
        self.add_item(self.user_id_input)
        
        self.regular_input = discord.ui.TextInput(
            label="Regular Invites",
            placeholder="Enter count (e.g. 5)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.regular_input)
        
        self.bonus_input = discord.ui.TextInput(
            label="Bonus Invites",
            placeholder="Enter count (e.g. 3)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.bonus_input)
        
        self.other_input = discord.ui.TextInput(
            label="Fake,Left Invites (comma separated)",
            placeholder="Format: fake,left (e.g. 2,1)",
            required=False,
            max_length=11,
            default="0,0"
        )
        self.add_item(self.other_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            user_id = int(self.user_id_input.value)

            try:
                member = await interaction.guild.fetch_member(user_id)
            except discord.errors.NotFound:
                await interaction.response.send_message("Could not find that user in this server.", ephemeral=True)
                return

            regular = int(self.regular_input.value or 0)
            bonus = int(self.bonus_input.value or 0)

            other_values = self.other_input.value.split(',')
            if len(other_values) >= 2:
                fake = int(other_values[0] or 0)
                left = int(other_values[1] or 0)
            else:
                fake = int(other_values[0] or 0)
                left = 0

            new_invites = self.cog.invite_tracker.add_invites(
                user_id, regular=regular, bonus=bonus, fake=fake, left=left
            )

            change_details = []
            if regular != 0:
                change_details.append(f"{regular} regular")
            if bonus != 0:
                change_details.append(f"{bonus} bonus")
            if fake != 0:
                change_details.append(f"{fake} fake")
            if left != 0:
                change_details.append(f"{left} left")
            
            change_text = ", ".join(change_details)

            embed = discord.Embed(
                title=f"Invite Changes for {member.display_name}",
                description=f"Added {change_text} invites.",
                color=discord.Color.green()
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
            logger.info(f"Invites added for user {user_id} by {interaction.user.id}")
            
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class InviteRemoveModal(discord.ui.Modal):
    """Modal for removing invites with member ID and count all at once."""
    
    def __init__(self, cog):
        super().__init__(title="Remove Member Invites")
        self.cog = cog
        
        self.user_id_input = discord.ui.TextInput(
            label="Member ID",
            placeholder="Right-click user, select 'Copy ID', paste here",
            required=True,
            min_length=17,
            max_length=19
        )
        self.add_item(self.user_id_input)
        
        self.regular_input = discord.ui.TextInput(
            label="Regular Invites",
            placeholder="Enter count to remove (e.g. 5)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.regular_input)
        
        self.bonus_input = discord.ui.TextInput(
            label="Bonus Invites",
            placeholder="Enter count to remove (e.g. 3)",
            required=False,
            max_length=5,
            default="0"
        )
        self.add_item(self.bonus_input)
        
        self.other_input = discord.ui.TextInput(
            label="Fake,Left Invites (comma separated)",
            placeholder="Format: fake,left (e.g. 2,1)",
            required=False,
            max_length=11,
            default="0,0"
        )
        self.add_item(self.other_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            user_id = int(self.user_id_input.value)

            try:
                member = await interaction.guild.fetch_member(user_id)
            except discord.errors.NotFound:
                await interaction.response.send_message("Could not find that user in this server.", ephemeral=True)
                return

            regular = int(self.regular_input.value or 0)
            bonus = int(self.bonus_input.value or 0)

            other_values = self.other_input.value.split(',')
            if len(other_values) >= 2:
                fake = int(other_values[0] or 0)
                left = int(other_values[1] or 0)
            else:
                fake = int(other_values[0] or 0)
                left = 0

            regular = -regular
            bonus = -bonus
            fake = -fake
            left = -left

            new_invites = self.cog.invite_tracker.add_invites(
                user_id, regular=regular, bonus=bonus, fake=fake, left=left
            )

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
                description=f"Removed {change_text} invites.",
                color=discord.Color.orange()
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
            logger.info(f"Invites removed for user {user_id} by {interaction.user.id}")
            
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class InviteResetModal(discord.ui.Modal):
    """Modal for resetting a member's invites."""
    
    def __init__(self, cog):
        super().__init__(title="Reset Member Invites")
        self.cog = cog
        
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

            try:
                member = await interaction.guild.fetch_member(user_id)
            except discord.errors.NotFound:
                await interaction.response.send_message("Could not find that user in this server.", ephemeral=True)
                return

            self.cog.invite_tracker.reset_user_invites(user_id)
            
            await interaction.response.send_message(f"Reset all invites for {member.mention}!", ephemeral=True)
            logger.info(f"Invites reset for user {user_id} by {interaction.user.id}")
            
        except ValueError:
            await interaction.response.send_message("Please enter a valid user ID!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error resetting invites: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class ChannelSelectModal(discord.ui.Modal):
    """Modal for selecting a channel by ID."""
    
    def __init__(self, cog):
        super().__init__(title="Set Invites Log Channel")
        self.cog = cog
        
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

            self.cog.invite_tracker.set_log_channel(interaction.guild.id, channel_id)
            
            await interaction.response.send_message(f"Set invite logs channel to {channel.mention}!", ephemeral=True)
            logger.info(f"Invite log channel set to {channel_id} by {interaction.user.id}")
            
        except ValueError:
            await interaction.response.send_message("Please enter a valid channel ID!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error setting log channel: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)