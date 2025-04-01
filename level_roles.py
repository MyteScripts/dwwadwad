import discord
from discord import app_commands
from discord.ext import commands
import logging
from logger import setup_logger
from permissions import is_admin

logger = setup_logger('level_roles', 'bot.log')

LEVEL_ROLES = {
    "1339331106557657089": 5,    # Level 5 role
    "1339332632860950589": 10,   # Level 10 role
    "1339333949201186878": 15,   # Level 15 role
    "1339571891848876075": 20,   # Level 20 role
    "1339572201430454272": 25,   # Level 25 role
    "1339572204433838142": 30,   # Level 30 role
    "1339572206895894602": 35,   # Level 35 role
    "1339572209848680458": 40,   # Level 40 role
    "1339572212285575199": 45,   # Level 45 role
    "1339572214881714176": 50,   # Level 50 role
    "1339574559136944240": 55,   # Level 55 role
    "1339574564685873245": 60,   # Level 60 role
    "1339574564983804018": 65,   # Level 65 role
    "1339574565780590632": 70,   # Level 70 role
    "1339574566669783180": 75,   # Level 75 role
    "1339574568276332564": 80,   # Level 80 role
    "1339574568586842112": 85,   # Level 85 role
    "1339574569417048085": 90,   # Level 90 role
    "1339576526458322954": 95,   # Level 95 role
    "1339576529377820733": 100,  # Level 100 role
}

SORTED_LEVEL_ROLES = sorted(LEVEL_ROLES.items(), key=lambda x: x[1])

class LevelRolesCog(commands.Cog):
    """Cog for managing level roles."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Level Roles cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Verify role IDs exist when the bot starts up."""
        for guild in self.bot.guilds:
            valid_roles = []
            invalid_roles = []
            
            for role_id, level in LEVEL_ROLES.items():
                role = guild.get_role(int(role_id))
                if role:
                    valid_roles.append(f"{role.name} (Level {level})")
                else:
                    invalid_roles.append(f"ID: {role_id} (Level {level})")
            
            if invalid_roles:
                logger.warning(f"Some level roles were not found in guild {guild.name}: {', '.join(invalid_roles)}")
            
            logger.info(f"Verified {len(valid_roles)} level roles in guild {guild.name}")
    
    async def update_member_roles(self, member, level):
        """Update a member's roles based on their level.
        
        Grants all level roles up to the member's current level.
        """
        if not member.guild:
            logger.warning(f"Cannot update roles for {member} - not in a guild")
            return False, "You are not in a server"

        if level < SORTED_LEVEL_ROLES[0][1]:
            logger.debug(f"{member} (Level {level}) is not eligible for any level roles yet")
            return False, f"You need to reach level {SORTED_LEVEL_ROLES[0][1]} to get your first role"

        eligible_role_ids = []

        for role_id, required_level in SORTED_LEVEL_ROLES:
            if level >= required_level:
                eligible_role_ids.append(role_id)
        
        if not eligible_role_ids:
            logger.debug(f"{member} (Level {level}) is not eligible for any level roles yet")
            return False, "No eligible roles found for your level"

        eligible_roles = []
        for role_id in eligible_role_ids:
            role = member.guild.get_role(int(role_id))
            if role:
                eligible_roles.append(role)
            else:
                logger.error(f"Could not find eligible role with ID {role_id}")
        
        if not eligible_roles:
            return False, "Could not find any valid roles to assign"

        current_level_roles = [
            role for role in member.roles 
            if str(role.id) in LEVEL_ROLES.keys()
        ]

        roles_to_add = [role for role in eligible_roles if role not in current_level_roles]
        roles_to_remove = [role for role in current_level_roles if role not in eligible_roles]

        if not roles_to_add and not roles_to_remove:
            logger.debug(f"{member} already has all the correct level roles")
            return True, "You already have all the appropriate roles for your level"
            
        try:

            if roles_to_remove:
                try:
                    await member.remove_roles(*roles_to_remove, reason="Level role update")
                    logger.info(f"Removed roles {[role.name for role in roles_to_remove]} from {member}")
                except Exception as e:
                    logger.error(f"Error removing old level roles: {e}")

            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Level role update")
                logger.info(f"Added roles {[role.name for role in roles_to_add]} to {member} (Level {level})")

            highest_role = eligible_roles[-1] if eligible_roles else None
            
            if highest_role:
                return True, f"Updated roles for {member.name} to include all level roles up to Level {LEVEL_ROLES[str(highest_role.id)]}"
            else:
                return True, f"Updated roles for {member.name} based on their level {level}"
        except discord.Forbidden:
            logger.error(f"Bot does not have permission to manage roles for {member}")
            return False, "Bot does not have permission to manage roles"
        except Exception as e:
            logger.error(f"Error updating roles for {member}: {e}")
            return False, f"Error updating roles: {str(e)}"

    @app_commands.command(name="updateroles", description="Update your roles based on your current level")
    async def update_roles(self, interaction: discord.Interaction):
        """Manually update your roles based on your current level."""

        leveling_cog = self.bot.get_cog("LevelingCog")
        if not leveling_cog:
            await interaction.response.send_message(
                "❌ Error: LevelingCog not found. Please report this to the administrator.",
                ephemeral=True
            )
            return

        db = leveling_cog.db
        user_id = interaction.user.id
        username = interaction.user.name
        
        user_data = db.get_or_create_user(user_id, username)
        if not user_data:
            await interaction.response.send_message(
                "❌ Error: Could not retrieve user data. Please try again later.",
                ephemeral=True
            )
            return
        
        level = user_data['level']

        success, message = await self.update_member_roles(interaction.user, level)
        
        if success:
            await interaction.response.send_message(
                f"✅ {message}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {message}",
                ephemeral=True
            )
    
    @app_commands.command(name="resetroles", description="Remove all level roles from a member (Admin only)")
    @app_commands.check(is_admin)
    async def reset_roles(self, interaction: discord.Interaction, member: discord.Member):
        """Remove all level roles from a member (Admin only)."""

        level_roles = [
            role for role in member.roles 
            if str(role.id) in LEVEL_ROLES.keys()
        ]
        
        if not level_roles:
            await interaction.response.send_message(
                f"{member.mention} doesn't have any level roles.",
                ephemeral=True
            )
            return
            
        try:

            if level_roles:
                try:
                    await member.remove_roles(*level_roles, reason="Level roles reset")
                    logger.info(f"Removed roles {[role.name for role in level_roles]} from {member}")
                except Exception as e:
                    logger.error(f"Error removing roles in reset_roles: {e}")
                    raise  # Re-raise so it's caught by the outer try-except
                
            await interaction.response.send_message(
                f"✅ Successfully removed all level roles from {member.mention}.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to manage roles.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error removing roles: {e}")
            await interaction.response.send_message(
                f"❌ Error removing roles: {str(e)}",
                ephemeral=True
            )
                
async def setup(bot):
    """Add the level roles cog to the bot."""
    logger.info("Starting Level Roles cog setup")
    
    cog = LevelRolesCog(bot)
    await bot.add_cog(cog)
    logger.info("Level Roles cog added to bot")

    @bot.event
    async def on_level_up(member, new_level):
        """Called when a member levels up."""
        logger.info(f"Level up event received for {member.name} (Level {new_level})")
        await cog.update_member_roles(member, new_level)

    leveling_cog = bot.get_cog("LevelingCog")
    if leveling_cog:
        logger.info("LevelingCog found - level up events will be processed")
    else:
        logger.warning("LevelingCog not found - level up events won't be processed")
    
    logger.info("Level Roles cog loaded")