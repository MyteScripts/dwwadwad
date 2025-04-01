import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import logging
import datetime
import random
import math
import asyncio
from database import Database

# Set up logging
logger = logging.getLogger('tournaments')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Path to tournament data
TOURNAMENTS_PATH = "data/tournaments.json"
GAME_VOTES_PATH = "data/tournament_votes.json"

def generate_random_id(length=5):
    """Generate a random alphanumeric ID.
    
    Args:
        length: Length of the ID to generate
        
    Returns:
        str: A random ID consisting of lowercase letters and numbers
    """
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join(random.choice(chars) for _ in range(length))

class TournamentManager:
    """Class to manage tournaments."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.active_tournaments = {}
        self.game_votes = {}
        self.load_data()
        
    def load_data(self):
        """Load tournament data from JSON file."""
        try:
            if os.path.exists(TOURNAMENTS_PATH):
                with open(TOURNAMENTS_PATH, 'r') as f:
                    self.active_tournaments = json.load(f)
                logger.info(f"Loaded {len(self.active_tournaments)} active tournaments")
            else:
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(TOURNAMENTS_PATH), exist_ok=True)
                self.save_tournaments()
                logger.info("Created new tournaments data file")
                
            if os.path.exists(GAME_VOTES_PATH):
                with open(GAME_VOTES_PATH, 'r') as f:
                    self.game_votes = json.load(f)
                logger.info(f"Loaded {len(self.game_votes)} game votes")
            else:
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(GAME_VOTES_PATH), exist_ok=True)
                self.save_game_votes()
                logger.info("Created new game votes data file")
        except Exception as e:
            logger.error(f"Error loading tournament data: {e}", exc_info=True)
    
    def save_tournaments(self):
        """Save tournament data to JSON file."""
        try:
            with open(TOURNAMENTS_PATH, 'w') as f:
                json.dump(self.active_tournaments, f, indent=4)
            logger.info("Saved tournament data")
        except Exception as e:
            logger.error(f"Error saving tournament data: {e}", exc_info=True)
            
    def save_game_votes(self):
        """Save game votes data to JSON file."""
        try:
            with open(GAME_VOTES_PATH, 'w') as f:
                json.dump(self.game_votes, f, indent=4)
            logger.info("Saved game votes data")
        except Exception as e:
            logger.error(f"Error saving game votes data: {e}", exc_info=True)
    
    def create_tournament(self, tournament_id, channel_id, creator_id, game, max_participants, 
                        start_time, team_count, players_per_team, prize):
        """Create a new tournament."""
        tournament = {
            "id": tournament_id,
            "channel_id": channel_id,
            "creator_id": creator_id,
            "game": game,
            "max_participants": max_participants,
            "start_time": start_time,
            "team_count": team_count,
            "players_per_team": players_per_team,
            "prize": prize,
            "participants": [],
            "teams": [],
            "brackets": [],
            "status": "recruiting",  # recruiting, team_formation, in_progress, completed
            "created_at": datetime.datetime.now().isoformat(),
            "message_id": None
        }
        
        self.active_tournaments[tournament_id] = tournament
        self.save_tournaments()
        return tournament
    
    def get_tournament(self, tournament_id):
        """Get tournament data by ID."""
        return self.active_tournaments.get(tournament_id)
    
    def get_all_tournaments(self):
        """Get all active tournaments."""
        return self.active_tournaments
    
    def delete_tournament(self, tournament_id):
        """Delete a tournament."""
        if tournament_id in self.active_tournaments:
            del self.active_tournaments[tournament_id]
            self.save_tournaments()
            return True
        return False
    
    def add_participant(self, tournament_id, user_id, username):
        """Add a participant to a tournament."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return False, "Tournament not found."
            
        if tournament["status"] != "recruiting":
            return False, "This tournament is no longer accepting participants."
            
        # Check if user is already a participant
        for participant in tournament["participants"]:
            if participant["id"] == user_id:
                return False, "You are already registered for this tournament."
                
        # Check if tournament is full
        if len(tournament["participants"]) >= tournament["max_participants"]:
            return False, "This tournament is already full."
            
        # Add the participant
        tournament["participants"].append({
            "id": user_id,
            "username": username,
            "joined_at": datetime.datetime.now().isoformat()
        })
        
        self.save_tournaments()
        return True, f"You have successfully joined the {tournament['game']} tournament!"
    
    def remove_participant(self, tournament_id, user_id):
        """Remove a participant from a tournament."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return False, "Tournament not found."
            
        if tournament["status"] != "recruiting":
            return False, "You can no longer leave this tournament."
            
        # Find and remove the participant
        for i, participant in enumerate(tournament["participants"]):
            if participant["id"] == user_id:
                tournament["participants"].pop(i)
                self.save_tournaments()
                return True, f"You have left the {tournament['game']} tournament."
                
        return False, "You are not registered for this tournament."
    
    def generate_teams(self, tournament_id):
        """Generate random teams for a tournament."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return False, "Tournament not found."
            
        if tournament["status"] != "recruiting":
            return False, "Teams have already been generated for this tournament."
            
        participants = tournament["participants"]
        team_count = tournament["team_count"]
        players_per_team = tournament["players_per_team"]
        
        # Check if we have enough participants
        if len(participants) < team_count * players_per_team:
            return False, f"Not enough participants. Need {team_count * players_per_team}, have {len(participants)}."
            
        # Shuffle participants
        random.shuffle(participants)
        
        # Create teams
        teams = []
        for i in range(team_count):
            team = {
                "id": i + 1,
                "name": f"Team {i + 1}",
                "members": participants[i * players_per_team:(i + 1) * players_per_team],
                "wins": 0,
                "losses": 0
            }
            teams.append(team)
            
        tournament["teams"] = teams
        tournament["status"] = "team_formation"
        
        self.save_tournaments()
        return True, f"Successfully generated {team_count} teams!"
    
    def generate_brackets(self, tournament_id):
        """Generate tournament brackets."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return False, "Tournament not found."
            
        if tournament["status"] not in ["team_formation", "recruiting"]:
            return False, "Brackets have already been generated for this tournament."
            
        teams = tournament["teams"]
        
        # If teams haven't been formed yet, form them now
        if not teams and tournament["status"] == "recruiting":
            success, message = self.generate_teams(tournament_id)
            if not success:
                return False, message
            teams = tournament["teams"]
        
        # Determine the number of rounds
        num_teams = len(teams)
        num_rounds = math.ceil(math.log2(num_teams))
        
        # Create initial bracket
        bracket = []
        
        # Create the first round matches
        matches = []
        team_ids = [team["id"] for team in teams]
        random.shuffle(team_ids)
        
        # If not a power of 2, some teams get a bye
        byes = 2 ** num_rounds - num_teams
        
        # Store the matchups for announcement
        first_round_matchups = []
        
        for i in range(0, num_teams - byes, 2):
            team1_id = team_ids[i]
            team2_id = team_ids[i + 1]
            
            # Store matchup info for announcement with detailed team info
            team1_info = self.get_team_info(tournament_id, team1_id)
            team2_info = self.get_team_info(tournament_id, team2_id)
            first_round_matchups.append((team1_info, team2_info))
            
            matches.append({
                "match_id": len(matches) + 1,
                "round": 1,
                "team1_id": team1_id,
                "team2_id": team2_id,
                "winner_id": None,
                "loser_id": None,
                "score": {"team1": 0, "team2": 0},
                "status": "pending"  # pending, in_progress, completed
            })
            
        # Add teams with byes directly to the next round
        for i in range(num_teams - byes, num_teams):
            bracket.append({
                "match_id": len(matches) + len(bracket) + 1,
                "round": 2,
                "team1_id": team_ids[i],
                "team2_id": None,  # Will be filled in when the previous round is completed
                "team2_from_match": None,  # Will be set when generating future rounds
                "winner_id": None,
                "loser_id": None,
                "score": {"team1": 0, "team2": 0},
                "status": "pending"
            })
        
        bracket.extend(matches)
        
        # Create the future rounds
        for round_num in range(2, num_rounds + 1):
            matches_in_round = []
            prev_round_matches = [m for m in bracket if m["round"] == round_num - 1]
            
            for i in range(0, len(prev_round_matches), 2):
                if i + 1 < len(prev_round_matches):
                    # Regular match between two winners
                    match = {
                        "match_id": len(bracket) + len(matches_in_round) + 1,
                        "round": round_num,
                        "team1_id": None,  # Will be filled in when previous matches are completed
                        "team2_id": None,
                        "team1_from_match": prev_round_matches[i]["match_id"],
                        "team2_from_match": prev_round_matches[i + 1]["match_id"],
                        "winner_id": None,
                        "loser_id": None,
                        "score": {"team1": 0, "team2": 0},
                        "status": "pending"
                    }
                    matches_in_round.append(match)
                elif i < len(prev_round_matches):
                    # Only one match in previous round, winner gets a bye
                    match = {
                        "match_id": len(bracket) + len(matches_in_round) + 1,
                        "round": round_num,
                        "team1_id": None,
                        "team2_id": None,
                        "team1_from_match": prev_round_matches[i]["match_id"],
                        "team2_from_match": None,
                        "winner_id": None,
                        "loser_id": None,
                        "score": {"team1": 0, "team2": 0},
                        "status": "pending"
                    }
                    matches_in_round.append(match)
            
            bracket.extend(matches_in_round)
        
        tournament["brackets"] = bracket
        tournament["status"] = "in_progress"
        
        # Format the first round matchups for announcement
        matchup_text = "\n".join([f"• **{team1}** vs **{team2}**" for team1, team2 in first_round_matchups])
        
        self.save_tournaments()
        return True, f"🎮 **Tournament Started!**\n\nThe {tournament['game']} tournament has officially begun!\n\n**First Round Matchups:**\n{matchup_text}\n\nBrackets have been generated with {num_rounds} rounds!"
    
    def set_match_winner(self, tournament_id, match_id, winner_id, team1_score, team2_score):
        """Set the winner for a match and update the bracket."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return False, "Tournament not found."
            
        if tournament["status"] != "in_progress":
            return False, "Tournament is not in progress."
            
        # Find the match
        match = None
        for m in tournament["brackets"]:
            if m["match_id"] == match_id:
                match = m
                break
                
        if not match:
            return False, "Match not found."
            
        if match["status"] == "completed":
            return False, "This match has already been completed."
            
        # Check if the winner is one of the teams in the match
        if winner_id != match["team1_id"] and winner_id != match["team2_id"]:
            return False, "The winner must be one of the teams in the match."
            
        loser_id = match["team2_id"] if winner_id == match["team1_id"] else match["team1_id"]
        
        # Update the match
        match["winner_id"] = winner_id
        match["loser_id"] = loser_id
        match["score"]["team1"] = team1_score
        match["score"]["team2"] = team2_score
        match["status"] = "completed"
        
        # Update team stats
        for team in tournament["teams"]:
            if team["id"] == winner_id:
                team["wins"] += 1
            elif team["id"] == loser_id:
                team["losses"] += 1
        
        # Update the next match in the bracket
        for next_match in tournament["brackets"]:
            if next_match["team1_from_match"] == match_id:
                next_match["team1_id"] = winner_id
            elif next_match["team2_from_match"] == match_id:
                next_match["team2_id"] = winner_id
                
        # Check if the tournament is completed
        final_round = max(m["round"] for m in tournament["brackets"])
        final_matches = [m for m in tournament["brackets"] if m["round"] == final_round]
        
        if all(m["status"] == "completed" for m in final_matches):
            tournament["status"] = "completed"
            
        self.save_tournaments()
        return True, f"Match {match_id} has been completed. Team {winner_id} wins!"
    
    def get_team_name(self, tournament_id, team_id):
        """Get a team's name by ID."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return f"Team {team_id}"
            
        for team in tournament["teams"]:
            if team["id"] == team_id:
                return team["name"]
                
        return f"Team {team_id}"
        
    def get_team_members(self, tournament_id, team_id):
        """Get a team's members by ID.
        
        Returns:
            list: A list of team member usernames or empty list if team not found
        """
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return []
            
        for team in tournament["teams"]:
            if team["id"] == team_id:
                return [member["username"] for member in team["members"]]
                
        return []
        
    def get_team_info(self, tournament_id, team_id):
        """Get a team's name and members as a formatted string.
        
        Returns:
            str: A formatted string with team name and members
        """
        team_name = self.get_team_name(tournament_id, team_id)
        members = self.get_team_members(tournament_id, team_id)
        
        # Get team stats if available
        tournament = self.get_tournament(tournament_id)
        wins = 0
        losses = 0
        if tournament and "teams" and team_id:
            for team in tournament["teams"]:
                if team["id"] == team_id:
                    wins = team.get("stats", {}).get("wins", 0)
                    losses = team.get("stats", {}).get("losses", 0)
                    break
        
        if not members:
            # If no members, just return team name with stats if available
            if wins > 0 or losses > 0:
                return f"{team_name} ({wins}W-{losses}L)"
            return team_name
        
        # If only one member, just show their name with the team
        if len(members) == 1:
            # Include stats if available
            if wins > 0 or losses > 0:
                return f"{team_name} ({members[0]}) ({wins}W-{losses}L)"
            return f"{team_name} ({members[0]})"
        
        # Format the member list: "Team Name (member1, member2, ...) (WW-LL)"
        members_str = ", ".join(members)
        if wins > 0 or losses > 0:
            return f"{team_name} ({members_str}) ({wins}W-{losses}L)"
        return f"{team_name} ({members_str})"
    
    def set_team_name(self, tournament_id, team_id, team_name):
        """Set a team's name."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return False, "Tournament not found."
            
        if tournament["status"] not in ["team_formation", "in_progress"]:
            return False, "Team names can only be set during team formation or while the tournament is in progress."
            
        # Find and update the team
        for team in tournament["teams"]:
            if team["id"] == team_id:
                team["name"] = team_name
                self.save_tournaments()
                return True, f"Team {team_id} has been renamed to '{team_name}'."
                
        return False, f"Team {team_id} not found."
    
    def create_game_vote(self, vote_id, channel_id, creator_id, games, duration_hours):
        """Create a new game vote for tournaments."""
        end_time = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
        
        vote = {
            "id": vote_id,
            "channel_id": channel_id,
            "creator_id": creator_id,
            "games": [{"name": game, "votes": 0} for game in games],
            "voters": {},
            "end_time": end_time.isoformat(),
            "status": "active",
            "message_id": None
        }
        
        self.game_votes[vote_id] = vote
        self.save_game_votes()
        return vote
    
    def get_game_vote(self, vote_id):
        """Get a game vote by ID."""
        return self.game_votes.get(vote_id)
    
    def vote_for_game(self, vote_id, user_id, game_index):
        """Record a user's vote for a game."""
        vote = self.get_game_vote(vote_id)
        if not vote:
            return False, "Vote not found."
            
        if vote["status"] != "active":
            return False, "This vote has ended."
            
        if game_index < 0 or game_index >= len(vote["games"]):
            return False, "Invalid game selection."
            
        # Remove previous vote if user already voted
        if user_id in vote["voters"]:
            prev_index = vote["voters"][user_id]
            vote["games"][prev_index]["votes"] -= 1
            
        # Add new vote
        vote["games"][game_index]["votes"] += 1
        vote["voters"][user_id] = game_index
        
        self.save_game_votes()
        return True, f"You voted for {vote['games'][game_index]['name']}!"
    
    def end_game_vote(self, vote_id):
        """End a game vote and determine the winner."""
        vote = self.get_game_vote(vote_id)
        if not vote:
            return False, "Vote not found."
            
        if vote["status"] != "active":
            return False, "This vote has already ended."
            
        # Find the game with the most votes
        max_votes = -1
        winners = []
        
        for game in vote["games"]:
            if game["votes"] > max_votes:
                max_votes = game["votes"]
                winners = [game]
            elif game["votes"] == max_votes:
                winners.append(game)
                
        # Select a random winner if there's a tie
        winner = random.choice(winners)
        
        vote["status"] = "completed"
        vote["winner"] = winner["name"]
        
        self.save_game_votes()
        return True, f"The vote has ended! {winner['name']} won with {winner['votes']} votes."
    
    def check_expired_votes(self):
        """Check for expired game votes and end them."""
        now = datetime.datetime.now()
        
        for vote_id, vote in list(self.game_votes.items()):
            if vote["status"] == "active":
                end_time = datetime.datetime.fromisoformat(vote["end_time"])
                if now > end_time:
                    self.end_game_vote(vote_id)
                    logger.info(f"Game vote {vote_id} automatically ended due to expiration")

