import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import asyncio
import logging
import datetime
import time

logger = logging.getLogger('investments')
from typing import Dict, List, Optional, Tuple, Union
from database import Database
from logger import setup_logger

logger = setup_logger('investments')

class Investment:
    def __init__(self, name, cost, hourly_return, max_holding, maintenance_drain, risk_level, risk_events=None):
        self.name = name
        self.cost = cost
        self.hourly_return = hourly_return
        self.max_holding = max_holding
        self.maintenance_drain = maintenance_drain  # percent per hour
        self.risk_level = risk_level  # "Low", "Medium", "High"

        self.risk_events = risk_events or ["Fire", "Infestation", "Power Outage"]
        
    def to_dict(self):
        return {
            "name": self.name,
            "cost": self.cost,
            "hourly_return": self.hourly_return,
            "max_holding": self.max_holding,
            "maintenance_drain": self.maintenance_drain,
            "risk_level": self.risk_level
        }
        
    @classmethod
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["cost"],
            data["hourly_return"],
            data["max_holding"],
            data["maintenance_drain"],
            data["risk_level"]
        )

class UserInvestment:
    def __init__(self, investment_name, purchase_time, maintenance=100, accumulated=0):
        self.investment_name = investment_name
        self.purchase_time = purchase_time
        self.maintenance = maintenance  # percentage 0-100
        self.accumulated = accumulated  # coins accumulated but not collected
        self.risk_event = False  # if a risk event has occurred
        self.risk_event_type = None  # type of risk event (Fire, Earthquake, etc.)
        self.daily_income = 0  # daily income calculation for maintenance cost
        self.last_update = time.time()  # timestamp of last update for persistence between bot restarts
        
    def to_dict(self):
        return {
            "investment_name": self.investment_name,
            "purchase_time": self.purchase_time,
            "maintenance": self.maintenance,
            "accumulated": self.accumulated,
            "risk_event": self.risk_event,
            "risk_event_type": self.risk_event_type,
            "daily_income": self.daily_income,
            "last_update": self.last_update
        }
        
    def get_risk_status_text(self):
        """Get formatted risk event text with the type."""
        if not self.risk_event:
            return None

        risk_type = self.risk_event_type or "Unknown Problem"
        emoji = "🔥"  # Default fire emoji
        
        if "Fire" in risk_type:
            emoji = "🔥"
        elif "Water" in risk_type or "Flood" in risk_type:
            emoji = "💧"
        elif "Power" in risk_type:
            emoji = "⚡"
        elif "Rob" in risk_type:
            emoji = "🦹"
        elif "Infestation" in risk_type:
            emoji = "🐜"
        elif "Health" in risk_type:
            emoji = "🏥"
        elif "Staff" in risk_type:
            emoji = "👨‍💼"
        elif "Server" in risk_type or "Data" in risk_type:
            emoji = "💻"
        elif "Legal" in risk_type or "Dispute" in risk_type:
            emoji = "⚖️"
        elif "Earthquake" in risk_type:
            emoji = "🌋"
        elif "Takeover" in risk_type:
            emoji = "👔"
        elif "Market" in risk_type:
            emoji = "📉"
        
        return f"{emoji} RISK EVENT: {risk_type} - Needs repair! {emoji}"
        
    def get_next_income_text(self, investment_type):
        """Calculate and format text about when next income will be available."""
        if self.accumulated > 0:
            return "💰 Ready to collect!"
            
        if self.risk_event or self.maintenance < 25:
            return "❌ Income stopped (needs maintenance or repair)"

        return f"🕒 Income arrives every hour ({investment_type.hourly_return} coins/hr)"
        
    @classmethod
    def from_dict(cls, data):
        investment = cls(
            data["investment_name"],
            data["purchase_time"],
            data.get("maintenance", 100),
            data.get("accumulated", 0)
        )
        investment.risk_event = data.get("risk_event", False)
        investment.risk_event_type = data.get("risk_event_type", None)
        investment.daily_income = data.get("daily_income", 0)

        if "last_update" in data:
            investment.last_update = data.get("last_update", time.time())
        return investment

