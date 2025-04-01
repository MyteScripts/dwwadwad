import os
import discord
import asyncio
import time
import json
from discord.ext import commands
from database import Database
from logger import setup_logger

logger = setup_logger('voice_rewards')

class VoiceUserActivity:
    """Class to track a single user's voice activity."""
    def __init__(self, user_id, username, join_time):
        self.user_id = user_id
        self.username = username
        self.join_time = join_time
        self.total_minutes = 0
        
    def calculate_time(self, leave_time=None):
        """Calculate time spent in voice channel in minutes."""
        end_time = leave_time or time.time()
        seconds_spent = end_time - self.join_time
        minutes_spent = int(seconds_spent // 60)  # Integer division to get only full minutes
        return minutes_spent
    
    def to_dict(self):
        """Convert this object to a dictionary for serialization."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'join_time': self.join_time,
            'total_minutes': self.total_minutes
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a VoiceUserActivity object from a dictionary."""
        instance = cls(data['user_id'], data['username'], data['join_time'])
        instance.total_minutes = data['total_minutes']
        return instance

class VoiceRewardsCog(commands.Cog):
    """Cog for managing voice channel rewards."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.voice_users = {}  # {user_id: VoiceUserActivity}
        self.downtime_users = []  # List of users to process for downtime rewards
        self.startup_task = None
        self.voice_states_file = 'data/voice_states.json'
        
    def save_voice_states(self):
        """Save current voice states to a JSON file."""
        try:

            voice_states = {}
            for user_id, activity in self.voice_users.items():
                voice_states[str(user_id)] = activity.to_dict()

            with open(self.voice_states_file, 'w') as f:
                json.dump(voice_states, f)
                
            logger.info(f"Saved {len(voice_states)} voice states to {self.voice_states_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving voice states: {e}")
            return False
    
    def load_voice_states(self):
        """Load voice states from a JSON file."""
        try:
            if not os.path.exists(self.voice_states_file):
                logger.info(f"No voice states file found at {self.voice_states_file}")
                return False
                
            with open(self.voice_states_file, 'r') as f:
                voice_states = json.load(f)

            self.downtime_users = []

            loaded_states = 0
            for user_id_str, data in voice_states.items():
                try:

                    original_join_time = data['join_time']
                    current_time = time.time()
                    minutes_spent = int((current_time - original_join_time) // 60)

                    if minutes_spent >= 1:

                        self.downtime_users.append({
                            'user_id': int(user_id_str),
                            'username': data['username'],
                            'minutes': minutes_spent
                        })

                    activity = VoiceUserActivity(int(user_id_str), data['username'], current_time)
                    self.voice_users[int(user_id_str)] = activity
                    loaded_states += 1
                    
                    logger.info(f"Loaded voice state for {data['username']} ({user_id_str}) - {minutes_spent} minutes during downtime")
                except Exception as e:
                    logger.error(f"Error loading voice state for user {user_id_str}: {e}")
                    
            logger.info(f"💾 LOADED DATA: Restored {loaded_states} voice states from previous session")

            os.remove(self.voice_states_file)
            logger.info(f"Removed voice states file {self.voice_states_file}")
            return True
        except Exception as e:
            logger.error(f"Error loading voice states: {e}")
            return False
            
    def cog_unload(self):
        """Called when the cog is unloaded."""

        if self.voice_users:
            logger.warning(f"Bot shutting down with {len(self.voice_users)} users still in voice channels.")
            self.save_voice_states()

        self.db.close()
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready. Check for users already in voice channels."""

        if self.startup_task is not None:
            self.startup_task.cancel()

        loaded = self.load_voice_states()
        if loaded:
            logger.info("🔄 STARTUP: Successfully loaded voice states from previous session")

        self.startup_task = asyncio.create_task(self.check_voice_channels())
        logger.info("🔍 STARTUP: Started voice channel scanning task")
        
    async def check_voice_channels(self):
        """Check all voice channels for users and start tracking them."""
        users_found = 0

        await asyncio.sleep(2)

        if hasattr(self, 'downtime_users') and self.downtime_users:
            logger.info(f"⏰ DOWNTIME PROCESSING: Awarding rewards to {len(self.downtime_users)} users from previous session")
            for user_info in self.downtime_users:
                user_id = user_info['user_id']
                username = user_info['username']
                minutes = user_info['minutes']

                await self.reward_downtime(user_id, username, minutes)

            self.downtime_users = []

        current_voice_users = set()
        
        for guild in self.bot.guilds:

            if not guild.me.guild_permissions.view_channel:
                continue
                
            for voice_channel in guild.voice_channels:

                for member in voice_channel.members:

                    if member.bot:
                        continue

                    user_id = member.id
                    current_voice_users.add(user_id)
                    username = member.display_name

                    if user_id not in self.voice_users:
                        self.voice_users[user_id] = VoiceUserActivity(user_id, username, time.time())
                        users_found += 1
                        logger.info(f"👤 USER ALREADY IN VOICE: {username} ({user_id}) found in channel {voice_channel.name}")

        users_to_reward = []
        for user_id in list(self.voice_users.keys()):
            if user_id not in current_voice_users:

                activity = self.voice_users.pop(user_id)
                users_to_reward.append((user_id, activity.username))

        for user_id, username in users_to_reward:
            logger.info(f"🎙️ LEFT DURING DOWNTIME: {username} ({user_id}) left voice channel while bot was offline, processing rewards")
            await self.reward_voice_time(user_id, username)
                        
        logger.info(f"👥 VOICE TRACKING: Found and started tracking {users_found} users already in voice channels")
        self.startup_task = None
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Triggered when a member changes their voice state.
        This includes:
        - Joining a voice channel
        - Leaving a voice channel
        - Moving between voice channels
        - Muting/unmuting
        - Deafening/undeafening
        """

        if member.bot:
            return
            
        user_id = member.id
        username = member.display_name

        if before.channel is None and after.channel is not None:
            logger.info(f"🎙️ JOINED VOICE: {username} ({user_id}) entered channel '{after.channel.name}'")

            self.voice_users[user_id] = VoiceUserActivity(user_id, username, time.time())

        elif before.channel is not None and after.channel is None:
            logger.info(f"🎙️ LEFT VOICE: {username} ({user_id}) left channel '{before.channel.name}'")

            await self.reward_voice_time(user_id, username)

        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            logger.info(f"🎙️ CHANGED CHANNEL: {username} ({user_id}) moved from '{before.channel.name}' to '{after.channel.name}'")

            if user_id in self.voice_users:

                await self.reward_voice_time(user_id, username)

                self.voice_users[user_id] = VoiceUserActivity(user_id, username, time.time())
                
    async def reward_voice_time(self, user_id, username):
        """
        Calculate rewards for time spent in voice and send DM to user.
        Rewards 1 coin and 1 XP per minute.
        """
        if user_id not in self.voice_users:
            return

        activity = self.voice_users.pop(user_id)

        minutes_spent = activity.calculate_time()

        if minutes_spent <= 0:
            return

        coin_multiplier = 1.0
        xp_multiplier = 1.0
        
        event_system_cog = self.bot.get_cog("EventSystemCog")
        if event_system_cog:

            coin_multiplier = await event_system_cog.get_coin_multiplier()
            xp_multiplier = await event_system_cog.get_xp_multiplier()

        coins_to_add = int(minutes_spent * coin_multiplier)

        updated_user = self.db.add_coins(user_id, username, coins_to_add)
        if updated_user is None:
            logger.error(f"Failed to add coins to user {username} ({user_id})")
            updated_user = {'level': 0}  # Default value to prevent errors
            level_up = False
        else:

            xp_enabled = self.db.get_xp_status()
            
            if xp_enabled:

                xp_result = self.db.add_xp(user_id, username, minutes_spent, xp_multiplier, coin_multiplier)
                if xp_result[0] is not None:  # Check if user data is returned
                    updated_user, level_up, xp_earned = xp_result
                else:
                    level_up = False
            else:

                level_up = False

        try:
            member = await self.bot.fetch_user(user_id)
            if member:

                embed = discord.Embed(
                    title="🎙️ Voice Time Rewards",
                    description=f"Thanks for spending time in voice chat!",
                    color=discord.Color.purple()
                )
                
                embed.add_field(
                    name="Time Spent",
                    value=f"{minutes_spent} minute{'s' if minutes_spent != 1 else ''}",
                    inline=False
                )

                xp_enabled = self.db.get_xp_status()

                multiplier_text = ""
                if coin_multiplier > 1.0 and xp_multiplier > 1.0:
                    if coin_multiplier == xp_multiplier:
                        multiplier_text = f"\n✨ **{coin_multiplier}x Event Bonus Active!**"
                    else:
                        multiplier_text = f"\n✨ **Event Bonus Active!** (XP: {xp_multiplier}x, Coins: {coin_multiplier}x)"
                elif coin_multiplier > 1.0:
                    multiplier_text = f"\n✨ **{coin_multiplier}x Coin Bonus Active!**"
                elif xp_multiplier > 1.0:
                    multiplier_text = f"\n✨ **{xp_multiplier}x XP Bonus Active!**"
                
                if xp_enabled:

                    xp_earned = int(minutes_spent * xp_multiplier)
                    coins_earned = coins_to_add
                    
                    embed.add_field(
                        name="Rewards Earned",
                        value=f"🪙 {coins_earned} Coin{'s' if coins_earned != 1 else ''}\n✨ {xp_earned} XP{multiplier_text}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Rewards Earned",
                        value=f"🪙 {coins_to_add} Coin{'s' if coins_to_add != 1 else ''}\n❌ *XP gain is currently disabled*{multiplier_text if coin_multiplier > 1.0 else ''}",
                        inline=False
                    )
                
                if level_up:
                    embed.add_field(
                        name="Level Up!",
                        value=f"🎉 Congratulations! You're now level {updated_user['level']}!",
                        inline=False
                    )

                if xp_enabled:
                    base_footer = "Earn 1 coin and 1 XP for every minute in voice channels!"
                    if coin_multiplier > 1.0 or xp_multiplier > 1.0:
                        if coin_multiplier == xp_multiplier and coin_multiplier > 1.0:
                            bonus_text = f" ({coin_multiplier}x event bonus active!)"
                        else:
                            if coin_multiplier > 1.0 and xp_multiplier > 1.0:
                                bonus_text = f" (Bonuses: XP {xp_multiplier}x, Coins {coin_multiplier}x)"
                            elif coin_multiplier > 1.0:
                                bonus_text = f" (Coins {coin_multiplier}x bonus active!)"
                            else:
                                bonus_text = f" (XP {xp_multiplier}x bonus active!)"
                        embed.set_footer(text=f"{base_footer}{bonus_text}")
                    else:
                        embed.set_footer(text=base_footer)
                else:
                    base_footer = "Earn 1 coin for every minute in voice channels! (XP gain is disabled)"
                    if coin_multiplier > 1.0:
                        bonus_text = f" (Coins {coin_multiplier}x bonus active!)"
                        embed.set_footer(text=f"{base_footer}{bonus_text}")
                    else:
                        embed.set_footer(text=base_footer)
                
                await member.send(embed=embed)
                
        except discord.Forbidden:
            logger.warning(f"Could not send DM to {username} ({user_id}). User may have DMs disabled.")
        except Exception as e:
            logger.error(f"Error sending voice rewards DM to {username} ({user_id}): {e}")

        if self.db.get_xp_status():

            xp_earned = int(minutes_spent * xp_multiplier)

            if xp_multiplier > 1.0 or coin_multiplier > 1.0:
                logger.info(f"💰 REWARD: {username} ({user_id}) earned {coins_to_add} coins and {xp_earned} XP for {minutes_spent} minutes in voice (with multipliers: XP {xp_multiplier}x, Coins {coin_multiplier}x)")
            else:
                logger.info(f"💰 REWARD: {username} ({user_id}) earned {coins_to_add} coins and {xp_earned} XP for {minutes_spent} minutes in voice")
        else:
            if coin_multiplier > 1.0:
                logger.info(f"💰 REWARD: {username} ({user_id}) earned {coins_to_add} coins for {minutes_spent} minutes in voice (XP disabled, Coin multiplier: {coin_multiplier}x)")
            else:
                logger.info(f"💰 REWARD: {username} ({user_id}) earned {coins_to_add} coins for {minutes_spent} minutes in voice (XP disabled)")
    
    async def reward_downtime(self, user_id, username, minutes_spent):
        """
        Special method to reward users for time spent in voice during bot downtime.
        Similar to reward_voice_time but specifically for downtime rewards.
        """

        if minutes_spent <= 0:
            return
            
        logger.info(f"⏰ PROCESSING DOWNTIME: {username} ({user_id}) was in voice for {minutes_spent} minutes while bot was offline")

        coin_multiplier = 1.0
        xp_multiplier = 1.0
        
        event_system_cog = self.bot.get_cog("EventSystemCog")
        if event_system_cog:

            coin_multiplier = await event_system_cog.get_coin_multiplier()
            xp_multiplier = await event_system_cog.get_xp_multiplier()

        coins_to_add = int(minutes_spent * coin_multiplier)

        updated_user = self.db.add_coins(user_id, username, coins_to_add)
        if updated_user is None:
            logger.error(f"Failed to add coins to user {username} ({user_id}) for downtime")
            updated_user = {'level': 0}  # Default value to prevent errors
            level_up = False
        else:

            xp_enabled = self.db.get_xp_status()
            
            if xp_enabled:

                xp_result = self.db.add_xp(user_id, username, minutes_spent, xp_multiplier, coin_multiplier)
                if xp_result[0] is not None:  # Check if user data is returned
                    updated_user, level_up, xp_earned = xp_result
                else:
                    level_up = False
            else:

                level_up = False

        try:
            member = await self.bot.fetch_user(user_id)
            if member:

                embed = discord.Embed(
                    title="🎙️ Voice Time Rewards During Bot Downtime",
                    description=f"Thanks for spending time in voice chat while the bot was offline! Here are your rewards:",
                    color=discord.Color.purple()
                )
                
                embed.add_field(
                    name="Time Spent During Downtime",
                    value=f"{minutes_spent} minute{'s' if minutes_spent != 1 else ''}",
                    inline=False
                )

                xp_enabled = self.db.get_xp_status()

                multiplier_text = ""
                if coin_multiplier > 1.0 and xp_multiplier > 1.0:
                    if coin_multiplier == xp_multiplier:
                        multiplier_text = f"\n✨ **{coin_multiplier}x Event Bonus Active!**"
                    else:
                        multiplier_text = f"\n✨ **Event Bonus Active!** (XP: {xp_multiplier}x, Coins: {coin_multiplier}x)"
                elif coin_multiplier > 1.0:
                    multiplier_text = f"\n✨ **{coin_multiplier}x Coin Bonus Active!**"
                elif xp_multiplier > 1.0:
                    multiplier_text = f"\n✨ **{xp_multiplier}x XP Bonus Active!**"
                
                if xp_enabled:

                    xp_earned = int(minutes_spent * xp_multiplier)
                    coins_earned = coins_to_add
                    
                    embed.add_field(
                        name="Rewards Earned",
                        value=f"🪙 {coins_earned} Coin{'s' if coins_earned != 1 else ''}\n✨ {xp_earned} XP{multiplier_text}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Rewards Earned",
                        value=f"🪙 {coins_to_add} Coin{'s' if coins_to_add != 1 else ''}\n❌ *XP gain is currently disabled*{multiplier_text if coin_multiplier > 1.0 else ''}",
                        inline=False
                    )
                
                if level_up:
                    embed.add_field(
                        name="Level Up!",
                        value=f"🎉 Congratulations! You're now level {updated_user['level']}!",
                        inline=False
                    )
                
                embed.add_field(
                    name="Continued Tracking",
                    value="Your voice time is now being tracked again. You'll continue earning rewards as long as you stay in the voice channel!",
                    inline=False
                )

                embed.set_footer(text="The bot was offline but we still tracked your time! Voice rewards are never lost.")
                
                await member.send(embed=embed)
                
        except discord.Forbidden:
            logger.warning(f"Could not send DM to {username} ({user_id}) for downtime rewards. User may have DMs disabled.")
        except Exception as e:
            logger.error(f"Error sending downtime rewards DM to {username} ({user_id}): {e}")

        if self.db.get_xp_status():

            xp_earned = int(minutes_spent * xp_multiplier)

            if xp_multiplier > 1.0 or coin_multiplier > 1.0:
                logger.info(f"⏰ DOWNTIME REWARD: {username} ({user_id}) earned {coins_to_add} coins and {xp_earned} XP for {minutes_spent} minutes during bot downtime (with multipliers: XP {xp_multiplier}x, Coins {coin_multiplier}x)")
            else:
                logger.info(f"⏰ DOWNTIME REWARD: {username} ({user_id}) earned {coins_to_add} coins and {xp_earned} XP for {minutes_spent} minutes during bot downtime")
        else:
            if coin_multiplier > 1.0:
                logger.info(f"⏰ DOWNTIME REWARD: {username} ({user_id}) earned {coins_to_add} coins for {minutes_spent} minutes during bot downtime (XP disabled, Coin multiplier: {coin_multiplier}x)")
            else:
                logger.info(f"⏰ DOWNTIME REWARD: {username} ({user_id}) earned {coins_to_add} coins for {minutes_spent} minutes during bot downtime (XP disabled)")

async def setup(bot):
    """Add the voice rewards cog to the bot."""
    voice_rewards_cog = VoiceRewardsCog(bot)
    await bot.add_cog(voice_rewards_cog)
    logger.info("Voice rewards cog loaded")