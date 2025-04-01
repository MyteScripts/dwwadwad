import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import os
import datetime
import asyncio
import random
import sqlite3
from logger import setup_logger

logger = setup_logger('mining', 'bot.log')

MINING_COOLDOWN = 60  # seconds between mining attempts
RESOURCES = {
    "Stone": {"value": 1, "chance": 0.75, "emoji": "🪨"},
    "Coal": {"value": 2, "chance": 0.5, "emoji": "⚫"},
    "Iron": {"value": 5, "chance": 0.3, "emoji": "🧲"},
    "Silver": {"value": 10, "chance": 0.15, "emoji": "🥈"},
    "Gold": {"value": 20, "chance": 0.08, "emoji": "🥇"},
    "Diamond": {"value": 50, "chance": 0.03, "emoji": "💎"},
    "Emerald": {"value": 75, "chance": 0.015, "emoji": "🟢"},
    "Ruby": {"value": 100, "chance": 0.01, "emoji": "❤️"}
}

PICKAXES = {
    "Wooden Pickaxe": {"level": 0, "multiplier": 1, "cost": 0},
    "Stone Pickaxe": {"level": 1, "multiplier": 1.5, "cost": 500},
    "Iron Pickaxe": {"level": 2, "multiplier": 2, "cost": 2000},
    "Gold Pickaxe": {"level": 3, "multiplier": 3, "cost": 5000},
    "Diamond Pickaxe": {"level": 4, "multiplier": 5, "cost": 15000},
    "Emerald Pickaxe": {"level": 5, "multiplier": 8, "cost": 50000},
    "Ruby Pickaxe": {"level": 6, "multiplier": 12, "cost": 100000},
    "Obsidian Pickaxe": {"level": 7, "multiplier": 20, "cost": 500000}
}

SHOP_ITEMS = {
    "Mining Helmet": {"description": "Increases mining success rate by 10%", "cost": 1000, "effect": {"type": "success_rate", "value": 0.1}},
    "Mining Gloves": {"description": "Increases resource amount by 20%", "cost": 2000, "effect": {"type": "resource_amount", "value": 0.2}},
    "Resource Bag": {"description": "Store 50% more resources", "cost": 3000, "effect": {"type": "storage", "value": 0.5}},
    "Energy Drink": {"description": "Reduces mining cooldown by 15%", "cost": 5000, "effect": {"type": "cooldown", "value": 0.15}},
    "Metal Detector": {"description": "10% chance to find rare resources", "cost": 7500, "effect": {"type": "rare_find", "value": 0.1}},
    "Dynamite Pack": {"description": "25% chance to double your resources on mining", "cost": 10000, "effect": {"type": "double_chance", "value": 0.25}}
}

PRESTIGE_BENEFITS = {
    "multiplier": 0.1,  # Each prestige level adds 10% to mining rewards
    "cooldown_reduction": 0.05,  # Each prestige level reduces cooldown by 5%
    "base_cost": 50000  # Base cost for first prestige
}

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect('data/leveling.db')
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    """Initialize the database tables for mining if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mining_stats (
        user_id TEXT PRIMARY KEY,
        money INTEGER DEFAULT 0,
        prestige_level INTEGER DEFAULT 0,
        pickaxe TEXT DEFAULT 'Wooden Pickaxe',
        last_mine_time TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mining_resources (
        user_id TEXT,
        resource_name TEXT,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, resource_name)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mining_items (
        user_id TEXT,
        item_name TEXT,
        purchase_time TIMESTAMP,
        PRIMARY KEY (user_id, item_name)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Mining database tables initialized")

def get_user_mining_stats(user_id):
    """Get a user's mining stats from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM mining_stats WHERE user_id = ?", (str(user_id),))
    user_data = cursor.fetchone()

    if not user_data:
        cursor.execute(
            "INSERT INTO mining_stats (user_id, money, prestige_level, pickaxe, last_mine_time) VALUES (?, 0, 0, 'Wooden Pickaxe', NULL)",
            (str(user_id),)
        )
        conn.commit()

        cursor.execute("SELECT * FROM mining_stats WHERE user_id = ?", (str(user_id),))
        user_data = cursor.fetchone()
    
    conn.close()
    return dict(user_data) if user_data else None

