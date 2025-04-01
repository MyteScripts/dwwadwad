import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio
import logging
from logger import setup_logger
import time
import sqlite3
import json
import random
import os

logger = setup_logger('gamevote', 'bot.log')

# Path for tournament game votes
TOURNAMENT_VOTES_PATH = "data/tournament_votes.json"

def generate_random_id(length=5):
    """Generate a random alphanumeric ID.
    
    Args:
        length: Length of the ID to generate
        
    Returns:
        str: A random ID consisting of lowercase letters and numbers
    """
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join(random.choice(chars) for _ in range(length))

GAME_EMOJIS = {
    "Roblox": "<:emoji_30:1350929090416349267>",
    "Fortnite": "<:fotnite:1350927486820548639>",
    "Among Us": "<:amongus:1350927627308765226>",
    "Minecraft": "<:minecraft:1350927574343221301>",
    "Brawl Stars": "<:brawlstars:1350928606003597496>",
    "CSGO": "<:csgo:1350928842885304330>",
    "Clash Royale": "<:emoji_29:1350928883872043069>",
    "Valorant": "<:valorant:1350927534623035422>"
}

class GameVoteCog(commands.Cog):
    """Cog for managing game voting."""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_votes = {}  # channel_id -> vote_info
        self.vote_messages = {}  # channel_id -> message_id
        self.db_name = 'data/leveling.db'
        self.setup_database()
        logger.info("Game Vote cog initialized")
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
    async def cog_load(self):
        """Called when the cog is loaded. Used to initialize active votes."""

        self.bot.add_listener(self.on_ready_resume_votes, 'on_ready')
        
    async def load_and_resume_votes(self):
        """Load votes from database and prepare to resume them when bot is ready."""

        try:

            self.load_active_votes()
        except Exception as e:
            logger.error(f"Error in load_and_resume_votes: {e}")

    async def on_ready_resume_votes(self):
        """Resume active votes when the bot is ready."""
        logger.info("Bot is ready - resuming any active votes")
        await self.resume_active_votes()
    
    async def resume_active_votes(self):
        """Resume active votes that were loaded from the database."""

        self.load_active_votes()

        for channel_id, vote_info in self.active_votes.items():

            now = datetime.datetime.now()
            end_time = vote_info['end_time']
            
            if now < end_time:

                remaining_seconds = (end_time - now).total_seconds()
                duration_minutes = int(remaining_seconds / 60)
                
                if remaining_seconds > 0:

                    asyncio.create_task(self.end_vote_after_duration(channel_id, duration_minutes))

                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        hours = int(remaining_seconds // 3600)
                        minutes = int((remaining_seconds % 3600) // 60)
                        
                        time_str = []
                        if hours > 0:
                            time_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
                        if minutes > 0:
                            time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                        
                        time_remaining = ", ".join(time_str) if time_str else "less than a minute"
                        
                        embed = discord.Embed(
                            title="🎮 GAME VOTE RESUMED",
                            description=f"The game vote has been resumed after bot restart!",
                            color=discord.Color.blue()
                        )
                        
                        embed.add_field(
                            name="Time Remaining",
                            value=f"Voting will end in **{time_remaining}**!",
                            inline=False
                        )
                        
                        try:
                            await channel.send(embed=embed)
                            logger.info(f"Resumed game vote in channel {channel_id} with {remaining_seconds/60:.1f} minutes remaining")
                        except Exception as e:
                            logger.error(f"Error announcing vote resume: {e}")
                    
            else:

                if 'vote_id' in vote_info:
                    self.update_vote_status(vote_info['vote_id'], False)
                    logger.info(f"Marking expired vote (ID: {vote_info['vote_id']}) as inactive")
        
    def setup_database(self):
        """Set up the database tables needed for game vote tracking."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                message_id INTEGER,
                created_by INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                is_active INTEGER
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Game vote database tables created")
        except Exception as e:
            logger.error(f"Error setting up game vote database: {e}")
    
    def load_active_votes(self):
        """Load active votes from the database when the bot starts."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, channel_id, message_id, created_by, start_time, end_time, duration_minutes
            FROM game_votes WHERE is_active = 1
            ''')
            
            active_votes = cursor.fetchall()
            conn.close()
            
            if not active_votes:
                logger.info("No active game votes found in database")
                return
                
            for vote in active_votes:
                vote_id, channel_id, message_id, created_by, start_time_str, end_time_str, duration_minutes = vote

                if start_time_str:
                    start_time = datetime.datetime.fromisoformat(start_time_str)
                else:
                    start_time = datetime.datetime.now()
                    
                if end_time_str:
                    end_time = datetime.datetime.fromisoformat(end_time_str)
                else:
                    end_time = start_time + datetime.timedelta(minutes=duration_minutes)

                now = datetime.datetime.now()
                if now > end_time:

                    self.update_vote_status(vote_id, False)
                    logger.info(f"Marking expired vote (ID: {vote_id}) as inactive")
                    continue

                self.active_votes[channel_id] = {
                    'end_time': end_time,
                    'duration_minutes': duration_minutes,
                    'start_time': start_time,
                    'created_by': created_by,
                    'message_id': message_id,
                    'vote_id': vote_id
                }
                
                self.vote_messages[channel_id] = message_id

                remaining_seconds = (end_time - now).total_seconds()
                if remaining_seconds > 0:
                    logger.info(f"Loaded active vote in channel {channel_id} with {remaining_seconds/60:.1f} minutes remaining")
                
            logger.info(f"Loaded {len(active_votes)} active game votes from database")
            
        except Exception as e:
            logger.error(f"Error loading active votes: {e}")
    
    def save_vote(self, channel_id):
        """Save a vote to the database."""
        if channel_id not in self.active_votes:
            return None
            
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            vote_info = self.active_votes[channel_id]

            start_time_str = vote_info['start_time'].isoformat() if 'start_time' in vote_info else None
            end_time_str = vote_info['end_time'].isoformat() if 'end_time' in vote_info else None
            created_by = vote_info.get('created_by')

            if 'vote_id' in vote_info:

                cursor.execute('''
                UPDATE game_votes 
                SET message_id = ?, created_by = ?, start_time = ?, end_time = ?, 
                    duration_minutes = ?, is_active = 1
                WHERE id = ?
                ''', (
                    vote_info['message_id'],
                    created_by,
                    start_time_str,
                    end_time_str,
                    vote_info['duration_minutes'],
                    vote_info['vote_id']
                ))
            else:

                cursor.execute('''
                INSERT INTO game_votes 
                (channel_id, message_id, created_by, start_time, end_time, duration_minutes, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (
                    channel_id,
                    vote_info['message_id'],
                    created_by,
                    start_time_str,
                    end_time_str,
                    vote_info['duration_minutes']
                ))
                
                vote_info['vote_id'] = cursor.lastrowid
            
            conn.commit()
            conn.close()
            logger.info(f"Game vote saved for channel {channel_id}")
            return vote_info['vote_id']
            
        except Exception as e:
            logger.error(f"Error saving vote: {e}")
            return None
    
    def update_vote_status(self, vote_id, is_active):
        """Update the active status of a vote in the database."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE game_votes SET is_active = ? WHERE id = ?
            ''', (1 if is_active else 0, vote_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Updated vote {vote_id} status to {'active' if is_active else 'inactive'}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating vote status: {e}")
            return False
    
    async def has_admin_permissions(self, user_id, guild_id):
        """Check if a user has admin permissions."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
            
        member = guild.get_member(user_id)
        if not member:
            return False
            
        # Check for administrator permission or manage server permission
        return member.guild_permissions.administrator or member.guild_permissions.manage_guild
    
    @app_commands.command(name="gamevote", description="Start or end a game vote")
    async def gamevote(self, interaction: discord.Interaction):
        """Open a panel to start or end a game vote."""
        # Check if user has permission
        user_roles = [str(role.id) for role in interaction.user.roles]
        allowed_roles = ["1350549403068530741", "1355474705187864789", "1350500295217643733", "1338482857974169683"]
        has_permission = any(role in user_roles for role in allowed_roles) or await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id)
        
        if not has_permission:
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return

        view = GameVoteView(self)

        embed = discord.Embed(
            title="🎮 Game Vote",
            description="Start a new game vote or end the latest one.",
            color=discord.Color.purple()
        )

        if interaction.channel_id in self.active_votes:
            vote_info = self.active_votes[interaction.channel_id]
            end_time = vote_info['end_time']
            now = datetime.datetime.now()

            if now < end_time:
                remaining = end_time - now
                days, seconds = remaining.days, remaining.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                
                time_str = []
                if days > 0:
                    time_str.append(f"{days} day{'s' if days != 1 else ''}")
                if hours > 0:
                    time_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes > 0:
                    time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds > 0 and days == 0 and hours == 0:
                    time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
                time_remaining = ", ".join(time_str)
                
                embed.add_field(
                    name="Active Vote",
                    value=f"Time remaining: **{time_remaining}**",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Game vote command used by {interaction.user}")
    
    async def start_vote(self, channel, duration_minutes):
        """Start a game vote in the specified channel."""

        if channel.id in self.active_votes:
            return False, "There's already an active vote in this channel!"

        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        
        embed = discord.Embed(
            title="🎮 GAME VOTE 🎮",
            description="React with the emoji of the game you want to play!",
            color=discord.Color.blue()
        )

        games_list = (
            f"{GAME_EMOJIS['Roblox']} Roblox\n"
            f"{GAME_EMOJIS['Fortnite']} Fortnite\n"
            f"{GAME_EMOJIS['Among Us']} Among Us\n"
            f"{GAME_EMOJIS['Minecraft']} Minecraft\n"
            f"{GAME_EMOJIS['Brawl Stars']} Brawl Stars\n"
            f"{GAME_EMOJIS['CSGO']} CSGO\n"
            f"{GAME_EMOJIS['Clash Royale']} Clash Royale\n"
            f"{GAME_EMOJIS['Valorant']} Valorant"
        )

        embed.add_field(name="Vote for your favorite game", value=games_list, inline=False)
        embed.add_field(name="⏰ Time Remaining", 
                       value=f"Voting ends in {duration_minutes} minute{'s' if duration_minutes != 1 else ''}!", 
                       inline=False)

        embed.set_footer(text=f"Vote started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

        vote_message = await channel.send(embed=embed)

        for emoji in GAME_EMOJIS.values():
            try:
                await vote_message.add_reaction(emoji)
                await asyncio.sleep(0.5)  # Brief delay to avoid rate limits
            except Exception as e:
                logger.error(f"Error adding reaction {emoji}: {e}")
        
        start_time = datetime.datetime.now()

        self.active_votes[channel.id] = {
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'start_time': start_time,
            'created_by': None,  # Will be set by the modal handler
            'message_id': vote_message.id
        }
        
        self.vote_messages[channel.id] = vote_message.id

        vote_id = self.save_vote(channel.id)
        logger.info(f"Started vote with ID {vote_id} in channel {channel.id}")

        asyncio.create_task(self.end_vote_after_duration(channel.id, duration_minutes))
        
        return True, f"Vote started and will end in {duration_minutes} minute{'s' if duration_minutes != 1 else ''}!"
    
    async def end_vote_after_duration(self, channel_id, duration_minutes):
        """End the vote after the specified duration."""
        await asyncio.sleep(duration_minutes * 60)

        if channel_id in self.active_votes:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.end_vote(channel)
    
    async def end_vote(self, channel):
        """End an active vote and display results."""
        if channel.id not in self.active_votes or channel.id not in self.vote_messages:
            return False, "There's no active vote in this channel!"

        message_id = self.vote_messages[channel.id]
        try:
            message = await channel.fetch_message(message_id)
        except Exception as e:
            logger.error(f"Error fetching vote message: {e}")
            return False, "Couldn't fetch the vote message. The vote has been cancelled."

        votes = {}
        for game_name, emoji in GAME_EMOJIS.items():
            votes[game_name] = 0

            for reaction in message.reactions:

                if str(reaction.emoji) == emoji:

                    bot_reacted = False
                    async for user in reaction.users():
                        if user.id == self.bot.user.id:
                            bot_reacted = True
                            break
                    
                    votes[game_name] = reaction.count - (1 if bot_reacted else 0)
                    break

        sorted_games = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_games[0][0]
        winner_votes = sorted_games[0][1]

        results_embed = discord.Embed(
            title="🏆 GAME VOTE RESULTS 🏆",
            description=f"**WINNER: {GAME_EMOJIS[winner]} {winner}** with {winner_votes} vote{'s' if winner_votes != 1 else ''}! 🎉",
            color=discord.Color.gold()
        )

        standings = ""
        for game, vote_count in sorted_games:
            standings += f"{GAME_EMOJIS[game]} {game}: {vote_count} vote{'s' if vote_count != 1 else ''}\n"

        results_embed.add_field(
            name="Final Standings",
            value=standings,
            inline=False
        )

        results_embed.set_footer(text=f"Vote ended at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

        await channel.send(embed=results_embed)

        if 'vote_id' in self.active_votes[channel.id]:
            vote_id = self.active_votes[channel.id]['vote_id']
            self.update_vote_status(vote_id, False)
            logger.info(f"Marked vote {vote_id} as inactive in database")

        del self.active_votes[channel.id]
        del self.vote_messages[channel.id]
        
        return True, "Vote ended and results displayed!"

class GameVoteModal(discord.ui.Modal):
    """Modal for creating a new game vote."""
    
    def __init__(self, cog):
        super().__init__(title="Create Game Vote")
        self.cog = cog
        
        self.duration_input = discord.ui.TextInput(
            label="Duration (number)",
            placeholder="How long the vote should last (e.g., 30)",
            required=True,
            max_length=5
        )
        self.add_item(self.duration_input)
        
        self.unit_input = discord.ui.TextInput(
            label="Time Unit",
            placeholder="minutes, hours, or days",
            default="minutes",
            required=True,
            max_length=10
        )
        self.add_item(self.unit_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            duration = int(self.duration_input.value)
            unit = self.unit_input.value.lower().strip()

            if unit in ["minute", "minutes", "min", "mins", "m"]:
                duration_minutes = duration
            elif unit in ["hour", "hours", "hr", "hrs", "h"]:
                duration_minutes = duration * 60
            elif unit in ["day", "days", "d"]:
                duration_minutes = duration * 60 * 24
            else:
                await interaction.response.send_message("Invalid time unit! Please use minutes, hours, or days.", ephemeral=True)
                return

            if duration <= 0:
                await interaction.response.send_message("Duration must be greater than 0!", ephemeral=True)
                return
            
            if duration_minutes > 10080:  # 1 week in minutes
                await interaction.response.send_message("Vote duration cannot be longer than 1 week!", ephemeral=True)
                return

            await interaction.response.send_message(f"Starting game vote for {duration} {unit}...", ephemeral=True)

            success, message = await self.cog.start_vote(interaction.channel, duration_minutes)

            if not success:
                await interaction.followup.send(message, ephemeral=True)
            else:

                if interaction.channel_id in self.cog.active_votes:
                    self.cog.active_votes[interaction.channel_id]['created_by'] = interaction.user.id

                    self.cog.save_vote(interaction.channel_id)
                
                logger.info(f"Game vote started by {interaction.user} in channel {interaction.channel_id} for {duration_minutes} minutes")
            
        except ValueError:
            await interaction.response.send_message("Please enter a valid number for duration!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error starting game vote: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class GameVoteView(discord.ui.View):
    """View with buttons for managing game votes."""
    
    def __init__(self, cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
    
    @discord.ui.button(label="Start Regular Vote", style=discord.ButtonStyle.primary, emoji="🎮")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to start a new regular game vote."""
        modal = GameVoteModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Start Tournament Vote", style=discord.ButtonStyle.primary, emoji="🏆")
    async def tournament_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to start a tournament game vote."""
        # Check if user has admin permissions
        if not await self.cog.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to start tournament votes.",
                ephemeral=True
            )
            return
        
        modal = TournamentGameVoteModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="End Latest Vote", style=discord.ButtonStyle.danger, emoji="🛑")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to end the current game vote."""
        if interaction.channel_id in self.cog.active_votes:
            vote_info = self.cog.active_votes[interaction.channel_id]

            is_creator = vote_info.get('created_by') == interaction.user.id
            has_manage_permission = interaction.user.guild_permissions.manage_messages
            
            if is_creator or has_manage_permission:
                await interaction.response.send_message("Ending game vote and tallying results...", ephemeral=True)

                success, message = await self.cog.end_vote(interaction.channel)
                
                if not success:
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    logger.info(f"Game vote ended by {interaction.user} in channel {interaction.channel_id}")
            else:
                await interaction.response.send_message("You don't have permission to end this vote!", ephemeral=True)
        else:
            await interaction.response.send_message("There's no active game vote in this channel!", ephemeral=True)

class TournamentGameVoteModal(discord.ui.Modal):
    """Modal for creating a tournament game vote."""
    
    def __init__(self, cog):
        super().__init__(title="Create Tournament Game Vote")
        self.cog = cog
        
        self.game1_input = discord.ui.TextInput(
            label="Game Option 1",
            placeholder="Enter first game option",
            required=True,
            max_length=50
        )
        self.add_item(self.game1_input)
        
        self.game2_input = discord.ui.TextInput(
            label="Game Option 2",
            placeholder="Enter second game option",
            required=True,
            max_length=50
        )
        self.add_item(self.game2_input)
        
        self.game3_input = discord.ui.TextInput(
            label="Game Option 3 (Optional)",
            placeholder="Enter third game option",
            required=False,
            max_length=50
        )
        self.add_item(self.game3_input)
        
        self.game4_input = discord.ui.TextInput(
            label="Game Option 4 (Optional)",
            placeholder="Enter fourth game option",
            required=False,
            max_length=50
        )
        self.add_item(self.game4_input)
        
        self.duration_input = discord.ui.TextInput(
            label="Duration (hours)",
            placeholder="How long the vote should last (e.g., 24)",
            default="24",
            required=True,
            max_length=3
        )
        self.add_item(self.duration_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:
            # Get game options
            games = [self.game1_input.value, self.game2_input.value]
            if self.game3_input.value:
                games.append(self.game3_input.value)
            if self.game4_input.value:
                games.append(self.game4_input.value)
                
            # Get duration
            try:
                duration_hours = int(self.duration_input.value)
                if duration_hours <= 0:
                    await interaction.response.send_message("Duration must be greater than 0 hours.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("Please enter a valid number for duration!", ephemeral=True)
                return
                
            await interaction.response.defer(ephemeral=True)
                
            # Create vote with a unique ID
            vote_id = generate_random_id(5)
            
            # Create tournament game votes file if it doesn't exist
            if not os.path.exists(TOURNAMENT_VOTES_PATH):
                os.makedirs(os.path.dirname(TOURNAMENT_VOTES_PATH), exist_ok=True)
                tournament_votes = {}
                with open(TOURNAMENT_VOTES_PATH, 'w') as f:
                    json.dump(tournament_votes, f, indent=4)
                
            # Load existing votes
            with open(TOURNAMENT_VOTES_PATH, 'r') as f:
                tournament_votes = json.load(f)
                
            # Check if ID already exists, generate a new one if needed
            while vote_id in tournament_votes:
                vote_id = generate_random_id(5)
                
            # Create tournament game vote
            end_time = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
            
            vote = {
                "id": vote_id,
                "channel_id": str(interaction.channel_id),
                "creator_id": str(interaction.user.id),
                "games": [{"name": game, "votes": 0} for game in games],
                "voters": {},
                "end_time": end_time.isoformat(),
                "status": "active",
                "message_id": None
            }
            
            # Save vote to file
            tournament_votes[vote_id] = vote
            with open(TOURNAMENT_VOTES_PATH, 'w') as f:
                json.dump(tournament_votes, f, indent=4)
                
            # Create an embed for the vote
            embed = discord.Embed(
                title="🏆 Tournament Game Vote",
                description="Vote for the game you'd like to play in the next tournament!",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="⏱️ Voting Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
            
            # Add game options
            for i, game in enumerate(games):
                embed.add_field(name=f"Option {i+1}", value=game, inline=True)
                
            # Add footer with vote ID
            embed.set_footer(text=f"Vote ID: {vote_id}")
            
            # Create view with vote buttons
            view = TournamentGameVoteButtonsView(vote_id, games)
            
            # Send the message
            response = await interaction.channel.send(embed=embed, view=view)
            
            # Save the message ID in the vote data
            tournament_votes[vote_id]["message_id"] = str(response.id)
            with open(TOURNAMENT_VOTES_PATH, 'w') as f:
                json.dump(tournament_votes, f, indent=4)
                
            await interaction.followup.send(
                f"Tournament game vote created successfully! The vote will end in {duration_hours} hours.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating tournament game vote: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while creating the tournament game vote. Please try again later.",
                ephemeral=True
            )

class TournamentGameVoteButtonsView(discord.ui.View):
    """View with buttons for tournament game voting."""
    
    def __init__(self, vote_id, games):
        super().__init__(timeout=None)  # No timeout for persistent buttons
        self.vote_id = vote_id
        
        # Add buttons for each game option
        for i, game in enumerate(games):
            button = discord.ui.Button(
                label=f"Option {i+1}",
                style=discord.ButtonStyle.primary,
                custom_id=f"tournament_vote_{vote_id}_{i}"
            )
            button.callback = self.vote_callback
            self.add_item(button)
    
    async def vote_callback(self, interaction: discord.Interaction):
        """Handle vote button clicks."""
        try:
            # Extract option index from custom_id
            custom_id = interaction.data["custom_id"]
            option_index = int(custom_id.split("_")[-1])
            
            # Load votes from file
            with open(TOURNAMENT_VOTES_PATH, 'r') as f:
                tournament_votes = json.load(f)
                
            # Check if vote exists and is active
            if self.vote_id not in tournament_votes:
                await interaction.response.send_message("This vote no longer exists.", ephemeral=True)
                return
                
            vote = tournament_votes[self.vote_id]
            if vote["status"] != "active":
                await interaction.response.send_message("This vote has ended.", ephemeral=True)
                return
                
            # Check if end time has passed
            end_time = datetime.datetime.fromisoformat(vote["end_time"])
            if datetime.datetime.now() > end_time:
                vote["status"] = "completed"
                with open(TOURNAMENT_VOTES_PATH, 'w') as f:
                    json.dump(tournament_votes, f, indent=4)
                await interaction.response.send_message("This vote has ended.", ephemeral=True)
                return
                
            # Record or update the user's vote
            user_id = str(interaction.user.id)
            
            # Check if user has already voted for a different option
            if user_id in vote["voters"]:
                previous_option = vote["voters"][user_id]
                vote["games"][previous_option]["votes"] -= 1
                
                await interaction.response.send_message(
                    f"You changed your vote to option {option_index+1}.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"You voted for option {option_index+1}.",
                    ephemeral=True
                )
                
            # Record the new vote
            vote["voters"][user_id] = option_index
            vote["games"][option_index]["votes"] += 1
            
            # Save the updated votes
            with open(TOURNAMENT_VOTES_PATH, 'w') as f:
                json.dump(tournament_votes, f, indent=4)
                
            # Update the embed to show current vote counts
            message = await interaction.channel.fetch_message(int(vote["message_id"]))
            embed = message.embeds[0]
            
            # Update vote counts in embed fields
            for i, game_info in enumerate(vote["games"]):
                game_name = game_info["name"]
                votes_count = game_info["votes"]
                
                # Get field index (offset by 1 because first field is the end time)
                field_index = i + 1
                
                # Update the field, preserving the option number in name
                if field_index < len(embed.fields):
                    field_name = embed.fields[field_index].name
                    embed.set_field_at(
                        field_index,
                        name=field_name,
                        value=f"{game_name} — {votes_count} vote{'s' if votes_count != 1 else ''}",
                        inline=True
                    )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error processing tournament game vote: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while processing your vote. Please try again.",
                ephemeral=True
            )

async def setup(bot):
    """Add the game vote cog to the bot."""

    cog = GameVoteCog(bot)

    cog.load_active_votes()

    await bot.add_cog(cog)
    logger.info("Game Vote cog loaded")