class TournamentCog(commands.Cog):
    """Commands for the tournament system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.tournament_manager = TournamentManager(bot)
        self.check_votes_task = None
        
    async def cog_load(self):
        """Called when the cog is loaded."""
        # We'll start the task in the on_ready event instead
        pass
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready."""
        # Start the periodic task to check for expired votes
        self.check_votes_task = self.bot.loop.create_task(self.check_expired_votes())
        
    async def cog_unload(self):
        """Called when the cog is unloaded."""
        # Cancel the periodic task
        if self.check_votes_task:
            self.check_votes_task.cancel()
            
    async def check_expired_votes(self):
        """Periodic task to check for expired game votes."""
        try:
            while not self.bot.is_closed():
                self.tournament_manager.check_expired_votes()
                await asyncio.sleep(60)  # Check every minute
        except asyncio.CancelledError:
            # Task was cancelled; clean up
            pass
        except Exception as e:
            logger.error(f"Error in check_expired_votes task: {e}", exc_info=True)
    
    @app_commands.command(
        name="createtournament",
        description="🏆 Create a new tournament (Admin only)"
    )
    @app_commands.describe(
        game="The game for the tournament",
        max_participants="Maximum number of participants",
        start_delay="When the tournament will start (e.g., 30 minutes, 2 hours, 1 day)",
        time_unit="Time unit for delay (min/hour/day)",
        team_count="Number of teams",
        players_per_team="Number of players per team",
        prize="The prize for the tournament"
    )
    @app_commands.choices(
        time_unit=[
            app_commands.Choice(name="Minutes", value="min"),
            app_commands.Choice(name="Hours", value="hour"),
            app_commands.Choice(name="Days", value="day")
        ]
    )
    async def createtournament(self, interaction: discord.Interaction, game: str, 
                            max_participants: int, start_delay: int, time_unit: str, 
                            team_count: int, players_per_team: int, prize: str):
        """Create a new tournament."""
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
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Calculate start time based on delay and unit
            now = datetime.datetime.now()
            
            if time_unit == "min":
                start_datetime = now + datetime.timedelta(minutes=start_delay)
            elif time_unit == "hour":
                start_datetime = now + datetime.timedelta(hours=start_delay)
            elif time_unit == "day":
                start_datetime = now + datetime.timedelta(days=start_delay)
            else:
                await interaction.followup.send(
                    "Invalid time unit. Please use min, hour, or day.",
                    ephemeral=True
                )
                return
                
            if max_participants <= 0:
                await interaction.followup.send(
                    "Maximum participants must be greater than 0.",
                    ephemeral=True
                )
                return
                
            if team_count <= 0:
                await interaction.followup.send(
                    "Team count must be greater than 0.",
                    ephemeral=True
                )
                return
                
            if players_per_team <= 0:
                await interaction.followup.send(
                    "Players per team must be greater than 0.",
                    ephemeral=True
                )
                return
                
            if team_count * players_per_team > max_participants:
                await interaction.followup.send(
                    f"Team configuration requires {team_count * players_per_team} players, but maximum participants is set to {max_participants}.",
                    ephemeral=True
                )
                return
            
            # Create the tournament with a short random ID (ensure uniqueness)
            tournament_id = generate_random_id(5)
            # Check if ID already exists, generate a new one if needed
            while tournament_id in self.tournament_manager.get_all_tournaments():
                tournament_id = generate_random_id(5)
                
            tournament = self.tournament_manager.create_tournament(
                tournament_id=tournament_id,
                channel_id=str(interaction.channel_id),
                creator_id=str(interaction.user.id),
                game=game,
                max_participants=max_participants,
                start_time=start_datetime.isoformat(),
                team_count=team_count,
                players_per_team=players_per_team,
                prize=prize
            )
            
            # Create an embed for the tournament
            embed = discord.Embed(
                title=f"🏆 {game} Tournament",
                description=f"A new tournament has been created! Join now to participate!",
                color=0x5865F2,
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="📅 Start Time", value=f"<t:{int(start_datetime.timestamp())}:F>", inline=False)
            embed.add_field(name="👥 Max Participants", value=f"{max_participants}", inline=True)
            embed.add_field(name="🏅 Prize", value=prize, inline=True)
            embed.add_field(name="🎮 Game", value=game, inline=True)
            embed.add_field(name="👪 Teams", value=f"{team_count} teams with {players_per_team} players each", inline=False)
            embed.add_field(name="👤 Registered", value="0/" + str(max_participants), inline=True)
            
            # Add footer with tournament ID
            embed.set_footer(text=f"Tournament ID: {tournament_id}")
            
            # Create view with join button
            view = TournamentJoinView(self.tournament_manager, tournament_id)
            
            # Send the message
            response = await interaction.channel.send(embed=embed, view=view)
            
            # Save the message ID in the tournament data
            tournament["message_id"] = str(response.id)
            self.tournament_manager.save_tournaments()
            
            await interaction.followup.send(
                f"Tournament created successfully! Players can now register via the join button.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating tournament: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while creating the tournament. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="tournament",
        description="🏆 View tournament details"
    )
    @app_commands.describe(
        tournament_id="ID of the tournament (leave empty to see active tournaments)"
    )
    async def tournament(self, interaction: discord.Interaction, tournament_id: str = None):
        """View tournament details."""
        await interaction.response.defer(ephemeral=False)
        
        try:
            if tournament_id:
                # Show details for a specific tournament
                tournament = self.tournament_manager.get_tournament(tournament_id)
                if not tournament:
                    await interaction.followup.send(
                        "Tournament not found. Please check the ID and try again.",
                        ephemeral=True
                    )
                    return
                    
                embed = self.create_tournament_embed(tournament)
                
                # If tournament is in recruiting phase, add join button
                view = None
                if tournament["status"] == "recruiting":
                    view = TournamentJoinView(self.tournament_manager, tournament_id)
                elif tournament["status"] in ["team_formation", "in_progress"]:
                    view = TournamentDetailsView(self.tournament_manager, tournament_id)
                
                await interaction.followup.send(embed=embed, view=view)
            else:
                # Show list of active tournaments
                tournaments = self.tournament_manager.get_all_tournaments()
                
                if not tournaments:
                    await interaction.followup.send(
                        "There are no active tournaments at the moment.",
                        ephemeral=False
                    )
                    return
                    
                embed = discord.Embed(
                    title="🏆 Active Tournaments",
                    description="Here's a list of all active tournaments:",
                    color=0x5865F2,
                    timestamp=datetime.datetime.now()
                )
                
                for tournament_id, tournament in tournaments.items():
                    status_emoji = "🔄"
                    if tournament["status"] == "recruiting":
                        status_emoji = "📝"
                    elif tournament["status"] == "team_formation":
                        status_emoji = "👥"
                    elif tournament["status"] == "in_progress":
                        status_emoji = "⚔️"
                    elif tournament["status"] == "completed":
                        status_emoji = "✅"
                        
                    start_time = datetime.datetime.fromisoformat(tournament["start_time"])
                    
                    embed.add_field(
                        name=f"{status_emoji} {tournament['game']} Tournament",
                        value=f"**Start Time:** <t:{int(start_time.timestamp())}:R>\n"
                             f"**Status:** {tournament['status'].replace('_', ' ').title()}\n"
                             f"**Participants:** {len(tournament['participants'])}/{tournament['max_participants']}\n"
                             f"**ID:** `{tournament_id}`\n"
                             f"Use `/tournament {tournament_id}` for details",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error viewing tournament: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while retrieving tournament information. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="managetournament",
        description="🏆 Manage a tournament (Admin only)"
    )
    @app_commands.describe(
        tournament_id="ID of the tournament to manage"
    )
    async def managetournament(self, interaction: discord.Interaction, tournament_id: str):
        """Manage a tournament."""
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
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the tournament
            tournament = self.tournament_manager.get_tournament(tournament_id)
            if not tournament:
                await interaction.followup.send(
                    "Tournament not found. Please check the ID and try again.",
                    ephemeral=True
                )
                return
                
            # Create management view
            view = TournamentManagementView(self.tournament_manager, tournament_id)
            
            # Create embed
            embed = discord.Embed(
                title=f"🔧 Tournament Management",
                description=f"Manage the {tournament['game']} tournament.",
                color=0x5865F2,
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="ID", value=tournament_id, inline=False)
            embed.add_field(name="Status", value=tournament["status"].replace("_", " ").title(), inline=True)
            embed.add_field(name="Participants", value=f"{len(tournament['participants'])}/{tournament['max_participants']}", inline=True)
            
            if tournament["status"] in ["team_formation", "in_progress", "completed"]:
                embed.add_field(name="Teams", value=f"{len(tournament['teams'])}", inline=True)
                
            if tournament["status"] in ["in_progress", "completed"]:
                embed.add_field(name="Matches", value=f"{len(tournament['brackets'])}", inline=True)
                
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error managing tournament: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while managing the tournament. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="jointournament",
        description="🏆 Join a tournament"
    )
    @app_commands.describe(
        tournament_id="ID of the tournament to join"
    )
    async def jointournament(self, interaction: discord.Interaction, tournament_id: str):
        """Join a tournament."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            
            success, message = self.tournament_manager.add_participant(tournament_id, user_id, username)
            
            if success:
                # Update the tournament message if it exists
                tournament = self.tournament_manager.get_tournament(tournament_id)
                if tournament and tournament["message_id"]:
                    try:
                        channel = self.bot.get_channel(int(tournament["channel_id"]))
                        if channel:
                            message_id = int(tournament["message_id"])
                            message = await channel.fetch_message(message_id)
                            
                            # Update the embed
                            embed = message.embeds[0]
                            for i, field in enumerate(embed.fields):
                                if field.name == "👤 Registered":
                                    embed.set_field_at(
                                        i, 
                                        name="👤 Registered", 
                                        value=f"{len(tournament['participants'])}/{tournament['max_participants']}",
                                        inline=True
                                    )
                                    break
                                    
                            await message.edit(embed=embed)
                    except Exception as e:
                        logger.error(f"Error updating tournament message: {e}", exc_info=True)
                
                await interaction.followup.send(
                    f"✅ {message}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ {message}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error joining tournament: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while joining the tournament. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="leavetournament",
        description="🏆 Leave a tournament"
    )
    @app_commands.describe(
        tournament_id="ID of the tournament to leave"
    )
    async def leavetournament(self, interaction: discord.Interaction, tournament_id: str):
        """Leave a tournament."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            
            success, message = self.tournament_manager.remove_participant(tournament_id, user_id)
            
            if success:
                # Update the tournament message if it exists
                tournament = self.tournament_manager.get_tournament(tournament_id)
                if tournament and tournament["message_id"]:
                    try:
                        channel = self.bot.get_channel(int(tournament["channel_id"]))
                        if channel:
                            message_id = int(tournament["message_id"])
                            message = await channel.fetch_message(message_id)
                            
                            # Update the embed
                            embed = message.embeds[0]
                            for i, field in enumerate(embed.fields):
                                if field.name == "👤 Registered":
                                    embed.set_field_at(
                                        i, 
                                        name="👤 Registered", 
                                        value=f"{len(tournament['participants'])}/{tournament['max_participants']}",
                                        inline=True
                                    )
                                    break
                                    
                            await message.edit(embed=embed)
                    except Exception as e:
                        logger.error(f"Error updating tournament message: {e}", exc_info=True)
                
                await interaction.followup.send(
                    f"✅ {message}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ {message}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error leaving tournament: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while leaving the tournament. Please try again later.",
                ephemeral=True
            )
    
    # The creategamevote command has been removed and consolidated into the global /gamevote command
    
    def create_tournament_embed(self, tournament):
        """Create an embed for a tournament."""
        status_map = {
            "recruiting": "📝 Recruiting",
            "team_formation": "👥 Team Formation",
            "in_progress": "⚔️ In Progress",
            "completed": "✅ Completed"
        }
        
        status_emoji = status_map.get(tournament["status"], "🔄")
        
        embed = discord.Embed(
            title=f"🏆 {tournament['game']} Tournament",
            description=f"Tournament details and information",
            color=0x5865F2,
            timestamp=datetime.datetime.now()
        )
        
        start_time = datetime.datetime.fromisoformat(tournament["start_time"])
        embed.add_field(name="📅 Start Time", value=f"<t:{int(start_time.timestamp())}:F>", inline=False)
        embed.add_field(name="🏅 Prize", value=tournament["prize"], inline=True)
        embed.add_field(name="🎮 Game", value=tournament["game"], inline=True)
        embed.add_field(name="📊 Status", value=f"{status_emoji} {tournament['status'].replace('_', ' ').title()}", inline=True)
        
        embed.add_field(name="👥 Teams", value=f"{tournament['team_count']} teams with {tournament['players_per_team']} players each", inline=False)
        embed.add_field(name="👤 Registered", value=f"{len(tournament['participants'])}/{tournament['max_participants']}", inline=True)
        
        # If in team formation or later, show teams
        if tournament["status"] in ["team_formation", "in_progress", "completed"] and tournament["teams"]:
            teams_text = ""
            for team in tournament["teams"]:
                teams_text += f"**{team['name']}** ({len(team['members'])} members)\n"
                
            if len(teams_text) > 1024:
                teams_text = teams_text[:1021] + "..."
                
            embed.add_field(name="🏅 Teams", value=teams_text, inline=False)
            
        # If in progress or completed, show bracket information
        if tournament["status"] in ["in_progress", "completed"] and tournament["brackets"]:
            rounds = {}
            for match in tournament["brackets"]:
                round_num = match["round"]
                if round_num not in rounds:
                    rounds[round_num] = []
                rounds[round_num].append(match)
                
            for round_num, matches in sorted(rounds.items()):
                round_text = ""
                for match in matches:
                    if match["status"] == "pending":
                        if match["team1_id"] and match["team2_id"]:
                            team1_name = self.tournament_manager.get_team_name(tournament["id"], match["team1_id"])
                            team2_name = self.tournament_manager.get_team_name(tournament["id"], match["team2_id"])
                            round_text += f"Match {match['match_id']}: {team1_name} vs {team2_name} (Pending)\n"
                        else:
                            round_text += f"Match {match['match_id']}: TBD vs TBD (Pending)\n"
                    elif match["status"] == "completed":
                        team1_name = self.tournament_manager.get_team_name(tournament["id"], match["team1_id"])
                        team2_name = self.tournament_manager.get_team_name(tournament["id"], match["team2_id"])
                        winner_name = self.tournament_manager.get_team_name(tournament["id"], match["winner_id"])
                        round_text += f"Match {match['match_id']}: {team1_name} vs {team2_name} (Winner: {winner_name})\n"
                        
                if round_text:
                    if len(round_text) > 1024:
                        round_text = round_text[:1021] + "..."
                        
                    embed.add_field(name=f"📊 Round {round_num}", value=round_text, inline=False)
            
        # Add footer with tournament ID
        embed.set_footer(text=f"Tournament ID: {tournament['id']}")
        
        return embed

