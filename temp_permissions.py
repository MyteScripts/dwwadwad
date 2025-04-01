import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import logging

logger = logging.getLogger(__name__)

async def has_admin_permissions(user_id, guild_id, bot=None):
    """Check if a user has admin permissions.
    
    Args:
        user_id: The ID of the user to check
        guild_id: The ID of the guild where the check is being performed
        bot: Optional bot instance to get guild and member info
        
    Returns:
        bool: True if the user has admin permissions, False otherwise
    """
    admin_user_ids = ["1308527904497340467", "479711321399623681", "1063511383397892256"]

    if str(user_id) in admin_user_ids:
        return True

    if bot:
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                admin_role_id = "1338482857974169683"
                for role in member.roles:
                    if str(role.id) == admin_role_id:
                        return True

    return False

class PermissionsCog(commands.Cog):
    """Cog for managing command permissions by role."""
    
    def __init__(self, bot):
        self.bot = bot
        self.permissions_file = "data/permissions.json"
        self.permissions = {}
        self.visible_commands = {}  # Dictionary to track command visibility
        self.load_permissions()

    def load_permissions(self):
        """Load permissions from JSON file."""

        self.visible_commands = {}
        
        try:
            if os.path.exists(self.permissions_file):
                with open(self.permissions_file, 'r') as f:
                    data = json.load(f)

                    self.permissions = data.get('permissions', {})
            else:
                self.permissions = {}
                self.save_permissions()
        except Exception as e:
            logger.error(f"Error loading permissions: {e}")
            self.permissions = {}
            self.visible_commands = {}
    
    def save_permissions(self):
        """Save permissions to JSON file."""
        try:

            data = {
                'permissions': self.permissions,
                'visible_commands': self.visible_commands
            }
            
            with open(self.permissions_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving permissions: {e}")
    
    def check_permission(self, command_name, member):
        """Check if a member has permission to use a command."""
        guild_id = str(member.guild.id)

        if guild_id not in self.permissions:
            return True

        if command_name not in self.permissions[guild_id]:
            return True

        allowed_roles = self.permissions[guild_id][command_name]
        if not allowed_roles:  # Empty list means no restrictions
            return True
            
        member_role_ids = [str(role.id) for role in member.roles]
        return any(role_id in member_role_ids for role_id in allowed_roles)
    
    def is_command_visible(self, command_name, member):
        """Check if a command should be visible to a member based on permissions."""
        guild_id = str(member.guild.id)

        if member.guild_permissions.administrator:
            return True

        if guild_id in self.visible_commands and command_name in self.visible_commands[guild_id]:
            return True

        if guild_id not in self.permissions or command_name not in self.permissions[guild_id]:
            return True

        allowed_roles = self.permissions[guild_id][command_name]
        if not allowed_roles:  # Empty list means no restrictions
            return True
            
        member_role_ids = [str(role.id) for role in member.roles]
        return any(role_id in member_role_ids for role_id in allowed_roles)
    
    async def command_check(self, interaction):
        """Check if a user can run a command based on their roles."""

        command_name = interaction.command.qualified_name

        removed_commands = ["/migeratedata", "/cancelscan", "/importusers"]
        if command_name in removed_commands:
            await interaction.response.send_message(
                "❌ This command has been removed.",
                ephemeral=True
            )
            return False

        admin_user_ids = ["1308527904497340467", "479711321399623681", "1063511383397892256"]

        admin_role_id = "1338482857974169683"
        has_admin_role = False
        for role in interaction.user.roles:
            if str(role.id) == admin_role_id:
                has_admin_role = True
                break
        
        if str(interaction.user.id) in admin_user_ids or has_admin_role:

            if command_name == "dbsync" and str(interaction.user.id) != "1308527904497340467":
                await interaction.response.send_message(
                    "❌ Only the primary admin can use the /dbsync command.",
                    ephemeral=True
                )
                return False
            return True

        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        return False

    async def get_commands_list(self):
        """Get a list of all slash commands registered to the bot."""
        commands = []
        for cmd in self.bot.tree.get_commands():
            commands.append(cmd.qualified_name)
        return sorted(commands)
    
    async def add_role_permission(self, guild_id, command_name, role_id):
        """Add a role to the list of roles allowed to use a command."""
        guild_id = str(guild_id)
        role_id = str(role_id)

        if guild_id not in self.permissions:
            self.permissions[guild_id] = {}

        if command_name not in self.permissions[guild_id]:
            self.permissions[guild_id][command_name] = []

        if role_id not in self.permissions[guild_id][command_name]:
            self.permissions[guild_id][command_name].append(role_id)
            self.save_permissions()
            return True, f"✅ Role <@&{role_id}> can now use /{command_name}"
        else:
            return False, f"⚠️ Role <@&{role_id}> already has permission to use /{command_name}"
    
    async def remove_role_permission(self, guild_id, command_name, role_id):
        """Remove a role from the list of roles allowed to use a command."""
        guild_id = str(guild_id)
        role_id = str(role_id)

        if (guild_id not in self.permissions or 
            command_name not in self.permissions[guild_id] or
            role_id not in self.permissions[guild_id][command_name]):
            return False, f"⚠️ Role <@&{role_id}> doesn't have specific permission for /{command_name}"

        self.permissions[guild_id][command_name].remove(role_id)
        self.save_permissions()
        
        return True, f"✅ Removed permission for role <@&{role_id}> to use /{command_name}"
    
    async def get_command_permissions(self, guild_id, command_name):
        """Get a list of roles that can use a specific command."""
        guild_id = str(guild_id)
        
        if (guild_id not in self.permissions or 
            command_name not in self.permissions[guild_id]):
            return []
        
        return self.permissions[guild_id][command_name]
    
    async def clear_command_permissions(self, guild_id, command_name):
        """Remove all role permissions for a command (making it available to everyone)."""
        guild_id = str(guild_id)
        
        if guild_id not in self.permissions:
            self.permissions[guild_id] = {}
        
        self.permissions[guild_id][command_name] = []
        self.save_permissions()
        
        return True, f"✅ Cleared all role restrictions for /{command_name}. Now available to everyone."
    
    async def set_command_permissions(self, guild_id, command_name, role_ids):
        """Set the complete list of roles that can use a command."""
        guild_id = str(guild_id)
        role_ids = [str(role_id) for role_id in role_ids]
        
        if guild_id not in self.permissions:
            self.permissions[guild_id] = {}
        
        self.permissions[guild_id][command_name] = role_ids
        self.save_permissions()
        
        if role_ids:
            role_mentions = ", ".join([f"<@&{role_id}>" for role_id in role_ids])
            return True, f"✅ Set permissions for /{command_name}. Allowed roles: {role_mentions}"
        else:
            return True, f"✅ Removed all role restrictions for /{command_name}. Now available to everyone."
    
    async def set_command_public(self, guild_id, command_name):
        """Set a command as public, making it visible to everyone regardless of permissions."""
        guild_id = str(guild_id)

        if guild_id not in self.visible_commands:
            self.visible_commands[guild_id] = []

        if command_name not in self.visible_commands[guild_id]:
            self.visible_commands[guild_id].append(command_name)
            self.save_permissions()
            return True, f"✅ Command /{command_name} is now public and visible to everyone."
        else:
            return False, f"⚠️ Command /{command_name} is already public."
            
    async def remove_command_public(self, guild_id, command_name):
        """Remove a command from public visibility."""
        guild_id = str(guild_id)

        if guild_id not in self.visible_commands or command_name not in self.visible_commands[guild_id]:
            return False, f"⚠️ Command /{command_name} is not set as public."

        self.visible_commands[guild_id].remove(command_name)
        self.save_permissions()

        is_restricted = (guild_id in self.permissions and 
                        command_name in self.permissions[guild_id] and 
                        self.permissions[guild_id][command_name])
        
        if is_restricted:
            return True, f"✅ Command /{command_name} is no longer public. Only specific roles can see and use it."
        else:
            return True, f"✅ Command /{command_name} is no longer public, but still visible to everyone (no role restrictions)."

class PermissionsView(discord.ui.View):
    """View with buttons for managing permissions."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog

        self.cog.save_permissions()
    
    @discord.ui.button(
        label="Add Permission", 
        style=discord.ButtonStyle.green,
        emoji="➕",
        row=0
    )
    async def add_permission_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to add a command permission for a role."""

        commands = await self.cog.get_commands_list()

        view = CommandSelectView(self.cog, commands, "add")
        
        embed = discord.Embed(
            title="Add Permission",
            description="Select a command to add role permission for:",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(
        label="Remove Permission", 
        style=discord.ButtonStyle.red,
        emoji="🗑️",
        row=0
    )
    async def remove_permission_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to remove a command permission for a role."""

        commands = await self.cog.get_commands_list()

        view = CommandSelectView(self.cog, commands, "remove")
        
        embed = discord.Embed(
            title="Remove Permission",
            description="Select a command to remove role permission from:",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(
        label="View Permissions", 
        style=discord.ButtonStyle.blurple,
        emoji="👁️",
        row=0
    )
    async def view_permissions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to view command permissions."""

        commands = await self.cog.get_commands_list()

        view = CommandSelectView(self.cog, commands, "view")
        
        embed = discord.Embed(
            title="View Permissions",
            description="Select a command to view its permissions:",
            color=discord.Color.blurple()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(
        label="Reset Command", 
        style=discord.ButtonStyle.gray,
        emoji="🔄",
        row=0
    )
    async def reset_command_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to reset a command's permissions (make it available to everyone)."""

        commands = await self.cog.get_commands_list()

        view = CommandSelectView(self.cog, commands, "reset")
        
        embed = discord.Embed(
            title="Reset Command Permissions",
            description="Select a command to reset its permissions (make available to everyone):",
            color=discord.Color.gray()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @discord.ui.button(
        label="Set Public", 
        style=discord.ButtonStyle.success,
        emoji="🌐",
        row=1
    )
    async def set_public_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set a command as public (visible to everyone)."""

        commands = await self.cog.get_commands_list()

        view = CommandSelectView(self.cog, commands, "set_public")
        
        embed = discord.Embed(
            title="Set Command Public",
            description="Select a command to make it visible to everyone:",
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(
        label="Remove Public", 
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        row=1
    )
    async def remove_public_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to remove a command from public visibility."""

        commands = await self.cog.get_commands_list()

        view = CommandSelectView(self.cog, commands, "remove_public")
        
        embed = discord.Embed(
            title="Remove Command Public",
            description="Select a command to remove from public visibility:",
            color=discord.Color.dark_red()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class CommandSelectView(discord.ui.View):
    """View with a select menu for choosing a command."""
    
    def __init__(self, cog, commands, action_type):
        super().__init__(timeout=120)  # 2 minute timeout
        self.cog = cog
        self.action_type = action_type

        self.cog.save_permissions()

        self.add_item(CommandSelect(commands, action_type))

class CommandSelect(discord.ui.Select):
    """Select menu for choosing a command."""
    
    def __init__(self, commands, action_type):

        options = []
        for cmd in commands[:25]:  # Discord limits to 25 options
            options.append(discord.SelectOption(
                label=cmd,
                description=f"Manage permissions for /{cmd}"
            ))

        super().__init__(
            placeholder="Choose a command...",
            min_values=1,
            max_values=1,
            options=options
        )
        
        self.action_type = action_type
    
    async def callback(self, interaction: discord.Interaction):
        """Handle command selection."""

        command_name = self.values[0]
        
        if self.action_type == "add":

            view = RoleSelectView(interaction.client.get_cog("PermissionsCog"), command_name, "add")
            
            embed = discord.Embed(
                title=f"Add Permission for /{command_name}",
                description="Select a role to give permission to use this command:",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        elif self.action_type == "remove":

            guild_id = interaction.guild.id
            allowed_role_ids = await interaction.client.get_cog("PermissionsCog").get_command_permissions(guild_id, command_name)
            
            if not allowed_role_ids:
                await interaction.response.send_message(
                    f"⚠️ No specific role permissions set for /{command_name}. The command is available to everyone.",
                    ephemeral=True
                )
                return

            view = RoleSelectView(interaction.client.get_cog("PermissionsCog"), command_name, "remove", allowed_role_ids)
            
            embed = discord.Embed(
                title=f"Remove Permission for /{command_name}",
                description="Select a role to remove permission to use this command:",
                color=discord.Color.red()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        elif self.action_type == "view":

            guild_id = interaction.guild.id
            allowed_role_ids = await interaction.client.get_cog("PermissionsCog").get_command_permissions(guild_id, command_name)

            guild_id_str = str(guild_id)
            is_public = False
            if guild_id_str in interaction.client.get_cog("PermissionsCog").visible_commands:
                if command_name in interaction.client.get_cog("PermissionsCog").visible_commands[guild_id_str]:
                    is_public = True
            
            embed = discord.Embed(
                title=f"Permissions for /{command_name}",
                color=discord.Color.blurple()
            )
            
            if is_public:
                embed.description = "🌐 This command is publicly visible to everyone."
                embed.add_field(
                    name="Role Permissions", 
                    value=("The command is also restricted to specific roles." if allowed_role_ids 
                          else "The command is usable by anyone."),
                    inline=False
                )
            
            if not allowed_role_ids:
                if not is_public:
                    embed.description = "🔓 This command is available to everyone."
            else:
                role_mentions = []
                for role_id in allowed_role_ids:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_mentions.append(f"• {role.mention}")
                
                if role_mentions:
                    if not is_public:
                        embed.description = "🔒 This command is restricted to the following roles:\n" + "\n".join(role_mentions)
                    else:
                        embed.add_field(
                            name="Restricted to Roles",
                            value="\n".join(role_mentions),
                            inline=False
                        )
                else:
                    if not is_public:
                        embed.description = "⚠️ This command has restrictions but the roles could not be found."
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif self.action_type == "reset":

            view = ConfirmResetView(interaction.client.get_cog("PermissionsCog"), command_name)
            
            embed = discord.Embed(
                title=f"Reset Permissions for /{command_name}",
                description="Are you sure you want to reset permissions for this command? This will make it available to everyone.",
                color=discord.Color.gold()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        elif self.action_type == "set_public":

            success, message = await interaction.client.get_cog("PermissionsCog").set_command_public(
                interaction.guild.id, command_name
            )
            
            embed = discord.Embed(
                title=f"Set /{command_name} as Public",
                description=message,
                color=discord.Color.green() if success else discord.Color.red()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif self.action_type == "remove_public":

            success, message = await interaction.client.get_cog("PermissionsCog").remove_command_public(
                interaction.guild.id, command_name
            )
            
            embed = discord.Embed(
                title=f"Remove /{command_name} from Public",
                description=message,
                color=discord.Color.green() if success else discord.Color.red()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

class RoleSelectView(discord.ui.View):
    """View for selecting a role."""
    
    def __init__(self, cog, command_name, action_type, allowed_role_ids=None):
        super().__init__(timeout=120)  # 2 minute timeout
        self.cog = cog
        self.command_name = command_name
        self.action_type = action_type

        self.cog.save_permissions()

        self.add_item(RoleSelect(command_name, action_type, allowed_role_ids))

class RoleSelect(discord.ui.RoleSelect):
    """Select menu for choosing a role."""
    
    def __init__(self, command_name, action_type, allowed_role_ids=None):

        super().__init__(
            placeholder="Choose a role...",
            min_values=1,
            max_values=1
        )
        
        self.command_name = command_name
        self.action_type = action_type
        self.allowed_role_ids = allowed_role_ids
    
    async def callback(self, interaction: discord.Interaction):
        """Handle role selection."""

        role = self.values[0]

        success = False
        message = "No action was taken."
        
        if self.action_type == "add":

            success, message = await interaction.client.get_cog("PermissionsCog").add_role_permission(
                interaction.guild.id, self.command_name, role.id
            )
        elif self.action_type == "remove":

            success, message = await interaction.client.get_cog("PermissionsCog").remove_role_permission(
                interaction.guild.id, self.command_name, role.id
            )

        embed = discord.Embed(
            title="Permission Update",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ConfirmResetView(discord.ui.View):
    """View for confirming permission reset."""
    
    def __init__(self, cog, command_name):
        super().__init__(timeout=60)  # 1 minute timeout
        self.cog = cog
        self.command_name = command_name
    
    @discord.ui.button(
        label="Yes, Reset", 
        style=discord.ButtonStyle.danger,
        emoji="✅"
    )
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to confirm reset."""

        success, message = await self.cog.clear_command_permissions(
            interaction.guild.id, self.command_name
        )

        embed = discord.Embed(
            title="Permission Reset",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
    
    @discord.ui.button(
        label="Cancel", 
        style=discord.ButtonStyle.gray,
        emoji="❌"
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to cancel reset."""
        await interaction.response.send_message(
            "✋ Permission reset cancelled.",
            ephemeral=True
        )
        self.stop()

# Helper functions for managing public commands
def save_public_commands(commands):
    """Save public commands to the JSON file."""
    os.makedirs("data", exist_ok=True)
    try:
        data = {"public_commands": list(set(commands))}  # Use set to remove duplicates
        with open("data/public_commands.json", "w") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving public commands: {e}")
        print(f"Error saving public commands: {e}")
        return False

def load_public_commands():
    """Load public commands from the JSON file."""
    try:
        if os.path.exists("data/public_commands.json"):
            with open("data/public_commands.json", "r") as f:
                data = json.load(f)
                return data.get("public_commands", [])
        return []
    except Exception as e:
        logger.error(f"Error loading public commands: {e}")
        print(f"Error loading public commands: {e}")
        return []

@app_commands.command(name="setpublic", description="Make a command publicly available (Admin only)")
@app_commands.describe(
    command_name="The name of the command to make public"
)
async def setpublic(interaction: discord.Interaction, command_name: str):
    """Make a command publicly available (Admin only)."""
    # Check if user has admin permissions for addlevel (same permission level)
    if not await is_admin(interaction):
        return
    
    # Get existing public commands
    public_commands = load_public_commands()
    
    # Normalize command name (remove slash and make lowercase)
    cmd_name = command_name.lower().strip("/")
    
    # Check if command is already public
    if cmd_name in public_commands:
        await interaction.response.send_message(
            f"⚠️ Command `{cmd_name}` is already set as public.",
            ephemeral=True
        )
        return
    
    # Add command to public list
    public_commands.append(cmd_name)
    
    # Save updated list
    if save_public_commands(public_commands):
        await interaction.response.send_message(
            f"✅ Command `{cmd_name}` is now publicly available.",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} made command '{cmd_name}' public")
        print(f"User {interaction.user.id} made command '{cmd_name}' public")
    else:
        await interaction.response.send_message(
            "❌ An error occurred while saving public commands.",
            ephemeral=True
        )

@app_commands.command(name="removepublic", description="Remove a command from public access (Admin only)")
@app_commands.describe(
    command_name="The name of the command to remove from public access"
)
async def removepublic(interaction: discord.Interaction, command_name: str):
    """Remove a command from public access (Admin only)."""
    # Check if user has admin permissions for addlevel (same permission level)
    if not await is_admin(interaction):
        return
    
    # Get existing public commands
    public_commands = load_public_commands()
    
    # Normalize command name (remove slash and make lowercase)
    cmd_name = command_name.lower().strip("/")
    
    # Check if command is in the public list
    if cmd_name not in public_commands:
        await interaction.response.send_message(
            f"⚠️ Command `{cmd_name}` is not in the public commands list.",
            ephemeral=True
        )
        return
    
    # Remove command from public list
    public_commands.remove(cmd_name)
    
    # Save updated list
    if save_public_commands(public_commands):
        await interaction.response.send_message(
            f"✅ Command `{cmd_name}` is no longer publicly available.",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} removed command '{cmd_name}' from public access")
        print(f"User {interaction.user.id} removed command '{cmd_name}' from public access")
    else:
        await interaction.response.send_message(
            "❌ An error occurred while saving public commands.",
            ephemeral=True
        )

async def setup(bot):
    """Add the permissions cog to the bot."""
    cog = PermissionsCog(bot)
    await bot.add_cog(cog)
    
    # Register the setpublic and removepublic commands
    bot.tree.add_command(setpublic)
    bot.tree.add_command(removepublic)

    @bot.check
    async def global_permissions(ctx):

        command_name = ctx.command.name.lower() if ctx.command else None

        admin_user_ids = ["1308527904497340467", "479711321399623681", "1063511383397892256"]

        if str(ctx.author.id) in admin_user_ids:
            return True

        admin_role_id = "1338482857974169683"
        has_admin_role = False
        for role in ctx.author.roles:
            if str(role.id) == admin_role_id:
                has_admin_role = True
                break
                
        if has_admin_role:
            return True

        public_commands = [
            'activityleaderboard',
            'leaderboard',
            'rank',
            'business',
            'invest',
            'invites',
            'inviteleaderboard',
            'work',
            'shop',
            'buy',
            'webtoken'
        ]
        
        # Load any additional public commands from JSON file
        try:
            if os.path.exists("data/public_commands.json"):
                with open("data/public_commands.json", "r") as f:
                    data = json.load(f)
                    additional_commands = data.get("public_commands", [])
                    public_commands.extend(additional_commands)
        except Exception as e:
            logger.error(f"Error loading public commands: {e}")
            print(f"Error loading public commands: {e}")

        public_commands = [cmd.lower() for cmd in public_commands]

        if command_name in public_commands:
            return True

        return False

    bot.tree.interaction_check = check_permissions

    @bot.event
    async def on_ready():

        cog.load_permissions()

        for guild in bot.guilds:
            guild_id = str(guild.id)
            logger.info(f"Setting up permissions for guild {guild_id} ({guild.name})")

            cog.visible_commands[guild_id] = []

        cog.save_permissions()
        
        # Get list of all public commands
        public_commands = [
            'activityleaderboard',
            'leaderboard',
            'rank',
            'business',
            'invest',
            'invites',
            'inviteleaderboard',
            'work',
            'shop',
            'buy',
            'webtoken'
        ]
        
        # Add any dynamic public commands
        additional_commands = []
        try:
            if os.path.exists("data/public_commands.json"):
                with open("data/public_commands.json", "r") as f:
                    data = json.load(f)
                    additional_commands = data.get("public_commands", [])
                    public_commands.extend(additional_commands)
                    print(f"LOADED DYNAMIC PUBLIC COMMANDS: {additional_commands}")
                    logger.warning(f"LOADED DYNAMIC PUBLIC COMMANDS: {additional_commands}")
        except Exception as e:
            logger.error(f"Error loading public commands: {e}")
            print(f"Error loading public commands: {e}")
            
        public_commands_str = ", ".join(public_commands)
        logger.info(f"MAXIMUM SECURITY: All commands restricted to admins except for the following public commands: {public_commands_str}")
        print(f"MAXIMUM SECURITY: All commands restricted to admins except for the following public commands: {public_commands_str}")
    
    logger.info("Permissions cog loaded")

async def is_admin(interaction: discord.Interaction) -> bool:
    """Check if a user has the required roles to use admin commands based on command and role."""

    command_name = interaction.command.name.lower() if interaction.command else None

    public_commands = [
        'activityleaderboard',
        'leaderboard',
        'rank',
        'business',
        'invest',
        'invites',
        'inviteleaderboard',
        'work',
        'shop',
        'buy',
        'webtoken'
    ]

    # Load any additional public commands from JSON file
    try:
        if os.path.exists("data/public_commands.json"):
            with open("data/public_commands.json", "r") as f:
                data = json.load(f)
                additional_commands = data.get("public_commands", [])
                public_commands.extend(additional_commands)
    except Exception as e:
        logger.error(f"Error loading public commands: {e}")

    public_commands = [cmd.lower() for cmd in public_commands]

    if command_name in public_commands:
        return True

    role_permissions = {

        "1338482857974169683": ["*"],  # All commands
        "1350879840794054758": ["*"],  # All commands

        "1339687502121795584": ["warn", "ban", "mute", "unmute", "unban", "warnings", "kick", "activitystart", "gamevote"],

        "1349101707702960330": ["warn", "unwarn", "mute", "unmute"],

        "1350500295217643733": ["gamevote", "warn", "unwarn", "mute", "unmute", "warnings", "kick", "ban"],

        "1348976063019094117": ["gcreate", "greroll", "mute", "unmute", "warn", "unwarn", "warnings"],

        "1339687513136169060": ["warn", "unwarn", "mute", "unmute", "ban", "kick", "unban", "warnings"],

        "1351806909874835487": ["warn", "ban", "mute", "unmute", "unban", "warnings", "kick", "activitystart", "gamevote"],

        "1350549403068530741": ["warn", "unwarn", "mute", "unmute", "ban", "kick", "unban", "warnings"]
    }

    has_permission = False
    
    if interaction.guild and interaction.user:
        member = interaction.guild.get_member(interaction.user.id)
        if member:
            user_role_ids = [str(role.id) for role in member.roles]

            for role_id in user_role_ids:
                if role_id in role_permissions:

                    if "*" in role_permissions[role_id]:
                        has_permission = True
                        break

                    if command_name in role_permissions[role_id]:
                        has_permission = True
                        break
    
    if has_permission:
        return True

    await interaction.response.send_message(
        "❌ You don't have required role to use this command.",
        ephemeral=True
    )
    return False

async def check_permissions(interaction: discord.Interaction):

    command_name = interaction.command.name.lower() if interaction.command else None
    print(f"Command attempted: {command_name}")

    user_id = str(interaction.user.id)

    logger.debug(f"Checking permissions for user {user_id} to use command '{command_name}'")
    print(f"Checking permissions for user {user_id} to use command '{command_name}'")

    public_commands = [
        'activityleaderboard',
        'leaderboard',
        'rank',
        'business',
        'invest',
        'invites',
        'inviteleaderboard',
        'work',
        'shop',
        'buy',
        'webtoken'
    ]
    
    # Load any additional public commands from JSON file
    try:
        if os.path.exists("data/public_commands.json"):
            with open("data/public_commands.json", "r") as f:
                data = json.load(f)
                additional_commands = data.get("public_commands", [])
                public_commands.extend(additional_commands)
    except Exception as e:
        logger.error(f"Error loading public commands: {e}")
        print(f"Error loading public commands: {e}")

    public_commands = [cmd.lower() for cmd in public_commands]

    if command_name in public_commands:
        logger.debug(f"Permission granted: Public command '{command_name}'")
        print(f"Permission granted: Public command '{command_name}' for user {user_id}")
        return True

    role_permissions = {

        "1338482857974169683": ["*"],  # All commands
        "1350879840794054758": ["*"],  # All commands

        "1339687502121795584": ["warn", "ban", "mute", "unmute", "unban", "warnings", "kick", "activitystart", "gamevote"],

        "1349101707702960330": ["warn", "unwarn", "mute", "unmute"],

        "1350500295217643733": ["gamevote", "warn", "unwarn", "mute", "unmute", "warnings", "kick", "ban"],

        "1348976063019094117": ["gcreate", "greroll", "mute", "unmute", "warn", "unwarn", "warnings"],

        "1339687513136169060": ["warn", "unwarn", "mute", "unmute", "ban", "kick", "unban", "warnings"],

        "1351806909874835487": ["warn", "ban", "mute", "unmute", "unban", "warnings", "kick", "activitystart", "gamevote"],

        "1350549403068530741": ["warn", "unwarn", "mute", "unmute", "ban", "kick", "unban", "warnings"]
    }

    has_permission = False
    user_roles = []
    
    if interaction.guild and interaction.user:
        member = interaction.guild.get_member(interaction.user.id)
        if member:
            user_role_ids = [str(role.id) for role in member.roles]

            for role_id in user_role_ids:
                if role_id in role_permissions:
                    user_roles.append(role_id)

                    if "*" in role_permissions[role_id]:
                        has_permission = True
                        break

                    if command_name in role_permissions[role_id]:
                        has_permission = True
                        break
    
    if has_permission:
        logger.debug(f"Permission granted: User {user_id} has role with permission for command '{command_name}'")
        print(f"Permission granted: User {user_id} has role with permission for command '{command_name}'")
        return True

    try:
        await interaction.response.send_message(
            "❌ You don't have required role to use this command.",
            ephemeral=True
        )
        logger.debug(f"Permission denied: User {user_id} without required role attempted to use '{command_name}'")
        print(f"Permission denied: User {user_id} without required role attempted to use '{command_name}'")
    except Exception as e:
        logger.error(f"Error responding to permission denial: {e}")
        print(f"Error responding to permission denial: {e}")
    
    return False