def get_user_resources(user_id):
    """Get a user's resources from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT resource_name, amount FROM mining_resources WHERE user_id = ?", (str(user_id),))
    resources = {row['resource_name']: row['amount'] for row in cursor.fetchall()}
    
    conn.close()

    for resource in RESOURCES:
        if resource not in resources:
            resources[resource] = 0
    
    return resources

def get_user_items(user_id):
    """Get items that a user has purchased."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT item_name FROM mining_items WHERE user_id = ?", (str(user_id),))
    items = [row['item_name'] for row in cursor.fetchall()]
    
    conn.close()
    return items

def update_user_money(user_id, amount):
    """Update a user's money balance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE mining_stats SET money = money + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    
    conn.close()

def update_user_resource(user_id, resource, amount):
    """Update a user's resource amount."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount FROM mining_resources WHERE user_id = ? AND resource_name = ?",
        (str(user_id), resource)
    )
    result = cursor.fetchone()
    
    if result:

        cursor.execute(
            "UPDATE mining_resources SET amount = amount + ? WHERE user_id = ? AND resource_name = ?",
            (amount, str(user_id), resource)
        )
    else:

        cursor.execute(
            "INSERT INTO mining_resources (user_id, resource_name, amount) VALUES (?, ?, ?)",
            (str(user_id), resource, amount)
        )
    
    conn.commit()
    conn.close()

def update_user_pickaxe(user_id, pickaxe):
    """Update a user's pickaxe."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE mining_stats SET pickaxe = ? WHERE user_id = ?", (pickaxe, str(user_id)))
    conn.commit()
    
    conn.close()

def add_user_item(user_id, item):
    """Add an item to a user's inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM mining_items WHERE user_id = ? AND item_name = ?",
        (str(user_id), item)
    )
    result = cursor.fetchone()
    
    if not result:

        cursor.execute(
            "INSERT INTO mining_items (user_id, item_name, purchase_time) VALUES (?, ?, ?)",
            (str(user_id), item, datetime.datetime.now())
        )
        conn.commit()
        added = True
    else:
        added = False
    
    conn.close()
    return added

def update_prestige_level(user_id, level):
    """Update a user's prestige level."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE mining_stats SET prestige_level = ? WHERE user_id = ?", (level, str(user_id)))
    conn.commit()
    
    conn.close()

def update_last_mine_time(user_id):
    """Update a user's last mine time."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE mining_stats SET last_mine_time = ? WHERE user_id = ?",
        (datetime.datetime.now(), str(user_id))
    )
    conn.commit()
    
    conn.close()

