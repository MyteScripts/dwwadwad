import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import logging
from database import Database
import datetime
import asyncio
import pytz

# Set up logging
logger = logging.getLogger('profile_system')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Path to profiles data
PROFILES_PATH = "data/profiles.db"

# Available timezones
TIMEZONES = [
    "UTC", "Europe/London", "Europe/Paris", "Europe/Berlin", 
    "America/New_York", "America/Los_Angeles", "Asia/Tokyo", 
    "Asia/Dubai", "Australia/Sydney", "Pacific/Auckland"
]

# Languages
LANGUAGES = [
    {"name": "English", "emoji": "🇬🇧", "code": "en"},
    {"name": "Arabic", "emoji": "🇸🇦", "code": "ar"},
    {"name": "French", "emoji": "🇫🇷", "code": "fr"},
    {"name": "Indonesian", "emoji": "🇮🇩", "code": "id"},
    {"name": "Finnish", "emoji": "🇫🇮", "code": "fi"},
    {"name": "Lithuanian", "emoji": "🇱🇹", "code": "lt"}
]

# Standing levels
STANDING_LEVELS = [
    {"name": "Clear", "emoji": "✅", "color": 0x2ECC71},
    {"name": "Flagged", "emoji": "⚠️", "color": 0xF1C40F},
    {"name": "Monitored", "emoji": "👁️", "color": 0xE67E22},
    {"name": "Sanctioned", "emoji": "🚫", "color": 0xE74C3C}
]

# Behavioral stances
BEHAVIORAL_STANCES = [
    {"name": "Competitive", "emoji": "🏆", "description": "Focused on competitions and challenges"},
    {"name": "Casual", "emoji": "😊", "description": "Enjoys relaxed, fun interactions"},
    {"name": "Social", "emoji": "👥", "description": "Primarily here to chat and make friends"},
    {"name": "Silent", "emoji": "🤫", "description": "Prefers to observe rather than participate"}
]

# Announcement preferences
ANNOUNCEMENT_TYPES = [
    {"name": "Server Updates", "emoji": "📢", "id": "server_updates"},
    {"name": "Bot Updates", "emoji": "🤖", "id": "bot_updates"},
    {"name": "Tournaments", "emoji": "🏅", "id": "tournaments"},
    {"name": "General Announcements", "emoji": "📣", "id": "general_announcements"},
    {"name": "General Giveaways", "emoji": "🎁", "id": "general_giveaways"},
    {"name": "Chat Activities", "emoji": "💬", "id": "chat_activities"}
]

