import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
import time
import logging
import asyncio
import datetime
import uuid
from database import Database
from logger import setup_logger

logger = setup_logger('grumbleteeth')

class GrumbleteethCog(commands.Cog):
    """Cog for handling the grumbleteeth malady system and shop"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.infected_users = {}  # Dict to store user_id -> infection_time
        self.inactive_threshold = 3 * 60 * 60  # 3 hours in seconds
        self.check_interval = 5 * 60  # Check every 5 minutes
        self.shop_items = {}  # Dict to store shop items
        self.user_purchases = {}  # Dict to store user purchases
        self.admin_user_id = "1308527904497340467"  # Admin user ID for restricted commands

        self.load_infected_users()
        self.load_shop_items()
        self.load_user_purchases()

        if not self.shop_items:
            self.shop_items["antidote"] = {
                "id": "antidote",
                "name": "🧪 Grumbleteeth Antidote",
                "description": "Cure yourself of the grumbleteeth malady",
                "price": 250,
                "type": "cure",
                "hidden": False,
                "admin_only": False,
                "code": "ANTI"
            }
            self.save_shop_items()

    def load_infected_users(self):
        """Load the infected users and their last activity time from file"""
        try:
            os.makedirs('data', exist_ok=True)
            if os.path.exists('data/grumbleteeth_users.json'):
                with open('data/grumbleteeth_users.json', 'r') as f:
                    self.infected_users = json.load(f)
                    logger.info(f"Loaded {len(self.infected_users)} infected users")
        except Exception as e:
            logger.error(f"Error loading infected users: {e}")
    
    def save_infected_users(self):
        """Save the infected users and their last activity time to file"""
        try:
            os.makedirs('data', exist_ok=True)
            with open('data/grumbleteeth_users.json', 'w') as f:
                json.dump(self.infected_users, f)
                logger.info(f"Saved {len(self.infected_users)} infected users")
        except Exception as e:
            logger.error(f"Error saving infected users: {e}")
    
    def is_infected(self, user_id):
        """Check if a user is infected with grumbleteeth"""
        return str(user_id) in self.infected_users
    
    def infect_user(self, user_id):
        """Infect a user with grumbleteeth"""
        if not self.is_infected(user_id):
            self.infected_users[str(user_id)] = time.time()
            self.save_infected_users()
            logger.info(f"User {user_id} infected with grumbleteeth")
    
    def cure_user(self, user_id):
        """Cure a user of grumbleteeth"""
        if self.is_infected(user_id):
            del self.infected_users[str(user_id)]
            self.save_infected_users()
            logger.info(f"User {user_id} cured of grumbleteeth")
            return True
        return False
    
    def load_shop_items(self):
        """Load shop items from file"""
        try:
            os.makedirs('data', exist_ok=True)
            if os.path.exists('data/shop_items.json'):
                with open('data/shop_items.json', 'r') as f:
                    self.shop_items = json.load(f)
                    logger.info(f"Loaded {len(self.shop_items)} shop items")
        except Exception as e:
            logger.error(f"Error loading shop items: {e}")
    
    def save_shop_items(self):
        """Save shop items to file"""
        try:
            os.makedirs('data', exist_ok=True)
            with open('data/shop_items.json', 'w') as f:
                json.dump(self.shop_items, f)
                logger.info(f"Saved {len(self.shop_items)} shop items")
        except Exception as e:
            logger.error(f"Error saving shop items: {e}")
    
    def load_user_purchases(self):
        """Load user purchases from file"""
        try:
            os.makedirs('data', exist_ok=True)
            if os.path.exists('data/user_purchases.json'):
                with open('data/user_purchases.json', 'r') as f:
                    self.user_purchases = json.load(f)

                    count = sum(len(purchases) for purchases in self.user_purchases.values())
                    logger.info(f"Loaded {count} user purchases for {len(self.user_purchases)} users")
        except Exception as e:
            logger.error(f"Error loading user purchases: {e}")
    
    def save_user_purchases(self):
        """Save user purchases to file"""
        try:
            os.makedirs('data', exist_ok=True)
            with open('data/user_purchases.json', 'w') as f:
                json.dump(self.user_purchases, f)

                count = sum(len(purchases) for purchases in self.user_purchases.values())
                logger.info(f"Saved {count} user purchases for {len(self.user_purchases)} users")
        except Exception as e:
            logger.error(f"Error saving user purchases: {e}")
    
    def get_purchase_count(self, user_id, item_id, cap_type):
        """Get the number of times a user has purchased an item within the cap period"""
        user_id = str(user_id)
        if user_id not in self.user_purchases:
            return 0
            
        count = 0
        current_time = time.time()

        if cap_type == "Monthly":

            now = datetime.datetime.now()
            start_of_month = datetime.datetime(now.year, now.month, 1)
            cap_start_time = start_of_month.timestamp()
        elif cap_type == "Seasonal":

            now = datetime.datetime.now()
            month = now.month
            year = now.year

            if month <= 2:  # Winter
                season_start_month = 12
                if month < 12:
                    year -= 1  # December of previous year
            elif month <= 5:  # Spring
                season_start_month = 3
            elif month <= 8:  # Summer
                season_start_month = 6
            else:  # Fall
                season_start_month = 9

            if season_start_month == 12:

                start_of_season = datetime.datetime(year, season_start_month, 1)
            else:
                start_of_season = datetime.datetime(year, season_start_month, 1)
                
            cap_start_time = start_of_season.timestamp()
        else:

            cap_start_time = 0

        for purchase in self.user_purchases[user_id]:
            if purchase["item_id"] == item_id and purchase["purchased_at"] >= cap_start_time:
                count += 1
                
        return count
        
    def add_item_to_inventory(self, user_id, item_id):
        """Add an item to a user's inventory"""
        user_id = str(user_id)
        if user_id not in self.user_purchases:
            self.user_purchases[user_id] = []

        purchase_id = str(uuid.uuid4())
        self.user_purchases[user_id].append({
            "item_id": item_id,
            "purchased_at": time.time(),
            "purchase_id": purchase_id
        })
        
        self.save_user_purchases()
        return purchase_id
    
    def use_item(self, user_id, purchase_id):
        """Use an item from a user's inventory"""
        user_id = str(user_id)
        if user_id not in self.user_purchases:
            return False, "You don't have any items."

        for i, purchase in enumerate(self.user_purchases[user_id]):
            if purchase["purchase_id"] == purchase_id:
                item_id = purchase["item_id"]

                self.user_purchases[user_id].pop(i)
                self.save_user_purchases()

                if item_id == "antidote":
                    success = self.cure_user(user_id)
                    return True, "You have been cured of the grumbleteeth malady!" if success else "You weren't infected."

                return True, f"You used the item."
        
        return False, "Item not found in your inventory."
    
    def get_user_inventory(self, user_id):
        """Get a user's inventory of purchased items"""
        user_id = str(user_id)
        if user_id not in self.user_purchases:
            return []
        
        inventory = []
        for purchase in self.user_purchases[user_id]:
            item_id = purchase["item_id"]
            if item_id in self.shop_items:
                item = self.shop_items[item_id].copy()
                item["purchase_id"] = purchase["purchase_id"]
                item["purchased_at"] = purchase["purchased_at"]
                inventory.append(item)
        
        return inventory
        
    def update_user_activity(self, user_id):
        """Update a user's last activity time"""

        if str(user_id) not in self.infected_users:

            current_time = time.time()
            user_key = f"activity_{user_id}"

            try:
                user_activity = {}
                if os.path.exists('data/user_activity.json'):
                    try:
                        with open('data/user_activity.json', 'r') as f:
                            user_activity = json.load(f)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error loading user_activity.json: {e}")

                        with open('data/user_activity.json', 'w') as f:
                            json.dump({}, f)
                
                user_activity[user_key] = current_time
                
                with open('data/user_activity.json', 'w') as f:
                    json.dump(user_activity, f)
            except Exception as e:
                logger.error(f"Error updating user activity: {e}")
    
    def grumblify_message(self, text):
        """Convert text to a pattern of 'm' and 'f' characters while keeping spaces and punctuation"""
        result = ""
        for char in text:
            if char.isalpha():
                result += random.choice(['m', 'f'])
            else:
                result += char  # Keep spaces, punctuation, etc.
        return result
        
    async def cog_load(self):
        """Called when the cog is loaded."""
        self.bg_task = asyncio.create_task(self.check_inactive_users())
        
    def cog_unload(self):
        """Called when the cog is unloaded."""
        if self.bg_task:
            self.bg_task.cancel()
    
    async def check_inactive_users(self):
        """Background task - DISABLED
        This function would normally check for inactive users and infect them with grumbleteeth,
        but this functionality is now disabled."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():

            await asyncio.sleep(300)  # Sleep for 5 minutes
    
    @app_commands.command(
        name="shop",
        description="Shop for items with your coins - some items may have purchase limits"
    )
    async def shop(self, interaction: discord.Interaction):
        """Shop for items with your coins"""

        user_id = interaction.user.id
        username = interaction.user.name
        user = self.db.get_or_create_user(user_id, username)
        
        if user is None:
            await interaction.response.send_message("❌ Failed to retrieve your profile. Please try again later.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛒 Item Shop",
            description="Welcome to the shop! Here you can purchase items with your coins. Some special items may have purchase limits per month or season.",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Your Balance",
            value=f"**{user['coins']}** coins",
            inline=False
        )

        available_items = []

        available_items.append({
            "id": "antidote",
            "name": "🧪 Grumbleteeth Antidote (DISABLED)",
            "description": "The grumbleteeth system has been disabled - this item no longer works",
            "price": 250,
            "type": "cure",
            "code": "ANTI"
        })

        for item_id, item in self.shop_items.items():

            if item.get("admin_only", False) and str(interaction.user.id) != "1308527904497340467":
                continue

            if item.get("hidden", False):
                continue

            if item_id == "antidote":
                continue

            available_items.append(item)

        if not available_items:
            embed.add_field(
                name="Available Items",
                value="No items available for purchase at this time.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        items_description = ""
        for i, item in enumerate(available_items):
            item_code = item.get("code", f"ITEM{i+1}")
            items_description += f"**{i+1}. {item['name']}** - {item['price']} coins - Code: `{item_code}`\n"
            items_description += f"  *{item['description']}*\n"

            if "cap_type" in item and "cap_value" in item:

                current_count = self.get_purchase_count(user_id, item["id"], item["cap_type"])
                period = "month" if item["cap_type"] == "Monthly" else "season"
                items_description += f"  Limit: {current_count}/{item['cap_value']} per {period}\n"
                
            items_description += "\n"
        
        embed.add_field(
            name="Available Items",
            value=items_description,
            inline=False
        )

        embed.add_field(
            name="How to Buy",
            value="Use `/buy [code]` to purchase an item from the shop.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="buy",
        description="Buy an item from the shop using its code (some items have purchase limits)"
    )
    @app_commands.describe(
        code="The code of the item you want to buy"
    )
    async def buy(self, interaction: discord.Interaction, code: str):
        """Buy an item from the shop using its code"""

        user_id = interaction.user.id
        username = interaction.user.name
        user = self.db.get_or_create_user(user_id, username)
        
        if user is None:
            await interaction.response.send_message("❌ Failed to retrieve your profile. Please try again later.", ephemeral=True)
            return

        code = code.upper().strip()

        item_to_buy = None

        if code == "ANTI":

            await interaction.response.send_message(
                "⚠️ The grumbleteeth system has been disabled. The antidote is no longer functional.",
                ephemeral=True
            )
            return
        else:

            for item_id, item in self.shop_items.items():
                item_code = item.get("code", "")
                if item_code.upper() == code:

                    if item.get("admin_only", False) and str(interaction.user.id) != "1308527904497340467":
                        await interaction.response.send_message("❌ This item is only available to administrators.", ephemeral=True)
                        return

                    if item.get("hidden", False):
                        await interaction.response.send_message("❌ This item is not available in the shop right now.", ephemeral=True)
                        return
                    
                    item_to_buy = item
                    break

        if item_to_buy is None:
            await interaction.response.send_message(f"❌ Could not find an item with code `{code}`. Use `/shop` to see available items.", ephemeral=True)
            return

        if user["coins"] < item_to_buy["price"]:
            await interaction.response.send_message(
                f"❌ You don't have enough coins to buy {item_to_buy['name']}. You need {item_to_buy['price'] - user['coins']} more coins.",
                ephemeral=True
            )
            return

        if "cap_type" in item_to_buy and "cap_value" in item_to_buy:
            cap_type = item_to_buy["cap_type"]
            cap_value = item_to_buy["cap_value"]

            current_count = self.get_purchase_count(user_id, item_to_buy["id"], cap_type)

            if current_count >= cap_value:
                period_name = "month" if cap_type == "Monthly" else "season"
                await interaction.response.send_message(
                    f"❌ You've reached the purchase limit for {item_to_buy['name']}. Maximum of {cap_value} per {period_name}.",
                    ephemeral=True
                )
                return

        self.db.add_coins(user_id, username, -item_to_buy["price"])

        try:
            log_channel = self.bot.get_channel(1352717796336996422)
            if log_channel:
                await log_channel.send(
                    f"💰 **Purchase Log**\n"
                    f"User: {username} (ID: {user_id})\n"
                    f"Item: {item_to_buy['name']} (Code: {item_to_buy.get('code', 'N/A')})\n"
                    f"Price: {item_to_buy['price']} coins\n"
                    f"Time: {discord.utils.format_dt(datetime.datetime.now())}"
                )
        except Exception as e:

            print(f"Error sending purchase log: {e}")

        item_id = item_to_buy["id"]

        if item_id == "antidote":

            if not self.is_infected(user_id):

                self.db.add_coins(user_id, username, item_to_buy["price"])
                await interaction.response.send_message(
                    f"❌ You don't need an antidote because you're not infected with grumbleteeth. Your {item_to_buy['price']} coins have been refunded.",
                    ephemeral=True
                )
                return

            self.cure_user(user_id)
            await interaction.response.send_message(
                f"✅ You have purchased {item_to_buy['name']} for {item_to_buy['price']} coins. You have been cured of the grumbleteeth malady!",
                ephemeral=True
            )
        else:

            purchase_id = self.add_item_to_inventory(user_id, item_id)
            await interaction.response.send_message(
                f"✅ You have purchased {item_to_buy['name']} for {item_to_buy['price']} coins. It has been added to your inventory.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="manageshop",
        description="Manage shop items (Admin only)"
    )
    @app_commands.describe(
        action="The action to perform (add, remove, list, edit)",
        name="The name of the item (for 'add' action)",
        description="The description of the item (for 'add' action)",
        price="The price of the item in coins (for 'add' action)",
        item_code="The item code for adding or item ID for editing/removing",
        hidden="Whether the item should be hidden from the shop (for 'add' action)",
        admin_only="Whether the item can only be purchased by admins (for 'add' action)",
        cap_type="Purchase cap type (Monthly or Seasonal) for limiting purchases",
        cap_value="Maximum number of purchases allowed per cap period"
    )
    async def manageshop(self, interaction: discord.Interaction, 
                        action: str,
                        item_code: str = None,
                        name: str = None, 
                        description: str = None, 
                        price: int = None,
                        hidden: bool = False, 
                        admin_only: bool = False,
                        cap_type: str = None,
                        cap_value: int = None):
        """Comprehensive command to manage shop items (Admin only)"""

        if str(interaction.user.id) != "1308527904497340467":
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        action = action.lower()

        if action == "add":
            if not all([name, description, price, item_code]):
                await interaction.response.send_message("❌ Missing required parameters. For 'add' action, you must provide: name, description, price, and item_code.", ephemeral=True)
                return

            item_id = f"item_{int(time.time())}_{uuid.uuid4().hex[:8]}"

            item_code = item_code.upper().strip()

            for existing_item in self.shop_items.values():
                if existing_item.get("code", "").upper() == item_code:
                    await interaction.response.send_message(f"❌ An item with code `{item_code}` already exists. Please choose a different code.", ephemeral=True)
                    return

            new_item = {
                "id": item_id,
                "name": name,
                "description": description,
                "price": price,
                "code": item_code,
                "hidden": hidden,
                "admin_only": admin_only,
                "created_at": time.time()
            }

            if cap_type and cap_value:

                if cap_type not in ["Monthly", "Seasonal"]:
                    await interaction.response.send_message(
                        f"❌ Invalid cap_type: `{cap_type}`. Must be either 'Monthly' or 'Seasonal'.",
                        ephemeral=True
                    )
                    return

                new_item["cap_type"] = cap_type
                new_item["cap_value"] = cap_value

            self.shop_items[item_id] = new_item
            self.save_shop_items()

            confirmation_msg = (
                f"✅ Item added to shop:\n"
                f"**{name}** - {price} coins - Code: `{item_code}`\n"
                f"*{description}*\n\n"
                f"Hidden: {hidden}\n"
                f"Admin only: {admin_only}"
            )

            if "cap_type" in new_item and "cap_value" in new_item:
                confirmation_msg += f"\nPurchase limit: {new_item['cap_value']} per {new_item['cap_type']}"
                
            await interaction.response.send_message(
                confirmation_msg,
                ephemeral=True
            )
            return

        elif action == "remove":
            if not item_code:
                await interaction.response.send_message("❌ Missing item ID. For 'remove' action, you must provide the item_code parameter with the ID of the item to remove.", ephemeral=True)
                return

            if item_code in self.shop_items:

                removed_item = self.shop_items[item_code]

                del self.shop_items[item_code]
                self.save_shop_items()

                await interaction.response.send_message(
                    f"✅ Item removed from shop:\n"
                    f"**{removed_item['name']}** - Code: `{removed_item.get('code', 'N/A')}`",
                    ephemeral=True
                )
            else:

                for item_id, item in list(self.shop_items.items()):
                    if item.get("code", "").upper() == item_code.upper():

                        removed_item = self.shop_items[item_id]

                        del self.shop_items[item_id]
                        self.save_shop_items()

                        await interaction.response.send_message(
                            f"✅ Item removed from shop:\n"
                            f"**{removed_item['name']}** - Code: `{removed_item.get('code', 'N/A')}`",
                            ephemeral=True
                        )
                        return

                await interaction.response.send_message(f"❌ Could not find an item with ID or code `{item_code}`.", ephemeral=True)
            
            return

        elif action == "edit":
            if not item_code:
                await interaction.response.send_message("❌ Missing item ID. For 'edit' action, you must provide the item_code parameter with the ID of the item to edit.", ephemeral=True)
                return

            item_to_edit = None
            item_id_to_edit = None

            if item_code in self.shop_items:
                item_to_edit = self.shop_items[item_code]
                item_id_to_edit = item_code
            else:

                for item_id, item in self.shop_items.items():
                    if item.get("code", "").upper() == item_code.upper():
                        item_to_edit = item
                        item_id_to_edit = item_id
                        break

            if not item_to_edit:
                await interaction.response.send_message(f"❌ Could not find an item with ID or code `{item_code}`.", ephemeral=True)
                return

            updated = False
            
            if name is not None:
                item_to_edit["name"] = name
                updated = True
                
            if description is not None:
                item_to_edit["description"] = description
                updated = True
                
            if price is not None:
                item_to_edit["price"] = price
                updated = True

            if item_to_edit.get("hidden", False) != hidden:
                item_to_edit["hidden"] = hidden
                updated = True
                
            if item_to_edit.get("admin_only", False) != admin_only:
                item_to_edit["admin_only"] = admin_only
                updated = True

            if cap_type is not None:

                if cap_type == "None" or cap_type == "":
                    if "cap_type" in item_to_edit:
                        del item_to_edit["cap_type"]
                        updated = True
                    if "cap_value" in item_to_edit:
                        del item_to_edit["cap_value"]
                        updated = True

                elif cap_type in ["Monthly", "Seasonal"]:

                    if cap_value is not None:
                        item_to_edit["cap_type"] = cap_type
                        item_to_edit["cap_value"] = cap_value
                        updated = True

                    elif "cap_value" in item_to_edit:
                        item_to_edit["cap_type"] = cap_type
                        updated = True
                else:
                    await interaction.response.send_message(
                        f"❌ Invalid cap_type: `{cap_type}`. Must be 'Monthly', 'Seasonal', or 'None'.",
                        ephemeral=True
                    )
                    return

            elif cap_value is not None and "cap_type" in item_to_edit:
                item_to_edit["cap_value"] = cap_value
                updated = True
            
            if updated:
                self.save_shop_items()

                confirmation_msg = (
                    f"✅ Item updated:\n"
                    f"**{item_to_edit['name']}** - {item_to_edit['price']} coins - Code: `{item_to_edit.get('code', 'N/A')}`\n"
                    f"*{item_to_edit['description']}*\n\n"
                    f"Hidden: {item_to_edit.get('hidden', False)}\n"
                    f"Admin only: {item_to_edit.get('admin_only', False)}"
                )

                if "cap_type" in item_to_edit and "cap_value" in item_to_edit:
                    confirmation_msg += f"\nPurchase limit: {item_to_edit['cap_value']} per {item_to_edit['cap_type']}"
                
                await interaction.response.send_message(
                    confirmation_msg,
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❓ No changes were made to the item.", ephemeral=True)
                
            return

        elif action == "list":

            embed = discord.Embed(
                title="🛒 Shop Management",
                description="View and manage all shop items.",
                color=discord.Color.dark_gold()
            )

            if not self.shop_items:
                embed.add_field(
                    name="No Items",
                    value="There are no items in the shop. Use `/manageshop add` to add items.",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            sorted_items = sorted(self.shop_items.values(), key=lambda x: x.get("created_at", 0), reverse=True)

            items_description = ""
            for i, item in enumerate(sorted_items):

                status = []
                if item.get("hidden", False):
                    status.append("🔒 Hidden")
                if item.get("admin_only", False):
                    status.append("👑 Admin Only")
                
                status_str = f" ({', '.join(status)})" if status else ""
                
                items_description += f"**{i+1}. {item['name']}**{status_str}\n"
                items_description += f"  *{item['description']}*\n"
                items_description += f"  Price: {item['price']} coins | Code: `{item.get('code', 'N/A')}`\n"

                if "cap_type" in item and "cap_value" in item:
                    items_description += f"  Limit: {item['cap_value']} per {item['cap_type']}\n"
                    
                items_description += f"  ID: `{item['id']}`\n\n"

                if len(items_description) > 900:
                    embed.add_field(
                        name=f"Items (Part {len(embed.fields) + 1})",
                        value=items_description,
                        inline=False
                    )
                    items_description = ""

            if items_description:
                embed.add_field(
                    name=f"Items (Part {len(embed.fields) + 1})",
                    value=items_description,
                    inline=False
                )

            embed.add_field(
                name="Shop Management Commands",
                value=(
                    "• `/manageshop add name:\"Item Name\" description:\"Description\" price:100 item_code:XYZ123` - Add a new item\n"
                    "• `/manageshop add name:\"Special Item\" description:\"Limited Edition\" price:500 item_code:SPECIAL cap_type:\"Monthly\" cap_value:2` - Add item with purchase limit\n"
                    "• `/manageshop remove item_code:XYZ123` - Remove an item\n"
                    "• `/manageshop edit item_code:XYZ123 name:\"New Name\" price:200` - Edit an item\n"
                    "• `/manageshop edit item_code:XYZ123 cap_type:\"Seasonal\" cap_value:5` - Add/update purchase limit\n"
                    "• `/manageshop edit item_code:XYZ123 cap_type:\"None\"` - Remove purchase limit\n"
                    "• `/manageshop list` - List all items"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        else:
            await interaction.response.send_message(
                f"❌ Unknown action: `{action}`\n\n"
                f"Valid actions are:\n"
                f"• `add` - Add a new item\n"
                f"• `remove` - Remove an item\n"
                f"• `edit` - Edit an item\n"
                f"• `list` - List all items",
                ephemeral=True
            )
            return
    
    @app_commands.command(
        name="gumbleteeth",
        description="Manually infect a member with grumbleteeth (Admin only)"
    )
    @app_commands.describe(
        member="The member to infect with grumbleteeth"
    )
    async def gumbleteeth_command(self, interaction: discord.Interaction, member: discord.Member):
        """Manually infect a member with grumbleteeth (Admin only) - DISABLED FUNCTIONALITY"""

        if str(interaction.user.id) != self.admin_user_id:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        await interaction.response.send_message(
            "⚠️ The grumbleteeth system has been disabled. This command no longer works.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="ungumbleteeth",
        description="Manually cure a member from grumbleteeth (Admin only)"
    )
    @app_commands.describe(
        member="The member to cure from grumbleteeth"
    )
    async def ungumbleteeth_command(self, interaction: discord.Interaction, member: discord.Member):
        """Manually cure a member from grumbleteeth (Admin only) - DISABLED FUNCTIONALITY"""

        if str(interaction.user.id) != self.admin_user_id:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        await interaction.response.send_message(
            "⚠️ The grumbleteeth system has been disabled. This command no longer works.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="inactivestats",
        description="Check who has been inactive for more than 3 hours"
    )
    async def inactivestats(self, interaction: discord.Interaction):
        """Display a list of inactive users - DISABLED FUNCTIONALITY"""

        if str(interaction.user.id) == "1308527904497340467":

            embed = discord.Embed(
                title="😴 Inactive User Statistics",
                description="The grumbleteeth system has been disabled",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="System Disabled",
                value="The grumbleteeth malady system has been completely disabled. Users will no longer be infected due to inactivity.",
                inline=False
            )

            user_activity = {}
            if os.path.exists('data/user_activity.json'):
                with open('data/user_activity.json', 'r') as f:
                    user_activity = json.load(f)
                    
            current_time = time.time()
            inactive_users = []
            
            for key, last_active_time in user_activity.items():
                if key.startswith("activity_"):
                    user_id = key.replace("activity_", "")

                    time_diff = current_time - float(last_active_time)
                    hours = int(time_diff // 3600)
                    minutes = int((time_diff % 3600) // 60)
                    
                    if hours > 3:  # Only show users inactive for more than 3 hours

                        member = None
                        for guild in self.bot.guilds:
                            member = guild.get_member(int(user_id))
                            if member:
                                break
                        
                        username = member.display_name if member else f"User {user_id}"
                        
                        inactive_users.append({
                            "user_id": user_id,
                            "username": username,
                            "time": f"{hours}h {minutes}m"
                        })

            inactive_users.sort(key=lambda x: -float(user_activity[f"activity_{x['user_id']}"]))

            if inactive_users:
                inactive_text = ""
                for user in inactive_users[:15]:  # Show top 15 to avoid too long messages
                    inactive_text += f"**{user['username']}** - Inactive for {user['time']}\n"
                
                embed.add_field(
                    name=f"Inactive Users ({len(inactive_users)})",
                    value=inactive_text if inactive_text else "None",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Inactive Users",
                    value="There are currently no users who have been inactive for more than 3 hours.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages to update activity, but do not apply grumbleteeth effect as it's disabled"""

        if message.author.bot:
            return

        self.update_user_activity(message.author.id)