class TournamentJoinView(discord.ui.View):
    """View with join button for tournaments."""
    
    def __init__(self, tournament_manager, tournament_id):
        super().__init__(timeout=None)
        self.tournament_manager = tournament_manager
        self.tournament_id = tournament_id
        
        # Add join button
        join_button = discord.ui.Button(
            label="Join Tournament",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id=f"join_tournament_{tournament_id}"
        )
        join_button.callback = self.join_callback
        self.add_item(join_button)
        
        # Add leave button
        leave_button = discord.ui.Button(
            label="Leave Tournament",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id=f"leave_tournament_{tournament_id}"
        )
        leave_button.callback = self.leave_callback
        self.add_item(leave_button)
        
    async def join_callback(self, interaction: discord.Interaction):
        """Called when the join button is clicked."""
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        
        success, message = self.tournament_manager.add_participant(self.tournament_id, user_id, username)
        
        if success:
            # Update the embed
            tournament = self.tournament_manager.get_tournament(self.tournament_id)
            embed = interaction.message.embeds[0]
            
            for i, field in enumerate(embed.fields):
                if field.name == "👤 Registered":
                    embed.set_field_at(
                        i, 
                        name="👤 Registered", 
                        value=f"{len(tournament['participants'])}/{tournament['max_participants']}",
                        inline=True
                    )
                    break
                    
            await interaction.message.edit(embed=embed)
            
            await interaction.response.send_message(
                f"✅ {message}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {message}",
                ephemeral=True
            )
            
    async def leave_callback(self, interaction: discord.Interaction):
        """Called when the leave button is clicked."""
        user_id = str(interaction.user.id)
        
        success, message = self.tournament_manager.remove_participant(self.tournament_id, user_id)
        
        if success:
            # Update the embed
            tournament = self.tournament_manager.get_tournament(self.tournament_id)
            embed = interaction.message.embeds[0]
            
            for i, field in enumerate(embed.fields):
                if field.name == "👤 Registered":
                    embed.set_field_at(
                        i, 
                        name="👤 Registered", 
                        value=f"{len(tournament['participants'])}/{tournament['max_participants']}",
                        inline=True
                    )
                    break
                    
            await interaction.message.edit(embed=embed)
            
            await interaction.response.send_message(
                f"✅ {message}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {message}",
                ephemeral=True
            )

