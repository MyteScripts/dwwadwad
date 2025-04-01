import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import asyncio
import random
import datetime
from datetime import timedelta
import logging
from typing import Dict, List, Optional, Tuple, Union
from database import Database
from income_breakdown import format_income_breakdown, get_property_income_contribution

def format_collection_cooldown(investment):
    """Format a string for the collection cooldown status.
    
    Args:
        investment: The investment object with a last_collect timestamp
        
    Returns:
        str: Formatted string showing cooldown status or ready to collect
    """
    if not hasattr(investment, 'last_collect') or not investment.last_collect:
        return "Ready to collect!"
        
    now = datetime.datetime.now()
    cooldown_end = investment.last_collect + timedelta(hours=1)
    
    if now >= cooldown_end:
        return "Ready to collect!"
    
    time_left = cooldown_end - now
    minutes = int(time_left.total_seconds() // 60)
    seconds = int(time_left.total_seconds() % 60)
    
    return f"Cooldown: {minutes}m {seconds}s remaining"

# Set up logging
logger = logging.getLogger('investment_system')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Define business investment categories with correct stats
LUXURY_PROPERTIES = {
    "🛒 Grocery Store": {
        "price": 1000,
        "hourly_income": 10,
        "max_accumulation": 120,
        "maintenance_cost": 50,
        "maintenance_decay": 5.0,
        "risk_factor": 0.2,
        "description": "A local grocery store serving the community with fresh produce and essentials.",
        "emoji": "🛒",
        "color": 0x2ECC71,
        "risk_events": ["Refrigeration failure", "Inventory spoilage", "Supply chain issues", "Pest infestation"],
        "image_url": "https://cdn.discordapp.com/attachments/1234567890/grocery.png"
    },
    "🏪 Shop": {
        "price": 1500,
        "hourly_income": 20,
        "max_accumulation": 240,
        "maintenance_cost": 100,
        "maintenance_decay": 8.0,
        "risk_factor": 0.3,
        "description": "A trendy retail shop in a popular shopping district.",
        "emoji": "🏪",
        "color": 0x3498DB,
        "risk_events": ["Shoplifting incident", "Display damage", "Heating/cooling failure", "Water leak"],
        "image_url": "https://cdn.discordapp.com/attachments/1234567890/retail.png"
    },
    "🍽️ Restaurant": {
        "price": 2300,
        "hourly_income": 35,
        "max_accumulation": 240,
        "maintenance_cost": 150,
        "maintenance_decay": 10.0,
        "risk_factor": 0.4,
        "description": "A popular restaurant known for its excellent cuisine and atmosphere.",
        "emoji": "🍽️",
        "color": 0xE74C3C,
        "risk_events": ["Kitchen fire", "Food safety violation", "Staff walkout", "Bad review crisis"],
        "image_url": "https://cdn.discordapp.com/attachments/1234567890/restaurant.png"
    },
    "🏢 Company": {
        "price": 3800,
        "hourly_income": 60,
        "max_accumulation": 600,
        "maintenance_cost": 150,
        "maintenance_decay": 15.0,
        "risk_factor": 0.4,
        "description": "A successful company with steady growth and reliable returns.",
        "emoji": "🏢",
        "color": 0x9B59B6,
        "risk_events": ["Legal dispute", "Key employee departure", "IT system failure", "Product recall"],
        "image_url": "https://cdn.discordapp.com/attachments/1234567890/company.png"
    },
    "🏘️ Real Estate": {
        "price": 5000,
        "hourly_income": 50,
        "max_accumulation": 300,
        "maintenance_cost": 80,
        "maintenance_decay": 2.5,
        "risk_factor": 0.2,
        "description": "A portfolio of residential and commercial properties generating steady rental income.",
        "emoji": "🏘️",
        "color": 0xF1C40F,
        "risk_events": ["Property damage", "Tenant issues", "Tax reassessment", "Market downturn"],
        "image_url": "https://cdn.discordapp.com/attachments/1234567890/realestate.png"
    },
    "🎯 Target": {
        "price": 4500,
        "hourly_income": 45,
        "max_accumulation": 400,
        "maintenance_cost": 120,
        "maintenance_decay": 7.5,
        "risk_factor": 0.3,
        "description": "A large retail chain with steady foot traffic and strong brand recognition.",
        "emoji": "🎯",
        "color": 0xE74C3C,
        "risk_events": ["Inventory shortages", "Security breach", "Compliance violation", "Customer complaint surge"],
        "image_url": "https://cdn.discordapp.com/attachments/1234567890/target.png"
    }
}

# Use the format_collection_cooldown function defined at the top of the file

class Investment:
    def __init__(self, property_name: str, purchase_time: datetime.datetime):
        self.property_name = property_name
        self.purchase_time = purchase_time
        self.maintenance = 100.0  # Start at 100%
        self.accumulated_income = 0
        self.last_update = datetime.datetime.now().timestamp()
        self.last_collect = datetime.datetime.now().timestamp()
        self.risk_event = False
        self.risk_event_type = None
        
    def to_dict(self):
        return {
            "property_name": self.property_name,
            "purchase_time": self.purchase_time.isoformat(),
            "maintenance": self.maintenance,
            "accumulated_income": self.accumulated_income,
            "last_update": self.last_update,
            "last_collect": self.last_collect,
            "risk_event": self.risk_event,
            "risk_event_type": self.risk_event_type
        }
        
    @classmethod
    def from_dict(cls, data):
        investment = cls(
            property_name=data["property_name"],
            purchase_time=datetime.datetime.fromisoformat(data["purchase_time"])
        )
        investment.maintenance = data["maintenance"]
        investment.accumulated_income = data["accumulated_income"]
        investment.last_update = data["last_update"]
        investment.last_collect = data.get("last_collect", investment.last_update)
        investment.risk_event = data.get("risk_event", False)
        investment.risk_event_type = data.get("risk_event_type", None)
        return investment


class InvestmentManager:
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.data_path = "data/luxury_properties.json"
        self.investments = {}  # {user_id: [Investment objects]}
        self.properties = LUXURY_PROPERTIES  # Our defined luxury properties
        self.load_data()
        self.update_task = None
        
    def load_data(self):
        """Load investment data from file."""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    
                for user_id, investments_data in data.items():
                    self.investments[user_id] = [Investment.from_dict(inv_data) for inv_data in investments_data]
                    
                logger.info(f"Loaded investment data for {len(self.investments)} users")
            else:
                logger.info("No investment data file found, starting fresh")
                self.investments = {}
                
        except Exception as e:
            logger.error(f"Error loading investment data: {e}", exc_info=True)
            self.investments = {}
            
    def save_data(self):
        """Save investment data to file."""
        try:
            data = {}
            for user_id, investments in self.investments.items():
                data[user_id] = [inv.to_dict() for inv in investments]
                
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=4)
                
            logger.info(f"Saved investment data for {len(self.investments)} users")
            
        except Exception as e:
            logger.error(f"Error saving investment data: {e}", exc_info=True)
            
    def get_user_properties(self, user_id: str) -> List[Investment]:
        """Get all properties for a user."""
        return self.investments.get(str(user_id), [])
        
    def get_property_details(self, property_name: str) -> dict:
        """Get property details from our catalog."""
        return self.properties.get(property_name, {})
        
    def purchase_property(self, user_id: str, property_name: str) -> Tuple[bool, str]:
        """User purchases a new property."""
        user_id = str(user_id)
        property_details = self.get_property_details(property_name)
        
        if not property_details:
            return False, f"Property {property_name} doesn't exist in our catalog."
            
        # Check if user has enough coins
        user_data = self.db.get_user(user_id)
        if not user_data:
            return False, "User not found in database."
            
        user_coins = user_data.get('coins', 0)
        price = property_details['price']
        
        if user_coins < price:
            return False, f"You don't have enough coins to purchase this property. You need {price:,} coins, but you only have {user_coins:,} coins."
            
        # Check if the user already owns this property
        user_investments = self.get_user_properties(user_id)
        if any(inv.property_name == property_name for inv in user_investments):
            return False, f"You already own {property_name}."
            
        # Purchase the property
        success = self.db.remove_coins(user_id, price)
        if not success:
            return False, "Failed to deduct coins from your account."
            
        # Add the property to user's portfolio
        if user_id not in self.investments:
            self.investments[user_id] = []
            
        self.investments[user_id].append(Investment(property_name, datetime.datetime.now()))
        self.save_data()
        
        return True, f"Successfully purchased {property_name} for {price:,} coins!"
        
    def sell_property(self, user_id: str, property_name: str) -> Tuple[bool, str, int]:
        """User sells a property, getting 70% of the original price back."""
        user_id = str(user_id)
        if user_id not in self.investments:
            return False, "You don't own any properties.", 0
            
        property_details = self.get_property_details(property_name)
        if not property_details:
            return False, f"Property {property_name} doesn't exist in our catalog.", 0
            
        # Find the property in user's investments
        user_investments = self.investments[user_id]
        investment = None
        for idx, inv in enumerate(user_investments):
            if inv.property_name == property_name:
                investment = inv
                break
                
        if not investment:
            return False, f"You don't own {property_name}.", 0
            
        # Calculate sell price (70% of original)
        price = property_details['price']
        sell_price = int(price * 0.7)
        
        # Remove the property
        self.investments[user_id].remove(investment)
        if not self.investments[user_id]:
            del self.investments[user_id]  # Clean up empty lists
            
        # Add coins to user
        success = self.db.add_coins(user_id, sell_price)
        if not success:
            # Put the property back if coins couldn't be added
            if user_id not in self.investments:
                self.investments[user_id] = []
            self.investments[user_id].append(investment)
            return False, "Failed to add coins to your account.", 0
            
        self.save_data()
        return True, f"Successfully sold {property_name} for {sell_price:,} coins (70% of original value).", sell_price
        
    def maintain_property(self, user_id: str, property_name: str) -> Tuple[bool, str]:
        """Perform maintenance on a property."""
        user_id = str(user_id)
        if user_id not in self.investments:
            return False, "You don't own any properties."
            
        property_details = self.get_property_details(property_name)
        if not property_details:
            return False, f"Property {property_name} doesn't exist in our catalog."
            
        # Find the property in user's investments
        user_investments = self.investments[user_id]
        investment = None
        for inv in user_investments:
            if inv.property_name == property_name:
                investment = inv
                break
                
        if not investment:
            return False, f"You don't own {property_name}."
            
        # Check if the property is under a risk event
        if investment.risk_event:
            return False, f"You need to repair {property_name} before maintaining it."
            
        # Check if maintenance is already at 100%
        if investment.maintenance >= 100:
            return False, f"{property_name} is already fully maintained."
            
        # Calculate maintenance cost
        maintenance_cost = property_details['maintenance_cost']
        
        # Check if user has enough coins
        user_data = self.db.get_user(user_id)
        if not user_data:
            return False, "User not found in database."
            
        user_coins = user_data.get('coins', 0)
        if user_coins < maintenance_cost:
            return False, f"You don't have enough coins to maintain this property. You need {maintenance_cost:,} coins, but you only have {user_coins:,} coins."
            
        # Perform maintenance
        success = self.db.remove_coins(user_id, maintenance_cost)
        if not success:
            return False, "Failed to deduct coins from your account."
            
        # Increase maintenance level (25-40% boost)
        boost = random.uniform(25, 40)
        investment.maintenance = min(100, investment.maintenance + boost)  # Cap at 100%
        self.save_data()
        
        return True, f"Successfully maintained {property_name} for {maintenance_cost:,} coins! Maintenance level increased by {boost:.1f}% to {investment.maintenance:.1f}%."
        
    def repair_property(self, user_id: str, property_name: str) -> Tuple[bool, str]:
        """Repair a property after a risk event."""
        user_id = str(user_id)
        if user_id not in self.investments:
            return False, "You don't own any properties."
            
        property_details = self.get_property_details(property_name)
        if not property_details:
            return False, f"Property {property_name} doesn't exist in our catalog."
            
        # Find the property in user's investments
        user_investments = self.investments[user_id]
        investment = None
        for inv in user_investments:
            if inv.property_name == property_name:
                investment = inv
                break
                
        if not investment:
            return False, f"You don't own {property_name}."
            
        # Check if the property is under a risk event
        if not investment.risk_event:
            return False, f"{property_name} doesn't need repair."
            
        # Calculate repair cost (2x maintenance cost)
        repair_cost = property_details['maintenance_cost'] * 2
        
        # Check if user has enough coins
        user_data = self.db.get_user(user_id)
        if not user_data:
            return False, "User not found in database."
            
        user_coins = user_data.get('coins', 0)
        if user_coins < repair_cost:
            return False, f"You don't have enough coins to repair this property. You need {repair_cost:,} coins, but you only have {user_coins:,} coins."
            
        # Perform repair
        success = self.db.remove_coins(user_id, repair_cost)
        if not success:
            return False, "Failed to deduct coins from your account."
            
        # Resolve risk event and set maintenance to 50%
        investment.risk_event = False
        investment.risk_event_type = None
        investment.maintenance = 50.0  # Start at 50% after repair
        self.save_data()
        
        return True, f"Successfully repaired {property_name} for {repair_cost:,} coins! The property is now operational with 50% maintenance."
        
    def collect_income(self, user_id: str, property_name: str) -> Tuple[bool, str, int]:
        """Collect accumulated income from a property."""
        user_id = str(user_id)
        if user_id not in self.investments:
            logger.error(f"User {user_id} not found in investments when collecting income from {property_name}")
            return False, "You don't own any properties.", 0
            
        property_details = self.get_property_details(property_name)
        if not property_details:
            logger.error(f"Property {property_name} not found in catalog when user {user_id} tried to collect income")
            return False, f"Property {property_name} doesn't exist in our catalog.", 0
            
        # Find the property in user's investments
        user_investments = self.investments[user_id]
        investment = None
        for inv in user_investments:
            if inv.property_name == property_name:
                investment = inv
                break
                
        if not investment:
            logger.error(f"User {user_id} doesn't own {property_name} but tried to collect income from it")
            return False, f"You don't own {property_name}.", 0
            
        # Check if the property is under a risk event
        if investment.risk_event:
            return False, f"{property_name} needs repair before you can collect income.", 0
            
        # Check if it's been at least one hour since last collection
        current_time = datetime.datetime.now().timestamp()
        if investment.last_collect:
            time_since_last_collect = current_time - investment.last_collect
            # Only enforce time limit if there's accumulated income
            if time_since_last_collect < 3600:  # 3600 seconds = 1 hour
                minutes_remaining = int((3600 - time_since_last_collect) / 60)
                return False, f"You can only collect income from {property_name} once per hour. Please wait {minutes_remaining} more minutes.", 0
            
        # Check if there's any income to collect - require at least 1 whole coin
        if investment.accumulated_income < 1:
            # Always reset to exactly 0 even if there's a fractional value
            investment.accumulated_income = 0
            return False, f"There's no income to collect from {property_name} yet.", 0
            
        # Collect the income - always round down to whole coins
        income = int(investment.accumulated_income)
        # Set to exactly 0, not a tiny fractional value
        investment.accumulated_income = 0
        investment.last_collect = current_time
        # Update the last_update timestamp to prevent maintenance decay upon collection
        investment.last_update = current_time
        
        try:
            # Add coins to user - using explicit try/except to catch any DB errors
            success = self.db.add_coins_simple(user_id, income)
            if not success:
                # Return the income if coins couldn't be added
                investment.accumulated_income = income
                logger.error(f"Failed to add {income} coins to user {user_id} when collecting from {property_name}")
                return False, "Failed to add coins to your account.", 0
                
            # Save to ensure we don't lose the update
            self.save_data()
            # Get the hourly income rate for the message
            hourly_rate = property_details.get('hourly_income', 0)
            logger.info(f"User {user_id} successfully collected {income} coins from {property_name} (hourly rate: {hourly_rate})")
            
            # Return message with both the collected amount and the hourly rate
            return True, f"Successfully collected {income:,} coins from {property_name}! (Rate: {hourly_rate:,} coins/hour)", income
            
        except Exception as e:
            # Revert the accumulated income change if there's an error
            investment.accumulated_income = income
            logger.error(f"Exception while collecting income for user {user_id} from {property_name}: {e}", exc_info=True)
            return False, "An error occurred while collecting income. Please try again.", 0
        
    def collect_all_income(self, user_id: str) -> Tuple[bool, str, int]:
        """Collect accumulated income from all properties."""
        user_id = str(user_id)
        if user_id not in self.investments or not self.investments[user_id]:
            logger.error(f"User {user_id} not found in investments when collecting all income")
            return False, "You don't own any properties.", 0
            
        user_investments = self.investments[user_id]
        total_collected = 0
        properties_collected = 0
        
        # Keep track of which investments had income for rollback
        investments_with_income = []
        original_amounts = []
        
        current_time = datetime.datetime.now().timestamp()
        
        for investment in user_investments:
            # Skip properties with risk events or no income
            if investment.risk_event or investment.accumulated_income < 1:
                # Always reset to exactly 0 even if there's a fractional value
                if investment.accumulated_income < 1 and investment.accumulated_income > 0:
                    investment.accumulated_income = 0
                continue
                
            # Skip properties that were collected less than an hour ago
            if investment.last_collect:
                time_since_last_collect = current_time - investment.last_collect
                if time_since_last_collect < 3600:  # 3600 seconds = 1 hour
                    continue
                
            # Collect the income
            income = int(investment.accumulated_income)
            investments_with_income.append(investment)
            original_amounts.append(income)
            
            investment.accumulated_income = 0
            investment.last_collect = current_time
            # Update the last_update timestamp to prevent maintenance decay upon collection
            investment.last_update = current_time
            total_collected += income
            properties_collected += 1
            
        # Check if there's no income to collect
        if total_collected <= 0:
            # Check if any properties are on cooldown
            cooldown_properties = []
            for investment in user_investments:
                if not investment.risk_event and investment.last_collect:
                    time_since_last_collect = current_time - investment.last_collect
                    if time_since_last_collect < 3600:  # 3600 seconds = 1 hour
                        minutes_remaining = int((3600 - time_since_last_collect) / 60)
                        cooldown_properties.append((investment.property_name, minutes_remaining))
            
            # If there are properties on cooldown, show that information
            if cooldown_properties:
                cooldown_msg = "\n".join([f"- {name}: {mins} minutes remaining" for name, mins in cooldown_properties])
                return False, f"Your properties are on cooldown. Please wait:\n{cooldown_msg}", 0
            else:
                # If no properties on cooldown, there's just no income
                return False, "There's no income to collect from any of your properties.", 0
        
        try:
            # Add coins to user
            success = self.db.add_coins_simple(user_id, total_collected)
            if not success:
                # Rollback the accumulated income changes
                for i, investment in enumerate(investments_with_income):
                    investment.accumulated_income = original_amounts[i]
                logger.error(f"Failed to add {total_collected} coins to user {user_id} in collect_all_income")
                return False, "Failed to add coins to your account.", 0
                
            # Save data to ensure we don't lose the update
            self.save_data()
            
            # Calculate total hourly income rate for all properties
            total_hourly_rate = 0
            for investment in user_investments:
                property_details = self.get_property_details(investment.property_name)
                if property_details and not investment.risk_event and investment.maintenance >= 25:
                    # Use base hourly income without maintenance factor
                    hourly_income = property_details.get('hourly_income', 0)
                    total_hourly_rate += hourly_income
                    logger.info(f"Adding {hourly_income} coins/hour from {investment.property_name} to total rate")
            
            logger.info(f"Total hourly rate calculated: {total_hourly_rate} coins/hour for user {user_id}")
                    
            logger.info(f"User {user_id} successfully collected {total_collected} coins from {properties_collected} properties (hourly rate: {total_hourly_rate})")
            return True, f"Successfully collected {total_collected:,} coins from {properties_collected} properties! (Total rate: {total_hourly_rate:,} coins/hour)", total_collected
            
        except Exception as e:
            # Rollback the accumulated income changes
            for i, investment in enumerate(investments_with_income):
                investment.accumulated_income = original_amounts[i]
            logger.error(f"Exception while collecting all income for user {user_id}: {e}", exc_info=True)
            return False, "An error occurred while collecting income. Please try again.", 0
        
    def maintain_all_properties(self, user_id: str) -> Tuple[bool, str, int]:
        """Perform maintenance on all properties that need it."""
        user_id = str(user_id)
        if user_id not in self.investments or not self.investments[user_id]:
            return False, "You don't own any properties.", 0
            
        user_investments = self.investments[user_id]
        total_cost = 0
        properties_maintained = 0
        
        # Calculate total maintenance cost for properties under 90%
        properties_to_maintain = []
        for investment in user_investments:
            if not investment.risk_event and investment.maintenance < 90:
                property_details = self.get_property_details(investment.property_name)
                if property_details:
                    properties_to_maintain.append((investment, property_details))
                    total_cost += property_details['maintenance_cost']
        
        if not properties_to_maintain:
            return False, "None of your properties need maintenance right now.", 0
            
        # Check if user has enough coins
        user_data = self.db.get_user(user_id)
        if not user_data:
            return False, "User not found in database.", 0
            
        user_coins = user_data.get('coins', 0)
        if user_coins < total_cost:
            return False, f"You don't have enough coins to maintain all properties. You need {total_cost:,} coins, but you only have {user_coins:,} coins.", 0
            
        # Perform maintenance on all properties
        success = self.db.remove_coins(user_id, total_cost)
        if not success:
            return False, "Failed to deduct coins from your account.", 0
            
        for investment, property_details in properties_to_maintain:
            # Increase maintenance level (25-40% boost)
            boost = random.uniform(25, 40)
            investment.maintenance = min(100, investment.maintenance + boost)  # Cap at 100%
            properties_maintained += 1
            
        self.save_data()
        
        return True, f"Successfully maintained {properties_maintained} properties for {total_cost:,} coins!", total_cost
        
    def format_time_difference(self, timestamp):
        """Format the time difference between now and a timestamp."""
        now = datetime.datetime.now().timestamp()
        diff = now - timestamp
        
        if diff < 60:
            return "just now"
        elif diff < 3600:
            minutes = int(diff // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff < 86400:
            hours = int(diff // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(diff // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
            
    def get_next_income_text(self, investment, property_details):
        """Calculate and return text about when next income will be available."""
        hourly_income = property_details.get('hourly_income', 0)
        max_accumulation = property_details.get('max_accumulation', 0)
        
        # If we're at max capacity
        if investment.accumulated_income >= max_accumulation:
            return "⚠️ At maximum capacity"
            
        # If maintenance is too low or there's a risk event
        if investment.maintenance < 25 or investment.risk_event:
            return "⚠️ Needs attention"
            
        # Calculate how long until max capacity
        remaining_capacity = max_accumulation - investment.accumulated_income
        hours_until_full = remaining_capacity / hourly_income
        
        # Format the time
        if hours_until_full <= 1:
            minutes = int(hours_until_full * 60)
            return f"⏳ Full in {minutes} minutes"
        else:
            hours = int(hours_until_full)
            return f"⏳ Full in {hours} hours"
            
    async def start_update_task(self):
        """Start background task to update properties."""
        self.update_task = self.bot.loop.create_task(self.property_updater())
        logger.info("Started property updater background task")
            
    async def property_updater(self):
        """Background task to update properties every hour, ensuring income is generated 
        even when the bot was offline by calculating time differences.
        """
        try:
            logger.info("Property updater task started")
            
            # Run immediately after startup to handle offline time
            try:
                logger.info("Running initial update to account for offline time...")
                users_updated, income_added = self.update_properties()
                self.save_data()
                logger.info(f"Initial update complete: {users_updated} users updated, {income_added:.2f} total income added")
                
                # Send maintenance reminders for properties needing attention
                await self.send_maintenance_reminders()
                
            except Exception as e:
                logger.error(f"Error in initial property update: {e}", exc_info=True)
            
            # Then run hourly on a schedule
            await asyncio.sleep(60)  # Short delay after initial update
            
            hour_counter = 0
            while True:
                try:
                    hour_counter += 1
                    logger.info(f"Running scheduled property update (hour {hour_counter})...")
                    users_updated, income_added = self.update_properties()
                    self.save_data()
                    logger.info(f"Hourly update complete: {users_updated} users updated, {income_added:.2f} total income added")
                    
                    # Send maintenance reminders periodically
                    if hour_counter % 4 == 0:  # Every 4 hours
                        await self.send_maintenance_reminders()
                        
                except Exception as e:
                    logger.error(f"Error in property updater task: {e}", exc_info=True)
                    
                # Update every hour (hourly income and maintenance)
                await asyncio.sleep(3600)
                
        except asyncio.CancelledError:
            logger.info("Property updater task cancelled")
            raise
        except Exception as e:
            logger.error(f"Unhandled exception in property updater: {e}", exc_info=True)
            
    async def send_maintenance_reminders(self):
        """Send reminders to users about properties with low maintenance."""
        for user_id, investments in self.investments.items():
            low_maintenance_properties = []
            risk_event_properties = []
            
            for investment in investments:
                if investment.risk_event:
                    risk_event_properties.append(investment.property_name)
                elif investment.maintenance < 30:
                    low_maintenance_properties.append(investment.property_name)
                    
            # Send DM if there are properties needing attention
            if low_maintenance_properties or risk_event_properties:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    if user:
                        embed = discord.Embed(
                            title="🏢 Property Management Alert",
                            description="Some of your luxury properties need attention!",
                            color=discord.Color.gold()
                        )
                        
                        if low_maintenance_properties:
                            embed.add_field(
                                name="⚠️ Low Maintenance",
                                value="\n".join(low_maintenance_properties),
                                inline=False
                            )
                            
                        if risk_event_properties:
                            embed.add_field(
                                name="🚨 Risk Events",
                                value="\n".join(risk_event_properties),
                                inline=False
                            )
                            
                        embed.set_footer(text="Use /business to manage your properties")
                        
                        await user.send(embed=embed)
                        logger.info(f"Sent maintenance reminder to user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending maintenance reminder to user {user_id}: {e}")
                    
    def update_properties(self):
        """Update all properties (accumulate income, decay maintenance, check for risk events).
        This function ensures income is accumulated hourly even when the bot was offline."""
        current_time = datetime.datetime.now().timestamp()
        users_updated = 0
        total_income_added = 0
        total_hours_processed = 0
        properties_updated = 0
        
        logger.info("Starting property update process...")
        
        for user_id, investments in list(self.investments.items()):  # Create a copy of items to modify safely
            user_total_income = 0
            
            for investment in investments:
                properties_updated += 1
                
                # Skip if there's a risk event
                if investment.risk_event:
                    continue
                    
                # Get property details
                property_details = self.get_property_details(investment.property_name)
                if not property_details:
                    continue
                    
                # Calculate time since last update
                time_diff = current_time - investment.last_update
                hours_passed = time_diff / 3600  # Convert to hours
                total_hours_processed += hours_passed
                
                # Log detailed information for debugging
                if hours_passed >= 1.0:
                    logger.info(f"Property {investment.property_name} for user {user_id} - Hours since last update: {hours_passed:.2f}")
                
                # Update maintenance (decay over time)
                decay_rate = property_details.get('maintenance_decay', 5.0)  # % per hour
                maintenance_decay = decay_rate * hours_passed
                old_maintenance = investment.maintenance
                investment.maintenance = max(0, investment.maintenance - maintenance_decay)
                
                # Update income (if maintenance is high enough)
                income_added = 0
                if investment.maintenance >= 25:
                    hourly_income = property_details.get('hourly_income', 0)
                    max_accumulation = property_details.get('max_accumulation', 0)
                    
                    # Instead of partial/fractional income, we add exact hourly rates for whole hours passed
                    # Calculate whole hours that have passed
                    whole_hours_passed = int(hours_passed)
                    
                    # Only add income if at least one hour has passed
                    if whole_hours_passed < 1:
                        logger.info(f"Not enough time ({hours_passed:.2f} hours) has passed to add income to {investment.property_name} for user {user_id}")
                        continue
                    
                    # Add exact hourly income for each full hour - maintenance only affects whether income is generated, not how much
                    income_to_add = hourly_income * whole_hours_passed
                    old_income = investment.accumulated_income
                    
                    # Cap at max accumulation
                    investment.accumulated_income = min(max_accumulation, investment.accumulated_income + income_to_add)
                    income_added = investment.accumulated_income - old_income
                    
                    # For tracking purposes
                    user_total_income += income_added
                    total_income_added += income_added
                    
                    # Log detailed income information
                    logger.info(f"Property {investment.property_name} for user {user_id}: Base income: {hourly_income}, " +
                                f"Maintenance: {investment.maintenance:.1f}%, " +
                                f"Added: {income_added} coins for {whole_hours_passed} full hours")
                    
                    # Log income generation for properties getting significant income
                    if income_added >= hourly_income:
                        logger.info(f"Added {income_added:.2f} coins to {investment.property_name} for user {user_id} (hourly rate: {hourly_income} coins)")
                    
                # Check for risk events (if maintenance is low)
                if not investment.risk_event and investment.maintenance < 30:
                    risk_factor = property_details.get('risk_factor', 0.3)
                    risk_chance = risk_factor * (1 - investment.maintenance / 100) * hours_passed / 24  # Higher chance with lower maintenance
                    
                    if random.random() < risk_chance:
                        investment.risk_event = True
                        risk_events = property_details.get('risk_events', ["Maintenance issue"])
                        investment.risk_event_type = random.choice(risk_events)
                        logger.info(f"Risk event triggered for {investment.property_name} (user {user_id}): {investment.risk_event_type}")
                
                # Always update the last_update timestamp
                investment.last_update = current_time
            
            if user_total_income > 0:
                users_updated += 1
                logger.info(f"User {user_id} gained total of {user_total_income:.2f} coins from {len(investments)} properties")
                
        logger.info(f"Property update complete: {properties_updated} properties for {len(self.investments)} users")
        logger.info(f"Added {total_income_added:.2f} coins total, processed {total_hours_processed:.2f} total hours")
        return users_updated, total_income_added
        
    def reset_all_accumulated_income(self):
        """Reset accumulated income for all users' properties to zero."""
        users_affected = 0
        properties_reset = 0
        
        for user_id, investments in self.investments.items():
            user_reset = False
            for investment in investments:
                if investment.accumulated_income > 0:
                    investment.accumulated_income = 0
                    properties_reset += 1
                    user_reset = True
                    
            if user_reset:
                users_affected += 1
                
        self.save_data()
        logger.info(f"Reset accumulated income for {properties_reset} properties belonging to {users_affected} users")
        return users_affected, properties_reset
        

class InvestmentCog(commands.Cog):
    """Commands for the luxury property investment system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.investment_manager = InvestmentManager(bot)
        self.db = Database()
        logger.info("Investment cog initialized")
        
    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Investment cog loaded")
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Start property updater task when bot is ready."""
        await self.investment_manager.start_update_task()
        logger.info("Started property updater from on_ready")
        
    # givebusiness command removed
    async def _removed_givebusiness(self):
        """Command removed"""
        pass
    
    @app_commands.command(
        name="hourlyincome",
        description="💰 Give users accumulated income based on their businesses (Admin only)"
    )
    @app_commands.describe(
        target="User to give accumulated income to (leave empty for all users)"
    )
    async def hourlyincome_command(self, interaction: discord.Interaction, target: Optional[discord.Member] = None):
        """Give users accumulated income based on their businesses (Admin only)."""
        # Check if user has admin permissions
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Run property update to accumulate income
            logger.info(f"Running property update via hourlyincome command from {interaction.user.id}")
            
            if target:
                # Update for a specific user
                user_id = str(target.id)
                if user_id not in self.investment_manager.investments or not self.investment_manager.investments[user_id]:
                    await interaction.followup.send(f"❌ {target.display_name} doesn't own any businesses.", ephemeral=True)
                    return
                    
                user_total_income = 0
                properties_updated = 0
                
                # Get current time
                current_time = datetime.datetime.now().timestamp()
                
                # Process each property for this user
                for investment in self.investment_manager.investments[user_id]:
                    if investment.risk_event:
                        continue  # Skip properties with risk events
                        
                    property_details = self.investment_manager.get_property_details(investment.property_name)
                    if not property_details:
                        continue
                        
                    hours_passed = (current_time - investment.last_update) / 3600
                    if hours_passed < 0.1:  # Require at least 6 minutes to have passed
                        continue
                        
                    # Extract property details
                    hourly_income = property_details.get('hourly_income', 0)
                    max_accumulation = property_details.get('max_accumulation', hourly_income * 24)
                    
                    # Calculate whole hours that have passed
                    whole_hours_passed = int(hours_passed)
                    
                    # Always add at least 1 hour of income when admin uses hourlyincome command
                    if whole_hours_passed == 0:
                        whole_hours_passed = 1
                        
                    # Add exact hourly income for each full hour
                    income_to_add = hourly_income * whole_hours_passed
                    old_income = investment.accumulated_income
                    
                    # Add income to property accumulation instead of directly to user balance
                    # Cap at maximum accumulation
                    investment.accumulated_income = min(max_accumulation, old_income + income_to_add)
                    income_added = investment.accumulated_income - old_income
                    
                    # For tracking purposes
                    user_total_income += income_added
                    properties_updated += 1
                    
                    # Update the last_update timestamp
                    investment.last_update = current_time
                
                self.investment_manager.save_data()
                
                # Always give at least a small hourly income
                if properties_updated == 0:
                    # Find eligible businesses that could generate income
                    eligible_properties = 0
                    bonus_income = 0
                    
                    for investment in self.investment_manager.investments[user_id]:
                        if not investment.risk_event:
                            property_details = self.investment_manager.get_property_details(investment.property_name)
                            if property_details:
                                hourly_income = property_details.get('hourly_income', 0)
                                bonus_income += hourly_income
                                eligible_properties += 1
                                # Update the last_update timestamp
                                investment.last_update = current_time
                    
                    if eligible_properties > 0:
                        # Add income to properties accumulation for each eligible property
                        for investment in self.investment_manager.investments[user_id]:
                            if not investment.risk_event:
                                property_details = self.investment_manager.get_property_details(investment.property_name)
                                if property_details:
                                    hourly_income = property_details.get('hourly_income', 0)
                                    max_accumulation = property_details.get('max_accumulation', hourly_income * 24)
                                    # Add 1 hour of income to accumulation
                                    old_income = investment.accumulated_income
                                    investment.accumulated_income = min(max_accumulation, old_income + hourly_income)
                        
                        user_total_income = bonus_income
                        properties_updated = eligible_properties
                        self.investment_manager.save_data()
                    
                # Always show success message with whatever income was added to accumulation
                await interaction.followup.send(
                    f"✅ Successfully added {user_total_income:,.0f} coins to {target.display_name}'s properties accumulation.\nThey can collect this income using the `/business` command.",
                    ephemeral=True
                )
            else:
                # Update for all users
                users_updated = 0
                total_income_added = 0
                
                # Process all users with the same code as for single user
                for user_id, investments in list(self.investment_manager.investments.items()):
                    user_total_income = 0
                    properties_updated = 0
                    
                    # Get current time
                    current_time = datetime.datetime.now().timestamp()
                    
                    # Process each property for this user
                    for investment in investments:
                        if investment.risk_event:
                            continue  # Skip properties with risk events
                            
                        property_details = self.investment_manager.get_property_details(investment.property_name)
                        if not property_details:
                            continue
                            
                        hours_passed = (current_time - investment.last_update) / 3600
                        if hours_passed < 0.1:  # Require at least 6 minutes to have passed
                            continue
                            
                        # Extract property details
                        hourly_income = property_details.get('hourly_income', 0)
                        max_accumulation = property_details.get('max_accumulation', hourly_income * 24)
                        
                        # Calculate whole hours that have passed
                        whole_hours_passed = int(hours_passed)
                        
                        # Always add at least 1 hour of income when admin uses hourlyincome command
                        if whole_hours_passed == 0:
                            whole_hours_passed = 1
                            
                        # Add exact hourly income for each full hour
                        income_to_add = hourly_income * whole_hours_passed
                        old_income = investment.accumulated_income
                        
                        # Add income to property accumulation instead of directly to user balance
                        # Cap at maximum accumulation
                        investment.accumulated_income = min(max_accumulation, old_income + income_to_add)
                        income_added = investment.accumulated_income - old_income
                        
                        # For tracking purposes
                        user_total_income += income_added
                        properties_updated += 1
                        
                        # Update the last_update timestamp
                        investment.last_update = current_time
                    
                    if user_total_income > 0:
                        users_updated += 1
                        total_income_added += user_total_income
                
                self.investment_manager.save_data()
                
                await interaction.followup.send(
                    f"✅ Successfully added {total_income_added:,.0f} coins to {users_updated} users' property accumulations.\nThey can collect this income using the `/business` command.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in hourlyincome command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(
        name="reset_properties",
        description="🏢 Reset all property income accumulation (Admin only)"
    )
    async def reset_properties(self, interaction: discord.Interaction):
        """Reset accumulated income for all users. Admin only command."""
        # Check if user has admin permissions
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            users_affected, properties_reset = self.investment_manager.reset_all_accumulated_income()
            
            await interaction.followup.send(
                f"✅ Successfully reset accumulated income for {properties_reset} properties belonging to {users_affected} users.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in reset_properties command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while resetting properties. Please try again later.",
                ephemeral=True
            )
            
    # edit_property command removed
            
    # add_property command removed
            
    # invest command removed
    async def _removed_invest(self):
        """Command removed"""
        pass
            
    # business command removed
    async def _removed_business(self):
        """Command removed"""
        pass


class PropertyCatalogView(discord.ui.View):
    """View with buttons for browsing and purchasing properties."""
    
    def __init__(self, investment_manager, db, user_id, owned_properties):
        super().__init__(timeout=180)
        self.investment_manager = investment_manager
        self.db = db
        self.user_id = user_id
        self.owned_properties = owned_properties
        self.current_page = 0
        self.properties_per_page = 3
        self.property_list = list(LUXURY_PROPERTIES.items())
        self.total_pages = (len(self.property_list) + self.properties_per_page - 1) // self.properties_per_page
        
        # Add navigation buttons
        self.add_item(discord.ui.Button(label="Previous", custom_id="prev_page", style=discord.ButtonStyle.secondary, disabled=True))
        self.add_item(discord.ui.Button(label="Next", custom_id="next_page", style=discord.ButtonStyle.primary, disabled=self.total_pages <= 1))
        
        # Initialize with first page
        self.update_property_buttons()
        
    def update_property_buttons(self):
        """Update property buttons for current page."""
        # Remove existing property buttons
        for item in list(self.children):
            if item.custom_id not in ["prev_page", "next_page"]:
                self.remove_item(item)
                
        # Get properties for current page
        start_idx = self.current_page * self.properties_per_page
        end_idx = min(start_idx + self.properties_per_page, len(self.property_list))
        page_properties = self.property_list[start_idx:end_idx]
        
        # Add property buttons
        for property_name, details in page_properties:
            is_owned = property_name in self.owned_properties
            # Create a unique ID for this property button
            unique_id = f"property_catalog_{self.user_id}_{details['price']}_{page_properties.index((property_name, details))}"
                
            button = discord.ui.Button(
                label=f"{details['emoji']} {details.get('name', property_name)}",
                custom_id=unique_id,
                style=discord.ButtonStyle.success if is_owned else discord.ButtonStyle.primary,
                disabled=is_owned,
                row=1
            )
            button.callback = self.make_property_callback(property_name, details)
            self.add_item(button)
            
        # Update navigation buttons
        for item in self.children:
            if item.custom_id == "prev_page":
                item.disabled = self.current_page == 0
                item.callback = self.prev_page_callback
            elif item.custom_id == "next_page":
                item.disabled = self.current_page >= self.total_pages - 1
                item.callback = self.next_page_callback
                
    def make_property_callback(self, property_name, property_details):
        async def callback(interaction: discord.Interaction):
            # Create property embed
            embed = discord.Embed(
                title=f"{property_details['emoji']} {property_name}",
                description=property_details['description'],
                color=property_details['color']
            )
            
            embed.add_field(
                name="💰 Purchase Price",
                value=f"{property_details['price']:,} coins",
                inline=True
            )
            
            # Calculate collection time info for owned properties
            owned_property = None
            for inv in self.investment_manager.get_user_properties(self.user_id):
                if inv.property_name == property_name:
                    owned_property = inv
                    break
                    
            income_text = f"{property_details['hourly_income']:,} coins/hr"
            
            # Add cooldown info if they own this property
            if owned_property:
                cooldown_text = format_collection_cooldown(owned_property)
                if cooldown_text:
                    income_text += f"\n{cooldown_text}"
                    
            embed.add_field(
                name="💵 Hourly Income",
                value=income_text,
                inline=True
            )
            
            embed.add_field(
                name="📦 Max Storage",
                value=f"{property_details['max_accumulation']:,} coins",
                inline=True
            )
            
            embed.add_field(
                name="🛠️ Maintenance",
                value=f"Cost: {property_details['maintenance_cost']:,} coins\nDecay: {property_details['maintenance_decay']}%/hr",
                inline=True
            )
            
            embed.add_field(
                name="⚠️ Risk Factor",
                value=f"{int(property_details['risk_factor'] * 100)}%",
                inline=True
            )
            
            embed.add_field(
                name="💸 Resale Value",
                value=f"{int(property_details['price'] * 0.7):,} coins (70%)",
                inline=True
            )
            
            # Create purchase confirmation view
            view = PropertyPurchaseView(self.investment_manager, self.user_id, property_name, property_details, self)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        return callback
        
    async def prev_page_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_property_buttons()
            
            # Create catalog embed
            user_data = self.db.get_user(self.user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            embed = discord.Embed(
                title="🏙️ Luxury Property Investments",
                description=f"Browse our exclusive selection of high-end investment opportunities (Page {self.current_page + 1}/{self.total_pages}).\n\n**Why invest?**\n• Earn passive income every hour\n• Build a diverse portfolio of luxury assets\n• Compete for the title of wealthiest investor",
                color=0xE6B325
            )
            
            embed.add_field(
                name="💰 Your Investment Capital",
                value=f"{user_coins:,} coins available",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
    async def next_page_callback(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_property_buttons()
            
            # Create catalog embed
            user_data = self.db.get_user(self.user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            embed = discord.Embed(
                title="🏙️ Luxury Property Investments",
                description=f"Browse our exclusive selection of high-end investment opportunities (Page {self.current_page + 1}/{self.total_pages}).\n\n**Why invest?**\n• Earn passive income every hour\n• Build a diverse portfolio of luxury assets\n• Compete for the title of wealthiest investor",
                color=0xE6B325
            )
            
            embed.add_field(
                name="💰 Your Investment Capital",
                value=f"{user_coins:,} coins available",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)


class PropertyPurchaseView(discord.ui.View):
    """View with buttons for confirming a property purchase."""
    
    def __init__(self, investment_manager, user_id, property_name, property_details, catalog_view):
        super().__init__(timeout=60)
        self.investment_manager = investment_manager
        self.user_id = user_id
        self.property_name = property_name
        self.property_details = property_details
        self.catalog_view = catalog_view
        
        # Add buttons with direct callbacks
        purchase_button = discord.ui.Button(label="Purchase", style=discord.ButtonStyle.success, row=0)
        purchase_button.callback = self.purchase_callback
        self.add_item(purchase_button)
        
        back_button = discord.ui.Button(label="Back to Catalog", style=discord.ButtonStyle.secondary, row=0)
        back_button.callback = self.back_callback
        self.add_item(back_button)
                
    async def purchase_callback(self, interaction: discord.Interaction):
        try:
            success, message = self.investment_manager.purchase_property(self.user_id, self.property_name)
            
            if success:
                embed = discord.Embed(
                    title="🎉 Purchase Successful",
                    description=message,
                    color=0x2ECC71
                )
                
                embed.add_field(
                    name="Next Steps",
                    value="Use `/business` command to manage your new property and collect income.",
                    inline=False
                )
                
                await interaction.response.edit_message(embed=embed, view=None)
                
            else:
                embed = discord.Embed(
                    title="❌ Purchase Failed",
                    description=message,
                    color=0xE74C3C
                )
                
                # Add a back button
                view = discord.ui.View(timeout=30)
                back_button = discord.ui.Button(label="Back to Catalog", style=discord.ButtonStyle.secondary)
                back_button.callback = self.back_callback
                view.add_item(back_button)
                
                await interaction.response.edit_message(embed=embed, view=view)
                
        except Exception as e:
            logger.error(f"Error in purchase_callback: {e}", exc_info=True)
            
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred during the purchase. Please try again later.",
                color=0xE74C3C
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
    async def back_callback(self, interaction: discord.Interaction):
        try:
            # Update the catalog view (in case user purchased something)
            user_data = self.catalog_view.db.get_user(self.user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            # Update owned properties
            user_properties = self.investment_manager.get_user_properties(self.user_id)
            self.catalog_view.owned_properties = [prop.property_name for prop in user_properties]
            self.catalog_view.update_property_buttons()
            
            embed = discord.Embed(
                title="🏙️ Luxury Property Investments",
                description=f"Browse our exclusive selection of high-end investment opportunities (Page {self.catalog_view.current_page + 1}/{self.catalog_view.total_pages}).\n\n**Why invest?**\n• Earn passive income every hour\n• Build a diverse portfolio of luxury assets\n• Compete for the title of wealthiest investor",
                color=0xE6B325
            )
            
            embed.add_field(
                name="💰 Your Investment Capital",
                value=f"{user_coins:,} coins available",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self.catalog_view)
            
        except Exception as e:
            logger.error(f"Error in back_callback: {e}", exc_info=True)
            
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try the command again.",
                color=0xE74C3C
            )
            
            await interaction.response.edit_message(embed=embed, view=None)


class PortfolioManagementView(discord.ui.View):
    """View with buttons for managing property portfolio."""
    
    def __init__(self, investment_manager, user_id, portfolio_embed):
        super().__init__(timeout=180)
        self.investment_manager = investment_manager
        self.user_id = user_id
        self.portfolio_embed = portfolio_embed
        self.properties_page = 0
        self.properties_per_page = 3
        
        # Get user properties
        self.user_properties = self.investment_manager.get_user_properties(user_id)
        self.total_pages = (len(self.user_properties) + self.properties_per_page - 1) // self.properties_per_page
        
        # Add buttons explicitly with their callbacks
        collect_all = discord.ui.Button(label="💰 Collect All Income", style=discord.ButtonStyle.success, row=0)
        collect_all.callback = self.collect_all_callback
        self.add_item(collect_all)
        
        maintain_all = discord.ui.Button(label="🛠️ Maintain All", style=discord.ButtonStyle.primary, row=0)
        maintain_all.callback = self.maintain_all_callback
        self.add_item(maintain_all)
        
        # Add navigation buttons if needed
        if self.total_pages > 1:
            prev_page = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=True, row=2)
            prev_page.callback = self.prev_page_callback
            self.add_item(prev_page)
            
            next_page = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, row=2)
            next_page.callback = self.next_page_callback
            self.add_item(next_page)
            
        # Update view with property buttons
        self.update_property_buttons()
                
    def update_property_buttons(self):
        """Update property buttons for current page."""
        # Remove existing property buttons
        for item in list(self.children):
            if not item.custom_id.startswith(("collect_all", "maintain_all", "prev_page", "next_page")):
                self.remove_item(item)
                
        # Get properties for current page
        start_idx = self.properties_page * self.properties_per_page
        end_idx = min(start_idx + self.properties_per_page, len(self.user_properties))
        page_properties = self.user_properties[start_idx:end_idx]
        
        # Add property buttons
        for investment in page_properties:
            property_details = self.investment_manager.get_property_details(investment.property_name)
            if property_details:
                button_style = discord.ButtonStyle.danger if investment.risk_event else discord.ButtonStyle.primary
                # Create a truly unique ID for each property based on its position in the list
                safe_id = f"property_{self.user_id}_{property_details['price']}_{page_properties.index(investment)}"
                
                # Just use a simpler label with emoji that doesn't try to parse the name
                button = discord.ui.Button(
                    label=f"{property_details['emoji']} {property_details.get('name', investment.property_name)}",
                    custom_id=safe_id,
                    style=button_style
                )
                button.callback = self.make_property_callback(investment, property_details)
                self.add_item(button)
                
        # Update navigation buttons
        for item in self.children:
            if item.custom_id == "prev_page":
                item.disabled = self.properties_page == 0
            elif item.custom_id == "next_page":
                item.disabled = self.properties_page >= self.total_pages - 1
                
    def make_property_callback(self, investment, property_details):
        async def callback(interaction: discord.Interaction):
            # Create property details embed
            embed = discord.Embed(
                title=f"{property_details['emoji']} {investment.property_name}",
                description=property_details['description'],
                color=property_details['color']
            )
            
            # Use our helper function to get income contribution details
            income_percentage, total_hourly_income, property_count, property_type = get_property_income_contribution(
                investment, 
                self.investment_manager.get_user_properties(self.user_id),
                self.investment_manager
            )
                
            embed.add_field(
                name="💰 Financial Details",
                value=f"**Purchase Price:** {property_details['price']:,} coins\n**Resale Value:** {int(property_details['price'] * 0.7):,} coins (70%)\n**Hourly Income:** {property_details['hourly_income']:,} coins/hr\n**Income Contribution:** {income_percentage:.1f}% of total\n**Similar Properties:** {property_count}x {property_type}",
                inline=False
            )
            
            # Status info
            maintenance_color = "🟢" if investment.maintenance >= 70 else "🟡" if investment.maintenance >= 30 else "🔴"
            income_status = "🛑 Stopped" if investment.maintenance < 25 or investment.risk_event else "✅ Active"
            
            max_accumulation = property_details.get('max_accumulation', 0)
            capacity_pct = min(100, int(investment.accumulated_income / max_accumulation * 100)) if max_accumulation > 0 else 0
            capacity_color = "🟢" if capacity_pct < 70 else "🟡" if capacity_pct < 90 else "🔴"
            
            embed.add_field(
                name="📊 Current Status",
                value=f"**Maintenance:** {maintenance_color} {investment.maintenance:.1f}%\n**Income Status:** {income_status}\n**Storage Capacity:** {capacity_color} {capacity_pct}% full\n**Income Rate:** {property_details['hourly_income']:,} coins/hr\n**Accumulated:** {int(investment.accumulated_income):,} coins{format_collection_cooldown(investment)}",
                inline=False
            )
            
            # Risk event info if applicable
            if investment.risk_event:
                embed.add_field(
                    name="🚨 Risk Event",
                    value=f"**Type:** {investment.risk_event_type}\n**Repair Cost:** {property_details['maintenance_cost'] * 2:,} coins",
                    inline=False
                )
                
            # Purchase date
            embed.add_field(
                name="📅 Owned Since",
                value=investment.purchase_time.strftime("%B %d, %Y"),
                inline=False
            )
            
            # Create property management view
            view = PropertyManagementView(self.investment_manager, self.user_id, investment, property_details, self)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        return callback
        
    async def collect_all_callback(self, interaction: discord.Interaction):
        success, message, amount = self.investment_manager.collect_all_income(self.user_id)
        
        if success:
            embed = discord.Embed(
                title="💰 Income Collected",
                description=message,
                color=0x2ECC71
            )
        else:
            embed = discord.Embed(
                title="❌ Collection Failed",
                description=message,
                color=0xE74C3C
            )
            
        # Add a back button
        view = discord.ui.View(timeout=30)
        back_button = discord.ui.Button(label="Back to Portfolio", custom_id="back_to_portfolio", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_to_portfolio_callback
        view.add_item(back_button)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def maintain_all_callback(self, interaction: discord.Interaction):
        success, message, cost = self.investment_manager.maintain_all_properties(self.user_id)
        
        if success:
            embed = discord.Embed(
                title="🛠️ Maintenance Complete",
                description=message,
                color=0x3498DB
            )
        else:
            embed = discord.Embed(
                title="❌ Maintenance Failed",
                description=message,
                color=0xE74C3C
            )
            
        # Add a back button
        view = discord.ui.View(timeout=30)
        back_button = discord.ui.Button(label="Back to Portfolio", custom_id="back_to_portfolio", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_to_portfolio_callback
        view.add_item(back_button)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def prev_page_callback(self, interaction: discord.Interaction):
        if self.properties_page > 0:
            self.properties_page -= 1
            self.update_property_buttons()
            await interaction.response.edit_message(view=self)
            
    async def next_page_callback(self, interaction: discord.Interaction):
        if self.properties_page < self.total_pages - 1:
            self.properties_page += 1
            self.update_property_buttons()
            await interaction.response.edit_message(view=self)
            
    async def back_to_portfolio_callback(self, interaction: discord.Interaction):
        # Refresh user properties and recalculate portfolio stats
        self.user_properties = self.investment_manager.get_user_properties(self.user_id)
        
        # Update the portfolio view
        self.total_pages = (len(self.user_properties) + self.properties_per_page - 1) // self.properties_per_page
        self.properties_page = 0  # Reset to first page
        
        # Create a fresh portfolio management view
        new_view = PortfolioManagementView(self.investment_manager, self.user_id, self.portfolio_embed)
        
        # Refresh portfolio embed
        user_data = new_view.investment_manager.db.get_user(self.user_id)
        user_coins = user_data.get('coins', 0) if user_data else 0
        
        # Calculate portfolio stats
        total_value = 0
        total_hourly_income = 0
        total_accumulated = 0
        properties_at_risk = 0
        properties_full = 0
        
        for investment in self.user_properties:
            property_details = self.investment_manager.get_property_details(investment.property_name)
            if property_details:
                total_value += property_details.get('price', 0) * 0.7  # Resale value
                
                if not investment.risk_event and investment.maintenance >= 25:
                    # Maintenance only affects whether income is generated, not how much
                    total_hourly_income += property_details.get('hourly_income', 0)
                    
                total_accumulated += investment.accumulated_income
                
                if investment.risk_event:
                    properties_at_risk += 1
                    
                max_accumulation = property_details.get('max_accumulation', 0)
                if investment.accumulated_income >= max_accumulation * 0.9:
                    properties_full += 1
                    
        embed = discord.Embed(
            title="🏙️ Your Luxury Property Portfolio",
            description=f"You own {len(self.user_properties)} exclusive properties with a total resale value of {int(total_value):,} coins.",
            color=0x3498DB
        )
        
        # Use our helper function to create a detailed income breakdown
        income_details = format_income_breakdown(
            self.user_properties, 
            self.investment_manager, 
            user_coins, 
            total_hourly_income, 
            total_accumulated
        )
        
        # Portfolio summary
        embed.add_field(
            name="💰 Portfolio Overview",
            value=income_details,
            inline=False
        )
        
        # Alerts
        if properties_at_risk > 0 or properties_full > 0:
            alerts = []
            if properties_at_risk > 0:
                alerts.append(f"🚨 {properties_at_risk} {'properties' if properties_at_risk > 1 else 'property'} with active risk events")
            if properties_full > 0:
                alerts.append(f"⚠️ {properties_full} {'properties' if properties_full > 1 else 'property'} near maximum capacity")
                
            embed.add_field(
                name="⚠️ Alerts",
                value="\n".join(alerts),
                inline=False
            )
            
        await interaction.response.edit_message(embed=embed, view=new_view)


class PropertyManagementView(discord.ui.View):
    """View with buttons for managing a specific property."""
    
    def __init__(self, investment_manager, user_id, investment, property_details, portfolio_view):
        super().__init__(timeout=60)
        self.investment_manager = investment_manager
        self.user_id = user_id
        self.investment = investment
        self.property_details = property_details
        self.portfolio_view = portfolio_view
        
        # Add property-specific action buttons with simpler configuration
        if not investment.risk_event:
            collect_button = discord.ui.Button(
                label="Collect Income", 
                style=discord.ButtonStyle.success,
                disabled=investment.accumulated_income <= 0,
                row=0
            )
            collect_button.callback = self.collect_callback
            self.add_item(collect_button)
            
            maintain_button = discord.ui.Button(
                label="Perform Maintenance", 
                style=discord.ButtonStyle.primary,
                disabled=investment.maintenance >= 100,
                row=0
            )
            maintain_button.callback = self.maintain_callback
            self.add_item(maintain_button)
        else:
            repair_button = discord.ui.Button(
                label="Repair Property", 
                style=discord.ButtonStyle.danger,
                row=0
            )
            repair_button.callback = self.repair_callback
            self.add_item(repair_button)
            
        # Add sell button
        sell_button = discord.ui.Button(
            label="Sell Property", 
            style=discord.ButtonStyle.secondary,
            row=1
        )
        sell_button.callback = self.sell_callback
        self.add_item(sell_button)
        
        # Add back button
        back_button = discord.ui.Button(
            label="Back to Portfolio", 
            style=discord.ButtonStyle.secondary,
            row=1
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)
        
    async def collect_callback(self, interaction: discord.Interaction):
        # Check if collecting too soon (within an hour of last collection)
        current_time = datetime.datetime.now().timestamp()
        if self.investment.last_collect:
            time_since_last_collect = current_time - self.investment.last_collect
            if time_since_last_collect < 3600:  # 3600 seconds = 1 hour
                minutes_remaining = int((3600 - time_since_last_collect) / 60)
                
                # Only show cooldown message if there's no income to collect
                if self.investment.accumulated_income < 1:
                    embed = discord.Embed(
                        title="⏳ Collection Cooldown",
                        description=f"You can only collect income from {self.investment.property_name} once per hour. Please wait {minutes_remaining} more minutes.",
                        color=0xF39C12  # Orange color
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                    return
        
        # Proceed with normal collection
        success, message, amount = self.investment_manager.collect_income(self.user_id, self.investment.property_name)
        
        if success:
            embed = discord.Embed(
                title="💰 Income Collected",
                description=message,
                color=0x2ECC71
            )
        else:
            embed = discord.Embed(
                title="❌ Collection Failed",
                description=message,
                color=0xE74C3C
            )
            
        # Update the property view
        view = PropertyManagementView(self.investment_manager, self.user_id, self.investment, self.property_details, self.portfolio_view)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def maintain_callback(self, interaction: discord.Interaction):
        success, message = self.investment_manager.maintain_property(self.user_id, self.investment.property_name)
        
        if success:
            embed = discord.Embed(
                title="🛠️ Maintenance Complete",
                description=message,
                color=0x3498DB
            )
        else:
            embed = discord.Embed(
                title="❌ Maintenance Failed",
                description=message,
                color=0xE74C3C
            )
            
        # Update the property view
        view = PropertyManagementView(self.investment_manager, self.user_id, self.investment, self.property_details, self.portfolio_view)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def repair_callback(self, interaction: discord.Interaction):
        success, message = self.investment_manager.repair_property(self.user_id, self.investment.property_name)
        
        if success:
            embed = discord.Embed(
                title="🔧 Repair Complete",
                description=message,
                color=0x2ECC71
            )
            
            # Refresh the investment object
            user_investments = self.investment_manager.get_user_properties(self.user_id)
            for inv in user_investments:
                if inv.property_name == self.investment.property_name:
                    self.investment = inv
                    break
        else:
            embed = discord.Embed(
                title="❌ Repair Failed",
                description=message,
                color=0xE74C3C
            )
            
        # Update the property view
        view = PropertyManagementView(self.investment_manager, self.user_id, self.investment, self.property_details, self.portfolio_view)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def sell_callback(self, interaction: discord.Interaction):
        sell_price = int(self.property_details['price'] * 0.7)
        
        embed = discord.Embed(
            title="🏷️ Confirm Sale",
            description=f"Are you sure you want to sell {self.investment.property_name} for {sell_price:,} coins?\n\nThis action cannot be undone.",
            color=0xF39C12
        )
        
        view = PropertySellConfirmationView(self.investment_manager, self.user_id, self.investment.property_name, self.portfolio_view)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def back_callback(self, interaction: discord.Interaction):
        # Go back to portfolio view
        self.portfolio_view.user_properties = self.investment_manager.get_user_properties(self.user_id)
        self.portfolio_view.update_property_buttons()
        
        # Recreate portfolio summary embed
        user_data = self.investment_manager.db.get_user(self.user_id)
        user_coins = user_data.get('coins', 0) if user_data else 0
        
        # Calculate portfolio stats
        user_properties = self.portfolio_view.user_properties
        total_value = 0
        total_hourly_income = 0
        total_accumulated = 0
        properties_at_risk = 0
        properties_full = 0
        
        for inv in user_properties:
            prop_details = self.investment_manager.get_property_details(inv.property_name)
            if prop_details:
                total_value += prop_details.get('price', 0) * 0.7  # Resale value
                
                if not inv.risk_event and inv.maintenance >= 25:
                    # Maintenance only affects whether income is generated, not how much
                    total_hourly_income += prop_details.get("hourly_income", 0)
                    
                total_accumulated += inv.accumulated_income
                
                if inv.risk_event:
                    properties_at_risk += 1
                    
                max_accumulation = prop_details.get('max_accumulation', 0)
                if inv.accumulated_income >= max_accumulation * 0.9:
                    properties_full += 1
                    
        embed = discord.Embed(
            title="🏙️ Your Luxury Property Portfolio",
            description=f"You own {len(user_properties)} exclusive properties with a total resale value of {int(total_value):,} coins.",
            color=0x3498DB
        )
        
        # Portfolio summary
        embed.add_field(
            name="💰 Portfolio Overview",
            value=f"**Wallet Balance:** {user_coins:,} coins\n**Hourly Income:** {int(total_hourly_income):,} coins/hr\n**Accumulated Income:** {int(total_accumulated):,} coins",
            inline=False
        )
        
        # Alerts
        if properties_at_risk > 0 or properties_full > 0:
            alerts = []
            if properties_at_risk > 0:
                alerts.append(f"🚨 {properties_at_risk} {'properties' if properties_at_risk > 1 else 'property'} with active risk events")
            if properties_full > 0:
                alerts.append(f"⚠️ {properties_full} {'properties' if properties_full > 1 else 'property'} near maximum capacity")
                
            embed.add_field(
                name="⚠️ Alerts",
                value="\n".join(alerts),
                inline=False
            )
            
        await interaction.response.edit_message(embed=embed, view=self.portfolio_view)


class PropertySellConfirmationView(discord.ui.View):
    """View for confirming property sale."""
    
    def __init__(self, investment_manager, user_id, property_name, portfolio_view):
        super().__init__(timeout=30)
        self.investment_manager = investment_manager
        self.user_id = user_id
        self.property_name = property_name
        self.portfolio_view = portfolio_view
        
        # Add confirmation buttons with simpler configuration
        confirm_button = discord.ui.Button(
            label="Confirm Sale", 
            style=discord.ButtonStyle.danger,
            row=0
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)
        
        cancel_button = discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.secondary,
            row=0
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
        
    async def confirm_callback(self, interaction: discord.Interaction):
        success, message, amount = self.investment_manager.sell_property(self.user_id, self.property_name)
        
        if success:
            embed = discord.Embed(
                title="💰 Property Sold",
                description=message,
                color=0x2ECC71
            )
        else:
            embed = discord.Embed(
                title="❌ Sale Failed",
                description=message,
                color=0xE74C3C
            )
            
        # Add a back button
        view = discord.ui.View(timeout=30)
        back_button = discord.ui.Button(label="Back to Portfolio", custom_id="back_to_portfolio", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_to_portfolio_callback
        view.add_item(back_button)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def cancel_callback(self, interaction: discord.Interaction):
        # Go back to property details
        property_details = self.investment_manager.get_property_details(self.property_name)
        
        # Refresh the investment object
        user_investments = self.investment_manager.get_user_properties(self.user_id)
        investment = None
        for inv in user_investments:
            if inv.property_name == self.property_name:
                investment = inv
                break
                
        if investment and property_details:
            # Create property details embed
            embed = discord.Embed(
                title=f"{property_details['emoji']} {investment.property_name}",
                description=property_details['description'],
                color=property_details['color']
            )
            
            # Get user's total income from all properties
            total_hourly_income = 0
            property_type = investment.property_name.split(' ')[0]  # "Luxury", "Premium", etc.
            property_count = 0
            
            for inv in self.investment_manager.get_user_properties(self.user_id):
                inv_details = self.investment_manager.get_property_details(inv.property_name)
                if inv_details and not inv.risk_event and inv.maintenance >= 25:
                    total_hourly_income += inv_details.get('hourly_income', 0)
                    if inv.property_name.split(' ')[0] == property_type:
                        property_count += 1
            
            # Basic property info with income contribution
            income_percentage = 0
            if total_hourly_income > 0:
                income_percentage = (property_details['hourly_income'] / total_hourly_income) * 100
                
            embed.add_field(
                name="💰 Financial Details",
                value=f"**Purchase Price:** {property_details['price']:,} coins\n**Resale Value:** {int(property_details['price'] * 0.7):,} coins (70%)\n**Hourly Income:** {property_details['hourly_income']:,} coins/hr\n**Income Contribution:** {income_percentage:.1f}% of total\n**Similar Properties:** {property_count}x {property_type}",
                inline=False
            )
            
            # Status info
            maintenance_color = "🟢" if investment.maintenance >= 70 else "🟡" if investment.maintenance >= 30 else "🔴"
            income_status = "🛑 Stopped" if investment.maintenance < 25 or investment.risk_event else "✅ Active"
            
            max_accumulation = property_details.get('max_accumulation', 0)
            capacity_pct = min(100, int(investment.accumulated_income / max_accumulation * 100)) if max_accumulation > 0 else 0
            capacity_color = "🟢" if capacity_pct < 70 else "🟡" if capacity_pct < 90 else "🔴"
            
            embed.add_field(
                name="📊 Current Status",
                value=f"**Maintenance:** {maintenance_color} {investment.maintenance:.1f}%\n**Income Status:** {income_status}\n**Storage Capacity:** {capacity_color} {capacity_pct}% full\n**Income Rate:** {property_details['hourly_income']:,} coins/hr\n**Accumulated:** {int(investment.accumulated_income):,} coins{format_collection_cooldown(investment)}",
                inline=False
            )
            
            # Risk event info if applicable
            if investment.risk_event:
                embed.add_field(
                    name="🚨 Risk Event",
                    value=f"**Type:** {investment.risk_event_type}\n**Repair Cost:** {property_details['maintenance_cost'] * 2:,} coins",
                    inline=False
                )
                
            # Purchase date
            embed.add_field(
                name="📅 Owned Since",
                value=investment.purchase_time.strftime("%B %d, %Y"),
                inline=False
            )
            
            # Create property management view
            view = PropertyManagementView(self.investment_manager, self.user_id, investment, property_details, self.portfolio_view)
            
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Something went wrong, go back to portfolio
            await self.back_to_portfolio_callback(interaction)
            
    async def back_to_portfolio_callback(self, interaction: discord.Interaction):
        # Refresh user properties and recalculate portfolio stats
        self.portfolio_view.user_properties = self.investment_manager.get_user_properties(self.user_id)
        self.portfolio_view.update_property_buttons()
        
        # Create a fresh portfolio management view
        new_view = PortfolioManagementView(
            self.investment_manager, 
            self.user_id, 
            self.portfolio_view.portfolio_embed
        )
        
        # Refresh portfolio embed
        user_data = new_view.investment_manager.db.get_user(self.user_id)
        user_coins = user_data.get('coins', 0) if user_data else 0
        
        # Calculate portfolio stats
        user_properties = self.portfolio_view.user_properties
        total_value = 0
        total_hourly_income = 0
        total_accumulated = 0
        properties_at_risk = 0
        properties_full = 0
        
        for inv in user_properties:
            prop_details = self.investment_manager.get_property_details(inv.property_name)
            if prop_details:
                total_value += prop_details.get('price', 0) * 0.7  # Resale value
                
                # Maintenance only affects whether income is generated, not how much
                if not inv.risk_event and inv.maintenance >= 25:
                    total_hourly_income += prop_details.get("hourly_income", 0)
                
                total_accumulated += inv.accumulated_income
                
                if inv.risk_event:
                    properties_at_risk += 1
                    
                max_accumulation = prop_details.get('max_accumulation', 0)
                if inv.accumulated_income >= max_accumulation * 0.9:
                    properties_full += 1
                    
        embed = discord.Embed(
            title="🏙️ Your Luxury Property Portfolio",
            description=f"You own {len(user_properties)} exclusive properties with a total resale value of {int(total_value):,} coins.",
            color=0x3498DB
        )
        
        # Use our helper function to create a detailed income breakdown
        income_details = format_income_breakdown(
            user_properties, 
            self.investment_manager, 
            user_coins, 
            total_hourly_income, 
            total_accumulated
        )
        
        # Portfolio summary
        embed.add_field(
            name="💰 Portfolio Overview",
            value=income_details,
            inline=False
        )
        
        # Alerts
        if properties_at_risk > 0 or properties_full > 0:
            alerts = []
            if properties_at_risk > 0:
                alerts.append(f"🚨 {properties_at_risk} {'properties' if properties_at_risk > 1 else 'property'} with active risk events")
            if properties_full > 0:
                alerts.append(f"⚠️ {properties_full} {'properties' if properties_full > 1 else 'property'} near maximum capacity")
                
            embed.add_field(
                name="⚠️ Alerts",
                value="\n".join(alerts),
                inline=False
            )
            
        await interaction.response.edit_message(embed=embed, view=new_view)


async def setup(bot):
    """Add the investment cog to the bot."""
    await bot.add_cog(InvestmentCog(bot))
    logger.info("Investment cog added to bot")