def reset_user_resources(user_id):
    """Reset a user's resources (for prestige)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM mining_resources WHERE user_id = ?", (str(user_id),))

    cursor.execute("UPDATE mining_stats SET money = 0, pickaxe = 'Wooden Pickaxe' WHERE user_id = ?", (str(user_id),))
    
    conn.commit()
    conn.close()

def get_mining_leaderboard(limit=10):
    """Get the top miners based on money + value of resources."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT user_id, money, prestige_level FROM mining_stats
    ORDER BY (money + prestige_level * ?) DESC, prestige_level DESC
    LIMIT ?
    """, (PRESTIGE_BENEFITS["base_cost"], limit))
    
    leaderboard = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return leaderboard

def get_effective_mining_cooldown(user_id):
    """Calculate the effective mining cooldown for a user based on their prestige level and items."""
    user_stats = get_user_mining_stats(user_id)
    user_items = get_user_items(user_id)
    
    cooldown = MINING_COOLDOWN

    if user_stats and user_stats['prestige_level'] > 0:
        cooldown *= (1 - (user_stats['prestige_level'] * PRESTIGE_BENEFITS["cooldown_reduction"]))

    if "Energy Drink" in user_items:
        cooldown *= (1 - SHOP_ITEMS["Energy Drink"]["effect"]["value"])
    
    return max(5, cooldown)  # Minimum 5 second cooldown

class MiningCog(commands.Cog):
    """Cog for the mining mini-game."""
    
    def __init__(self, bot):
        self.bot = bot

        initialize_db()

        self.mining_cooldowns = {}
    
    @app_commands.command(name="mine", description="⛏️ Mine for valuable resources and gems")
    async def mine(self, interaction: discord.Interaction):
        """Mine for resources and discover valuable treasures."""
        user_id = interaction.user.id

        cooldown = get_effective_mining_cooldown(user_id)
        current_time = datetime.datetime.now().timestamp()
        
        if user_id in self.mining_cooldowns:
            time_left = cooldown - (current_time - self.mining_cooldowns[user_id])
            if time_left > 0:
                embed = discord.Embed(
                    title="⏳ Mining Cooldown Active",
                    description=f"Your pickaxe needs time to recover!",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="Time Remaining",
                    value=f"**{time_left:.1f}** seconds before you can mine again",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        self.mining_cooldowns[user_id] = current_time
        update_last_mine_time(user_id)

        user_stats = get_user_mining_stats(user_id)
        user_items = get_user_items(user_id)

        pickaxe = user_stats['pickaxe']
        pickaxe_data = PICKAXES[pickaxe]
        multiplier = pickaxe_data['multiplier']

        if user_stats['prestige_level'] > 0:
            multiplier += user_stats['prestige_level'] * PRESTIGE_BENEFITS["multiplier"]

        embed = discord.Embed(
            title="⛏️ Mining Expedition Results ⛏️",
            description=f"You swung your **{pickaxe}** with mighty strength and discovered these treasures:",
            color=discord.Color.dark_gold()
        )

        mined_resources = {}
        total_value = 0

        has_metal_detector = "Metal Detector" in user_items
        metal_detector_chance = SHOP_ITEMS["Metal Detector"]["effect"]["value"] if has_metal_detector else 0

        mining_helmet_bonus = SHOP_ITEMS["Mining Helmet"]["effect"]["value"] if "Mining Helmet" in user_items else 0

        mining_gloves_bonus = SHOP_ITEMS["Mining Gloves"]["effect"]["value"] if "Mining Gloves" in user_items else 0

        has_dynamite = "Dynamite Pack" in user_items
        dynamite_chance = SHOP_ITEMS["Dynamite Pack"]["effect"]["value"] if has_dynamite else 0

        for resource, data in RESOURCES.items():

            modified_chance = data["chance"] + mining_helmet_bonus

            if has_metal_detector and data["value"] >= 20:  # 20 is Gold value
                modified_chance += metal_detector_chance

            if random.random() < modified_chance:

                base_amount = random.randint(1, 3)
                amount = int(base_amount * multiplier * (1 + mining_gloves_bonus))

                if has_dynamite and random.random() < dynamite_chance:
                    amount *= 2
                    doubled = True
                else:
                    doubled = False

                value = amount * data["value"]
                total_value += value

                mined_resources[resource] = {
                    "amount": amount,
                    "value": value,
                    "doubled": doubled
                }

                update_user_resource(user_id, resource, amount)

        update_user_money(user_id, total_value)

        for resource, data in mined_resources.items():
            embed.add_field(
                name=f"{RESOURCES[resource]['emoji']} {resource}",
                value=f"Amount: **{data['amount']}** {' 💥 **DOUBLED!** 💥' if data['doubled'] else ''}\nValue: **{data['value']}** 💎 gems",
                inline=True
            )

        embed.add_field(
            name="💰 Total Reward 💰",
            value=f"**{total_value}** 💎 gems added to your balance!",
            inline=False
        )

        embed.set_footer(text=f"Mining cooldown: {cooldown:.1f} seconds")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="balance", description="💰 Check your mining balance and resources")
    async def balance(self, interaction: discord.Interaction):
        """Check your mining balance and resources."""
        user_id = interaction.user.id

        user_stats = get_user_mining_stats(user_id)
        user_resources = get_user_resources(user_id)
        user_items = get_user_items(user_id)

        embed = discord.Embed(
            title="💰 Mining Treasure Vault 💰",
            description=f"**{interaction.user.name}'s Mining Empire**",
            color=discord.Color.green()
        )

        embed.add_field(
            name="💎 Gem Balance",
            value=f"**{user_stats['money']}** gems",
            inline=True
        )
        
        embed.add_field(
            name="⛏️ Equipment",
            value=f"**{user_stats['pickaxe']}**",
            inline=True
        )
        
        embed.add_field(
            name="✨ Prestige Level",
            value=f"**{user_stats['prestige_level']}**",
            inline=True
        )

        resources_text = ""
        for resource in sorted(RESOURCES.keys(), key=lambda r: RESOURCES[r]["value"]):
            amount = user_resources.get(resource, 0)
            if amount > 0:
                emoji = RESOURCES[resource]["emoji"]
                resources_text += f"{emoji} **{resource}**: {amount} (Worth: {amount * RESOURCES[resource]['value']} 💎)\n"
        
        embed.add_field(
            name="🏗️ Resource Storage",
            value=resources_text if resources_text else "*Your storage is empty. Start mining to collect resources!*",
            inline=False
        )

        if user_items:
            items_text = "\n".join([f"🔹 **{item}**: {SHOP_ITEMS[item]['description']}" for item in user_items])
            embed.add_field(
                name="🧰 Special Equipment",
                value=items_text,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="upgrade", description="🔨 Upgrade your pickaxe")
    async def upgrade(self, interaction: discord.Interaction):
        """Upgrade your pickaxe."""
        user_id = interaction.user.id

        user_stats = get_user_mining_stats(user_id)
        current_pickaxe = user_stats['pickaxe']
        current_level = PICKAXES[current_pickaxe]['level']

        available_pickaxes = []
        for pickaxe, data in PICKAXES.items():
            if data['level'] == current_level + 1:
                available_pickaxes.append((pickaxe, data))
        
        if not available_pickaxes:
            await interaction.response.send_message(
                f"You already have the best pickaxe available: **{current_pickaxe}**",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Choose a pickaxe upgrade:",
            view=PickaxeUpgradeView(user_id, user_stats, available_pickaxes),
            ephemeral=False
        )
    
    @app_commands.command(name="sell", description="💰 Sell your mined resources")
    @app_commands.describe(resource="The resource to sell (or 'all' to sell everything)")
    @app_commands.choices(resource=[
        app_commands.Choice(name=resource, value=resource) 
        for resource in list(RESOURCES.keys()) + ["all"]
    ])
    async def sell(self, interaction: discord.Interaction, resource: str):
        """Sell your mined resources for gems."""
        user_id = interaction.user.id

        user_resources = get_user_resources(user_id)

        if resource.lower() == "all":
            total_value = 0
            resources_sold = []
            
            for res_name, amount in user_resources.items():
                if amount > 0:
                    value = amount * RESOURCES[res_name]["value"]
                    total_value += value
                    resources_sold.append((res_name, amount, value))

                    update_user_resource(user_id, res_name, -amount)
            
            if total_value > 0:
                update_user_money(user_id, total_value)

                embed = discord.Embed(
                    title="💰 Resources Sold",
                    description=f"You sold all your resources for **{total_value}** gems!",
                    color=discord.Color.green()
                )

                for res_name, amount, value in resources_sold:
                    embed.add_field(
                        name=f"{RESOURCES[res_name]['emoji']} {res_name}",
                        value=f"Sold {amount} for {value} gems",
                        inline=True
                    )
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    "You don't have any resources to sell!",
                    ephemeral=True
                )
        else:

            if resource not in RESOURCES:
                await interaction.response.send_message(
                    f"Resource '{resource}' not recognized. Please choose a valid resource.",
                    ephemeral=True
                )
                return

            amount = user_resources.get(resource, 0)
            if amount <= 0:
                await interaction.response.send_message(
                    f"You don't have any {resource} to sell!",
                    ephemeral=True
                )
                return

            value = amount * RESOURCES[resource]["value"]

            update_user_resource(user_id, resource, -amount)
            update_user_money(user_id, value)

            embed = discord.Embed(
                title="💰 Resource Sold",
                description=f"You sold **{amount}x {RESOURCES[resource]['emoji']} {resource}** for **{value}** gems!",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="mining_shop", description="🛒 View items available in the mining shop")
    async def mining_shop(self, interaction: discord.Interaction):
        """View items available in the shop."""
        user_id = interaction.user.id

        user_stats = get_user_mining_stats(user_id)
        user_items = get_user_items(user_id)

        embed = discord.Embed(
            title="🛒 Miner's Equipment Emporium 🛒",
            description="Enhance your mining adventures with these special items!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="💎 Your Gem Balance",
            value=f"**{user_stats['money']}** gems available to spend",
            inline=False
        )

        # Define item emojis
        item_emojis = {
            "Mining Helmet": "⛑️",
            "Mining Gloves": "🧤",
            "Resource Bag": "👝",
            "Energy Drink": "🥤",
            "Metal Detector": "🔍",
            "Dynamite Pack": "💣"
        }

        for item_name, item_data in SHOP_ITEMS.items():
            owned = item_name in user_items
            emoji = item_emojis.get(item_name, "🔧")
            
            embed.add_field(
                name=f"{emoji} {item_name} - {item_data['cost']} 💎 {' ✅' if owned else ''}",
                value=f"{item_data['description']}",
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            view=ShopView(user_id, user_stats, user_items),
            ephemeral=False
        )
    
    @app_commands.command(name="mining_buy", description="🛍️ Buy an item from the mining shop")
    @app_commands.describe(item="The item to buy")
    @app_commands.choices(item=[
        app_commands.Choice(name=item, value=item) for item in SHOP_ITEMS.keys()
    ])
    async def mining_buy(self, interaction: discord.Interaction, item: str):
        """Buy an item from the shop."""
        user_id = interaction.user.id

        if item not in SHOP_ITEMS:
            await interaction.response.send_message(
                f"Item '{item}' not found in the shop.",
                ephemeral=True
            )
            return

        user_stats = get_user_mining_stats(user_id)
        user_items = get_user_items(user_id)

        if item in user_items:
            await interaction.response.send_message(
                f"You already own a **{item}**!",
                ephemeral=True
            )
            return

        item_cost = SHOP_ITEMS[item]["cost"]
        if user_stats['money'] < item_cost:
            await interaction.response.send_message(
                f"You don't have enough gems to buy a **{item}**!\n"
                f"Cost: **{item_cost}** gems\n"
                f"Your balance: **{user_stats['money']}** gems",
                ephemeral=True
            )
            return

        update_user_money(user_id, -item_cost)
        add_user_item(user_id, item)

        embed = discord.Embed(
            title="🛍️ Item Purchased",
            description=f"You bought a **{item}** for **{item_cost}** gems!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Effect",
            value=SHOP_ITEMS[item]["description"],
            inline=False
        )
        
        embed.add_field(
            name="New Balance",
            value=f"**{user_stats['money'] - item_cost}** gems",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="prestige", description="✨ Reset progress for permanent bonuses")
    async def prestige(self, interaction: discord.Interaction):
        """Reset progress in exchange for permanent bonuses."""
        user_id = interaction.user.id

        user_stats = get_user_mining_stats(user_id)
        current_prestige = user_stats['prestige_level']

        prestige_cost = PRESTIGE_BENEFITS["base_cost"] * (current_prestige + 1)

        if user_stats['money'] < prestige_cost:
            embed = discord.Embed(
                title="❌ Insufficient Gems for Prestige",
                description=f"You need more gems to ascend to the next prestige level!",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="💎 Required Gems",
                value=f"**{prestige_cost}** gems",
                inline=True
            )
            
            embed.add_field(
                name="💰 Your Balance",
                value=f"**{user_stats['money']}** gems",
                inline=True
            )
            
            embed.add_field(
                name="💎 Gems Needed",
                value=f"**{prestige_cost - user_stats['money']}** more gems",
                inline=True
            )
            
            embed.set_footer(text="Keep mining and selling resources to earn more gems!")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = PrestigeConfirmationView(user_id, current_prestige, prestige_cost)

        embed = discord.Embed(
            title="✨ Prestige Opportunity ✨",
            description="Are you ready to ascend to a higher level of mining mastery?",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🔄 Reset",
            value="• 💰 All your gems\n• 📦 All your resources\n• ⛏️ Your pickaxe (back to Wooden)",
            inline=True
        )
        
        embed.add_field(
            name="📥 Keep",
            value="• 🧰 All purchased shop items\n• 🏆 Your leaderboard status",
            inline=True
        )
        
        embed.add_field(
            name="⬆️ Gain",
            value=f"• ✨ Prestige Level {current_prestige + 1}\n"
                  f"• 💎 +{(current_prestige + 1) * PRESTIGE_BENEFITS['multiplier'] * 100}% resource rewards\n"
                  f"• ⏱️ -{(current_prestige + 1) * PRESTIGE_BENEFITS['cooldown_reduction'] * 100}% mining cooldown",
            inline=False
        )
        
        embed.add_field(
            name="💰 Cost",
            value=f"**{prestige_cost}** 💎 gems",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="lb", description="🏆 Show the mining leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show the top miners on the server."""

        leaderboard_data = get_mining_leaderboard(10)

        embed = discord.Embed(
            title="🏆 Mining Champions Leaderboard 🏆",
            description="The most successful miners in the realm!",
            color=discord.Color.gold()
        )

        # Medal emojis for top 3
        medals = ["👑", "🥈", "🥉"]
        
        for i, entry in enumerate(leaderboard_data):
            user_id = int(entry['user_id'])
            try:
                user = await self.bot.fetch_user(user_id)
                username = user.name
            except:
                username = f"User {user_id}"
            
            # Add medal emoji for top 3
            rank_display = f"{medals[i]} " if i < 3 else f"{i+1}. "
            
            # Add prestige stars
            prestige_stars = "⭐" * entry['prestige_level']
            prestige_display = f" {prestige_stars}" if entry['prestige_level'] > 0 else ""
            
            embed.add_field(
                name=f"{rank_display}{username}{prestige_display}",
                value=f"💎 **{entry['money']}** gems\n"
                      f"✨ Prestige Level: **{entry['prestige_level']}**",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

class PickaxeUpgradeView(discord.ui.View):
    """View for upgrading pickaxes."""
    
    def __init__(self, user_id, user_stats, available_pickaxes):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_stats = user_stats

        for pickaxe, data in available_pickaxes:
            button = discord.ui.Button(
                label=f"{pickaxe} - {data['cost']} gems",
                style=discord.ButtonStyle.primary,
                custom_id=f"pickaxe_{pickaxe}"
            )
            button.callback = self.make_callback(pickaxe, data)
            self.add_item(button)
    
    def make_callback(self, pickaxe, data):
        """Create a callback function for the button."""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This isn't your upgrade menu!",
                    ephemeral=True
                )
                return

            if self.user_stats['money'] < data['cost']:
                await interaction.response.send_message(
                    f"You don't have enough gems to buy a {pickaxe}!\n"
                    f"Cost: **{data['cost']}** gems\n"
                    f"Your balance: **{self.user_stats['money']}** gems",
                    ephemeral=True
                )
                return

            update_user_money(self.user_id, -data['cost'])
            update_user_pickaxe(self.user_id, pickaxe)

            embed = discord.Embed(
                title="⛏️ Pickaxe Upgraded",
                description=f"You upgraded to a **{pickaxe}** for **{data['cost']}** gems!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="New Multiplier",
                value=f"**{data['multiplier']}x** mining rewards",
                inline=True
            )
            
            embed.add_field(
                name="New Balance",
                value=f"**{self.user_stats['money'] - data['cost']}** gems",
                inline=True
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
        
        return callback

class ShopView(discord.ui.View):
    """View for the shop."""
    
    def __init__(self, user_id, user_stats, user_items):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_stats = user_stats
        self.user_items = user_items

        for item_name, item_data in SHOP_ITEMS.items():

            if item_name in user_items:
                button = discord.ui.Button(
                    label=f"{item_name} (Owned)",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                    custom_id=f"shop_{item_name}"
                )
            else:
                button = discord.ui.Button(
                    label=f"{item_name} - {item_data['cost']} gems",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"shop_{item_name}"
                )
                button.callback = self.make_callback(item_name, item_data)
            self.add_item(button)
    
    def make_callback(self, item_name, item_data):
        """Create a callback function for the button."""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This isn't your shop menu!",
                    ephemeral=True
                )
                return

            if self.user_stats['money'] < item_data['cost']:
                await interaction.response.send_message(
                    f"You don't have enough gems to buy a {item_name}!\n"
                    f"Cost: **{item_data['cost']}** gems\n"
                    f"Your balance: **{self.user_stats['money']}** gems",
                    ephemeral=True
                )
                return

            update_user_money(self.user_id, -item_data['cost'])
            add_user_item(self.user_id, item_name)

            for child in self.children:
                if child.custom_id == f"shop_{item_name}":
                    child.disabled = True
                    child.label = f"{item_name} (Owned)"
                    child.style = discord.ButtonStyle.secondary
                    break

            embed = discord.Embed(
                title="🛍️ Item Purchased",
                description=f"You bought a **{item_name}** for **{item_data['cost']}** gems!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Effect",
                value=item_data["description"],
                inline=False
            )
            
            embed.add_field(
                name="New Balance",
                value=f"**{self.user_stats['money'] - item_data['cost']}** gems",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        return callback

class PrestigeConfirmationView(discord.ui.View):
    """View for confirming prestige."""
    
    def __init__(self, user_id, current_prestige, prestige_cost):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.current_prestige = current_prestige
        self.prestige_cost = prestige_cost
    
    @discord.ui.button(label="Confirm Prestige", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your prestige confirmation!",
                ephemeral=True
            )
            return

        reset_user_resources(self.user_id)

        update_prestige_level(self.user_id, self.current_prestige + 1)

        embed = discord.Embed(
            title="✨✨ Prestige Attained! ✨✨",
            description=f"Congratulations! You've ascended to Prestige Level **{self.current_prestige + 1}**!",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🌟 New Powerful Bonuses 🌟",
            value=f"• 💎 +{(self.current_prestige + 1) * PRESTIGE_BENEFITS['multiplier'] * 100}% resource rewards\n"
                  f"• ⏱️ -{(self.current_prestige + 1) * PRESTIGE_BENEFITS['cooldown_reduction'] * 100}% mining cooldown",
            inline=False
        )
        
        embed.add_field(
            name="🔄 New Beginning 🔄",
            value="• ⛏️ Reset to a Wooden Pickaxe\n"
                  "• 💰 Reset to 0 gems\n"
                  "• 📦 Reset all resources\n"
                  "• 🧰 Kept all your special items",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your prestige confirmation!",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="Prestige cancelled. Your progress remains unchanged.",
            embed=None,
            view=None
        )

async def setup(bot):
    """Add the mining cog to the bot."""
    await bot.add_cog(MiningCog(bot))
    logger.info("Mining cog loaded")