class ProfileManager:
    """Class to manage user profiles."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.profiles = {}
        self.load_profiles()
        
    def load_profiles(self):
        """Load profiles from the profiles database."""
        try:
            if os.path.exists(PROFILES_PATH):
                from sqlite3 import connect
                conn = connect(PROFILES_PATH)
                cursor = conn.cursor()
                
                # Check if the table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'")
                if not cursor.fetchone():
                    self.create_profiles_table(cursor)
                    conn.commit()
                
                # Load all profiles
                cursor.execute("SELECT * FROM profiles")
                for row in cursor.fetchall():
                    user_id = row[0]
                    self.profiles[user_id] = {
                        'mini_bio': row[1],
                        'standing_level': row[2],
                        'behavioral_stance': row[3],
                        'timezone': row[4],
                        'preferred_languages': json.loads(row[5]) if row[5] else [],
                        'announcement_preferences': json.loads(row[6]) if row[6] else [],
                        'infractions': json.loads(row[7]) if row[7] else {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0}
                    }
                
                conn.close()
                logger.info(f"Loaded {len(self.profiles)} profiles from database")
            else:
                # Create the database and table
                from sqlite3 import connect
                conn = connect(PROFILES_PATH)
                cursor = conn.cursor()
                self.create_profiles_table(cursor)
                conn.commit()
                conn.close()
                logger.info("Created new profiles database")
        except Exception as e:
            logger.error(f"Error loading profiles: {e}", exc_info=True)
    
    def create_profiles_table(self, cursor):
        """Create the profiles table in the database."""
        # First drop the old table if it exists (to fix schema issues)
        try:
            cursor.execute("DROP TABLE IF EXISTS profiles")
        except Exception as e:
            logger.error(f"Error dropping profiles table: {e}")
            
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                mini_bio TEXT,
                standing_level TEXT,
                behavioral_stance TEXT,
                timezone TEXT,
                preferred_languages TEXT,
                announcement_preferences TEXT,
                infractions TEXT
            )
        ''')
        logger.info("Created profiles table in database")
    
    def save_profile(self, user_id, profile_data):
        """Save a profile to the database."""
        try:
            from sqlite3 import connect
            conn = connect(PROFILES_PATH)
            cursor = conn.cursor()
            
            # Convert dictionaries to JSON strings
            preferred_languages = json.dumps(profile_data.get('preferred_languages', []))
            announcement_preferences = json.dumps(profile_data.get('announcement_preferences', []))
            infractions = json.dumps(profile_data.get('infractions', {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0}))
            
            # Check if the profile already exists
            cursor.execute("SELECT 1 FROM profiles WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                # Update existing profile
                cursor.execute('''
                    UPDATE profiles SET 
                    mini_bio = ?,
                    standing_level = ?,
                    behavioral_stance = ?,
                    timezone = ?,
                    preferred_languages = ?,
                    announcement_preferences = ?,
                    infractions = ?
                    WHERE user_id = ?
                ''', (
                    profile_data.get('mini_bio', ''),
                    profile_data.get('standing_level', 'Clear'),
                    profile_data.get('behavioral_stance', 'Casual'),
                    profile_data.get('timezone', 'UTC'),
                    preferred_languages,
                    announcement_preferences,
                    infractions,
                    user_id
                ))
            else:
                # Insert new profile
                cursor.execute('''
                    INSERT INTO profiles (
                        user_id, mini_bio, standing_level, behavioral_stance, 
                        timezone, preferred_languages, announcement_preferences, infractions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    profile_data.get('mini_bio', ''),
                    profile_data.get('standing_level', 'Clear'),
                    profile_data.get('behavioral_stance', 'Casual'),
                    profile_data.get('timezone', 'UTC'),
                    preferred_languages,
                    announcement_preferences,
                    infractions
                ))
            
            conn.commit()
            conn.close()
            
            # Update in-memory cache
            self.profiles[user_id] = profile_data
            
            logger.info(f"Saved profile for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving profile for user {user_id}: {e}", exc_info=True)
            return False
    
    def get_profile(self, user_id):
        """Get a user's profile."""
        # Check if profile is in memory cache
        if user_id in self.profiles:
            return self.profiles[user_id]
        
        # Try to load from database
        try:
            from sqlite3 import connect
            conn = connect(PROFILES_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                profile = {
                    'mini_bio': row[1],
                    'standing_level': row[2],
                    'behavioral_stance': row[3],
                    'timezone': row[4],
                    'preferred_languages': json.loads(row[5]) if row[5] else [],
                    'announcement_preferences': json.loads(row[6]) if row[6] else [],
                    'infractions': json.loads(row[7]) if row[7] else {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0}
                }
                
                # Cache in memory
                self.profiles[user_id] = profile
                
                conn.close()
                return profile
            else:
                # Create default profile
                default_profile = {
                    'mini_bio': '',
                    'standing_level': 'Clear',
                    'behavioral_stance': 'Casual',
                    'timezone': 'UTC',
                    'preferred_languages': ['en'],
                    'announcement_preferences': [],
                    'infractions': {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0}
                }
                
                # Save the default profile
                self.save_profile(user_id, default_profile)
                
                conn.close()
                return default_profile
        except Exception as e:
            logger.error(f"Error getting profile for user {user_id}: {e}", exc_info=True)
            
            # Return a default profile
            return {
                'mini_bio': '',
                'standing_level': 'Clear',
                'behavioral_stance': 'Casual',
                'timezone': 'UTC',
                'preferred_languages': ['en'],
                'announcement_preferences': [],
                'infractions': {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0}
            }
    
    def update_infraction(self, user_id, infraction_type, increment=1):
        """Update a user's infraction count."""
        profile = self.get_profile(user_id)
        
        if 'infractions' not in profile:
            profile['infractions'] = {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0}
            
        if infraction_type in profile['infractions']:
            profile['infractions'][infraction_type] += increment
        else:
            profile['infractions'][infraction_type] = increment
            
        # Save the updated profile
        self.save_profile(user_id, profile)
        
    def set_mini_bio(self, user_id, mini_bio):
        """Set a user's mini bio."""
        profile = self.get_profile(user_id)
        profile['mini_bio'] = mini_bio
        return self.save_profile(user_id, profile)
        
    def set_standing_level(self, user_id, standing_level):
        """Set a user's standing level."""
        profile = self.get_profile(user_id)
        profile['standing_level'] = standing_level
        return self.save_profile(user_id, profile)
        
    def set_behavioral_stance(self, user_id, behavioral_stance):
        """Set a user's behavioral stance."""
        profile = self.get_profile(user_id)
        profile['behavioral_stance'] = behavioral_stance
        return self.save_profile(user_id, profile)
        
    def set_timezone(self, user_id, timezone):
        """Set a user's timezone."""
        profile = self.get_profile(user_id)
        profile['timezone'] = timezone
        return self.save_profile(user_id, profile)
        
    def set_preferred_languages(self, user_id, languages):
        """Set a user's preferred languages."""
        profile = self.get_profile(user_id)
        profile['preferred_languages'] = languages
        return self.save_profile(user_id, profile)
        
    def toggle_announcement_preference(self, user_id, announcement_id):
        """Toggle an announcement preference."""
        profile = self.get_profile(user_id)
        
        if 'announcement_preferences' not in profile:
            profile['announcement_preferences'] = []
            
        if announcement_id in profile['announcement_preferences']:
            profile['announcement_preferences'].remove(announcement_id)
        else:
            profile['announcement_preferences'].append(announcement_id)
            
        return self.save_profile(user_id, profile)
        
    def get_current_time_in_timezone(self, timezone):
        """Get the current time in a specified timezone."""
        try:
            tz = pytz.timezone(timezone)
            now = datetime.datetime.now(tz)
            return now.strftime("%H:%M %Z")
        except Exception as e:
            logger.error(f"Error getting time for timezone {timezone}: {e}")
            return "Unknown"
            
    def should_send_announcement(self, user_id, announcement_type):
        """Check if a user should receive a specific announcement."""
        profile = self.get_profile(user_id)
        return announcement_type in profile.get('announcement_preferences', [])
        
    def get_users_with_preference(self, announcement_type):
        """Get all users who have opted in to a specific announcement type."""
        users = []
        
        for user_id, profile in self.profiles.items():
            if announcement_type in profile.get('announcement_preferences', []):
                users.append(user_id)
                
        return users
        
    def get_language_emoji(self, language_code):
        """Get the emoji for a language code."""
        for language in LANGUAGES:
            if language['code'] == language_code:
                return language['emoji']
        return "🌐"  # Default emoji
        
    def get_standing_level_details(self, standing_level):
        """Get details for a standing level."""
        for level in STANDING_LEVELS:
            if level['name'] == standing_level:
                return level
        return STANDING_LEVELS[0]  # Default to Clear
        
    def get_behavioral_stance_details(self, behavioral_stance):
        """Get details for a behavioral stance."""
        for stance in BEHAVIORAL_STANCES:
            if stance['name'] == behavioral_stance:
                return stance
        return BEHAVIORAL_STANCES[1]  # Default to Casual

class ProfileCog(commands.Cog):
    """Commands for the profile system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.profile_manager = ProfileManager(bot)
        
    @app_commands.command(
        name="profile",
        description="🧑‍💼 View your profile or another user's profile"
    )
    @app_commands.describe(
        user="The user whose profile you want to view (leave empty to view your own)"
    )
    async def profile(self, interaction: discord.Interaction, user: discord.User = None):
        """View your profile or another user's profile."""
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Determine whose profile to show
            target_user = user if user else interaction.user
            target_id = str(target_user.id)
            
            # Check if viewing own profile
            is_own_profile = target_user.id == interaction.user.id
            
            # Get the profile data
            profile_data = self.profile_manager.get_profile(target_id)
            
            # Get server join date
            join_date = "Unknown"
            if interaction.guild:
                member = await interaction.guild.fetch_member(target_user.id)
                if member:
                    join_date = f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown"
            
            # Get standing level details
            standing_level = profile_data.get('standing_level', 'Clear')
            standing_details = self.profile_manager.get_standing_level_details(standing_level)
            
            # Get behavioral stance details
            behavioral_stance = profile_data.get('behavioral_stance', 'Casual')
            behavior_details = self.profile_manager.get_behavioral_stance_details(behavioral_stance)
            
            # Create the embed
            embed = discord.Embed(
                title=f"{target_user.display_name}'s Profile",
                description=profile_data.get('mini_bio', '*No bio set*'),
                color=standing_details['color']
            )
            
            # Set the user's avatar as the thumbnail
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Add join date
            embed.add_field(
                name="📅 Joined Server",
                value=join_date,
                inline=True
            )
            
            # Add standing level
            embed.add_field(
                name="🛡️ Standing",
                value=f"{standing_details['emoji']} {standing_level}",
                inline=True
            )
            
            # Add behavioral stance
            embed.add_field(
                name="🧠 Behavioral Stance",
                value=f"{behavior_details['emoji']} {behavioral_stance}",
                inline=True
            )
            
            # Add infractions if any
            infractions = profile_data.get('infractions', {"warnings": 0, "mutes": 0, "kicks": 0, "bans": 0})
            total_infractions = sum(infractions.values())
            
            if total_infractions > 0:
                infraction_text = []
                if infractions.get('warnings', 0) > 0:
                    infraction_text.append(f"⚠️ Warnings: {infractions['warnings']}")
                if infractions.get('mutes', 0) > 0:
                    infraction_text.append(f"🔇 Mutes: {infractions['mutes']}")
                if infractions.get('kicks', 0) > 0:
                    infraction_text.append(f"👢 Kicks: {infractions['kicks']}")
                if infractions.get('bans', 0) > 0:
                    infraction_text.append(f"🚫 Bans: {infractions['bans']}")
                    
                embed.add_field(
                    name=f"⚖️ Infractions ({total_infractions})",
                    value="\n".join(infraction_text),
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚖️ Infractions",
                    value="No infractions on record ✨",
                    inline=False
                )
            
            # Add timezone if set
            timezone = profile_data.get('timezone')
            if timezone:
                current_time = self.profile_manager.get_current_time_in_timezone(timezone)
                embed.add_field(
                    name="🕒 Timezone",
                    value=f"{timezone} ({current_time})",
                    inline=True
                )
            
            # Add preferred languages if set
            languages = profile_data.get('preferred_languages', [])
            if languages:
                language_display = []
                for lang_code in languages:
                    emoji = self.profile_manager.get_language_emoji(lang_code)
                    lang_name = next((lang['name'] for lang in LANGUAGES if lang['code'] == lang_code), lang_code)
                    language_display.append(f"{emoji} {lang_name}")
                    
                embed.add_field(
                    name="🗣️ Preferred Languages",
                    value=", ".join(language_display),
                    inline=True
                )
            
            # Add announcement preferences if set
            preferences = profile_data.get('announcement_preferences', [])
            if preferences:
                pref_display = []
                for pref_id in preferences:
                    pref = next((a for a in ANNOUNCEMENT_TYPES if a['id'] == pref_id), None)
                    if pref:
                        pref_display.append(f"{pref['emoji']} {pref['name']}")
                        
                embed.add_field(
                    name="🔔 DM Announcement Preferences",
                    value="\n".join(pref_display),
                    inline=False
                )
            
            # Create view with edit button if viewing own profile
            if is_own_profile:
                view = ProfileView(self.bot, self.profile_manager, target_id, embed)
                await interaction.followup.send(embed=embed, view=view)
            else:
                # If not viewing own profile, don't include a view
                await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in profile command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while retrieving the profile. Please try again later.",
                ephemeral=True
            )
            
    @app_commands.command(
        name="setbio",
        description="✏️ Set your profile bio"
    )
    @app_commands.describe(
        bio="Your new profile bio (max 200 characters)"
    )
    async def setbio(self, interaction: discord.Interaction, bio: str):
        """Set your profile bio."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Limit bio length
            if len(bio) > 200:
                bio = bio[:197] + "..."
                
            # Update the bio
            user_id = str(interaction.user.id)
            success = self.profile_manager.set_mini_bio(user_id, bio)
            
            if success:
                await interaction.followup.send(
                    f"✅ Your profile bio has been updated!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ There was an error updating your bio. Please try again later.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in setbio command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="setstance",
        description="🧠 Set your behavioral stance"
    )
    @app_commands.describe(
        stance="Your new behavioral stance"
    )
    @app_commands.choices(stance=[
        app_commands.Choice(name=f"{stance['emoji']} {stance['name']}", value=stance['name'])
        for stance in BEHAVIORAL_STANCES
    ])
    async def setstance(self, interaction: discord.Interaction, stance: str):
        """Set your behavioral stance."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Update the stance
            user_id = str(interaction.user.id)
            success = self.profile_manager.set_behavioral_stance(user_id, stance)
            
            # Get stance details for the response
            stance_details = next((s for s in BEHAVIORAL_STANCES if s['name'] == stance), None)
            
            if success and stance_details:
                await interaction.followup.send(
                    f"✅ Your behavioral stance has been set to {stance_details['emoji']} **{stance}**!\n*{stance_details['description']}*",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ There was an error updating your stance. Please try again later.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in setstance command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="settimezone",
        description="🕒 Set your timezone"
    )
    @app_commands.describe(
        timezone="Your timezone"
    )
    @app_commands.choices(timezone=[
        app_commands.Choice(name=tz, value=tz)
        for tz in TIMEZONES
    ])
    async def settimezone(self, interaction: discord.Interaction, timezone: str):
        """Set your timezone."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Update the timezone
            user_id = str(interaction.user.id)
            success = self.profile_manager.set_timezone(user_id, timezone)
            
            if success:
                # Get current time in the new timezone
                current_time = self.profile_manager.get_current_time_in_timezone(timezone)
                
                await interaction.followup.send(
                    f"✅ Your timezone has been set to **{timezone}**!\nCurrent time: {current_time}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ There was an error updating your timezone. Please try again later.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in settimezone command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="setstanding",
        description="🛡️ Set a user's standing level (Admin only)"
    )
    @app_commands.describe(
        user="The user whose standing to update",
        standing="The new standing level"
    )
    @app_commands.choices(standing=[
        app_commands.Choice(name=f"{level['emoji']} {level['name']}", value=level['name'])
        for level in STANDING_LEVELS
    ])
    async def setstanding(self, interaction: discord.Interaction, user: discord.User, standing: str):
        """Set a user's standing level (Admin only)."""
        # Check if user has admin permissions
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Update the standing level
            user_id = str(user.id)
            success = self.profile_manager.set_standing_level(user_id, standing)
            
            # Get standing details for the response
            standing_details = next((s for s in STANDING_LEVELS if s['name'] == standing), None)
            
            if success and standing_details:
                await interaction.followup.send(
                    f"✅ {user.mention}'s standing level has been set to {standing_details['emoji']} **{standing}**!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ There was an error updating the standing level. Please try again later.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in setstanding command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="setlanguages",
        description="🗣️ Set your preferred languages"
    )
    async def setlanguages(self, interaction: discord.Interaction):
        """Set your preferred languages."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            profile = self.profile_manager.get_profile(user_id)
            current_languages = profile.get('preferred_languages', [])
            
            # Create view with language selection buttons
            view = LanguageSelectionView(self.profile_manager, user_id, current_languages)
            
            # Create embed
            embed = discord.Embed(
                title="🗣️ Select Your Preferred Languages",
                description="Click the buttons below to toggle your preferred languages. Selected languages will have a green button.",
                color=0x3498DB
            )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in setlanguages command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="setannouncementpreferences",
        description="🔔 Set your DM announcement preferences"
    )
    async def setannouncementpreferences(self, interaction: discord.Interaction):
        """Set your DM announcement preferences."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            profile = self.profile_manager.get_profile(user_id)
            current_preferences = profile.get('announcement_preferences', [])
            
            # Create view with announcement preference toggles
            view = AnnouncementPreferencesView(self.profile_manager, user_id, current_preferences)
            
            # Create embed
            embed = discord.Embed(
                title="🔔 Select Your DM Announcement Preferences",
                description="Toggle which announcements you'd like to receive via DM. Selected options will have a green button.",
                color=0x3498DB
            )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in setannouncementpreferences command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="addinfraction",
        description="⚖️ Add an infraction to a user (Admin only)"
    )
    @app_commands.describe(
        user="The user to add an infraction to",
        infraction_type="The type of infraction",
        count="Number of infractions to add (default: 1)"
    )
    @app_commands.choices(infraction_type=[
        app_commands.Choice(name="⚠️ Warning", value="warnings"),
        app_commands.Choice(name="🔇 Mute", value="mutes"),
        app_commands.Choice(name="👢 Kick", value="kicks"),
        app_commands.Choice(name="🚫 Ban", value="bans")
    ])
    async def addinfraction(self, interaction: discord.Interaction, user: discord.User, infraction_type: str, count: int = 1):
        """Add an infraction to a user (Admin only)."""
        # Check if user has admin permissions
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate count
            if count <= 0:
                await interaction.followup.send(
                    "❌ Infraction count must be greater than 0.",
                    ephemeral=True
                )
                return
                
            # Update the infraction count
            user_id = str(user.id)
            self.profile_manager.update_infraction(user_id, infraction_type, count)
            
            # Get the infraction type display name
            infraction_display = {
                "warnings": "Warning(s)",
                "mutes": "Mute(s)",
                "kicks": "Kick(s)",
                "bans": "Ban(s)"
            }.get(infraction_type, infraction_type)
            
            await interaction.followup.send(
                f"✅ Added {count} {infraction_display} to {user.mention}'s record.",
                ephemeral=True
            )
                
        except Exception as e:
            logger.error(f"Error in addinfraction command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )

class ProfileView(discord.ui.View):
    """View with button to edit a profile."""
    
    def __init__(self, bot, profile_manager, user_id, embed):
        super().__init__(timeout=180)
        self.bot = bot
        self.profile_manager = profile_manager
        self.user_id = user_id
        self.embed = embed
        
        # Add edit button
        edit_button = discord.ui.Button(
            label="Edit Profile",
            style=discord.ButtonStyle.primary,
            emoji="✏️"
        )
        edit_button.callback = self.edit_callback
        self.add_item(edit_button)
        
    async def edit_callback(self, interaction: discord.Interaction):
        """Callback for the edit button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Create a profile editor view
        view = ProfileEditorView(self.bot, self.profile_manager, self.user_id, self.embed)
        
        # Create an embed
        embed = discord.Embed(
            title="✏️ Edit Your Profile",
            description="Select what you'd like to edit:",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ProfileEditorView(discord.ui.View):
    """View with buttons to edit different parts of a profile."""
    
    def __init__(self, bot, profile_manager, user_id, profile_embed):
        super().__init__(timeout=180)
        self.bot = bot
        self.profile_manager = profile_manager
        self.user_id = user_id
        self.profile_embed = profile_embed
        
        # Add edit buttons with proper callbacks
        edit_bio_button = discord.ui.Button(
            label="Edit Bio",
            style=discord.ButtonStyle.secondary,
            emoji="📝",
            row=0
        )
        edit_bio_button.callback = self.edit_bio_callback
        self.add_item(edit_bio_button)
        
        change_stance_button = discord.ui.Button(
            label="Change Stance",
            style=discord.ButtonStyle.secondary,
            emoji="🧠",
            row=0
        )
        change_stance_button.callback = self.change_stance_callback
        self.add_item(change_stance_button)
        
        set_timezone_button = discord.ui.Button(
            label="Set Timezone",
            style=discord.ButtonStyle.secondary,
            emoji="🕒",
            row=1
        )
        set_timezone_button.callback = self.set_timezone_callback
        self.add_item(set_timezone_button)
        
        languages_button = discord.ui.Button(
            label="Languages",
            style=discord.ButtonStyle.secondary,
            emoji="🗣️",
            row=1
        )
        languages_button.callback = self.languages_callback
        self.add_item(languages_button)
        
        dm_preferences_button = discord.ui.Button(
            label="DM Preferences",
            style=discord.ButtonStyle.secondary,
            emoji="🔔",
            row=2
        )
        dm_preferences_button.callback = self.dm_preferences_callback
        self.add_item(dm_preferences_button)
        
    # Removed redundant callback assignment since we're now setting callbacks directly when creating buttons
    
    async def edit_bio_callback(self, interaction: discord.Interaction):
        """Callback for the edit bio button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Create a modal for bio editing
        modal = BioEditModal(self.profile_manager, self.user_id)
        await interaction.response.send_modal(modal)
    
    async def change_stance_callback(self, interaction: discord.Interaction):
        """Callback for the change stance button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Create a view for stance selection
        view = StanceSelectionView(self.profile_manager, self.user_id)
        
        # Create an embed
        embed = discord.Embed(
            title="🧠 Select Your Behavioral Stance",
            description="Choose the option that best describes how you engage with our community:",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def set_timezone_callback(self, interaction: discord.Interaction):
        """Callback for the set timezone button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Create a view for timezone selection
        view = TimezoneSelectionView(self.profile_manager, self.user_id)
        
        # Create an embed
        embed = discord.Embed(
            title="🕒 Select Your Timezone",
            description="Choose your timezone to help others know when you might be active:",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def languages_callback(self, interaction: discord.Interaction):
        """Callback for the languages button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Get current languages
        profile = self.profile_manager.get_profile(self.user_id)
        current_languages = profile.get('preferred_languages', [])
        
        # Create a view for language selection
        view = LanguageSelectionView(self.profile_manager, self.user_id, current_languages)
        
        # Create an embed
        embed = discord.Embed(
            title="🗣️ Select Your Preferred Languages",
            description="Toggle the languages you're comfortable using:",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def dm_preferences_callback(self, interaction: discord.Interaction):
        """Callback for the DM preferences button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Get current preferences
        profile = self.profile_manager.get_profile(self.user_id)
        current_preferences = profile.get('announcement_preferences', [])
        
        # Create a view for announcement preferences
        view = AnnouncementPreferencesView(self.profile_manager, self.user_id, current_preferences)
        
        # Create an embed
        embed = discord.Embed(
            title="🔔 DM Announcement Preferences",
            description="Select which types of announcements you'd like to receive via DM:",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class BioEditModal(discord.ui.Modal):
    """Modal for editing user bio."""
    
    bio = discord.ui.TextInput(
        label="Bio (max 200 characters)",
        placeholder="Tell us a bit about yourself...",
        default="",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=False
    )
    
    def __init__(self, profile_manager, user_id):
        super().__init__(title="Edit Your Profile Bio")
        self.profile_manager = profile_manager
        self.user_id = user_id
        
        # Set current bio as default
        profile = self.profile_manager.get_profile(user_id)
        self.bio.default = profile.get('mini_bio', '')
    
    async def on_submit(self, interaction: discord.Interaction):
        """Called when the user submits the modal."""
        try:
            # Update the bio
            success = self.profile_manager.set_mini_bio(self.user_id, self.bio.value)
            
            if success:
                await interaction.response.send_message(
                    "✅ Your profile bio has been updated!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ There was an error updating your bio. Please try again later.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error updating bio from modal: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred. Please try again later.",
                ephemeral=True
            )

class StanceSelectionView(discord.ui.View):
    """View with buttons for selecting a behavioral stance."""
    
    def __init__(self, profile_manager, user_id):
        super().__init__(timeout=180)
        self.profile_manager = profile_manager
        self.user_id = user_id
        
        # Add stance buttons
        for stance in BEHAVIORAL_STANCES:
            button = discord.ui.Button(
                label=stance['name'],
                style=discord.ButtonStyle.secondary,
                emoji=stance['emoji'],
                custom_id=f"stance_{stance['name']}"
            )
            button.callback = self.make_stance_callback(stance['name'])
            self.add_item(button)
    
    def make_stance_callback(self, stance_name):
        """Create a callback for a stance button."""
        async def stance_callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
                return
                
            # Update the stance
            success = self.profile_manager.set_behavioral_stance(self.user_id, stance_name)
            
            # Get stance details
            stance_details = next((s for s in BEHAVIORAL_STANCES if s['name'] == stance_name), None)
            
            if success and stance_details:
                # Create embed
                embed = discord.Embed(
                    title="✅ Behavioral Stance Updated",
                    description=f"Your stance has been set to {stance_details['emoji']} **{stance_name}**",
                    color=0x2ECC71
                )
                
                embed.add_field(
                    name="Description",
                    value=stance_details['description'],
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "❌ There was an error updating your stance. Please try again later.",
                    ephemeral=True
                )
                
        return stance_callback

class TimezoneSelectionView(discord.ui.View):
    """View with a select menu for choosing a timezone."""
    
    def __init__(self, profile_manager, user_id):
        super().__init__(timeout=180)
        self.profile_manager = profile_manager
        self.user_id = user_id
        
        # Add select menu
        self.add_item(TimezoneSelect(profile_manager, user_id))

class TimezoneSelect(discord.ui.Select):
    """Select menu for timezone selection."""
    
    def __init__(self, profile_manager, user_id):
        self.profile_manager = profile_manager
        self.user_id = user_id
        
        # Create options for timezones
        options = []
        for tz in TIMEZONES:
            try:
                timezone = pytz.timezone(tz)
                now = datetime.datetime.now(timezone)
                time_str = now.strftime("%H:%M")
                
                options.append(discord.SelectOption(
                    label=tz,
                    description=f"Current time: {time_str}",
                    value=tz
                ))
            except:
                # Skip invalid timezones
                continue
        
        super().__init__(
            placeholder="Select your timezone...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Called when the user selects an option."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        selected_timezone = self.values[0]
        
        # Update the timezone
        success = self.profile_manager.set_timezone(self.user_id, selected_timezone)
        
        if success:
            # Get current time in the new timezone
            current_time = self.profile_manager.get_current_time_in_timezone(selected_timezone)
            
            # Create embed
            embed = discord.Embed(
                title="✅ Timezone Updated",
                description=f"Your timezone has been set to **{selected_timezone}**",
                color=0x2ECC71
            )
            
            embed.add_field(
                name="Current Time",
                value=current_time,
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ There was an error updating your timezone. Please try again later.",
                ephemeral=True
            )

class LanguageSelectionView(discord.ui.View):
    """View with buttons for selecting preferred languages."""
    
    def __init__(self, profile_manager, user_id, current_languages):
        super().__init__(timeout=180)
        self.profile_manager = profile_manager
        self.user_id = user_id
        self.current_languages = current_languages
        
        # Add language toggle buttons
        for language in LANGUAGES:
            is_selected = language['code'] in current_languages
            button = discord.ui.Button(
                label=language['name'],
                style=discord.ButtonStyle.success if is_selected else discord.ButtonStyle.secondary,
                emoji=language['emoji'],
                custom_id=f"lang_{language['code']}"
            )
            button.callback = self.make_language_callback(language['code'])
            self.add_item(button)
        
        # Add save button
        save_button = discord.ui.Button(
            label="Save",
            style=discord.ButtonStyle.primary,
            emoji="💾",
            row=2
        )
        save_button.callback = self.save_callback
        self.add_item(save_button)
    
    def make_language_callback(self, language_code):
        """Create a callback for a language button."""
        async def language_callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
                return
                
            # Toggle the language
            if language_code in self.current_languages:
                self.current_languages.remove(language_code)
            else:
                self.current_languages.append(language_code)
                
            # Update button styles
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("lang_"):
                    button_lang_code = item.custom_id.split("_")[1]
                    item.style = discord.ButtonStyle.success if button_lang_code in self.current_languages else discord.ButtonStyle.secondary
            
            await interaction.response.edit_message(view=self)
            
        return language_callback
    
    async def save_callback(self, interaction: discord.Interaction):
        """Callback for the save button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Save the languages
        success = self.profile_manager.set_preferred_languages(self.user_id, self.current_languages)
        
        if success:
            # Create display of selected languages
            language_display = []
            for lang_code in self.current_languages:
                for language in LANGUAGES:
                    if language['code'] == lang_code:
                        language_display.append(f"{language['emoji']} {language['name']}")
                        break
            
            # Create embed
            embed = discord.Embed(
                title="✅ Languages Updated",
                description="Your preferred languages have been updated!",
                color=0x2ECC71
            )
            
            if language_display:
                embed.add_field(
                    name="Selected Languages",
                    value=", ".join(language_display),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Selected Languages",
                    value="None selected",
                    inline=False
                )
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(
                "❌ There was an error saving your languages. Please try again later.",
                ephemeral=True
            )

class AnnouncementPreferencesView(discord.ui.View):
    """View with buttons for selecting announcement preferences."""
    
    def __init__(self, profile_manager, user_id, current_preferences):
        super().__init__(timeout=180)
        self.profile_manager = profile_manager
        self.user_id = user_id
        self.current_preferences = current_preferences
        
        # Add preference toggle buttons
        for announcement in ANNOUNCEMENT_TYPES:
            is_selected = announcement['id'] in current_preferences
            button = discord.ui.Button(
                label=announcement['name'],
                style=discord.ButtonStyle.success if is_selected else discord.ButtonStyle.secondary,
                emoji=announcement['emoji'],
                custom_id=f"pref_{announcement['id']}"
            )
            button.callback = self.make_preference_callback(announcement['id'])
            self.add_item(button)
        
        # Add save button
        save_button = discord.ui.Button(
            label="Save",
            style=discord.ButtonStyle.primary,
            emoji="💾",
            row=2
        )
        save_button.callback = self.save_callback
        self.add_item(save_button)
    
    def make_preference_callback(self, preference_id):
        """Create a callback for a preference button."""
        async def preference_callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
                return
                
            # Toggle the preference
            if preference_id in self.current_preferences:
                self.current_preferences.remove(preference_id)
            else:
                self.current_preferences.append(preference_id)
                
            # Update button styles
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("pref_"):
                    button_pref_id = item.custom_id.split("_")[1]
                    item.style = discord.ButtonStyle.success if button_pref_id in self.current_preferences else discord.ButtonStyle.secondary
            
            await interaction.response.edit_message(view=self)
            
        return preference_callback
    
    async def save_callback(self, interaction: discord.Interaction):
        """Callback for the save button."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can only edit your own profile!", ephemeral=True)
            return
            
        # Update the profile with current preferences
        profile = self.profile_manager.get_profile(self.user_id)
        profile['announcement_preferences'] = self.current_preferences
        success = self.profile_manager.save_profile(self.user_id, profile)
        
        if success:
            # Create display of selected preferences
            preference_display = []
            for pref_id in self.current_preferences:
                for pref in ANNOUNCEMENT_TYPES:
                    if pref['id'] == pref_id:
                        preference_display.append(f"{pref['emoji']} {pref['name']}")
                        break
            
            # Create embed
            embed = discord.Embed(
                title="✅ Announcement Preferences Updated",
                description="Your DM announcement preferences have been updated!",
                color=0x2ECC71
            )
            
            if preference_display:
                embed.add_field(
                    name="You'll receive DMs for:",
                    value="\n".join(preference_display),
                    inline=False
                )
            else:
                embed.add_field(
                    name="DM Preferences",
                    value="You've opted out of all announcement DMs",
                    inline=False
                )
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(
                "❌ There was an error saving your preferences. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    """Add the profile system cog to the bot."""
    await bot.add_cog(ProfileCog(bot))
    logger.info("Profile system cog loaded")