class ShopView(discord.ui.View):
    """View with buttons for the shop interface"""
    
    def __init__(self, cog, items, user):
        super().__init__(timeout=60)
        self.cog = cog
        self.items = items
        self.user = user

        for i, item in enumerate(items):
            button = discord.ui.Button(
                label=f"Buy {item['name']}",
                style=discord.ButtonStyle.primary,
                custom_id=f"buy_{item['id']}"
            )
            button.callback = self.buy_item
            self.add_item(button)
    
    async def buy_item(self, interaction: discord.Interaction):
        """Handle item purchase"""

        item_id = interaction.data["custom_id"].replace("buy_", "")

        item = next((i for i in self.items if i["id"] == item_id), None)
        if not item:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return

        if self.user["coins"] < item["price"]:
            await interaction.response.send_message(
                f"❌ You don't have enough coins to buy {item['name']}. You need {item['price'] - self.user['coins']} more coins.",
                ephemeral=True
            )
            return

        if "cap_type" in item and "cap_value" in item:
            cap_type = item["cap_type"]
            cap_value = item["cap_value"]

            current_count = self.cog.get_purchase_count(interaction.user.id, item_id, cap_type)

            if current_count >= cap_value:
                period_name = "month" if cap_type == "Monthly" else "season"
                await interaction.response.send_message(
                    f"❌ You've reached the purchase limit for {item['name']}. Maximum of {cap_value} per {period_name}.",
                    ephemeral=True
                )
                return

        if item_id == "antidote":

            if not self.cog.is_infected(interaction.user.id):
                await interaction.response.send_message(
                    f"❌ You don't need an antidote because you're not infected with grumbleteeth.",
                    ephemeral=True
                )
                return

            self.cog.db.add_coins(interaction.user.id, interaction.user.name, -item["price"])

            self.cog.cure_user(interaction.user.id)
            
            await interaction.response.send_message(
                f"✅ You have purchased {item['name']} for {item['price']} coins. You have been cured of the grumbleteeth malady!",
                ephemeral=True
            )

        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(view=self)

async def setup(bot):
    """Add the grumbleteeth cog to the bot"""
    await bot.add_cog(GrumbleteethCog(bot))
    logger.info("Grumbleteeth cog loaded")