class TournamentDetailsView(discord.ui.View):
    """View with buttons to show tournament details."""
    
    def __init__(self, tournament_manager, tournament_id):
        super().__init__(timeout=None)
        self.tournament_manager = tournament_manager
        self.tournament_id = tournament_id
        
        # Add teams button
        teams_button = discord.ui.Button(
            label="View Teams",
            style=discord.ButtonStyle.primary,
            emoji="👥",
            custom_id=f"view_teams_{tournament_id}"
        )
        teams_button.callback = self.teams_callback
        self.add_item(teams_button)
        
        # Add brackets button if tournament has brackets
        tournament = tournament_manager.get_tournament(tournament_id)
        if tournament and tournament["status"] in ["in_progress", "completed"] and tournament["brackets"]:
            brackets_button = discord.ui.Button(
                label="View Brackets",
                style=discord.ButtonStyle.primary,
                emoji="📊",
                custom_id=f"view_brackets_{tournament_id}"
            )
            brackets_button.callback = self.brackets_callback
            self.add_item(brackets_button)
            
    async def teams_callback(self, interaction: discord.Interaction):
        """Called when the teams button is clicked."""
        tournament = self.tournament_manager.get_tournament(self.tournament_id)
        
        if not tournament:
            await interaction.response.send_message(
                "Tournament not found. It may have been deleted.",
                ephemeral=True
            )
            return
            
        if not tournament["teams"]:
            await interaction.response.send_message(
                "Teams have not been formed for this tournament yet.",
                ephemeral=True
            )
            return
            
        embed = discord.Embed(
            title=f"👥 Tournament Teams",
            description=f"Teams for the {tournament['game']} tournament",
            color=0x5865F2,
            timestamp=datetime.datetime.now()
        )
        
        for team in tournament["teams"]:
            # Show team stats
            team_header = f"Team {team['id']}: {team['name']}"
            if "wins" in team and "losses" in team:
                team_header += f" (Wins: {team['wins']}, Losses: {team['losses']})"
            
            # List all team members with clearer formatting
            members_text = ""
            for i, member in enumerate(team["members"], 1):
                members_text += f"{i}. **{member['username']}** (ID: {member['id']})\n"
                
            embed.add_field(
                name=team_header,
                value=members_text or "No members",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    async def brackets_callback(self, interaction: discord.Interaction):
        """Called when the brackets button is clicked."""
        try:
            tournament = self.tournament_manager.get_tournament(self.tournament_id)
            
            if not tournament:
                await interaction.response.send_message(
                    "❌ Tournament not found. It may have been deleted.",
                    ephemeral=True
                )
                return
                
            if not tournament["brackets"]:
                await interaction.response.send_message(
                    "❌ Brackets have not been generated for this tournament yet.",
                    ephemeral=True
                )
                return
                
            rounds = {}
            for match in tournament["brackets"]:
                round_num = match["round"]
                if round_num not in rounds:
                    rounds[round_num] = []
                rounds[round_num].append(match)
                
            embed = discord.Embed(
                title=f"🏆 {tournament['game']} Tournament Brackets",
                description=f"**Tournament Status: {tournament['status'].replace('_', ' ').title()}**\n\nView all matchups and results for this tournament.\nID: `{tournament['id']}`",
                color=0x5865F2,
                timestamp=datetime.datetime.now()
            )
            
            # Sort the matches by ID within each round for consistent display
            for round_num in rounds:
                rounds[round_num].sort(key=lambda x: x["match_id"])
            
            # Process each round of the tournament
            for round_num, matches in sorted(rounds.items()):
                round_text = ""
                
                # Different visuals depending on round number
                round_emoji = "🎮"
                if round_num == 1:
                    round_emoji = "🥇"
                elif round_num == max(rounds.keys()):
                    if round_num == 2:
                        round_emoji = "🏆"  # Finals
                    elif round_num == 3:
                        round_emoji = "💎"  # Semifinals + Finals
                
                for match in matches:
                    match_id = match['match_id']
                    
                    if match["status"] == "pending":
                        team1_info = "TBD"
                        team2_info = "TBD"
                        
                        if match["team1_id"]:
                            team1_info = self.tournament_manager.get_team_info(tournament["id"], match["team1_id"])
                        if match["team2_id"]:
                            team2_info = self.tournament_manager.get_team_info(tournament["id"], match["team2_id"])
                        
                        # Visual divider for the matchup
                        divider = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
                        
                        # Enhanced display for matchups with team members and stats
                        if team1_info != "TBD" and team2_info != "TBD":
                            round_text += f"**Match {match_id}**\n"
                            round_text += f"🔵 **{team1_info}**\n"
                            round_text += f"🆚\n"
                            round_text += f"🔴 **{team2_info}**\n"
                            round_text += f"{divider}\n"
                        else:
                            if team1_info == "TBD" and team2_info == "TBD":
                                round_text += f"**Match {match_id}:** ⏳ Waiting for qualifiers\n"
                                round_text += f"{divider}\n"
                            else:
                                waiting_text = "Waiting for opponent"
                                round_text += f"**Match {match_id}**\n"
                                if team1_info != "TBD":
                                    round_text += f"🔵 **{team1_info}**\n"
                                    round_text += f"🆚\n"
                                    round_text += f"⏳ {waiting_text}\n"
                                else:
                                    round_text += f"⏳ {waiting_text}\n"
                                    round_text += f"🆚\n"
                                    round_text += f"🔴 **{team2_info}**\n"
                                round_text += f"{divider}\n"
                            
                    elif match["status"] == "completed":
                        team1_info = self.tournament_manager.get_team_info(tournament["id"], match["team1_id"])
                        team2_info = self.tournament_manager.get_team_info(tournament["id"], match["team2_id"])
                        
                        score1 = match["score"]["team1"]
                        score2 = match["score"]["team2"]
                        
                        # Visual divider for the matchup
                        divider = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
                        
                        # Show match with detailed scores and a trophy for the winner
                        round_text += f"**Match {match_id} (Completed)**\n"
                        
                        if match["winner_id"] == match["team1_id"]:
                            round_text += f"🏆 **{team1_info}** Score: **{score1}**\n"
                            round_text += f"🆚\n"
                            round_text += f"❌ {team2_info} Score: {score2}\n"
                        else:
                            round_text += f"❌ {team1_info} Score: {score1}\n"
                            round_text += f"🆚\n"
                            round_text += f"🏆 **{team2_info}** Score: **{score2}**\n"
                        
                        round_text += f"{divider}\n"
                
                if round_text:
                    if len(round_text) > 1024:
                        # If too long, make a summary
                        matches_count = len(matches)
                        completed = sum(1 for m in matches if m["status"] == "completed")
                        round_text = f"This round has {matches_count} matches ({completed} completed).\nToo many details to display - use `/tournament {tournament['id']}` for more information."
                    
                    # Add round header with appropriate emoji
                    if round_num == 1:
                        round_header = f"{round_emoji} First Round"
                    elif round_num == max(rounds.keys()):
                        if max(rounds.keys()) == 2:
                            round_header = f"{round_emoji} Finals"
                        else:
                            round_header = f"{round_emoji} Finals (Round {round_num})"
                    elif round_num == max(rounds.keys()) - 1:
                        round_header = f"{round_emoji} Semi-Finals (Round {round_num})"
                    else:
                        round_header = f"{round_emoji} Round {round_num}"
                        
                    embed.add_field(name=round_header, value=round_text, inline=False)
            
            # Add tournament info footer    
            embed.set_footer(text=f"Tournament ID: {tournament['id']} | Created by: {tournament.get('creator_username', 'Admin')}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error displaying brackets: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An error occurred while displaying the brackets: {str(e)}",
                ephemeral=True
            )

class TournamentManagementView(discord.ui.View):
    """View for tournament management."""
    
    def __init__(self, tournament_manager, tournament_id):
        super().__init__(timeout=None)
        self.tournament_manager = tournament_manager
        self.tournament_id = tournament_id
        
        tournament = tournament_manager.get_tournament(tournament_id)
        
        # Add view participants button (available for all tournament states)
        participants_button = discord.ui.Button(
            label="View Participants",
            style=discord.ButtonStyle.secondary,
            emoji="👪",
            custom_id=f"view_participants_{tournament_id}"
        )
        participants_button.callback = self.participants_callback
        self.add_item(participants_button)
        
        if tournament["status"] == "recruiting":
            # Add form teams button
            form_teams_button = discord.ui.Button(
                label="Form Teams",
                style=discord.ButtonStyle.primary,
                emoji="👥",
                custom_id=f"form_teams_{tournament_id}"
            )
            form_teams_button.callback = self.form_teams_callback
            self.add_item(form_teams_button)
            
        if tournament["status"] in ["recruiting", "team_formation"]:
            # Add generate brackets button
            generate_brackets_button = discord.ui.Button(
                label="Generate Brackets",
                style=discord.ButtonStyle.primary,
                emoji="📊",
                custom_id=f"generate_brackets_{tournament_id}"
            )
            generate_brackets_button.callback = self.generate_brackets_callback
            self.add_item(generate_brackets_button)
            
        if tournament["status"] in ["team_formation", "in_progress"]:
            # Add rename team button
            rename_team_button = discord.ui.Button(
                label="Rename Team",
                style=discord.ButtonStyle.secondary,
                emoji="✏️",
                custom_id=f"rename_team_{tournament_id}"
            )
            rename_team_button.callback = self.rename_team_callback
            self.add_item(rename_team_button)
            
        if tournament["status"] == "in_progress":
            # Add update match button
            update_match_button = discord.ui.Button(
                label="Update Match",
                style=discord.ButtonStyle.secondary,
                emoji="⚔️",
                custom_id=f"update_match_{tournament_id}"
            )
            update_match_button.callback = self.update_match_callback
            self.add_item(update_match_button)
            
        # Add delete tournament button
        delete_button = discord.ui.Button(
            label="Delete Tournament",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            custom_id=f"delete_tournament_{tournament_id}"
        )
        delete_button.callback = self.delete_callback
        self.add_item(delete_button)
        
    async def form_teams_callback(self, interaction: discord.Interaction):
        """Called when the form teams button is clicked."""
        success, message = self.tournament_manager.generate_teams(self.tournament_id)
        
        if success:
            await interaction.response.send_message(
                f"✅ {message} You can now proceed to generate brackets.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {message}",
                ephemeral=True
            )
            
    async def generate_brackets_callback(self, interaction: discord.Interaction):
        """Called when the generate brackets button is clicked."""
        try:
            success, message = self.tournament_manager.generate_brackets(self.tournament_id)
            
            if success:
                # First notify the admin privately
                await interaction.response.send_message(
                    f"✅ Tournament started successfully! Brackets have been generated.",
                    ephemeral=True
                )
                
                # Then post the announcement to the channel so everyone can see
                tournament = self.tournament_manager.get_tournament(self.tournament_id)
                if tournament:
                    # Find the channel where to post the announcement
                    channel_id = int(tournament.get("channel_id", 0))
                    channel = interaction.guild.get_channel(channel_id) if channel_id else interaction.channel
                    
                    if not channel and interaction.guild:
                        # If channel not found or not specified, use the current channel
                        channel = interaction.channel
                    
                    # Create an embed for the tournament start announcement
                    embed = discord.Embed(
                        title=f"🎮 {tournament['game']} Tournament Has Started!",
                        description=message,
                        color=0x00FF00,
                        timestamp=datetime.datetime.now()
                    )
                    
                    # Add team information to the announcement
                    if tournament["teams"]:
                        teams_info = ""
                        for team in tournament["teams"]:
                            member_names = [f"<@{member['id']}>" for member in team["members"]]
                            teams_info += f"**Team {team['id']}: {team['name']}**\n"
                            teams_info += f"Members: {', '.join(member_names)}\n\n"
                        
                        if teams_info:
                            embed.add_field(name="🏆 Teams", value=teams_info, inline=False)
                    
                    embed.set_footer(text=f"Tournament ID: {self.tournament_id}")
                    
                    # Post public announcement if channel is available
                    if channel:
                        await channel.send(embed=embed)
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
        except Exception as e:
            # Handle errors that might occur
            logger.error(f"Error generating brackets: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An error occurred while generating brackets: {str(e)}",
                ephemeral=True
            )
            
    async def rename_team_callback(self, interaction: discord.Interaction):
        """Called when the rename team button is clicked."""
        # Create modal for team renaming
        await interaction.response.send_modal(TeamRenameModal(self.tournament_manager, self.tournament_id))
            
    async def update_match_callback(self, interaction: discord.Interaction):
        """Called when the update match button is clicked."""
        # Create modal for match updating
        await interaction.response.send_modal(MatchUpdateModal(self.tournament_manager, self.tournament_id))
            
    async def participants_callback(self, interaction: discord.Interaction):
        """Called when the view participants button is clicked."""
        tournament = self.tournament_manager.get_tournament(self.tournament_id)
        
        if not tournament:
            await interaction.response.send_message(
                "❌ Tournament not found. It may have been deleted.",
                ephemeral=True
            )
            return
            
        participants = tournament["participants"]
        
        if not participants:
            await interaction.response.send_message(
                "❌ This tournament has no participants yet.",
                ephemeral=True
            )
            return
            
        # Create embed to display participants
        embed = discord.Embed(
            title="👪 Tournament Participants",
            description=f"All participants registered for the {tournament['game']} tournament",
            color=0x5865F2,
            timestamp=datetime.datetime.now()
        )
        
        # Add fields for tournament info
        embed.add_field(
            name="Tournament ID", 
            value=self.tournament_id, 
            inline=True
        )
        embed.add_field(
            name="Participants", 
            value=f"{len(participants)}/{tournament['max_participants']}", 
            inline=True
        )
        embed.add_field(
            name="Status", 
            value=tournament["status"].replace("_", " ").title(), 
            inline=True
        )
        
        # Sort participants by join date
        sorted_participants = sorted(participants, key=lambda p: p["joined_at"])
        
        # Create a formatted list of participants
        participants_text = ""
        for i, participant in enumerate(sorted_participants, 1):
            join_time = datetime.datetime.fromisoformat(participant["joined_at"])
            participants_text += f"{i}. **{participant['username']}** (ID: {participant['id']})\n"
            participants_text += f"   Joined: <t:{int(join_time.timestamp())}:R>\n"
            
            # Split into multiple fields if the list gets too long
            if i % 10 == 0 or i == len(sorted_participants):
                embed.add_field(
                    name=f"Participants {i-9}-{i}" if i % 10 == 0 else f"Participants {i-(i%10)+1}-{i}",
                    value=participants_text,
                    inline=False
                )
                participants_text = ""
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    async def delete_callback(self, interaction: discord.Interaction):
        """Called when the delete button is clicked."""
        # Create confirmation view
        view = TournamentDeleteConfirmView(self.tournament_manager, self.tournament_id)
        
        embed = discord.Embed(
            title="⚠️ Delete Tournament",
            description=f"Are you sure you want to delete this tournament? This action cannot be undone.",
            color=0xE74C3C,
            timestamp=datetime.datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class TeamRenameModal(discord.ui.Modal):
    """Modal for renaming a team."""
    
    team_id = discord.ui.TextInput(
        label="Team ID",
        placeholder="Enter the team ID",
        required=True,
        min_length=1,
        max_length=5
    )
    
    new_name = discord.ui.TextInput(
        label="New Team Name",
        placeholder="Enter the new team name",
        required=True,
        min_length=1,
        max_length=30
    )
    
    def __init__(self, tournament_manager, tournament_id):
        super().__init__()
        self.tournament_manager = tournament_manager
        self.tournament_id = tournament_id
        
    async def on_submit(self, interaction: discord.Interaction):
        """Called when the form is submitted."""
        try:
            team_id = int(self.team_id.value)
            new_name = self.new_name.value
            
            success, message = self.tournament_manager.set_team_name(self.tournament_id, team_id, new_name)
            
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
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid team ID. Please enter a valid number.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error renaming team: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while renaming the team. Please try again later.",
                ephemeral=True
            )

class MatchUpdateModal(discord.ui.Modal):
    """Modal for updating a match."""
    
    match_id = discord.ui.TextInput(
        label="Match ID",
        placeholder="Enter the match ID",
        required=True,
        min_length=1,
        max_length=5
    )
    
    winner_id = discord.ui.TextInput(
        label="Winner Team ID",
        placeholder="Enter the ID of the winning team",
        required=True,
        min_length=1,
        max_length=5
    )
    
    team1_score = discord.ui.TextInput(
        label="Team 1 Score",
        placeholder="Enter the score for team 1",
        required=True,
        min_length=1,
        max_length=5
    )
    
    team2_score = discord.ui.TextInput(
        label="Team 2 Score",
        placeholder="Enter the score for team 2",
        required=True,
        min_length=1,
        max_length=5
    )
    
    def __init__(self, tournament_manager, tournament_id):
        super().__init__()
        self.tournament_manager = tournament_manager
        self.tournament_id = tournament_id
        
    async def on_submit(self, interaction: discord.Interaction):
        """Called when the form is submitted."""
        try:
            match_id = int(self.match_id.value)
            winner_id = int(self.winner_id.value)
            team1_score = int(self.team1_score.value)
            team2_score = int(self.team2_score.value)
            
            success, message = self.tournament_manager.set_match_winner(
                self.tournament_id, match_id, winner_id, team1_score, team2_score
            )
            
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
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid input. Please enter valid numbers for all fields.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error updating match: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while updating the match. Please try again later.",
                ephemeral=True
            )