class InvestmentSystem:
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.data_file = "data/investments.json"
        self.maintenance_file = 'data/maintenance_times.json'
        self.last_update = datetime.datetime.now()
        # Updated investments with new specs:
        # Investment(name, cost, hourly_return, max_holding, maintenance_drain, risk_level, risk_events)
        self.investments = {
            "🏪 Grocery Store": Investment("🏪 Grocery Store", 1000, 10, 120, 5, "Low", 
                                        ["Fire", "Water Damage", "Power Outage"]),
            "🛍️ Shop": Investment("🛍️ Shop", 1500, 20, 240, 8, "Medium",
                                    ["Robbery", "Infestation", "Flooding"]),
            "🍔 Restaurant": Investment("🍔 Restaurant", 2300, 35, 240, 10, "High",
                                    ["Fire", "Health Code Violation", "Staff Shortage"]),
            "🏭 Company": Investment("🏭 Company", 3800, 60, 600, 15, "High",
                                    ["Equipment Failure", "Data Breach", "Legal Dispute"]),
            "🏘️ Real Estate": Investment("🏘️ Real Estate", 5000, 50, 300, 2.5, "Low",
                                           ["Fire", "Earthquake", "Property Damage", "Market Crash"])
        }

        self.load_maintenance_times()

        self.save_last_maintenance_time()

        self.user_investments = {}
        self.load_data()

        logger.info("Investment system initialized")
        
    def load_maintenance_times(self):
        """Load maintenance times from file."""
        try:
            with open(self.maintenance_file, 'r') as f:
                self.maintenance_times = json.load(f)
        except:
            self.maintenance_times = {}
            self.save_last_maintenance_time()

    def save_last_maintenance_time(self):
        """Save the last maintenance check time."""
        current_time = time.time()
        self.maintenance_times['last_check'] = current_time
        with open(self.maintenance_file, 'w') as f:
            json.dump(self.maintenance_times, f)

        logger.info(f"Saved maintenance timestamp: {datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
    
    def load_data(self):
        """Load investment data from file."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)

                    if "last_update" in data:
                        try:
                            self.last_update = datetime.datetime.fromisoformat(data["last_update"])
                            logger.info(f"Loaded last investment update time: {self.last_update}")
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error parsing last_update time: {e}")
                            self.last_update = datetime.datetime.now()

                    for user_id, investments in data.get("user_investments", {}).items():
                        self.user_investments[user_id] = []
                        for inv_data in investments:
                            self.user_investments[user_id].append(UserInvestment.from_dict(inv_data))
            else:

                self.save_data()
        except Exception as e:
            logger.error(f"Error loading investment data: {e}")

            self.save_data()
    
    def save_data(self):
        """Save investment data to file."""
        try:
            data = {
                "last_update": self.last_update.isoformat(),
                "user_investments": {
                    user_id: [inv.to_dict() for inv in investments]
                    for user_id, investments in self.user_investments.items()
                }
            }
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving investment data: {e}")
    
    async def investment_updater(self):
        """Background task to update investments every few minutes.
        This allows for hourly income accumulation and maintenance drain."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                current_time = datetime.datetime.now()
                
                # Run every 5 minutes to check for accumulated hourly income
                if (current_time - self.last_update).total_seconds() >= 300:  # 300 seconds = 5 minutes
                    logger.info(f"Running investment update at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.update_investments()
                    self.last_update = current_time
                    logger.info(f"Investment update completed, next update at approximately {(current_time + datetime.timedelta(seconds=300)).strftime('%Y-%m-%d %H:%M:%S')}")

                    # Send reminders for properties with low maintenance
                    await self.send_maintenance_reminders()

                self.save_data()

                await asyncio.sleep(300)  # 300 seconds = 5 minutes
            except Exception as e:
                logger.error(f"Error in investment updater: {e}", exc_info=True)
                await asyncio.sleep(300)
    
    async def send_maintenance_reminders(self):
        """Send reminders to users about businesses with low maintenance (0-50%)."""
        try:
            for user_id, investments in self.user_investments.items():

                if not investments:
                    continue

                low_maintenance_businesses = []
                for inv in investments:

                    if inv.risk_event:
                        continue

                    if 0 <= inv.maintenance <= 50:
                        low_maintenance_businesses.append((inv.investment_name, inv.maintenance))

                if low_maintenance_businesses:
                    try:

                        discord_user = self.bot.get_user(int(user_id))
                        if not discord_user:

                            discord_user = await self.bot.fetch_user(int(user_id))
                        
                        if discord_user:

                            message = "⚠️ **Business Maintenance Reminder** ⚠️\n\n"
                            message += "The following businesses need maintenance (below 50%):\n"
                            
                            for business_name, maintenance in low_maintenance_businesses:
                                emoji = "🔴" if maintenance < 25 else "🟠"  # Red for very low, orange for moderately low
                                message += f"{emoji} **{business_name}**: {maintenance:.1f}% maintenance\n"
                            
                            message += "\nLow maintenance can lead to risk events! Use `/invest` and then the 'Maintain All' button or manage individual businesses to perform maintenance."

                            await discord_user.send(message)
                            logger.info(f"Sent maintenance reminder to user {user_id} for {len(low_maintenance_businesses)} businesses")
                    except discord.errors.Forbidden:

                        logger.warning(f"Could not send maintenance reminder to user {user_id} (DMs closed)")
                    except Exception as e:
                        logger.error(f"Error sending maintenance reminder to user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Error in send_maintenance_reminders: {e}")
    
    def reset_all_accumulated_income(self):
        """Reset accumulated income for all users' investments to zero."""
        count = 0
        for user_id, investments in self.user_investments.items():
            for inv in investments:
                if inv.accumulated > 0:
                    inv.accumulated = 0
                    count += 1
        logger.info(f"Reset accumulated income for {count} investments across all users")
        self.save_data()
        return count

    def update_investments(self):
        """Update all user investments (accumulate hourly returns, decrease maintenance)."""
        users_to_update = list(self.user_investments.keys())
        current_time = time.time()

        self.save_last_maintenance_time()
        
        for user_id in users_to_update:
            investments = self.user_investments[user_id]
            for inv in investments:
                investment_type = self.investments.get(inv.investment_name)
                if not investment_type:
                    continue

                hours_since_update = 0
                last_system_check = self.maintenance_times.get('last_check', time.time())

                if not hasattr(inv, 'last_update'):
                    inv.last_update = current_time

                most_recent_time = max(inv.last_update, last_system_check)

                if most_recent_time > current_time:

                    logger.warning(f"Found future timestamp for investment {inv.investment_name} (user {user_id}), using current time")

                    elapsed_seconds = 60  # Default to 1 minute (60 seconds) of progress

                    inv.last_update = current_time
                else:
                    elapsed_seconds = current_time - most_recent_time

                hours_since_update = min(elapsed_seconds / 3600, 24)
                logger.debug(f"Investment {inv.investment_name} for user {user_id}: {hours_since_update:.2f} hours since last update")

                if inv.maintenance < 25 or inv.risk_event:

                    inv.last_update = current_time
                    continue

                if inv.accumulated < investment_type.max_holding:

                    full_hours_passed = int(hours_since_update)

                    if full_hours_passed >= 1:

                        coins_to_add = investment_type.hourly_return * full_hours_passed

                        logger.info(f"Investment {inv.investment_name} for user {user_id}: Adding {coins_to_add} coins for {full_hours_passed} full hours (hourly_return: {investment_type.hourly_return})")

                        if inv.accumulated + coins_to_add > investment_type.max_holding:
                            inv.accumulated = investment_type.max_holding
                        else:
                            inv.accumulated += coins_to_add
                    else:

                        logger.debug(f"Investment {inv.investment_name} for user {user_id}: No full hour has passed ({hours_since_update:.2f} hours), not adding income")

                    inv.accumulated = round(inv.accumulated, 2)
                    logger.info(f"Investment {inv.investment_name} now has {inv.accumulated:.2f} accumulated coins (max: {investment_type.max_holding})")

                maintenance_before = inv.maintenance
                maintenance_decrease = investment_type.maintenance_drain * hours_since_update
                inv.maintenance -= maintenance_decrease

                logger.info(f"Investment {inv.investment_name} for user {user_id}: Maintenance decreased from {maintenance_before:.2f}% to {inv.maintenance:.2f}% (drain rate: {investment_type.maintenance_drain}%/hr * {hours_since_update:.2f} hours)")

                inv.maintenance = round(inv.maintenance, 2)
                
                if inv.maintenance < 0:
                    inv.maintenance = 0

                inv.daily_income = investment_type.hourly_return * 24

                inv.last_update = current_time

                if inv.maintenance < 25 and not inv.risk_event:
                    risk_level = investment_type.risk_level
                    risk_chance = {"Low": 0.1, "Medium": 0.3, "High": 0.5, "Very High": 0.7}.get(risk_level, 0.2)
                    if random.random() < risk_chance:
                        inv.risk_event = True

                        inv.risk_event_type = random.choice(investment_type.risk_events)
                        logger.info(f"Risk event '{inv.risk_event_type}' occurred for {user_id}'s {inv.investment_name}")

            self.user_investments[user_id] = [
                inv for inv in investments 
                if inv.maintenance > 0 or inv.accumulated > 0 or not inv.risk_event
            ]

            if not self.user_investments[user_id]:
                del self.user_investments[user_id]
    
    def get_user_investments(self, user_id):
        """Get all investments for a user."""
        return self.user_investments.get(str(user_id), [])
    
    def add_investment(self, user_id, investment_name):
        """Add a new investment for a user."""
        user_id = str(user_id)
        if investment_name not in self.investments:
            return False
            
        if user_id not in self.user_investments:
            self.user_investments[user_id] = []

        for inv in self.user_investments[user_id]:
            if inv.investment_name == investment_name:
                return False

        purchase_time = datetime.datetime.now().isoformat()
        self.user_investments[user_id].append(
            UserInvestment(investment_name, purchase_time)
        )
        self.save_data()
        return True
        
    def give_investment(self, target_user_id, investment_name):
        """Give a business directly to a user (admin function).
        
        Args:
            target_user_id: The user ID to give the business to
            investment_name: The exact name of the business to give
            
        Returns:
            tuple: (success, message)
        """
        try:

            target_user_id = str(target_user_id)

            if investment_name not in self.investments:
                return False, f"This business type ({investment_name}) doesn't exist"

            if target_user_id not in self.user_investments:
                self.user_investments[target_user_id] = []

            for inv in self.user_investments[target_user_id]:
                if inv.investment_name == investment_name:
                    return False, f"User already has the {investment_name} business"

            purchase_time = datetime.datetime.now().isoformat()
            new_investment = UserInvestment(investment_name, purchase_time)

            new_investment.maintenance = 100

            new_investment.accumulated = 0

            self.user_investments[target_user_id].append(new_investment)

            self.save_data()
            
            return True, f"Successfully gave {investment_name} to user"
        except Exception as e:
            logger.error(f"Error in give_investment: {e}")
            return False, f"An error occurred: {str(e)}"
    
    def remove_investment(self, user_id, investment_name):
        """Remove an investment from a user."""
        user_id = str(user_id)
        if user_id not in self.user_investments:
            return False
            
        initial_count = len(self.user_investments[user_id])
        self.user_investments[user_id] = [
            inv for inv in self.user_investments[user_id]
            if inv.investment_name != investment_name
        ]

        if len(self.user_investments[user_id]) < initial_count:
            self.save_data()
            return True
        return False
    
    def maintain_investment(self, user_id, investment_name, amount=25):
        """Perform maintenance on an investment."""
        user_id = str(user_id)
        if user_id not in self.user_investments:
            return False
            
        for inv in self.user_investments[user_id]:
            if inv.investment_name == investment_name:

                if inv.risk_event:
                    return False

                if inv.maintenance >= 50:

                    investment_type = self.investments.get(inv.investment_name)
                    if not investment_type:
                        return False

                    if inv.daily_income == 0:
                        inv.daily_income = investment_type.hourly_return * 24

                    inv.maintenance += amount
                    if inv.maintenance > 100:
                        inv.maintenance = 100

                    inv.last_update = time.time()
                    
                    self.save_data()
                    return True
                else:

                    inv.maintenance += amount
                    if inv.maintenance > 100:
                        inv.maintenance = 100

                    inv.last_update = time.time()
                    
                    self.save_data()
                    return True
                
        return False
    
    def collect_investment(self, user_id, investment_name):
        """Collect accumulated coins from an investment.
        
        Returns:
            float: Collected coins if successful, 0 if nothing to collect
            -1: If collection is on cooldown (not yet an hour since last collection)
        """
        user_id = str(user_id)
        if user_id not in self.user_investments:
            return 0
            
        for inv in self.user_investments[user_id]:
            if inv.investment_name == investment_name:

                if inv.risk_event:
                    return 0

                current_time = time.time()
                last_collection_time = getattr(inv, 'last_collection_time', 0)
                time_since_last_collection = current_time - last_collection_time

                if time_since_last_collection < 3600:  # 3600 seconds = 1 hour
                    return -1

                # Use the correct accumulated value (which is already set in update_investments)
                accumulated_float = float(inv.accumulated)
                
                # If accumulated is too small (potential bug), we'll use the investment's actual hourly return
                if accumulated_float <= 1 and inv.maintenance >= 25:
                    investment_type = self.investments.get(inv.investment_name)
                    if investment_type:
                        # Calculate the proper accumulated coins based on investment type
                        logger.info(f"Fixing accumulated amount for {investment_name}, was {accumulated_float}")
                        hours_since_update = time_since_last_collection / 3600
                        accumulated_float = investment_type.hourly_return * hours_since_update
                        logger.info(f"Fixed to {accumulated_float} ({investment_type.hourly_return} * {hours_since_update:.2f} hours)")
                
                coins = int(accumulated_float)
                
                if coins < accumulated_float:
                    coins = coins + 1  # Round up

                # Ensure we collect at least the hourly income amount
                if coins <= 1 and inv.maintenance >= 25:
                    investment_type = self.investments.get(inv.investment_name)
                    if investment_type:
                        coins = max(coins, int(investment_type.hourly_return))
                        logger.info(f"Ensuring minimum income of {coins} coins for {investment_name}")

                inv.accumulated = 0
                inv.last_collection_time = current_time
                inv.last_update = current_time
                
                self.save_data()
                return coins
                
        return 0
    
    def repair_investment(self, user_id, investment_name):
        """Repair an investment after a risk event."""
        user_id = str(user_id)
        if user_id not in self.user_investments:
            return False
            
        for inv in self.user_investments[user_id]:
            if inv.investment_name == investment_name and inv.risk_event:

                investment_type = self.investments.get(inv.investment_name)
                if not investment_type:
                    return False

                inv.risk_event = False
                inv.risk_event_type = None

                inv.maintenance = 50

                if inv.daily_income == 0:
                    inv.daily_income = investment_type.hourly_return * 24

                inv.last_update = time.time()
                
                self.save_data()
                return True
                
        return False

class InvestmentsCog(commands.Cog):
    """Cog for managing the investment system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.investment_system = InvestmentSystem(bot)
        self.db = Database()
        self.investment_task = None
        logger.info("Investments cog initialized")
        
    async def cog_load(self):
        """Called when the cog is loaded."""

        self.started_updater = False
        logger.info("Investment cog loaded, will start updater task when bot is ready")
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Start investment updater task when bot is ready."""
        try:
            if not hasattr(self, 'started_updater') or not self.started_updater:
                self.investment_task = self.bot.loop.create_task(self.investment_system.investment_updater())
                logger.info("Started investment updater background task from on_ready")
                self.started_updater = True
        except Exception as e:
            logger.error(f"Failed to start investment updater task from on_ready: {e}")
        
    async def cog_unload(self):
        """Called when the cog is unloaded."""

        if hasattr(self, 'investment_task') and self.investment_task:
            self.investment_task.cancel()
        if self.investment_task:
            self.investment_task.cancel()
            logger.info("Cancelled investment updater background task")
    
    @app_commands.command(
        name="reset_investments",
        description="⚠️ Reset all accumulated income (Admin only)"
    )
    async def reset_investments(self, interaction: discord.Interaction):
        """Reset accumulated income for all users. Admin only command."""
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        try:
            # Check for admin permission
            if not any(role.id in [1338482857974169683, 1350879840794054758] for role in interaction.user.roles):
                await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
                return
                
            # Reset all accumulated income
            count = self.investment_system.reset_all_accumulated_income()
            
            await interaction.followup.send(
                f"✅ Successfully reset accumulated income for {count} investments across all users.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in reset_investments command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while resetting investments. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="invest",
        description="💰 Manage your investments with new hourly returns"
    )
    async def invest(self, interaction: discord.Interaction):
        """View available investments or manage your current investments.
        This feature has been updated with new hourly returns system!
        """
        await interaction.response.defer(thinking=True)
        
        try:
            user_id = str(interaction.user.id)
            user_investments = self.investment_system.get_user_investments(user_id)
            
            rainbow_color = random.randint(0, 0xFFFFFF)
            
            # Check user's coins
            user_data = self.db.get_user(user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            embed = discord.Embed(
                title="🏙️ Premium Investment System",
                description="Welcome to the luxury investment marketplace! Earnings are paid out **every hour**. Collect regularly to maximize your profits!",
                color=discord.Color(rainbow_color)
            )
            
            embed.add_field(
                name="💰 Your Investment Capital",
                value=f"{user_coins:,} coins available",
                inline=False
            )
            
            info_embed = discord.Embed(
                title="📊 Income System",
                description="Manage your properties to generate passive income. Each property has unique traits:",
                color=discord.Color(rainbow_color)
            )
            
            info_embed.add_field(
                name="⏱️ Hourly Returns",
                value=(
                    "🏪 Grocery Store: 10 coins/hr (200 max)\n"
                    "🛍️ Retail Shop: 25 coins/hr (300 max)\n"
                    "🍔 Restaurant: 60 coins/hr (400 max)\n"
                    "🏭 Private Company: 100 coins/hr (600 max)\n"
                    "🏘️ Real Estate: 50 coins/hr (300 max)"
                ),
                inline=False
            )
            
            info_embed.add_field(
                name="⚠️ Maintenance System",
                value=(
                    "Each property loses durability hourly:\n"
                    "🏪 Grocery Store: -3%/hr (Low risk)\n"
                    "🛍️ Retail Shop: -4%/hr (Medium risk)\n"
                    "🍔 Restaurant: -5%/hr (High risk)\n"
                    "🏭 Private Company: -3.5%/hr (Medium risk)\n"
                    "🏘️ Real Estate: -2.5%/hr (Low risk)"
                ),
                inline=False
            )
            
            info_embed.add_field(
                name="⚙️ Important Rules",
                value=(
                    "• Income stops when maintenance < 25%\n"
                    "• Risk events can occur when maintenance is low\n"
                    "• You need to maintain properties regularly to keep earning\n"
                    "• Max storage capacity means you must collect income regularly"
                ),
                inline=False
            )
            
            if user_investments:
                view = ManageInvestmentsView(self.investment_system, self.db, user_id, user_investments, info_embed)
                await interaction.followup.send(embed=embed, view=view)
            else:
                view = InvestmentPurchaseView(self.investment_system, self.db, user_id, info_embed)
                await interaction.followup.send(embed=embed, view=view)
                
        except Exception as e:
            logger.error(f"Error in invest command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while accessing the investment system. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="givebusiness",
        description="📋 [DISABLED] This feature has been phased out"
    )
    async def givebusiness(self, interaction: discord.Interaction):
        """Panel to give a business to another user.
        THIS FEATURE HAS BEEN DISABLED: The investment system has been phased out.
        """
        from permissions import check_permissions
        if not await check_permissions(interaction):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        await interaction.followup.send(
            "⚠️ This command has been disabled as the investment system is being phased out.",
            ephemeral=True
        )
        
    @app_commands.command(
        name="incometoall",
        description="🏭 [DISABLED] This feature has been phased out"
    )
    async def incometoall(self, interaction: discord.Interaction):
        """Admin command to give hourly income to all users with businesses.
        THIS FEATURE HAS BEEN DISABLED: The investment system has been phased out.
        """
        from permissions import check_permissions
        if not await check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        
        await interaction.followup.send(
            "⚠️ This command has been disabled as the investment system is being phased out.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="business",
        description="🏢 Manage your luxury property portfolio"
    )
    async def business(self, interaction: discord.Interaction):
        """View and manage your current investments with an enhanced UI.
        Features detailed property analytics and management tools.
        """
        await interaction.response.defer(thinking=True)
        
        try:
            user_id = str(interaction.user.id)
            user_investments = self.investment_system.get_user_investments(user_id)
            
            # Generate a more pleasing color - blue-green range for business theme
            rainbow_color = random.randint(0x007799, 0x33CCAA)
            
            # Check user's coins
            user_data = self.db.get_user(user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            embed = discord.Embed(
                title="🏙️ Luxury Property Portfolio",
                description="Your exclusive access to premium income-generating assets. Each property generates revenue **hourly**!",
                color=discord.Color(rainbow_color)
            )
            
            # Add a custom footer for branding
            embed.set_footer(text="GridBot Premium Investment Platform | Collect regularly for maximum profits")
            
            embed.add_field(
                name="💰 Investment Capital",
                value=f"**{user_coins:,}** coins available for expansion",
                inline=False
            )
            
            if user_investments:
                # Display summary of properties with status indicators
                properties_list = []
                total_hourly_income = 0
                total_accumulated = 0
                properties_needing_maintenance = 0
                properties_with_risk = 0
                
                for inv in user_investments:
                    # Get investment details
                    investment_type = self.investment_system.investments.get(inv.investment_name)
                    if not investment_type:
                        continue
                    
                    # Calculate status
                    if inv.risk_event:
                        properties_with_risk += 1
                    elif inv.maintenance < 25:
                        properties_needing_maintenance += 1
                    else:
                        total_hourly_income += investment_type.hourly_return
                    
                    total_accumulated += inv.accumulated
                
                # Create detailed property summary
                embed.add_field(
                    name="🏙️ Property Portfolio Summary",
                    value=(
                        f"**{len(user_investments)}** premium assets in your portfolio\n"
                        f"**{total_hourly_income:,}** coins hourly passive income\n"
                        f"**{int(total_accumulated):,}** coins accumulated and ready to collect"
                    ),
                    inline=True
                )
                
                # Add status indicators
                status_value = "✅ All properties operating optimally"
                if properties_with_risk > 0 or properties_needing_maintenance > 0:
                    status_items = []
                    if properties_with_risk > 0:
                        status_items.append(f"⚠️ **{properties_with_risk}** properties with risk events")
                    if properties_needing_maintenance > 0:
                        status_items.append(f"🛠️ **{properties_needing_maintenance}** properties need maintenance")
                    status_value = "\n".join(status_items)
                    
                embed.add_field(
                    name="📊 Property Status",
                    value=status_value,
                    inline=True
                )
                
                # Create info embed for button callback
                info_embed = discord.Embed(
                    title="💎 Premium Investment Guide",
                    description="Your exclusive portfolio analysis and property management toolkit:",
                    color=discord.Color(rainbow_color)
                )
                
                info_embed.add_field(
                    name="⏱️ Hourly Revenue Generation",
                    value=(
                        "🏪 Grocery Store: 10 coins/hr (200 max storage)\n"
                        "🛍️ Retail Shop: 25 coins/hr (300 max storage)\n"
                        "🍔 Restaurant: 60 coins/hr (400 max storage)\n"
                        "🏭 Private Company: 100 coins/hr (600 max storage)\n"
                        "🏘️ Real Estate: 50 coins/hr (300 max storage)"
                    ),
                    inline=False
                )
                
                # Create view for managing investments
                view = ManageInvestmentsView(self.investment_system, self.db, user_id, user_investments, info_embed)
                await interaction.followup.send(embed=embed, view=view)
            else:
                embed.add_field(
                    name="💼 Begin Your Investment Journey",
                    value=(
                        "You haven't acquired any premium assets yet! Start building your passive income empire today.\n\n"
                        "**Why invest?**\n"
                        "• Generate passive income every hour\n"
                        "• Build a diverse portfolio of assets\n"
                        "• Grow your wealth while you're offline"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="🏆 Recommended First Purchase",
                    value=(
                        "🏪 **Grocery Store - 500 coins**\n"
                        "• 10 coins hourly return\n" 
                        "• Low maintenance requirements\n"
                        "• Perfect for beginning investors"
                    ),
                    inline=True
                )
                
                embed.add_field(
                    name="📈 For Experienced Investors",
                    value=(
                        "🏭 **Private Company - 5,000 coins**\n"
                        "• 100 coins hourly return\n"
                        "• Higher maintenance needs\n"
                        "• Maximum long-term profits"
                    ),
                    inline=True
                )
                
                # Create a view with a button to the invest command
                view = discord.ui.View(timeout=120)
                invest_button = discord.ui.Button(
                    label="💎 Browse Available Properties",
                    style=discord.ButtonStyle.primary
                )
                
                async def invest_callback(inner_interaction):
                    await inner_interaction.response.defer(thinking=True)
                    await self.invest(inner_interaction)
                
                invest_button.callback = invest_callback
                view.add_item(invest_button)
                
                await interaction.followup.send(embed=embed, view=view)
                
        except Exception as e:
            logger.error(f"Error in business command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while accessing the business management system. Please try again later.",
                ephemeral=True
            )

class InvestmentView(discord.ui.View):
    """View with buttons for purchasing investments."""
    
    def __init__(self, investment_system, db, user_id, user_investments):
        super().__init__(timeout=120)
        self.investment_system = investment_system
        self.db = db
        self.user_id = user_id
        self.user_investments = user_investments
        self.owned_investments = [inv.investment_name for inv in user_investments]

        for name, inv in self.investment_system.investments.items():
            button = discord.ui.Button(
                label=f"Buy {name}" if name not in self.owned_investments else f"View {name}",
                custom_id=f"invest_{name}",
                style=discord.ButtonStyle.primary if name not in self.owned_investments else discord.ButtonStyle.secondary
            )
            button.callback = self.make_callback(name, inv)
            self.add_item(button)
            
    def make_callback(self, name, investment):
        async def callback(interaction: discord.Interaction):

            try:

                await interaction.response.defer(thinking=True, ephemeral=True)

                await asyncio.sleep(0.5)

                try:
                    user_data = self.db.get_user(self.user_id)
                except Exception as db_error:
                    logger.error(f"Database error when getting user data: {db_error}")
                    await interaction.followup.send("Error retrieving your account data. Please try again.", ephemeral=True)
                    return
                if name in self.owned_investments:

                    user_investment = None
                    for inv in self.user_investments:
                        if inv.investment_name == name:
                            user_investment = inv
                            break

                    embed = discord.Embed(
                        title=f"🏢 {name} Details",
                        description="You already own this business.",
                        color=discord.Color.green()
                    )

                    if user_investment:
                        maintenance_level = user_investment.maintenance
                        maintenance_emoji = "✅"  # Good condition
                        
                        if user_investment.risk_event:
                            risk_status = user_investment.get_risk_status_text()
                            embed.add_field(
                                name="⚠️ ALERT",
                                value=risk_status,
                                inline=False
                            )
                            maintenance_emoji = "❌"  # Critical
                        elif maintenance_level < 25:
                            maintenance_emoji = "⛔"  # Critical
                        elif maintenance_level < 50:
                            maintenance_emoji = "⚠️"  # Warning
                        elif maintenance_level < 75:
                            maintenance_emoji = "📊"  # Moderate
                        
                        embed.add_field(
                            name="Maintenance Status",
                            value=f"{maintenance_emoji} {maintenance_level:.1f}%",
                            inline=False
                        )
                    
                    embed.add_field(
                        name="Hourly Return",
                        value=f"{investment.hourly_return} coins/hr",
                        inline=True
                    )
                    embed.add_field(
                        name="Max Storage",
                        value=f"{investment.max_holding} coins",
                        inline=True
                    )
                    embed.add_field(
                        name="Maintenance Drain",
                        value=f"{investment.maintenance_drain}%/hr",
                        inline=True
                    )

                    if user_investment and user_investment.accumulated > 0:

                        accumulated_display = int(user_investment.accumulated)
                            
                        embed.add_field(
                            name="💰 Accumulated Income",
                            value=f"{accumulated_display:,} coins ready to collect",
                            inline=False
                        )

                    risk_emoji = "🔰"  # Default low risk
                    if investment.risk_level == "Low":
                        risk_emoji = "🔰"
                    elif investment.risk_level == "Medium":
                        risk_emoji = "⚠️"
                    elif investment.risk_level == "High":
                        risk_emoji = "🚨"
                    elif investment.risk_level == "Very High":
                        risk_emoji = "☢️"
                    
                    embed.add_field(
                        name="Risk Level",
                        value=f"{risk_emoji} {investment.risk_level}",
                        inline=True
                    )
                    
                    view = BusinessDetailView(self.investment_system, self.db, self.user_id, name)

                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                else:

                    if user_data["coins"] < investment.cost:

                        await interaction.followup.send(
                            f"You don't have enough coins to purchase this business. You need {investment.cost} coins.",
                            ephemeral=True
                        )
                        return

                    self.db.add_coins(self.user_id, user_data["username"], -investment.cost)
                    success = self.investment_system.add_investment(self.user_id, name)
                    
                    if success:
                        embed = discord.Embed(
                            title="🎉 Business Purchased!",
                            description=f"You are now the proud owner of {name}!",
                            color=discord.Color.green()
                        )
                        embed.add_field(
                            name="Hourly Return",
                            value=f"{investment.hourly_return} coins/hr",
                            inline=True
                        )
                        embed.add_field(
                            name="Max Storage",
                            value=f"{investment.max_holding} coins",
                            inline=True
                        )
                        embed.add_field(
                            name="Maintenance",
                            value="Your business requires regular maintenance to keep running. If maintenance drops below 25%, income will stop and risk events may occur.",
                            inline=False
                        )
                        embed.add_field(
                            name="Next Steps",
                            value="Use `/business` to manage your businesses, collect income, and perform maintenance.",
                            inline=False
                        )

                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:

                        await interaction.followup.send(
                            f"There was an error purchasing this business. You may already own it.",
                            ephemeral=True
                        )
            except Exception as e:

                import logging
                logger = logging.getLogger('investments')
                logger.error(f"Error in investment callback: {e}")

                try:
                    await interaction.followup.send(
                        "An error occurred while processing your investment. Please try again later.",
                        ephemeral=True
                    )
                except Exception as msg_error:
                    logger.error(f"Failed to send error message: {msg_error}")  # Log but continue
        return callback

class InvestmentPurchaseView(discord.ui.View):
    """View with buttons for purchasing new investments."""
    
    def __init__(self, investment_system, db, user_id, info_embed):
        super().__init__(timeout=300)  # 5 minute timeout
        self.investment_system = investment_system
        self.db = db
        self.user_id = user_id
        self.info_embed = info_embed
        
        # Add info button
        info_button = discord.ui.Button(
            label="ℹ️ View Investment Details",
            style=discord.ButtonStyle.secondary,
            custom_id="investment_info"
        )
        info_button.callback = self.info_callback
        self.add_item(info_button)
        
        # Add investment buttons
        for name, inv in self.investment_system.investments.items():
            button = discord.ui.Button(
                label=f"Buy {name.split(' ', 1)[1]} ({inv.cost} coins)",
                emoji=name.split(' ')[0],
                custom_id=f"buy_{name}",
                style=discord.ButtonStyle.primary
            )
            button.callback = self.make_buy_callback(name, inv)
            self.add_item(button)
    
    async def info_callback(self, interaction: discord.Interaction):
        """Show detailed information about investments."""
        await interaction.response.send_message(embed=self.info_embed, ephemeral=True)
    
    def make_buy_callback(self, name, investment):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            
            try:
                user_data = self.db.get_user(self.user_id)
                if not user_data:
                    await interaction.followup.send("Could not find your user data. Please try again later.", ephemeral=True)
                    return
                
                user_coins = user_data.get('coins', 0)
                
                if user_coins < investment.cost:
                    await interaction.followup.send(
                        f"❌ You don't have enough coins to purchase {name}.\n"
                        f"Required: {investment.cost:,} coins\n"
                        f"You have: {user_coins:,} coins", 
                        ephemeral=True
                    )
                    return
                
                # Try to purchase the investment
                self.db.add_coins(self.user_id, user_data.get('username', 'User'), -investment.cost)
                success = self.investment_system.add_investment(self.user_id, name)
                
                if success:
                    # Create a beautiful success embed
                    embed = discord.Embed(
                        title=f"🎉 {name} Purchased!",
                        description="Congratulations on your new business investment!",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="💰 Hourly Return",
                        value=f"{investment.hourly_return} coins/hour",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="⏱️ Max Storage",
                        value=f"{investment.max_holding} coins",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="🔧 Maintenance",
                        value=f"-{investment.maintenance_drain}%/hour",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="⚠️ Risk Level",
                        value=f"{investment.risk_level}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Next Steps",
                        value="Use `/invest` to manage your new property and collect income.",
                        inline=False
                    )
                    
                    # Get updated user investments
                    user_investments = self.investment_system.get_user_investments(self.user_id)
                    
                    # Create a new view with the "Manage Investments" button
                    view = discord.ui.View(timeout=60)
                    manage_button = discord.ui.Button(
                        label="🏢 Manage Your Investments",
                        style=discord.ButtonStyle.success,
                        custom_id="manage_investments"
                    )
                    
                    async def manage_callback(inner_interaction):
                        await inner_interaction.response.defer(thinking=True)
                        
                        rainbow_color = random.randint(0, 0xFFFFFF)
                        manage_embed = discord.Embed(
                            title="🏙️ Investment Management",
                            description="Manage your investments to earn passive income.",
                            color=discord.Color(rainbow_color)
                        )
                        
                        # Get updated user data
                        updated_user_data = self.db.get_user(self.user_id)
                        updated_coins = updated_user_data.get('coins', 0) if updated_user_data else 0
                        
                        manage_embed.add_field(
                            name="💰 Your Coins",
                            value=f"{updated_coins:,} coins",
                            inline=False
                        )
                        
                        new_view = ManageInvestmentsView(
                            self.investment_system,
                            self.db,
                            self.user_id,
                            user_investments,
                            self.info_embed
                        )
                        
                        await inner_interaction.followup.send(
                            embed=manage_embed,
                            view=new_view
                        )
                    
                    manage_button.callback = manage_callback
                    view.add_item(manage_button)
                    
                    await interaction.followup.send(embed=embed, view=view)
                else:
                    # Refund the coins if purchase failed
                    self.db.add_coins(self.user_id, user_data.get('username', 'User'), investment.cost)
                    
                    await interaction.followup.send(
                        f"❌ Error purchasing {name}. You may already own this property. Your coins have been refunded.",
                        ephemeral=True
                    )
            except Exception as e:
                logger.error(f"Error in investment purchase: {e}", exc_info=True)
                await interaction.followup.send(
                    "An error occurred while processing your purchase. Please try again.",
                    ephemeral=True
                )
        
        return callback

class ManageInvestmentsView(discord.ui.View):
    """View with buttons for managing investments."""
    
    def __init__(self, investment_system, db, user_id, user_investments, info_embed):
        super().__init__(timeout=300)  # 5 minute timeout
        self.investment_system = investment_system
        self.db = db
        self.user_id = user_id
        self.user_investments = user_investments
        self.info_embed = info_embed
        
        # Add info button
        info_button = discord.ui.Button(
            label="ℹ️ Investment Guide",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        info_button.callback = self.info_callback
        self.add_item(info_button)
        
        # Add collect all button
        collect_all = discord.ui.Button(
            label="💰 Collect All Income",
            style=discord.ButtonStyle.success,
            row=0
        )
        collect_all.callback = self.collect_all_callback
        self.add_item(collect_all)

        # Add maintain all button
        maintain_all = discord.ui.Button(
            label="🔧 Maintain All (+25%)",
            style=discord.ButtonStyle.primary,
            row=0
        )
        maintain_all.callback = self.maintain_all_callback
        self.add_item(maintain_all)
        
        # Add business buttons
        row_num = 1
        for i, inv in enumerate(user_investments):
            # Start a new row after every 2 buttons (Discord supports up to 5 buttons per row)
            if i > 0 and i % 2 == 0:
                row_num += 1
                if row_num >= 5:  # Discord supports up to 5 rows
                    break
            
            # Choose emoji based on risk state
            emoji = inv.investment_name.split(' ')[0]  # Default emoji from name
            if inv.risk_event:
                emoji = "🔥"  # Risk event
            elif inv.maintenance < 25:
                emoji = "⛔"  # Critical
            elif inv.maintenance < 50:
                emoji = "⚠️"  # Warning
            
            button = discord.ui.Button(
                label=f"Manage {inv.investment_name.split(' ', 1)[1]}",
                emoji=emoji,
                row=row_num,
                style=discord.ButtonStyle.secondary if inv.maintenance >= 50 else discord.ButtonStyle.danger
            )
            button.callback = self.make_manage_callback(inv.investment_name)
            self.add_item(button)
    
    async def info_callback(self, interaction: discord.Interaction):
        """Show detailed information about investments."""
        await interaction.response.send_message(embed=self.info_embed, ephemeral=True)
    
    async def collect_all_callback(self, interaction: discord.Interaction):
        """Collect income from all investments."""
        await interaction.response.defer(thinking=True)
        
        try:
            total_collected = 0
            collected_businesses = []
            failed_businesses = []
            cooldown_businesses = []
            
            for inv in self.user_investments:
                if inv.risk_event or inv.maintenance < 25:
                    failed_businesses.append(inv.investment_name)
                    continue
                
                collected = self.investment_system.collect_investment(self.user_id, inv.investment_name)
                
                if collected == -1:  # On cooldown
                    cooldown_businesses.append(inv.investment_name)
                elif collected > 0:
                    total_collected += collected
                    collected_businesses.append((inv.investment_name, collected))
                    self.db.add_coins(self.user_id, None, collected)
            
            rainbow_color = random.randint(0, 0xFFFFFF)
            embed = discord.Embed(
                title="💰 Collection Results",
                color=discord.Color(rainbow_color)
            )
            
            if total_collected > 0:
                embed.description = f"You collected a total of **{total_collected:,} coins** from your investments!"
                
                collection_details = ""
                for name, amount in collected_businesses:
                    collection_details += f"• {name}: {amount:,} coins\n"
                
                embed.add_field(
                    name="📊 Collection Details",
                    value=collection_details,
                    inline=False
                )
            else:
                embed.description = "No income was available to collect at this time."
            
            if failed_businesses:
                failed_list = "\n".join([f"• {name}" for name in failed_businesses])
                embed.add_field(
                    name="❌ Failed Collections",
                    value=f"These businesses need repairs or maintenance:\n{failed_list}",
                    inline=False
                )
            
            if cooldown_businesses:
                cooldown_list = "\n".join([f"• {name}" for name in cooldown_businesses])
                embed.add_field(
                    name="⏱️ On Cooldown",
                    value=f"These businesses have been collected recently:\n{cooldown_list}",
                    inline=False
                )
            
            # Get updated user data
            user_data = self.db.get_user(self.user_id)
            current_coins = user_data.get('coins', 0) if user_data else 0
            
            embed.add_field(
                name="💰 Your Coins",
                value=f"{current_coins:,} coins",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error collecting all income: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while collecting income. Please try again.",
                ephemeral=True
            )
    
    async def maintain_all_callback(self, interaction: discord.Interaction):
        """Perform maintenance on all investments."""
        await interaction.response.defer(thinking=True)
        
        try:
            maintained_businesses = []
            failed_businesses = []
            risk_businesses = []
            
            for inv in self.user_investments:
                if inv.risk_event:
                    risk_businesses.append(inv.investment_name)
                    continue
                
                if inv.maintenance < 100:  # Only maintain if not at max
                    success = self.investment_system.maintain_investment(self.user_id, inv.investment_name, 25)
                    if success:
                        maintained_businesses.append(inv.investment_name)
                    else:
                        failed_businesses.append(inv.investment_name)
            
            rainbow_color = random.randint(0, 0xFFFFFF)
            embed = discord.Embed(
                title="🔧 Maintenance Results",
                color=discord.Color(rainbow_color)
            )
            
            if maintained_businesses:
                maintained_list = "\n".join([f"• {name}" for name in maintained_businesses])
                embed.description = f"Successfully performed maintenance on the following businesses:\n{maintained_list}"
                embed.add_field(
                    name="✅ Result",
                    value="Maintenance level increased by 25% for each business.",
                    inline=False
                )
            else:
                embed.description = "No businesses needed maintenance at this time."
            
            if failed_businesses:
                failed_list = "\n".join([f"• {name}" for name in failed_businesses])
                embed.add_field(
                    name="❌ Failed Maintenance",
                    value=f"Could not maintain these businesses:\n{failed_list}",
                    inline=False
                )
            
            if risk_businesses:
                risk_list = "\n".join([f"• {name}" for name in risk_businesses])
                embed.add_field(
                    name="🔥 Risk Events",
                    value=f"These businesses need repairs before maintenance:\n{risk_list}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error maintaining all businesses: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while performing maintenance. Please try again.",
                ephemeral=True
            )
    
    def make_manage_callback(self, name):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            
            try:
                # Find the investment
                investment = None
                for inv in self.user_investments:
                    if inv.investment_name == name:
                        investment = inv
                        break
                
                if not investment:
                    await interaction.followup.send(
                        f"Could not find your {name} business. It may have been deleted.",
                        ephemeral=True
                    )
                    return
                
                # Get investment type
                investment_type = self.investment_system.investments.get(name)
                if not investment_type:
                    await interaction.followup.send(
                        f"Error retrieving details for {name}.",
                        ephemeral=True
                    )
                    return
                
                # Create detailed management embed
                rainbow_color = random.randint(0, 0xFFFFFF)
                embed = discord.Embed(
                    title=f"{name} Management",
                    color=discord.Color(rainbow_color)
                )
                
                # Status and maintenance information
                status_value = "✅ Operational"
                maintenance_color = "🟢"  # Green by default
                
                if investment.risk_event:
                    risk_status = investment.get_risk_status_text()
                    status_value = f"🔥 {risk_status}"
                    maintenance_color = "🔥"
                elif investment.maintenance < 25:
                    status_value = "⛔ CRITICAL - Income stopped"
                    maintenance_color = "🔴"
                elif investment.maintenance < 50:
                    status_value = "⚠️ WARNING - Risk of failure"
                    maintenance_color = "🟡"
                elif investment.maintenance < 75:
                    maintenance_color = "🟡"
                
                embed.add_field(
                    name="Status",
                    value=status_value,
                    inline=False
                )
                
                embed.add_field(
                    name="Maintenance",
                    value=f"{maintenance_color} {investment.maintenance:.1f}%\nDrain rate: {investment_type.maintenance_drain}%/hr",
                    inline=True
                )
                
                # Income information
                if investment.risk_event:
                    income_status = "❌ STOPPED (Risk Event)"
                elif investment.maintenance < 25:
                    income_status = "❌ STOPPED (Low Maintenance)"
                else:
                    income_status = f"✅ {investment_type.hourly_return} coins/hr"
                
                embed.add_field(
                    name="Income",
                    value=income_status,
                    inline=True
                )
                
                # Storage information
                storage_percent = (investment.accumulated / investment_type.max_holding) * 100 if investment_type.max_holding > 0 else 0
                
                storage_value = f"{int(investment.accumulated):,}/{investment_type.max_holding:,} coins ({storage_percent:.1f}%)"
                
                if storage_percent >= 100:
                    storage_value = f"**FULL!** {storage_value}"
                
                embed.add_field(
                    name="Storage",
                    value=storage_value,
                    inline=True
                )
                
                # Risk information
                risk_value = f"{investment_type.risk_level} risk level"
                risk_examples = ", ".join(investment_type.risk_events[:2]) + "..."
                risk_value += f"\nPossible events: {risk_examples}"
                
                embed.add_field(
                    name="Risk Profile",
                    value=risk_value,
                    inline=False
                )
                
                # Create management view
                view = BusinessManagementView(self.investment_system, self.db, self.user_id, name)
                
                await interaction.followup.send(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Error displaying business management: {e}", exc_info=True)
                await interaction.followup.send(
                    "An error occurred while accessing business management. Please try again.",
                    ephemeral=True
                )
        
        return callback

class BusinessManagementView(discord.ui.View):
    """View with buttons for managing a specific business."""
    
    def __init__(self, investment_system, db, user_id, business_name):
        super().__init__(timeout=180)  # 3 minute timeout
        self.investment_system = investment_system
        self.db = db
        self.user_id = user_id
        self.business_name = business_name
        
        # Add collect income button
        collect_button = discord.ui.Button(
            label="💰 Collect Income",
            style=discord.ButtonStyle.success,
            row=0
        )
        collect_button.callback = self.collect_callback
        self.add_item(collect_button)
        
        # Add maintain button
        maintain_button = discord.ui.Button(
            label="🔧 Perform Maintenance (+25%)",
            style=discord.ButtonStyle.primary,
            row=0
        )
        maintain_button.callback = self.maintain_callback
        self.add_item(maintain_button)
        
        # Add repair button
        repair_button = discord.ui.Button(
            label="🛠️ Repair Business",
            style=discord.ButtonStyle.danger,
            row=1
        )
        repair_button.callback = self.repair_callback
        self.add_item(repair_button)
        
        # Add back button
        back_button = discord.ui.Button(
            label="◀️ Back to All Investments",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)
    
    async def collect_callback(self, interaction: discord.Interaction):
        """Collect income from this business."""
        await interaction.response.defer(thinking=True)
        
        try:
            # Check if business exists
            user_investments = self.investment_system.get_user_investments(self.user_id)
            business = None
            for inv in user_investments:
                if inv.investment_name == self.business_name:
                    business = inv
                    break
            
            if not business:
                await interaction.followup.send(
                    f"Could not find your {self.business_name} business. It may have been deleted.",
                    ephemeral=True
                )
                return
            
            # Check for risk events or low maintenance
            if business.risk_event:
                await interaction.followup.send(
                    f"❌ Cannot collect income! Your business has a risk event: {business.get_risk_status_text()}\n"
                    f"You need to repair the business first.",
                    ephemeral=True
                )
                return
            
            if business.maintenance < 25:
                await interaction.followup.send(
                    f"❌ Cannot collect income! Maintenance is too low ({business.maintenance:.1f}%).\n"
                    f"You need to maintain the business to at least 25% first.",
                    ephemeral=True
                )
                return
            
            # Try to collect income
            collected = self.investment_system.collect_investment(self.user_id, self.business_name)
            
            if collected == -1:  # On cooldown
                await interaction.followup.send(
                    "⏱️ This business has been collected from recently. Please wait at least an hour between collections.",
                    ephemeral=True
                )
                return
            
            if collected > 0:
                # Add the coins to the user's balance
                self.db.add_coins(self.user_id, None, collected)
                
                # Get the updated user data
                user_data = self.db.get_user(self.user_id)
                current_coins = user_data.get('coins', 0) if user_data else 0
                
                # Create a success embed
                rainbow_color = random.randint(0, 0xFFFFFF)
                embed = discord.Embed(
                    title="💰 Income Collected!",
                    description=f"You collected **{collected:,} coins** from your {self.business_name}!",
                    color=discord.Color(rainbow_color)
                )
                
                embed.add_field(
                    name="Your Balance",
                    value=f"{current_coins:,} coins",
                    inline=False
                )
                
                # Get the investment type for additional info
                investment_type = self.investment_system.investments.get(self.business_name)
                if investment_type:
                    embed.add_field(
                        name="Next Income",
                        value=f"You can collect again in 1 hour (max {investment_type.max_holding:,} coins storage)",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"No income was available to collect from {self.business_name} at this time.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error collecting income: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while collecting income. Please try again later.",
                ephemeral=True
            )
    
    async def maintain_callback(self, interaction: discord.Interaction):
        """Perform maintenance on this business."""
        await interaction.response.defer(thinking=True)
        
        try:
            # Check if business exists
            user_investments = self.investment_system.get_user_investments(self.user_id)
            business = None
            for inv in user_investments:
                if inv.investment_name == self.business_name:
                    business = inv
                    break
            
            if not business:
                await interaction.followup.send(
                    f"Could not find your {self.business_name} business. It may have been deleted.",
                    ephemeral=True
                )
                return
            
            # Check for risk events
            if business.risk_event:
                await interaction.followup.send(
                    f"❌ Cannot perform maintenance! Your business has a risk event: {business.get_risk_status_text()}\n"
                    f"You need to repair the business first.",
                    ephemeral=True
                )
                return
            
            # Check if already at max maintenance
            if business.maintenance >= 100:
                await interaction.followup.send(
                    f"✅ {self.business_name} is already at 100% maintenance!",
                    ephemeral=True
                )
                return
            
            # Try to perform maintenance
            prev_maintenance = business.maintenance
            success = self.investment_system.maintain_investment(self.user_id, self.business_name, 25)
            
            if success:
                # Get updated business info
                user_investments = self.investment_system.get_user_investments(self.user_id)
                updated_business = None
                for inv in user_investments:
                    if inv.investment_name == self.business_name:
                        updated_business = inv
                        break
                
                if not updated_business:
                    await interaction.followup.send(
                        "Maintenance was successful, but could not retrieve updated business information.",
                        ephemeral=True
                    )
                    return
                
                # Create success embed
                rainbow_color = random.randint(0, 0xFFFFFF)
                embed = discord.Embed(
                    title="🔧 Maintenance Complete",
                    description=f"You successfully performed maintenance on your {self.business_name}!",
                    color=discord.Color(rainbow_color)
                )
                
                embed.add_field(
                    name="Maintenance Level",
                    value=f"{prev_maintenance:.1f}% → {updated_business.maintenance:.1f}%",
                    inline=False
                )
                
                # Get investment type for additional info
                investment_type = self.investment_system.investments.get(self.business_name)
                if investment_type:
                    embed.add_field(
                        name="Maintenance Info",
                        value=f"This business loses {investment_type.maintenance_drain}% maintenance per hour.",
                        inline=False
                    )
                
                if updated_business.maintenance >= 25 and prev_maintenance < 25:
                    embed.add_field(
                        name="✅ Income Restored",
                        value="Your business is now operational and generating income again!",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"Failed to perform maintenance on {self.business_name}. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error performing maintenance: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while performing maintenance. Please try again later.",
                ephemeral=True
            )
    
    async def repair_callback(self, interaction: discord.Interaction):
        """Repair a business after a risk event."""
        await interaction.response.defer(thinking=True)
        
        try:
            # Check if business exists
            user_investments = self.investment_system.get_user_investments(self.user_id)
            business = None
            for inv in user_investments:
                if inv.investment_name == self.business_name:
                    business = inv
                    break
            
            if not business:
                await interaction.followup.send(
                    f"Could not find your {self.business_name} business. It may have been deleted.",
                    ephemeral=True
                )
                return
            
            # Check if there's a risk event
            if not business.risk_event:
                await interaction.followup.send(
                    f"Your {self.business_name} doesn't need repairs at this time.",
                    ephemeral=True
                )
                return
            
            # Try to repair
            risk_type = business.risk_event_type
            success = self.investment_system.repair_investment(self.user_id, self.business_name)
            
            if success:
                # Create success embed
                rainbow_color = random.randint(0, 0xFFFFFF)
                embed = discord.Embed(
                    title="🛠️ Repairs Completed",
                    description=f"You successfully repaired your {self.business_name} from {risk_type}!",
                    color=discord.Color(rainbow_color)
                )
                
                embed.add_field(
                    name="Status",
                    value="✅ Your business is now operational again at 50% maintenance.",
                    inline=False
                )
                
                embed.add_field(
                    name="Next Steps",
                    value="Consider performing additional maintenance to reduce the risk of future incidents.",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"Failed to repair {self.business_name}. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error repairing business: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while repairing the business. Please try again later.",
                ephemeral=True
            )
    
    async def back_callback(self, interaction: discord.Interaction):
        """Go back to the main investments view."""
        await interaction.response.defer(thinking=True)
        
        try:
            # Get updated user data and investments
            user_data = self.db.get_user(self.user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            user_investments = self.investment_system.get_user_investments(self.user_id)
            
            # Create main embed
            rainbow_color = random.randint(0, 0xFFFFFF)
            embed = discord.Embed(
                title="🏙️ Investment System",
                description="Manage your investments to earn passive income.",
                color=discord.Color(rainbow_color)
            )
            
            embed.add_field(
                name="💰 Your Coins",
                value=f"{user_coins:,} coins",
                inline=False
            )
            
            # Create info embed
            info_embed = discord.Embed(
                title="📊 Income System",
                description="Manage your properties to generate passive income. Each property has unique traits:",
                color=discord.Color(rainbow_color)
            )
            
            info_embed.add_field(
                name="⏱️ Hourly Returns",
                value=(
                    "🏪 Grocery Store: 10 coins/hr (200 max)\n"
                    "🛍️ Retail Shop: 25 coins/hr (300 max)\n"
                    "🍔 Restaurant: 60 coins/hr (400 max)\n"
                    "🏭 Private Company: 100 coins/hr (600 max)\n"
                    "🏘️ Real Estate: 50 coins/hr (300 max)"
                ),
                inline=False
            )
            
            info_embed.add_field(
                name="⚠️ Maintenance System",
                value=(
                    "Each property loses durability hourly:\n"
                    "🏪 Grocery Store: -3%/hr (Low risk)\n"
                    "🛍️ Retail Shop: -4%/hr (Medium risk)\n"
                    "🍔 Restaurant: -5%/hr (High risk)\n"
                    "🏭 Private Company: -3.5%/hr (Medium risk)\n"
                    "🏘️ Real Estate: -2.5%/hr (Low risk)"
                ),
                inline=False
            )
            
            info_embed.add_field(
                name="⚙️ Important Rules",
                value=(
                    "• Income stops when maintenance < 25%\n"
                    "• Risk events can occur when maintenance is low\n"
                    "• You need to maintain properties regularly to keep earning\n"
                    "• Max storage capacity means you must collect income regularly"
                ),
                inline=False
            )
            
            # Create view based on investments
            if user_investments:
                view = ManageInvestmentsView(self.investment_system, self.db, self.user_id, user_investments, info_embed)
                await interaction.followup.send(embed=embed, view=view)
            else:
                view = InvestmentPurchaseView(self.investment_system, self.db, self.user_id, info_embed)
                await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error returning to investments view: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while returning to the investments menu. Please try `/invest` again.",
                ephemeral=True
            )
            
    def make_callback(self, name):
        async def callback(interaction: discord.Interaction):

            investment = None
            for inv in self.user_investments:
                if inv.investment_name == name:
                    investment = inv
                    break
                    
            if not investment:
                await interaction.response.send_message(
                    f"Error finding your {name} business.",
                    ephemeral=True
                )
                return
                
            investment_type = self.investment_system.investments.get(name)
            if not investment_type:
                await interaction.response.send_message(
                    f"Error retrieving details for {name}.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🏢 {name} Management",
                description="Manage your business operations here.",
                color=discord.Color.blue()
            )

            if investment.risk_event:
                risk_status = investment.get_risk_status_text()
                status = f"🔥 {risk_status}"
            else:
                status = "✅ Operational"
                
            embed.add_field(
                name="Status",
                value=status,
                inline=True
            )

            maintenance_color = "🟢" if investment.maintenance >= 50 else "🟡" if investment.maintenance >= 25 else "🔴"
            embed.add_field(
                name="Maintenance",
                value=f"{maintenance_color} {investment.maintenance:.1f}%\nDrain: {investment_type.maintenance_drain}%/hr",
                inline=True
            )

            if investment.risk_event:
                income_status = "❌ STOPPED (Risk Event)"
            elif investment.maintenance < 25:
                income_status = "❌ STOPPED (Low Maintenance)"
            else:
                income_status = f"✅ {investment_type.hourly_return} coins/hr"
                
            embed.add_field(
                name="Income",
                value=income_status,
                inline=True
            )

            storage_percent = (investment.accumulated / investment_type.max_holding) * 100

            accumulated_display = int(investment.accumulated)
            
            embed.add_field(
                name="Storage",
                value=f"{accumulated_display:,}/{investment_type.max_holding} coins ({storage_percent:.1f}%)",
                inline=True
            )

            view = BusinessDetailView(self.investment_system, self.db, self.user_id, name)
            await interaction.response.edit_message(embed=embed, view=view)
            
        return callback
        
    async def collect_all_callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)
        
        total_collected = 0
        user_data = self.db.get_user(self.user_id)

        cooldowns = []

        message = await interaction.followup.send(
            "🧮 Counting coins from all your businesses...",
            ephemeral=True
        )

        active_businesses = []

        for inv in self.user_investments:
            if not inv.risk_event:

                coins = self.investment_system.collect_investment(self.user_id, inv.investment_name)
                
                if coins > 0:

                    total_collected += coins
                    active_businesses.append(inv.investment_name)  # Track which businesses provided income
                elif coins == -1:

                    cooldowns.append(inv.investment_name)

        if total_collected > 0:
            self.db.add_coins(self.user_id, user_data["username"], total_collected)

            frames = [
                f"💰 Collecting coins... `[⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 0%",
                f"💰 Collecting coins... `[🪙⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 10%",
                f"💰 Collecting coins... `[🪙🪙⬛⬛⬛⬛⬛⬛⬛⬛]` 20%",
                f"💰 Collecting coins... `[🪙🪙🪙⬛⬛⬛⬛⬛⬛⬛]` 30%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙⬛⬛⬛⬛⬛⬛]` 40%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙🪙⬛⬛⬛⬛⬛]` 50%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙⬛⬛⬛⬛]` 60%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙⬛⬛⬛]` 70%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙🪙⬛⬛]` 80%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙🪙🪙⬛]` 90%",
                f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙🪙🪙🪙]` 100%",
            ]

            for frame in frames:
                await asyncio.sleep(0.4)  # Slightly faster for collecting from multiple businesses
                await message.edit(content=frame)

            final_message = f"🤑 JACKPOT! You collected {total_collected:,} coins from your businesses! 💰"

            if active_businesses:
                businesses_text = ", ".join(active_businesses)
                final_message += f"\n\n✅ Income collected from: {businesses_text}"

            if cooldowns:
                if len(cooldowns) == 1:
                    final_message += f"\n\n⏱️ {cooldowns[0]} is on hourly cooldown and could not be collected."
                else:
                    business_list = ", ".join(cooldowns)
                    final_message += f"\n\n⏱️ The following businesses are on hourly cooldown and could not be collected: {business_list}"

            await asyncio.sleep(0.5)  # Slight delay before final message
            await message.edit(content=final_message)
        elif cooldowns:

            if len(cooldowns) == 1:
                await message.edit(
                    content=f"⏱️ {cooldowns[0]} is on hourly cooldown. You must wait 1 hour between collections."
                )
            else:
                business_list = ", ".join(cooldowns)
                await message.edit(
                    content=f"⏱️ All your businesses are on hourly cooldown and cannot be collected yet: {business_list}\nYou must wait 1 hour between collections."
                )
        else:
            await message.edit(
                content="There are no coins to collect at this time."
            )
            
    async def maintain_all_callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        total_maintenance_cost = 0
        maintenance_details = []
        businesses_to_maintain = []

        message = await interaction.followup.send(
            "🧰 Checking your businesses for maintenance needs...",
            ephemeral=True
        )
        
        for inv in self.user_investments:
            if not inv.risk_event and inv.maintenance < 100:
                investment_type = self.investment_system.investments.get(inv.investment_name)
                if not investment_type:
                    continue

                if inv.daily_income == 0:
                    inv.daily_income = investment_type.hourly_return * 24

                if inv.investment_name == "🏪 Grocery Store":
                    maintenance_cost = 40
                elif inv.investment_name == "🛍️ Retail Shop":
                    maintenance_cost = 80
                elif inv.investment_name == "🍔 Restaurant":
                    maintenance_cost = 160
                elif inv.investment_name == "🏭 Private Company" or inv.investment_name == "🏘️ Real Estate":
                    maintenance_cost = 200
                else:

                    maintenance_cost = int(inv.daily_income * 0.25)
                    if maintenance_cost < 10:  # Minimum cost of 10 coins
                        maintenance_cost = 10
                    
                total_maintenance_cost += maintenance_cost
                maintenance_details.append((inv, maintenance_cost))
                businesses_to_maintain.append(inv.investment_name)

        user_data = self.db.get_user(self.user_id)
        if not maintenance_details:
            await message.edit(content="No businesses need maintenance or all businesses have risk events.")
            return
            
        if user_data["coins"] < total_maintenance_cost:
            await message.edit(content=f"You don't have enough coins for maintenance. You need {total_maintenance_cost:,} coins total.")
            return

        frames = [
            f"🔧 Performing maintenance... `[⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 0%",
            f"🔧 Performing maintenance... `[🔧⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 10%",
            f"🔧 Performing maintenance... `[🔧🔧⬛⬛⬛⬛⬛⬛⬛⬛]` 20%",
            f"🔧 Performing maintenance... `[🔧🔧🔧⬛⬛⬛⬛⬛⬛⬛]` 30%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧⬛⬛⬛⬛⬛⬛]` 40%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧⬛⬛⬛⬛⬛]` 50%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧⬛⬛⬛⬛]` 60%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧⬛⬛⬛]` 70%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧⬛⬛]` 80%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧⬛]` 90%",
            f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧🔧]` 100%",
        ]

        for frame in frames:
            await asyncio.sleep(0.4)  # Slightly faster for multiple businesses
            await message.edit(content=frame)

        businesses_maintained = 0
        for inv, cost in maintenance_details:
            success = self.investment_system.maintain_investment(self.user_id, inv.investment_name)
            if success:
                businesses_maintained += 1

        self.investment_system.save_last_maintenance_time()
                
        if businesses_maintained > 0:
            self.db.add_coins(self.user_id, user_data["username"], -total_maintenance_cost)

            final_message = f"✅ Performed maintenance on {businesses_maintained} businesses (+25% maintenance on each) for {total_maintenance_cost:,} coins total."

            if businesses_to_maintain:
                businesses_text = ", ".join(businesses_to_maintain)
                final_message += f"\n\n🔧 Businesses maintained: {businesses_text}"
            
            await asyncio.sleep(0.5)  # Slight delay before final message
            await message.edit(content=final_message)
        else:
            await message.edit(content="Unable to perform maintenance on any businesses.")

class BusinessDetailView(discord.ui.View):
    """View with buttons for managing a specific investment."""
    
    def __init__(self, investment_system, db, user_id, business_name):
        super().__init__(timeout=120)
        self.investment_system = investment_system
        self.db = db
        self.user_id = user_id
        self.business_name = business_name

        has_risk_event = False
        risk_event_type = None

        user_investments = self.investment_system.get_user_investments(user_id)
        for inv in user_investments:
            if inv.investment_name == business_name and inv.risk_event:
                has_risk_event = True
                risk_event_type = inv.risk_event_type
                break

        if not has_risk_event:
            collect = discord.ui.Button(
                label="Collect Income",
                style=discord.ButtonStyle.success,
                custom_id="collect"
            )
            collect.callback = self.collect_callback
            self.add_item(collect)

        if not has_risk_event:
            maintain = discord.ui.Button(
                label="Maintain (+25%)",
                style=discord.ButtonStyle.primary,
                custom_id="maintain"
            )
            maintain.callback = self.maintain_callback
            self.add_item(maintain)

        if has_risk_event:

            repair_label = f"Repair {risk_event_type}" if risk_event_type else "Repair Business"
            repair = discord.ui.Button(
                label=repair_label,
                style=discord.ButtonStyle.danger,
                custom_id="repair"
            )
            repair.callback = self.repair_callback
            self.add_item(repair)

        sell = discord.ui.Button(
            label="Sell Business",
            style=discord.ButtonStyle.secondary,
            custom_id="sell"
        )
        sell.callback = self.sell_callback
        self.add_item(sell)

        back = discord.ui.Button(
            label="Back to All Businesses",
            style=discord.ButtonStyle.secondary,
            custom_id="back"
        )
        back.callback = self.back_callback
        self.add_item(back)
        
    async def collect_callback(self, interaction: discord.Interaction):
        try:

            await interaction.response.defer(ephemeral=True)
            
            user_data = self.db.get_user(self.user_id)
            coins = self.investment_system.collect_investment(self.user_id, self.business_name)
            
            if coins > 0:

                self.db.add_coins(self.user_id, user_data["username"], coins)

                message = await interaction.followup.send(
                    f"🧮 Counting coins from your {self.business_name}...",
                    ephemeral=True
                )

                frames = [
                    f"💰 Collecting coins... `[⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 0%",
                    f"💰 Collecting coins... `[🪙⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 10%",
                    f"💰 Collecting coins... `[🪙🪙⬛⬛⬛⬛⬛⬛⬛⬛]` 20%",
                    f"💰 Collecting coins... `[🪙🪙🪙⬛⬛⬛⬛⬛⬛⬛]` 30%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙⬛⬛⬛⬛⬛⬛]` 40%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙🪙⬛⬛⬛⬛⬛]` 50%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙⬛⬛⬛⬛]` 60%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙⬛⬛⬛]` 70%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙🪙⬛⬛]` 80%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙🪙🪙⬛]` 90%",
                    f"💰 Collecting coins... `[🪙🪙🪙🪙🪙🪙🪙🪙🪙🪙]` 100%",
                ]

                for frame in frames:
                    await asyncio.sleep(0.5)  # Wait 0.5 seconds between frames
                    await message.edit(content=frame)

                await asyncio.sleep(0.5)  # Slight delay before final message
                await message.edit(content=f"💰 Ka-ching! You collected {coins:,} coins from your {self.business_name}! 💰")
            elif coins == -1:

                user_investments = self.investment_system.get_user_investments(self.user_id)
                for inv in user_investments:
                    if inv.investment_name == self.business_name:
                        current_time = time.time()
                        last_collection_time = getattr(inv, 'last_collection_time', 0)
                        seconds_remaining = 3600 - (current_time - last_collection_time)
                        minutes_remaining = max(1, int(seconds_remaining / 60))
                        
                        await interaction.followup.send(
                            f"⏱️ Collection on cooldown! You must wait {minutes_remaining} more minutes before collecting again from your {self.business_name}.",
                            ephemeral=True
                        )
                        return

                await interaction.followup.send(
                    f"⏱️ Collection on cooldown! You must wait 1 hour between collections from your {self.business_name}.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"There are no coins to collect from your {self.business_name} at this time.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in collect_callback: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred while collecting income. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred while collecting income. Please try again.", ephemeral=True)
            except:
                pass
            
    async def maintain_callback(self, interaction: discord.Interaction):
        try:

            await interaction.response.defer(ephemeral=True)
            
            user_data = self.db.get_user(self.user_id)

            user_investments = self.investment_system.get_user_investments(self.user_id)
            investment = None
            for inv in user_investments:
                if inv.investment_name == self.business_name:
                    investment = inv
                    break
                    
            if not investment:
                await interaction.followup.send(
                    f"Unable to find your {self.business_name} business.",
                    ephemeral=True
                )
                return

            message = await interaction.followup.send(
                f"🧰 Checking maintenance needs for your {self.business_name}...",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in maintain_callback: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            except:
                pass
            return

        investment_type = self.investment_system.investments.get(self.business_name)
        if not investment_type:
            await message.edit(content=f"Error retrieving details for {self.business_name}.")
            return

        if investment.daily_income == 0:
            investment.daily_income = investment_type.hourly_return * 24

        if self.business_name == "🏪 Grocery Store":
            maintenance_cost = 40
        elif self.business_name == "🛍️ Retail Shop":
            maintenance_cost = 80
        elif self.business_name == "🍔 Restaurant":
            maintenance_cost = 160
        elif self.business_name == "🏭 Private Company" or self.business_name == "🏘️ Real Estate":
            maintenance_cost = 200
        else:

            maintenance_cost = int(investment.daily_income * 0.25)
            if maintenance_cost < 10:  # Minimum cost of 10 coins
                maintenance_cost = 10
            
        if investment.maintenance >= 50:
            if user_data["coins"] < maintenance_cost:
                await message.edit(content=f"You don't have enough coins for maintenance. You need {maintenance_cost:,} coins.")
                return

            frames = [
                f"🔧 Performing maintenance... `[⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 0%",
                f"🔧 Performing maintenance... `[🔧⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 10%",
                f"🔧 Performing maintenance... `[🔧🔧⬛⬛⬛⬛⬛⬛⬛⬛]` 20%",
                f"🔧 Performing maintenance... `[🔧🔧🔧⬛⬛⬛⬛⬛⬛⬛]` 30%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧⬛⬛⬛⬛⬛⬛]` 40%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧⬛⬛⬛⬛⬛]` 50%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧⬛⬛⬛⬛]` 60%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧⬛⬛⬛]` 70%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧⬛⬛]` 80%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧⬛]` 90%",
                f"🔧 Performing maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧🔧]` 100%",
            ]

            for frame in frames:
                await asyncio.sleep(0.5)  # Wait 0.5 seconds between frames
                await message.edit(content=frame)

            success = self.investment_system.maintain_investment(self.user_id, self.business_name)
            
            if success:
                self.db.add_coins(self.user_id, user_data["username"], -maintenance_cost)

                self.investment_system.save_last_maintenance_time()

                await asyncio.sleep(0.5)  # Slight delay before final message
                await message.edit(content=f"✅ Performed maintenance on your {self.business_name} (+25% maintenance) for {maintenance_cost:,} coins.\n\nMaintenance level is now {investment.maintenance}%.")

                await self.business_command_refresh(interaction)
            else:
                await message.edit(content=f"Unable to maintain your {self.business_name}. It may have a risk event or already be at 100% maintenance.")
        else:

            await message.edit(content=f"⚠️ Your {self.business_name} is at {investment.maintenance:.1f}% maintenance, which is below 50%. You need to fix this quickly before a risk event occurs! Maintenance will cost {maintenance_cost:,} coins.")

            frames = [
                f"🚨 Emergency maintenance... `[⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 0%",
                f"🚨 Emergency maintenance... `[🔧⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 10%",
                f"🚨 Emergency maintenance... `[🔧🔧⬛⬛⬛⬛⬛⬛⬛⬛]` 20%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧⬛⬛⬛⬛⬛⬛⬛]` 30%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧⬛⬛⬛⬛⬛⬛]` 40%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧🔧⬛⬛⬛⬛⬛]` 50%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧🔧🔧⬛⬛⬛⬛]` 60%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧🔧🔧🔧⬛⬛⬛]` 70%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧⬛⬛]` 80%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧⬛]` 90%",
                f"🚨 Emergency maintenance... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧🔧]` 100%",
            ]

            for frame in frames:
                await asyncio.sleep(0.3)  # Faster for emergency maintenance
                await message.edit(content=frame)

            success = self.investment_system.maintain_investment(self.user_id, self.business_name)
            
            if success:
                self.db.add_coins(self.user_id, user_data["username"], -maintenance_cost)

                self.investment_system.save_last_maintenance_time()

                await asyncio.sleep(0.5)  # Slight delay before final message
                await message.edit(content=f"✅ Performed emergency maintenance on your {self.business_name} (+25% maintenance) for {maintenance_cost:,} coins.\n\nMaintenance level is now {investment.maintenance}%.")

                await self.business_command_refresh(interaction)
            else:
                await message.edit(content=f"⚠️ Unable to maintain your {self.business_name}. It may have a risk event.")
            
    async def repair_callback(self, interaction: discord.Interaction):
        try:

            await interaction.response.defer(ephemeral=True)
            
            user_data = self.db.get_user(self.user_id)

            user_investments = self.investment_system.get_user_investments(self.user_id)
            investment = None
            for inv in user_investments:
                if inv.investment_name == self.business_name:
                    investment = inv
                    break
                    
            if not investment:
                await interaction.followup.send(
                    f"Unable to find your {self.business_name} business.",
                    ephemeral=True
                )
                return

            message = await interaction.followup.send(
                f"🔍 Inspecting your {self.business_name} for problems...",
                ephemeral=True
            )

            investment_type = self.investment_system.investments.get(self.business_name)
            if not investment_type:
                await message.edit(content=f"Error retrieving details for {self.business_name}.")
                return

            if not investment.risk_event:
                await message.edit(content=f"Your {self.business_name} doesn't need repairs.")
                return

            repair_cost = investment_type.hourly_return * 10
            if repair_cost < 100:  # Minimum cost of 100 coins
                repair_cost = 100
                
            risk_status_text = investment.get_risk_status_text()
            risk_type = investment.risk_event_type or "Unknown Issue"

            await message.edit(content=f"🔍 Problem found: {risk_type}\n\nYour {self.business_name} needs repairs due to {risk_status_text}. Repair cost: {repair_cost:,} coins.")
            await asyncio.sleep(1.5)  # Pause after diagnosis
            
            if user_data["coins"] < repair_cost:
                await message.edit(content=f"❌ You don't have enough coins to repair this business. You need {repair_cost:,} coins to fix the {risk_type}.")
                return

            frames = [
                f"🛠️ Repairing {risk_type}... `[⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 0%",
                f"🛠️ Repairing {risk_type}... `[🔧⬛⬛⬛⬛⬛⬛⬛⬛⬛]` 10%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧⬛⬛⬛⬛⬛⬛⬛⬛]` 20%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧⬛⬛⬛⬛⬛⬛⬛]` 30%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧⬛⬛⬛⬛⬛⬛]` 40%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧🔧⬛⬛⬛⬛⬛]` 50%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧🔧🔧⬛⬛⬛⬛]` 60%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧🔧🔧🔧⬛⬛⬛]` 70%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧🔧🔧🔧🔧⬛⬛]` 80%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧⬛]` 90%",
                f"🛠️ Repairing {risk_type}... `[🔧🔧🔧🔧🔧🔧🔧🔧🔧🔧]` 100%",
            ]

            for frame in frames:
                await asyncio.sleep(0.5)  # Wait 0.5 seconds between frames
                await message.edit(content=frame)

            success = self.investment_system.repair_investment(self.user_id, self.business_name)

            if success:
                self.db.add_coins(self.user_id, user_data["username"], -repair_cost)

                success_frames = []
                if "fire" in risk_type.lower():
                    success_frames = [
                        "🔥 Fire extinguished...",
                        "💨 Smoke clearing...",
                        "🧹 Cleaning up debris...",
                        "🔧 Rebuilding damaged section...",
                        "🪠 Fixing plumbing...",
                        "🔌 Rewiring electrical...",
                        "🎨 Repainting walls...",
                        "🧪 Safety inspection..."
                    ]
                elif "flood" in risk_type.lower():
                    success_frames = [
                        "💧 Draining water...",
                        "🧹 Mopping floors...",
                        "🌬️ Drying out walls...",
                        "🔧 Repairing water damage...",
                        "🪠 Fixing plumbing leaks...",
                        "🔌 Checking electrical safety...",
                        "🎨 Restoring damaged areas...",
                        "🧪 Treating for mold..."
                    ]
                elif "theft" in risk_type.lower() or "robbery" in risk_type.lower():
                    success_frames = [
                        "📋 Filing police report...",
                        "🔍 Investigating break-in...",
                        "📊 Inventorying losses...",
                        "🔐 Installing new locks...",
                        "📹 Setting up security cameras...",
                        "🚨 Adding alarm system...",
                        "🧰 Replacing stolen equipment...",
                        "🧪 Security testing..."
                    ]
                elif "infestation" in risk_type.lower() or "pest" in risk_type.lower():
                    success_frames = [
                        "🐜 Identifying pests...",
                        "🧪 Applying treatment...",
                        "🧹 Removing nests...",
                        "🔨 Sealing entry points...",
                        "🧽 Deep cleaning surfaces...",
                        "🧰 Setting preventative measures...",
                        "🔍 Inspecting for stragglers...",
                        "🧪 Final sanitation check..."
                    ]
                else:

                    success_frames = [
                        "🔍 Diagnosing issue...",
                        "📋 Creating repair plan...",
                        "🧰 Getting tools ready...",
                        "🔧 Making repairs...",
                        "🧪 Testing systems...",
                        "📊 Verifying operations...",
                        "🧹 Cleaning up...",
                        "✅ Final inspection..."
                    ]

                if success_frames:
                    for frame in success_frames:
                        await asyncio.sleep(0.3)  # Slightly faster for these frames
                        await message.edit(content=frame)

                await asyncio.sleep(0.5)  # Brief pause before final message
                await message.edit(content=f"✅ Solved the {risk_type} at your {self.business_name}! It is now operational again with 50% maintenance.")

                await self.business_command_refresh(interaction)
            else:
                await message.edit(content=f"❌ Unable to repair your {self.business_name}. The issue may be more severe than anticipated.")
        except Exception as e:
            logger.error(f"Error in repair_callback: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred while repairing. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred while repairing. Please try again.", ephemeral=True)
            except:
                pass
            
    async def sell_callback(self, interaction: discord.Interaction):
        try:

            user_data = self.db.get_user(self.user_id)
            investment_type = self.investment_system.investments.get(self.business_name)
            
            if not investment_type:

                await interaction.response.send_message(
                    f"Error retrieving details for {self.business_name}.",
                    ephemeral=True
                )
                return

            sell_price = investment_type.cost // 2

            confirm_view = ConfirmSellView(self.investment_system, self.db, self.user_id, self.business_name, sell_price)
            
            embed = discord.Embed(
                title="🏢 Sell Business Confirmation",
                description=f"Are you sure you want to sell your {self.business_name} for {sell_price} coins?\n\nThis action cannot be undone.",
                color=discord.Color.red()
            )
            
            await interaction.response.edit_message(embed=embed, view=confirm_view)
        except Exception as e:
            logger.error(f"Error in sell_callback: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred while preparing the sale. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred while preparing the sale. Please try again.", ephemeral=True)
            except:
                pass
        
    async def back_callback(self, interaction: discord.Interaction):
        await self.business_command_refresh(interaction)
        
    async def business_command_refresh(self, interaction: discord.Interaction):
        """Re-run the business command to refresh the view."""
        try:

            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
                
            user_id = str(interaction.user.id)
            user_data = self.db.get_user(user_id)

            user_investments = self.investment_system.get_user_investments(user_id)
            
            if not user_investments:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            content="You don't own any businesses yet. Use `/invest` to purchase one.",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.edit_message(
                            content="You don't own any businesses yet. Use `/invest` to purchase one.",
                            embed=None,
                            view=None
                        )
                except Exception as e:
                    logger.error(f"Error sending no businesses message: {e}")

                    try:
                        await interaction.followup.send(
                            content="You don't own any businesses yet. Use `/invest` to purchase one.",
                            ephemeral=True
                        )
                    except:
                        pass
                return

            embed = discord.Embed(
                title="🏢 Your Businesses",
                description="Here are your current investments and their status.",
                color=discord.Color.green()
            )

            for inv in user_investments:
                investment_type = self.investment_system.investments.get(inv.investment_name)
                if not investment_type:
                    continue

                if inv.risk_event:
                    status_emoji = "🔥"
                    status_text = inv.get_risk_status_text()
                elif inv.maintenance < 25:
                    status_emoji = "⚠️"
                    status_text = f"LOW MAINTENANCE ({inv.maintenance:.1f}%)"
                elif inv.maintenance < 50:
                    status_emoji = "⚠️"
                    status_text = f"Maintenance: {inv.maintenance:.1f}%"
                else:
                    status_emoji = "✅"
                    status_text = f"Maintenance: {inv.maintenance:.1f}%"

                storage_percent = (inv.accumulated / investment_type.max_holding) * 100

                accumulated_display = int(inv.accumulated)
                
                storage_text = f"Storage: {accumulated_display:,}/{investment_type.max_holding} coins ({storage_percent:.1f}%)"

                collect_status = "💰 Ready to collect!" if inv.accumulated > 0 else "🕒 Accumulating..."

                display_text = (
                    f"{status_text}\n"
                    f"{storage_text}\n"
                    f"Return: {investment_type.hourly_return} coins/hr\n"
                    f"Maintenance Drain: {investment_type.maintenance_drain}%/hr\n"
                    f"{collect_status}"
                )
                
                embed.add_field(
                    name=f"{status_emoji} {inv.investment_name}",
                    value=display_text,
                    inline=False
                )

            view = BusinessView(self.investment_system, self.db, user_id, user_investments)

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:

            import logging
            logger = logging.getLogger('investments')
            logger.error(f"Error in business_command_refresh: {e}")

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "An error occurred while refreshing your business view. Please try again with `/business`.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "An error occurred while refreshing your business view. Please try again with `/business`.",
                        ephemeral=True
                    )
            except:
                pass  # If we can't send a message, we've done our best

class ConfirmSellView(discord.ui.View):
    """View with confirmation buttons for selling a business."""
    
    def __init__(self, investment_system, db, user_id, business_name, sell_price):
        super().__init__(timeout=60)
        self.investment_system = investment_system
        self.db = db
        self.user_id = user_id
        self.business_name = business_name
        self.sell_price = sell_price

        confirm = discord.ui.Button(
            label="Confirm Sale",
            style=discord.ButtonStyle.danger,
            custom_id="confirm"
        )
        confirm.callback = self.confirm_callback
        self.add_item(confirm)

        cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel"
        )
        cancel.callback = self.cancel_callback
        self.add_item(cancel)
        
    async def confirm_callback(self, interaction: discord.Interaction):
        try:
            user_data = self.db.get_user(self.user_id)

            success = self.investment_system.remove_investment(self.user_id, self.business_name)
            
            if success:
                self.db.add_coins(self.user_id, user_data["username"], self.sell_price)
                await interaction.response.edit_message(
                    content=f"💸 CHA-CHING! You sold your {self.business_name} for {self.sell_price} coins! 💵",
                    embed=None,
                    view=None
                )
            else:
                await interaction.response.send_message(
                    f"Error selling your {self.business_name}. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in confirm_callback: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred while selling. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred while selling. Please try again.", ephemeral=True)
            except:
                pass
            
    async def cancel_callback(self, interaction: discord.Interaction):
        try:

            investment_type = self.investment_system.investments.get(self.business_name)
            
            embed = discord.Embed(
                title=f"🏢 {self.business_name} Management",
                description="Manage your business operations here.",
                color=discord.Color.blue()
            )

            investment = None
            for inv in self.investment_system.get_user_investments(self.user_id):
                if inv.investment_name == self.business_name:
                    investment = inv
                    break
                    
            if investment and investment_type:

                if investment.risk_event:
                    risk_status = investment.get_risk_status_text()
                    status = f"🔥 {risk_status}"
                else:
                    status = "✅ Operational"
                    
                embed.add_field(
                    name="Status",
                    value=status,
                    inline=True
                )

                maintenance_color = "🟢" if investment.maintenance >= 50 else "🟡" if investment.maintenance >= 25 else "🔴"
                embed.add_field(
                    name="Maintenance",
                    value=f"{maintenance_color} {investment.maintenance:.1f}%\nDrain: {investment_type.maintenance_drain}%/hr",
                    inline=True
                )

                if investment.risk_event:
                    income_status = "❌ STOPPED (Risk Event)"
                elif investment.maintenance < 25:
                    income_status = "❌ STOPPED (Low Maintenance)"
                else:
                    income_status = f"✅ {investment_type.hourly_return} coins/hr"
                    
                embed.add_field(
                    name="Income",
                    value=income_status,
                    inline=True
                )

                storage_percent = (investment.accumulated / investment_type.max_holding) * 100

                accumulated_display = int(investment.accumulated)
                
                embed.add_field(
                    name="Storage",
                    value=f"{accumulated_display:,}/{investment_type.max_holding} coins ({storage_percent:.1f}%)",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Error",
                    value="Could not retrieve business details.",
                    inline=False
                )
                
            view = BusinessDetailView(self.investment_system, self.db, self.user_id, self.business_name)
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error in cancel_callback: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred. Please use the /business command again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred. Please use the /business command again.", ephemeral=True)
            except:
                pass

class GiveBusinessView(discord.ui.View):
    """View with buttons for the business giving interface."""
    
    def __init__(self, modal):
        super().__init__(timeout=300)
        self.modal = modal

        button = discord.ui.Button(
            label="Give Business Form",
            style=discord.ButtonStyle.primary,
            emoji="🏢",
            custom_id="open_give_business_modal"
        )
        button.callback = self.button_callback
        self.add_item(button)

        list_button = discord.ui.Button(
            label="View Available Businesses",
            style=discord.ButtonStyle.secondary,
            emoji="📋",
            custom_id="view_available_businesses"
        )
        list_button.callback = self.view_businesses_callback
        self.add_item(list_button)
        
    async def button_callback(self, interaction: discord.Interaction):
        """Button callback to open the modal."""
        await interaction.response.send_modal(self.modal)
        
    async def view_businesses_callback(self, interaction: discord.Interaction):
        """Button callback to view available business types."""
        investment_list = "\n".join([f"• **{name}**" for name in self.modal.investment_system.investments.keys()])
        
        embed = discord.Embed(
            title="📋 Available Business Types",
            description="Here are all the businesses you can give to users:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Business Types",
            value=investment_list,
            inline=False
        )
        embed.add_field(
            name="Instructions",
            value="Click the 'Give Business Form' button to open the form. Copy and paste the exact business name from the list above.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GiveBusinessModal(discord.ui.Modal, title="Give Business"):
    """Modal for giving a business to a user."""
    
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user's ID (right-click user & Copy ID)",
        required=True
    )
    
    business_type = discord.ui.TextInput(
        label="Business Type",
        placeholder="Enter the business name (e.g., '🏪 Grocery Store')",
        required=True
    )
    
    def __init__(self, investment_system):
        super().__init__()
        self.investment_system = investment_system

        self.business_options = "\n".join([f"- {name}" for name in self.investment_system.investments.keys()])
        self.business_type.placeholder = f"Choose from: {', '.join(list(self.investment_system.investments.keys())[:2])}..."
        
    async def on_submit(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        try:

            target_user_id = self.user_id.value.strip()
            business_name = self.business_type.value.strip()

            try:
                target_user_id = str(int(target_user_id))  # Ensure it's a valid integer string
            except ValueError:
                await interaction.response.send_message(
                    "Invalid user ID. Please provide a valid Discord user ID.",
                    ephemeral=True
                )
                return

            target_user = interaction.guild.get_member(int(target_user_id))
            if not target_user:
                await interaction.response.send_message(
                    "User not found in this server. Please check the ID and try again.",
                    ephemeral=True
                )
                return

            if not any(business_name.lower() == b_name.lower() for b_name in self.investment_system.investments.keys()):

                closest_match = None
                for b_name in self.investment_system.investments.keys():
                    if business_name.lower() in b_name.lower() or b_name.lower() in business_name.lower():
                        closest_match = b_name
                        break
                
                if closest_match:
                    business_name = closest_match
                else:
                    await interaction.response.send_message(
                        f"❌ Business type '{business_name}' not found. Available types are:\n{self.business_options}",
                        ephemeral=True
                    )
                    return

            for b_name in self.investment_system.investments.keys():
                if business_name.lower() == b_name.lower():
                    business_name = b_name  # Use the exact case-sensitive name
                    break

            success, message = self.investment_system.give_investment(target_user_id, business_name)
            
            if success:

                try:
                    log_channel = interaction.client.get_channel(1352717796336996422)
                    if log_channel:
                        await log_channel.send(
                            f"📋 **Business Assignment**\n"
                            f"Admin: {interaction.user.name} (ID: {interaction.user.id})\n"
                            f"Recipient: {target_user.name} (ID: {target_user_id})\n"
                            f"Business: {business_name}\n"
                            f"Time: {discord.utils.format_dt(datetime.datetime.now())}"
                        )
                except Exception as e:
                    logger.error(f"Error sending business assignment log: {e}")
                
                embed = discord.Embed(
                    title="🎁 Business Given",
                    description=f"Successfully gave {business_name} to {target_user.mention}!",
                    color=discord.Color.green()
                )
                embed.set_footer(text="The user can now manage this business with /business")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"❌ Error: {message}\n\nAvailable businesses:\n{self.business_options}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in on_submit: {e}")
            try:
                await interaction.response.send_message(
                    "An error occurred while giving the business. Please try again.",
                    ephemeral=True
                )
            except:
                pass

async def setup(bot):
    await bot.add_cog(InvestmentsCog(bot))
    logger.info("Investments cog loaded")
