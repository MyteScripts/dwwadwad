import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import logging
from database import Database
import datetime
import asyncio

# Set up logging
logger = logging.getLogger('shop_system')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(filename='logs/bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Shop items with prices and descriptions
SHOP_ITEMS = {
    "BGL": {
        "price": 13000,
        "description": "1 BGL - Blue Gem Lock",
        "emoji": "💎",
        "color": 0x3498DB
    },
    "Steam Gift Card 10$": {
        "price": 10000,
        "description": "10$ Steam Gift Card",
        "emoji": "🎮",
        "color": 0x1E1E1E
    },
    "Discord Nitro": {
        "price": 8200,
        "description": "Discord Nitro",
        "emoji": "🚀",
        "color": 0x5865F2
    },
    "PayPal 10€": {
        "price": 10000,
        "description": "10€ PayPal Payout",
        "emoji": "💸",
        "color": 0x169BD7
    },
    "PayPal 20€": {
        "price": 19000,
        "description": "20€ PayPal Payout",
        "emoji": "💸",
        "color": 0x169BD7
    }
}

# Path to the notification channel ID file
SHOP_CONFIG_PATH = "data/shop_settings.json"

class ShopManager:
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        # Set the default notification channel ID
        self.notification_channel_id = "1352717796336996422"
        self.load_config()
        
    def load_config(self):
        """Load shop configuration from JSON file."""
        try:
            if os.path.exists(SHOP_CONFIG_PATH):
                with open(SHOP_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                # If there's no notification channel in config, use the default one
                if config.get('notification_channel_id') is None:
                    self.save_config()
                else:
                    self.notification_channel_id = config.get('notification_channel_id')
                logger.info(f"Loaded shop configuration. Notification channel: {self.notification_channel_id}")
            else:
                self.save_config()
                logger.info("Created new shop configuration file with default notification channel")
        except Exception as e:
            logger.error(f"Error loading shop configuration: {e}", exc_info=True)
            
    def save_config(self):
        """Save shop configuration to JSON file."""
        try:
            config = {
                'notification_channel_id': self.notification_channel_id
            }
            
            # Create the data directory if it doesn't exist
            os.makedirs(os.path.dirname(SHOP_CONFIG_PATH), exist_ok=True)
            
            with open(SHOP_CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=4)
                
            logger.info(f"Saved shop configuration. Notification channel: {self.notification_channel_id}")
        except Exception as e:
            logger.error(f"Error saving shop configuration: {e}", exc_info=True)
            
    def set_notification_channel(self, channel_id):
        """Set the channel where purchase notifications will be sent."""
        self.notification_channel_id = channel_id
        self.save_config()
        
    def get_item_details(self, item_name):
        """Get details for a specific shop item."""
        return SHOP_ITEMS.get(item_name)
    
    def get_all_items(self):
        """Get all available shop items."""
        return SHOP_ITEMS
        
    async def purchase_item(self, user_id, user_name, item_name):
        """Process a purchase for an item."""
        # Get user data
        user_data = self.db.get_user(user_id)
        if not user_data:
            return False, "User not found in database."
            
        # Get item details
        item_details = self.get_item_details(item_name)
        if not item_details:
            return False, "Item not found in shop."
            
        # Check if user has enough coins
        user_coins = user_data.get('coins', 0)
        item_price = item_details['price']
        
        if user_coins < item_price:
            return False, f"You don't have enough coins. You have {user_coins:,} coins, but {item_name} costs {item_price:,} coins."
            
        # Process purchase
        self.db.remove_coins(user_id, item_price)
        
        # Record purchase in user_purchases.json
        self.record_purchase(user_id, user_name, item_name, item_price)
        
        # Send notification to designated channel
        await self.send_purchase_notification(user_id, user_name, item_name, item_details)
        
        return True, f"Successfully purchased {item_name} for {item_price:,} coins!"
        
    def record_purchase(self, user_id, user_name, item_name, price):
        """Record a purchase in the purchase history."""
        purchase_data_path = "data/user_purchases.json"
        
        try:
            # Load existing purchase data
            purchases = {}
            if os.path.exists(purchase_data_path):
                with open(purchase_data_path, 'r') as f:
                    purchases = json.load(f)
                    
            # Add the new purchase
            if user_id not in purchases:
                purchases[user_id] = []
                
            purchase_time = datetime.datetime.now().isoformat()
            purchases[user_id].append({
                "item": item_name,
                "price": price,
                "timestamp": purchase_time,
                "username": user_name
            })
            
            # Save updated purchase data
            with open(purchase_data_path, 'w') as f:
                json.dump(purchases, f, indent=4)
                
            logger.info(f"Recorded purchase: {user_name} ({user_id}) bought {item_name} for {price} coins")
        except Exception as e:
            logger.error(f"Error recording purchase: {e}", exc_info=True)
            
    async def send_purchase_notification(self, user_id, user_name, item_name, item_details):
        """Send a notification to the designated channel about a purchase."""
        if not self.notification_channel_id:
            logger.warning("No notification channel set for shop purchases")
            return
            
        try:
            channel = self.bot.get_channel(int(self.notification_channel_id))
            if not channel:
                logger.error(f"Could not find channel with ID {self.notification_channel_id}")
                return
                
            # Create an embed for the purchase notification
            embed = discord.Embed(
                title=f"🛍️ New Shop Purchase!",
                description=f"A user has purchased an item from the shop.",
                color=item_details.get('color', 0x3498DB),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="User", value=f"<@{user_id}> ({user_name})", inline=False)
            embed.add_field(name="Item Purchased", value=f"{item_details['emoji']} {item_name}", inline=True)
            embed.add_field(name="Price", value=f"{item_details['price']:,} coins", inline=True)
            embed.set_footer(text=f"ID: {user_id}")
            
            await channel.send(embed=embed)
            logger.info(f"Sent purchase notification for {user_name}'s purchase of {item_name}")
        except Exception as e:
            logger.error(f"Error sending purchase notification: {e}", exc_info=True)

class ShopCog(commands.Cog):
    """Commands for the shop system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.shop_manager = ShopManager(bot)
        
    @app_commands.command(
        name="shop",
        description="🛍️ Browse and purchase items from the shop"
    )
    async def shop(self, interaction: discord.Interaction):
        """View and purchase items from the shop."""
        await interaction.response.defer(ephemeral=False)
        
        try:
            user_id = str(interaction.user.id)
            user_name = interaction.user.display_name
            
            # Get user's coins
            user_data = self.db.get_user(user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            # Create main shop embed
            embed = discord.Embed(
                title="🛍️ Exclusive Rewards Shop",
                description="Browse our collection of exclusive rewards that you can purchase with your coins.",
                color=0xE6B325
            )
            
            embed.add_field(
                name="💰 Your Balance",
                value=f"{user_coins:,} coins available",
                inline=False
            )
            
            # Create a view with our shop items
            view = ShopView(self.shop_manager, self.db, user_id, user_name)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in shop command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )
            
    @app_commands.command(
        name="setshopnotificationchannel",
        description="🔔 Set the channel for shop purchase notifications (Admin only)"
    )
    @app_commands.describe(
        channel="The channel where purchase notifications will be sent"
    )
    async def set_shop_notification_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel where shop purchase notifications will be sent."""
        # Check if user has admin permissions
        if not await self.bot.has_admin_permissions(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Set the notification channel
            self.shop_manager.set_notification_channel(str(channel.id))
            
            await interaction.followup.send(
                f"✅ Shop purchase notifications will now be sent to {channel.mention}.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in set_shop_notification_channel command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred. Please try again later.",
                ephemeral=True
            )

class ShopView(discord.ui.View):
    """View with buttons for browsing and purchasing shop items."""
    
    def __init__(self, shop_manager, db, user_id, user_name):
        super().__init__(timeout=180)
        self.shop_manager = shop_manager
        self.db = db
        self.user_id = user_id
        self.user_name = user_name
        self.shop_items = shop_manager.get_all_items()
        
        # Add item buttons
        for item_name, item_details in self.shop_items.items():
            button = discord.ui.Button(
                label=f"{item_name} - {item_details['price']:,} coins",
                style=discord.ButtonStyle.secondary,
                custom_id=f"shop_item_{item_name}",
                emoji=item_details["emoji"]
            )
            button.callback = self.make_purchase_callback(item_name, item_details)
            self.add_item(button)
    
    def make_purchase_callback(self, item_name, item_details):
        async def purchase_callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("This is not your shop menu!", ephemeral=True)
                return
                
            # Get updated user coins
            user_data = self.db.get_user(self.user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            
            # Check if the user can afford the item
            if user_coins < item_details['price']:
                await interaction.response.send_message(
                    f"❌ You don't have enough coins to purchase this item! You have {user_coins:,} coins, but {item_name} costs {item_details['price']:,} coins.",
                    ephemeral=True
                )
                return
                
            # Create confirmation view
            confirm_view = ShopPurchaseConfirmationView(
                self.shop_manager,
                self.user_id,
                self.user_name,
                item_name,
                item_details
            )
            
            # Create confirmation embed
            embed = discord.Embed(
                title=f"🛒 Confirm Purchase: {item_name}",
                description=f"Are you sure you want to purchase this item?",
                color=item_details.get('color', 0x3498DB)
            )
            
            embed.add_field(name="Item", value=f"{item_details['emoji']} {item_name}", inline=True)
            embed.add_field(name="Price", value=f"{item_details['price']:,} coins", inline=True)
            embed.add_field(name="Description", value=item_details['description'], inline=False)
            embed.add_field(name="Your Balance", value=f"{user_coins:,} coins", inline=False)
            embed.add_field(name="Balance After Purchase", value=f"{user_coins - item_details['price']:,} coins", inline=False)
            
            await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
            
        return purchase_callback

class ShopPurchaseConfirmationView(discord.ui.View):
    """View for confirming a shop purchase."""
    
    def __init__(self, shop_manager, user_id, user_name, item_name, item_details):
        super().__init__(timeout=60)
        self.shop_manager = shop_manager
        self.user_id = user_id
        self.user_name = user_name
        self.item_name = item_name
        self.item_details = item_details
        
        # Add buttons
        confirm_button = discord.ui.Button(
            label="Confirm Purchase",
            style=discord.ButtonStyle.success,
            custom_id="confirm_purchase"
        )
        confirm_button.callback = self.confirm_callback
        
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.danger,
            custom_id="cancel_purchase"
        )
        cancel_button.callback = self.cancel_callback
        
        self.add_item(confirm_button)
        self.add_item(cancel_button)
        
    async def confirm_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This is not your confirmation dialog!", ephemeral=True)
            return
            
        # Process the purchase
        success, message = await self.shop_manager.purchase_item(
            self.user_id,
            self.user_name,
            self.item_name
        )
        
        if success:
            # Create success embed
            embed = discord.Embed(
                title="✅ Purchase Successful!",
                description=f"You have purchased {self.item_details['emoji']} {self.item_name}!",
                color=self.item_details.get('color', 0x2ECC71)
            )
            
            embed.add_field(name="Price", value=f"{self.item_details['price']:,} coins", inline=True)
            
            # Get updated user coins
            user_data = self.shop_manager.db.get_user(self.user_id)
            user_coins = user_data.get('coins', 0) if user_data else 0
            embed.add_field(name="Remaining Balance", value=f"{user_coins:,} coins", inline=True)
            
            embed.add_field(
                name="Next Steps",
                value="The staff has been notified of your purchase and will contact you shortly to deliver your reward.",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            # Create error embed
            embed = discord.Embed(
                title="❌ Purchase Failed",
                description=message,
                color=0xE74C3C
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
    async def cancel_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This is not your confirmation dialog!", ephemeral=True)
            return
            
        # Create cancel embed
        embed = discord.Embed(
            title="🛑 Purchase Cancelled",
            description="You have cancelled this purchase.",
            color=0xE74C3C
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    """Add the shop cog to the bot."""
    await bot.add_cog(ShopCog(bot))
    logger.info("Shop cog loaded")