class TournamentDeleteConfirmView(discord.ui.View):
    """View for confirming tournament deletion."""
    
    def __init__(self, tournament_manager, tournament_id):
        super().__init__(timeout=None)
        self.tournament_manager = tournament_manager
        self.tournament_id = tournament_id
        
        # Add confirm button
        confirm_button = discord.ui.Button(
            label="Confirm Delete",
            style=discord.ButtonStyle.danger,
            emoji="✅",
            custom_id=f"confirm_delete_{tournament_id}"
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)
        
        # Add cancel button
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            emoji="❌",
            custom_id=f"cancel_delete_{tournament_id}"
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
        
    async def confirm_callback(self, interaction: discord.Interaction):
        """Called when the confirm button is clicked."""
        success = self.tournament_manager.delete_tournament(self.tournament_id)
        
        if success:
            await interaction.response.send_message(
                "✅ Tournament deleted successfully.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to delete tournament. It may have already been deleted.",
                ephemeral=True
            )
            
    async def cancel_callback(self, interaction: discord.Interaction):
        """Called when the cancel button is clicked."""
        await interaction.response.send_message(
            "❌ Tournament deletion cancelled.",
            ephemeral=True
        )

class GameVoteView(discord.ui.View):
    """View with buttons for game voting."""
    
    def __init__(self, tournament_manager, vote_id):
        super().__init__(timeout=None)
        self.tournament_manager = tournament_manager
        self.vote_id = vote_id
        
        vote = tournament_manager.get_game_vote(vote_id)
        if not vote:
            return
            
        # Add vote buttons for each game
        for i, game in enumerate(vote["games"]):
            button = discord.ui.Button(
                label=f"Vote: {game['name']}",
                style=discord.ButtonStyle.primary,
                emoji="🎮",
                custom_id=f"vote_game_{vote_id}_{i}"
            )
            button.callback = self.make_vote_callback(i)
            self.add_item(button)
            
        # Add results button
        results_button = discord.ui.Button(
            label="View Results",
            style=discord.ButtonStyle.secondary,
            emoji="📊",
            custom_id=f"view_results_{vote_id}"
        )
        results_button.callback = self.results_callback
        self.add_item(results_button)
        
    def make_vote_callback(self, game_index):
        """Create a callback for a vote button."""
        async def vote_callback(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            
            success, message = self.tournament_manager.vote_for_game(self.vote_id, user_id, game_index)
            
            if success:
                # Update the embed if applicable
                vote = self.tournament_manager.get_game_vote(self.vote_id)
                
                await interaction.response.send_message(
                    f"✅ {message}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
                
        return vote_callback
        
    async def results_callback(self, interaction: discord.Interaction):
        """Called when the results button is clicked."""
        vote = self.tournament_manager.get_game_vote(self.vote_id)
        
        if not vote:
            await interaction.response.send_message(
                "❌ Vote not found. It may have been deleted.",
                ephemeral=True
            )
            return
            
        # Create results embed
        embed = discord.Embed(
            title="📊 Game Vote Results",
            description="Current results for the game vote",
            color=0x5865F2,
            timestamp=datetime.datetime.now()
        )
        
        end_time = datetime.datetime.fromisoformat(vote["end_time"])
        embed.add_field(name="⏱️ Voting Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
        
        # Get total votes
        total_votes = sum(game["votes"] for game in vote["games"])
        
        # Add results for each game
        for i, game in enumerate(vote["games"]):
            percentage = 0
            if total_votes > 0:
                percentage = (game["votes"] / total_votes) * 100
                
            embed.add_field(
                name=f"{game['name']}",
                value=f"Votes: {game['votes']} ({percentage:.1f}%)",
                inline=False
            )
            
        embed.set_footer(text=f"Total votes: {total_votes}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    """Add the tournament cog to the bot."""
    await bot.add_cog(TournamentCog(bot))
    logger.info("Tournament cog loaded")