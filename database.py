import sqlite3
import os
import time
import datetime
from logger import setup_logger

logger = setup_logger('database')

class Database:
    def __init__(self, db_name='data/leveling.db'):
        """Initialize the database connection."""

        self.db_path = db_name
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self._create_tables()

        self.settings = self.get_settings()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                coins REAL DEFAULT 0,
                prestige INTEGER DEFAULT 0,
                last_xp_time INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                voice_minutes INTEGER DEFAULT 0,
                boost_end_time INTEGER DEFAULT 0,
                boost_multiplier REAL DEFAULT 1.0,
                streaming_minutes INTEGER DEFAULT 0,
                images_shared INTEGER DEFAULT 0
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                xp_per_message INTEGER DEFAULT 15,
                xp_multiplier REAL DEFAULT 1.0,
                coins_per_level INTEGER DEFAULT 35,
                xp_cooldown INTEGER DEFAULT 60,
                base_xp_required INTEGER DEFAULT 75,
                min_xp_per_message INTEGER DEFAULT 5,
                max_xp_per_message INTEGER DEFAULT 15,
                voice_active_xp INTEGER DEFAULT 2,
                voice_inactive_xp INTEGER DEFAULT 1,
                voice_active_coins REAL DEFAULT 1.0,
                voice_inactive_coins REAL DEFAULT 0.5,
                image_xp INTEGER DEFAULT 30,
                streaming_xp INTEGER DEFAULT 5,
                streaming_coins REAL DEFAULT 3.0,
                xp_enabled INTEGER DEFAULT 1,
                levels_per_prestige INTEGER DEFAULT 100,
                max_prestige INTEGER DEFAULT 5,
                prestige_coins INTEGER DEFAULT 2000,
                prestige_boost_multiplier REAL DEFAULT 1.5,
                prestige_boost_duration INTEGER DEFAULT 172800,
                xp_cooldown_min INTEGER DEFAULT 5,
                xp_cooldown_max INTEGER DEFAULT 10
            )
        ''')

        try:
            # Check for and add missing columns in settings table
            self.cursor.execute('PRAGMA table_info(settings)')
            settings_columns = [column[1] for column in self.cursor.fetchall()]

            new_settings_columns = {
                'voice_active_xp': 'INTEGER DEFAULT 2',
                'voice_inactive_xp': 'INTEGER DEFAULT 1',
                'voice_active_coins': 'REAL DEFAULT 1.0',
                'voice_inactive_coins': 'REAL DEFAULT 0.5',
                'image_xp': 'INTEGER DEFAULT 30',
                'streaming_xp': 'INTEGER DEFAULT 5',
                'streaming_coins': 'REAL DEFAULT 3.0',
                'levels_per_prestige': 'INTEGER DEFAULT 100',
                'max_prestige': 'INTEGER DEFAULT 5', 
                'prestige_coins': 'INTEGER DEFAULT 2000',
                'prestige_boost_multiplier': 'REAL DEFAULT 1.5',
                'prestige_boost_duration': 'INTEGER DEFAULT 172800',
                'xp_cooldown_min': 'INTEGER DEFAULT 5',
                'xp_cooldown_max': 'INTEGER DEFAULT 10'
            }

            for column_name, column_def in new_settings_columns.items():
                if column_name not in settings_columns:
                    logger.info(f"Adding {column_name} column to settings table")
                    self.cursor.execute(f'ALTER TABLE settings ADD COLUMN {column_name} {column_def}')

            # Check for and add missing columns in users table
            self.cursor.execute('PRAGMA table_info(users)')
            users_columns = [column[1] for column in self.cursor.fetchall()]

            new_users_columns = {
                'voice_minutes': 'INTEGER DEFAULT 0',
                'boost_end_time': 'INTEGER DEFAULT 0',
                'boost_multiplier': 'REAL DEFAULT 1.0',
                'streaming_minutes': 'INTEGER DEFAULT 0',
                'images_shared': 'INTEGER DEFAULT 0'
            }

            for column_name, column_def in new_users_columns.items():
                if column_name not in users_columns:
                    logger.info(f"Adding {column_name} column to users table")
                    self.cursor.execute(f'ALTER TABLE users ADD COLUMN {column_name} {column_def}')

            # Update default settings
            self.cursor.execute('''
                UPDATE settings 
                SET base_xp_required = 75,
                    min_xp_per_message = 5,
                    max_xp_per_message = 15,
                    coins_per_level = 35
                WHERE id = 1 AND 
                    (base_xp_required != 75 OR 
                     min_xp_per_message != 5 OR 
                     max_xp_per_message != 15 OR
                     coins_per_level != 35)
            ''')
                
        except Exception as e:
            logger.error(f"Error checking/adding columns to database tables: {e}")

        self.cursor.execute('''
            INSERT OR IGNORE INTO settings (
                id, xp_per_message, xp_multiplier, coins_per_level, 
                xp_cooldown, base_xp_required, min_xp_per_message, max_xp_per_message
            )
            VALUES (1, 15, 1.0, 35, 60, 75, 5, 15)
        ''')
        
        self.conn.commit()
        logger.debug("Database tables created/verified")
    
    def get_settings(self):
        """Get leveling system settings."""
        self.cursor.execute('SELECT * FROM settings WHERE id = 1')
        result = self.cursor.fetchone()
        
        if result:
            columns = [column[0] for column in self.cursor.description]
            
            # Default fallback settings
            settings = {
                'xp_per_message': 15,
                'xp_multiplier': 1.0,
                'coins_per_level': 35,
                'xp_cooldown': 60,
                'base_xp_required': 75,
                'xp_enabled': 1,
                'min_xp_per_message': 5,
                'max_xp_per_message': 15,
                'voice_active_xp': 2,
                'voice_inactive_xp': 1,
                'voice_active_coins': 1.0,
                'voice_inactive_coins': 0.5,
                'image_xp': 30,
                'streaming_xp': 5,
                'streaming_coins': 3.0,
                'levels_per_prestige': 100,
                'max_prestige': 5,
                'prestige_coins': 2000,
                'prestige_boost_multiplier': 1.5,
                'prestige_boost_duration': 172800,  # 48 hours in seconds
                'xp_cooldown_min': 5,
                'xp_cooldown_max': 10
            }

            # Populate settings from database result
            try:
                for i, column_name in enumerate(columns):
                    if i < len(result):
                        settings[column_name] = result[i]
            except Exception as e:
                logger.error(f"Error mapping settings from database: {e}")
            
            return settings
        else:
            logger.error("Settings not found in database!")
            return {
                'xp_per_message': 15,
                'xp_multiplier': 1.0,
                'coins_per_level': 35,
                'xp_cooldown': 60,
                'base_xp_required': 75,
                'xp_enabled': 1,
                'min_xp_per_message': 5,
                'max_xp_per_message': 15,
                'voice_active_xp': 2,
                'voice_inactive_xp': 1,
                'voice_active_coins': 1.0,
                'voice_inactive_coins': 0.5,
                'image_xp': 30,
                'streaming_xp': 5,
                'streaming_coins': 3.0,
                'levels_per_prestige': 100,
                'max_prestige': 5,
                'prestige_coins': 2000,
                'prestige_boost_multiplier': 1.5,
                'prestige_boost_duration': 172800,  # 48 hours in seconds
                'xp_cooldown_min': 5,
                'xp_cooldown_max': 10
            }
    
    def update_settings(self, settings_dict):
        """Update leveling system settings."""

        if 'min_xp_per_message' in settings_dict or 'max_xp_per_message' in settings_dict:
            self.cursor.execute('''
                UPDATE settings
                SET xp_per_message = ?,
                    xp_multiplier = ?,
                    coins_per_level = ?,
                    xp_cooldown = ?,
                    base_xp_required = ?,
                    xp_enabled = ?,
                    min_xp_per_message = ?,
                    max_xp_per_message = ?
                WHERE id = 1
            ''', (
                settings_dict['xp_per_message'],
                settings_dict['xp_multiplier'],
                settings_dict['coins_per_level'],
                settings_dict['xp_cooldown'],
                settings_dict['base_xp_required'],
                settings_dict.get('xp_enabled', 1),
                settings_dict.get('min_xp_per_message', 10),
                settings_dict.get('max_xp_per_message', 20)
            ))
        else:

            self.cursor.execute('''
                UPDATE settings
                SET xp_per_message = ?,
                    xp_multiplier = ?,
                    coins_per_level = ?,
                    xp_cooldown = ?,
                    base_xp_required = ?,
                    xp_enabled = ?
                WHERE id = 1
            ''', (
                settings_dict['xp_per_message'],
                settings_dict['xp_multiplier'],
                settings_dict['coins_per_level'],
                settings_dict['xp_cooldown'],
                settings_dict['base_xp_required'],
                settings_dict.get('xp_enabled', 1)
            ))
        
        self.conn.commit()
        self.settings = self.get_settings()
        logger.info(f"Settings updated: {settings_dict}")
        return self.settings
    
    def get_user(self, user_id):
        """Get user data, create if not exists."""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = self.cursor.fetchone()
        
        if not user:
            return None

        # Format coins nicely
        coins = round(user[4], 2)
        if coins == int(coins):
            coins = int(coins)
            
        # Get column names for safe mapping
        columns = [column[0] for column in self.cursor.description]
        
        # Create base user data
        user_data = {
            'user_id': user[0],
            'username': user[1],
            'xp': user[2],
            'level': user[3],
            'coins': coins,
            'prestige': user[5],
            'last_xp_time': user[6],
            'message_count': 0,
            'voice_minutes': 0,
            'boost_end_time': 0,
            'boost_multiplier': 1.0,
            'streaming_minutes': 0,
            'images_shared': 0
        }
        
        # Add additional fields if they exist in the database
        additional_fields = {
            'message_count': 7,
            'voice_minutes': 8,
            'boost_end_time': 9,
            'boost_multiplier': 10,
            'streaming_minutes': 11,
            'images_shared': 12
        }
        
        for field_name, index in additional_fields.items():
            if len(user) > index:
                user_data[field_name] = user[index]
                
        return user_data
    
    def create_user(self, user_id, username):
        """Create a new user in the database."""
        self.cursor.execute(
            '''INSERT OR IGNORE INTO users 
               (user_id, username, xp, level, coins, prestige, last_xp_time, message_count,
                voice_minutes, boost_end_time, boost_multiplier, streaming_minutes, images_shared) 
               VALUES (?, ?, 0, 1, 0, 0, 0, 0, 0, 0, 1.0, 0, 0)''',
            (user_id, username)
        )
        self.conn.commit()
        return self.get_user(user_id)
    
    def get_or_create_user(self, user_id, username):
        """Get user data or create if not exists."""
        user = self.get_user(user_id)
        if not user:
            user = self.create_user(user_id, username)
            if not user:
                logger.error(f"Failed to create user {username} ({user_id})")

                return {
                    'user_id': user_id,
                    'username': username,
                    'xp': 0,
                    'level': 1,
                    'coins': 0,
                    'prestige': 0,
                    'last_xp_time': 0,
                    'message_count': 0,
                    'voice_minutes': 0,
                    'boost_end_time': 0,
                    'boost_multiplier': 1.0,
                    'streaming_minutes': 0,
                    'images_shared': 0
                }
        return user
    
    def update_username(self, user_id, new_username):
        """Update a user's username."""
        self.cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (new_username, user_id))
        self.conn.commit()
    
    def update_user(self, user_id, data):
        """Update user data with the provided values."""

        set_clauses = []
        params = []
        
        for key, value in data.items():
            set_clauses.append(f"{key} = ?")
            params.append(value)

        params.append(user_id)

        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = ?"
        self.cursor.execute(query, params)
        self.conn.commit()
    
    def get_user_perk_boosts(self, user_id):
        """Get a user's active perk boosts from the shop system.
        
        Returns:
            dict: Dictionary with keys for different boost types and their multiplier values
        """
        try:
            import json
            import os
            
            # Default boosts (no boost)
            boosts = {
                'xp': 1.0,
                'coins': 1.0,
                'voice_xp': 1.0,
                'message_xp': 1.0,
                'image_xp': 1.0
            }
            
            perks_file = f'data/user_perks/{user_id}.json'
            if not os.path.exists(perks_file):
                return boosts
                
            with open(perks_file, 'r') as f:
                perks_data = json.load(f)
                
            # Apply permanent boosts
            permanent_boosts = perks_data.get('permanent_boosts', {})
            for stat, value in permanent_boosts.items():
                if stat in boosts:
                    boosts[stat] = value
            
            # Apply temporary boosts
            current_time = int(time.time())
            active_boosts = perks_data.get('active_boosts', [])
            
            for boost in active_boosts:
                if boost.get('end_time', 0) <= current_time:
                    continue  # Skip expired boosts
                    
                stat = boost.get('stat')
                value = boost.get('value', 1.0)
                
                if stat in boosts:
                    # Apply the highest boost only
                    boosts[stat] = max(boosts[stat], value)
            
            return boosts
        except Exception as e:
            logger.error(f"Error getting perk boosts for user {user_id}: {e}")
            # Return default values if there's an error
            return {
                'xp': 1.0,
                'coins': 1.0,
                'voice_xp': 1.0,
                'message_xp': 1.0,
                'image_xp': 1.0
            }
    
    def add_xp(self, user_id, username, xp_amount=None, xp_multiplier=1.0, coin_multiplier=1.0):
        """Add XP to a user and handle level ups. Also checks for and applies prestige boost."""

        logger.info(f"add_xp called for {username} (ID: {user_id})")
        
        # Check if XP gain is globally disabled
        if not self.settings.get('xp_enabled', 1):
            logger.info("XP gain is disabled globally")
            return None, False, 0  # XP gain is disabled, no level up, 0 XP
            
        # Determine XP amount if not provided
        if xp_amount is None:
            min_xp = self.settings.get('min_xp_per_message', 0)
            max_xp = self.settings.get('max_xp_per_message', 0)
            
            if min_xp > 0 and max_xp > 0 and min_xp != max_xp:
                import random
                xp_amount = random.randint(min_xp, max_xp)
                logger.info(f"Random XP amount generated: {xp_amount} (min: {min_xp}, max: {max_xp})")
            else:
                xp_amount = self.settings['xp_per_message']
                logger.info(f"Using fixed XP amount: {xp_amount}")
        else:
            logger.info(f"Using provided XP amount: {xp_amount}")
        
        user = self.get_or_create_user(user_id, username)
        if user is None:
            logger.error(f"Failed to get or create user {username} ({user_id})")
            return None, False, 0  # No user, no level up, 0 XP
            
        current_time = int(time.time())
        
        # Get user's perk boosts
        perk_boosts = self.get_user_perk_boosts(user_id)
        message_xp_boost = perk_boosts.get('message_xp', 1.0)  # For message-specific boost
        general_xp_boost = perk_boosts.get('xp', 1.0)  # For general XP boost
        coin_boost = perk_boosts.get('coins', 1.0)  # For coin boost
        
        # Apply message XP boost and general XP boost to XP multiplier
        if message_xp_boost > 1.0 or general_xp_boost > 1.0:
            old_multiplier = xp_multiplier
            xp_multiplier *= message_xp_boost * general_xp_boost
            logger.info(f"Applied perk boosts: message_xp_boost={message_xp_boost}x, general_xp_boost={general_xp_boost}x")
            logger.info(f"XP multiplier updated from {old_multiplier}x to {xp_multiplier}x")
            
        # Apply coin boost to coin multiplier
        if coin_boost > 1.0:
            old_coin_multiplier = coin_multiplier
            coin_multiplier *= coin_boost
            logger.info(f"Applied coin boost: {coin_boost}x (new multiplier: {coin_multiplier}x)")
        
        # Check if user has an active prestige boost
        boost_end_time = user.get('boost_end_time', 0)
        boost_multiplier = user.get('boost_multiplier', 1.0)
        has_active_boost = boost_end_time > current_time
        
        if has_active_boost:
            logger.info(f"User {username} has active prestige boost! ({boost_multiplier}x XP boost until {datetime.datetime.fromtimestamp(boost_end_time).strftime('%Y-%m-%d %H:%M:%S')})")
            xp_multiplier *= boost_multiplier
            logger.info(f"Updated XP multiplier with boost: {xp_multiplier}x")
        elif boost_end_time > 0 and boost_multiplier > 1.0:
            # Expired boost should be reset
            boost_multiplier = 1.0
            boost_end_time = 0
            logger.info(f"User {username} had a boost but it expired. Resetting boost.")
            self.cursor.execute('UPDATE users SET boost_multiplier = 1.0, boost_end_time = 0 WHERE user_id = ?', (user_id,))
            
        # Calculate final XP to add with all multipliers
        xp_to_add = round(xp_amount * xp_multiplier)
        logger.info(f"XP to add after all multipliers: {xp_to_add}")
        
        # Check for cooldown
        last_xp_time = user.get('last_xp_time', 0)
        cooldown = self.settings['xp_cooldown']
        time_since_last_xp = current_time - last_xp_time
        
        logger.info(f"Last XP time: {last_xp_time}, Current time: {current_time}, Cooldown: {cooldown}")
        logger.info(f"Time since last XP: {time_since_last_xp} seconds")
        
        if time_since_last_xp < cooldown:
            logger.info(f"User is on cooldown. Needs to wait {cooldown - time_since_last_xp} more seconds")
            return None, False, 0  # Still on cooldown, no level up, 0 XP

        # Update XP and message count
        new_xp = user['xp'] + xp_to_add
        new_message_count = user.get('message_count', 0) + 1
        
        logger.info(f"Updating user {username} ({user_id}) - Current XP: {user['xp']}, Adding: {xp_to_add}, New XP: {new_xp}")
        logger.info(f"Setting last_xp_time to {current_time} ({datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')})")
        
        try:
            self.cursor.execute('UPDATE users SET xp = ?, last_xp_time = ?, message_count = ? WHERE user_id = ?', 
                              (new_xp, current_time, new_message_count, user_id))

            self.cursor.execute('SELECT xp, last_xp_time FROM users WHERE user_id = ?', (user_id,))
            verify_result = self.cursor.fetchone()
            logger.info(f"Verification after update: XP = {verify_result[0]}, last_xp_time = {verify_result[1]}")
            
        except Exception as e:
            logger.error(f"Error updating user XP: {e}")

        # Check for level up
        current_level = user['level']
        required_xp = self.calculate_required_xp(current_level)
        
        level_up = False
        new_level = current_level
        
        # Handle level ups
        while new_xp >= required_xp:
            new_level += 1
            new_xp -= required_xp
            required_xp = self.calculate_required_xp(new_level)
            level_up = True
        
        if level_up:
            coins_to_add = round(self.settings['coins_per_level'] * (new_level - current_level) * coin_multiplier)
            new_coins = user['coins'] + coins_to_add
            
            logger.info(f"Level up for {username}: Level {current_level} -> {new_level}, Coins: +{coins_to_add}")
            
            try:
                self.cursor.execute('UPDATE users SET level = ?, xp = ?, coins = ? WHERE user_id = ?', 
                                  (new_level, new_xp, new_coins, user_id))

                self.cursor.execute('SELECT level, xp, coins FROM users WHERE user_id = ?', (user_id,))
                verify_result = self.cursor.fetchone()
                logger.info(f"Verification after level up: Level = {verify_result[0]}, XP = {verify_result[1]}, Coins = {verify_result[2]}")
                
                # Check if this level up makes the user eligible for prestige
                levels_per_prestige = self.settings.get('levels_per_prestige', 100)
                max_prestige = self.settings.get('max_prestige', 5)
                
                if new_level >= levels_per_prestige and user['prestige'] < max_prestige:
                    logger.info(f"User {username} reached level {new_level} and is eligible for prestige!")
                
            except Exception as e:
                logger.error(f"Error updating user level: {e}")
        
        try:
            self.conn.commit()
            logger.info(f"Database commit successful for user {username} ({user_id})")
        except Exception as e:
            logger.error(f"Error committing changes to database: {e}")
            try:
                self.conn.rollback()
                logger.info("Database rollback performed")
            except Exception as e2:
                logger.error(f"Error rolling back transaction: {e2}")

        updated_user = self.get_user(user_id)
        return updated_user, level_up, xp_to_add
    
    def add_coins(self, user_id, username, amount):
        """Add coins to a user. No coins are added if XP/coin gain is disabled and command is not /addcoin."""

        import traceback
        call_stack = traceback.extract_stack()
        is_addcoin_command = any('addcoin' in frame.name for frame in call_stack)

        if not is_addcoin_command and not self.settings.get('xp_enabled', 1):
            logger.debug(f"Skipping coin addition for {username}: XP/coins gain is disabled globally")
            return self.get_user(user_id)  # Return current user data without changes
            
        user = self.get_or_create_user(user_id, username)
        if user is None:
            logger.error(f"Failed to get or create user {username} ({user_id})")
            return None

        rounded_amount = round(amount)
        new_coins = user['coins'] + rounded_amount

        source = "via /addcoin" if is_addcoin_command else "normal gain"
        logger.debug(f"Adding {rounded_amount} coins to {username} ({user_id}) {source}")
        
        self.cursor.execute('UPDATE users SET coins = ? WHERE user_id = ?', (new_coins, user_id))
        self.conn.commit()
        
        return self.get_user(user_id)
    
    def prestige_user(self, user_id, username):
        """Prestige a user - reset level and xp, keep coins, increase prestige, and add XP boost."""
        user = self.get_or_create_user(user_id, username)
        if user is None:
            logger.error(f"Failed to get or create user {username} ({user_id})")
            return False, None
        
        # Get the required level for prestige from settings, default to 100
        required_level = self.settings.get('levels_per_prestige', 100)
        
        if user['level'] < required_level:  # Minimum level required to prestige
            logger.info(f"User {username} ({user_id}) tried to prestige at level {user['level']}, but level {required_level} is required")
            return False, user
        
        # Check if user already reached max prestige
        max_prestige = self.settings.get('max_prestige', 5)
        if user['prestige'] >= max_prestige:
            logger.info(f"User {username} ({user_id}) tried to prestige but already at max prestige {max_prestige}")
            return False, user
        
        new_prestige = user['prestige'] + 1
        
        # Calculate boost end time and rewards
        current_time = int(time.time())
        boost_duration = self.settings.get('prestige_boost_duration', 172800)  # 48 hours in seconds
        boost_end_time = current_time + boost_duration
        boost_multiplier = self.settings.get('prestige_boost_multiplier', 1.5)
        prestige_coins = self.settings.get('prestige_coins', 2000)
        
        # Add prestige reward coins
        new_coins = user['coins'] + prestige_coins
        
        logger.info(f"User {username} ({user_id}) prestiging: Prestige {user['prestige']} -> {new_prestige}, +{prestige_coins} coins, {boost_multiplier}x XP boost for {boost_duration/3600} hours")
        
        self.cursor.execute('''
            UPDATE users 
            SET level = 1, 
                xp = 0, 
                prestige = ?,
                coins = ?,
                boost_end_time = ?,
                boost_multiplier = ?
            WHERE user_id = ?
        ''', (new_prestige, new_coins, boost_end_time, boost_multiplier, user_id))
        
        self.conn.commit()
        return True, self.get_user(user_id)
    
    def calculate_required_xp(self, level):
        """Calculate XP required for a given level."""

        base_xp = self.settings['base_xp_required']
        return base_xp * level
    
    def get_leaderboard(self, limit=10):
        """Get the top users by level and XP."""

        self.cursor.execute('''
            SELECT user_id, username, xp, level, coins, prestige
            FROM users
            ORDER BY prestige DESC, level DESC, xp DESC
            LIMIT ?
        ''', (limit,))
        
        result = []
        for row in self.cursor.fetchall():

            coins = round(row[4], 2)

            if coins == int(coins):
                coins = int(coins)
                
            result.append({
                'user_id': row[0],
                'username': row[1],
                'xp': row[2],
                'level': row[3],
                'coins': coins,
                'prestige': row[5]
            })
        return result
    
    def toggle_xp(self, enable=True):
        """Enable or disable XP and coin gain globally."""

        self.cursor.execute('UPDATE settings SET xp_enabled = ? WHERE id = 1', (1 if enable else 0,))
        self.conn.commit()

        self.settings = self.get_settings()
        logger.info(f"XP and coin gain {'enabled' if enable else 'disabled'}")
        return self.settings
    
    def get_xp_status(self):
        """Get the current XP and coin gain status (enabled/disabled)."""
        return bool(self.settings.get('xp_enabled', 1))
    
    def add_coins_simple(self, user_id, amount):
        """Add coins to a user without additional validations.
        Used for simple coin adjustments.
        """
        if not user_id:
            logger.error("Cannot add coins: user_id is empty")
            return False
            
        user = self.get_user(user_id)
        if not user:
            logger.error(f"Failed to get user {user_id}")
            return False

        new_coins = user['coins'] + amount
        
        logger.debug(f"Adding {amount} coins to user {user_id}. New balance: {new_coins}")
        
        try:
            self.cursor.execute('UPDATE users SET coins = ? WHERE user_id = ?', (new_coins, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding coins to user {user_id}: {e}")
            return False
            
    def remove_coins(self, user_id, amount):
        """Remove coins from a user."""
        if not user_id:
            logger.error("Cannot remove coins: user_id is empty")
            return False
            
        user = self.get_user(user_id)
        if not user:
            logger.error(f"Failed to get user {user_id}")
            return False
            
        if user['coins'] < amount:
            logger.debug(f"Insufficient coins: User {user_id} has {user['coins']} coins, but {amount} are needed")
            return False
            
        new_coins = user['coins'] - amount
        
        logger.debug(f"Removing {amount} coins from user {user_id}. New balance: {new_coins}")
        
        try:
            self.cursor.execute('UPDATE users SET coins = ? WHERE user_id = ?', (new_coins, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error removing coins from user {user_id}: {e}")
            return False
    
    def add_voice_activity(self, user_id, username, minutes, is_streaming=False, is_active=True):
        """Add voice activity time and reward XP and coins.
        
        Args:
            user_id (str): The user's Discord ID
            username (str): The user's Discord username
            minutes (int): Number of minutes spent in voice channel
            is_streaming (bool): Whether the user was streaming
            is_active (bool): Whether the user was active (speaking/unmuted)
            
        Returns:
            tuple: (user_data, xp_gained, coins_gained)
        """
        if not self.settings.get('xp_enabled', 1):
            logger.info(f"Voice XP gain is disabled globally for {username}")
            return self.get_user(user_id), 0, 0
            
        user = self.get_or_create_user(user_id, username)
        if user is None:
            logger.error(f"Failed to get or create user {username} ({user_id})")
            return None, 0, 0
            
        # Update voice minutes counter
        current_voice_minutes = user.get('voice_minutes', 0)
        new_voice_minutes = current_voice_minutes + minutes
        
        # Initialize streaming minutes variable
        new_streaming_minutes = 0
        
        # Calculate XP to add based on activity type
        if is_streaming:
            xp_per_minute = self.settings.get('streaming_xp', 5)
            coins_per_minute = self.settings.get('streaming_coins', 3.0)
            current_streaming_minutes = user.get('streaming_minutes', 0)
            new_streaming_minutes = current_streaming_minutes + minutes
            activity_type = "streaming"
        elif is_active:
            xp_per_minute = self.settings.get('voice_active_xp', 2)
            coins_per_minute = self.settings.get('voice_active_coins', 1.0)
            activity_type = "active"
        else:
            xp_per_minute = self.settings.get('voice_inactive_xp', 1)
            coins_per_minute = self.settings.get('voice_inactive_coins', 0.5)
            activity_type = "inactive"
        
        # Get user's perk boosts
        perk_boosts = self.get_user_perk_boosts(user_id)
        voice_xp_boost = perk_boosts.get('voice_xp', 1.0)  # For voice-specific boost
        general_xp_boost = perk_boosts.get('xp', 1.0)  # For general XP boost
        coin_boost = perk_boosts.get('coins', 1.0)  # For coin boost
        
        # Apply voice XP boost and general XP boost
        xp_multiplier = 1.0
        if voice_xp_boost > 1.0 or general_xp_boost > 1.0:
            xp_multiplier = voice_xp_boost * general_xp_boost
            logger.info(f"Applied perk boosts for voice activity: voice_xp_boost={voice_xp_boost}x, general_xp_boost={general_xp_boost}x")
            logger.info(f"XP multiplier: {xp_multiplier}x")
            
        # Apply coin boost
        if coin_boost > 1.0:
            coins_per_minute *= coin_boost
            logger.info(f"Applied coin boost for voice activity: {coin_boost}x (new coins_per_minute: {coins_per_minute})")
        
        # Check if user has an active prestige boost
        current_time = int(time.time())
        boost_end_time = user.get('boost_end_time', 0)
        boost_multiplier = user.get('boost_multiplier', 1.0)
        
        has_active_boost = boost_end_time > current_time
        
        if has_active_boost:
            logger.info(f"User {username} has active prestige boost! ({boost_multiplier}x XP boost)")
            xp_multiplier = boost_multiplier
        else:
            xp_multiplier = 1.0
        
        # Calculate total XP and coins to add
        xp_to_add = round(xp_per_minute * minutes * xp_multiplier)
        coins_to_add = round(coins_per_minute * minutes, 2)
        
        logger.info(f"Adding voice activity for {username} ({user_id}): {minutes} minutes {activity_type}, +{xp_to_add} XP, +{coins_to_add} coins")
        
        # Update user stats
        try:
            if is_streaming:
                self.cursor.execute('''
                    UPDATE users 
                    SET voice_minutes = ?, 
                        streaming_minutes = ?,
                        xp = xp + ?,
                        coins = coins + ?
                    WHERE user_id = ?
                ''', (new_voice_minutes, new_streaming_minutes, xp_to_add, coins_to_add, user_id))
            else:
                self.cursor.execute('''
                    UPDATE users 
                    SET voice_minutes = ?,
                        xp = xp + ?,
                        coins = coins + ?
                    WHERE user_id = ?
                ''', (new_voice_minutes, xp_to_add, coins_to_add, user_id))
                
            self.conn.commit()
            
            # Check for level ups after adding XP
            updated_user = self.get_user(user_id)
            if updated_user is None:
                logger.error(f"Failed to retrieve updated user after voice activity update for {username} ({user_id})")
                return user, xp_to_add, coins_to_add
                
            current_xp = updated_user['xp']
            current_level = updated_user['level']
            required_xp = self.calculate_required_xp(current_level)
            
            if current_xp >= required_xp:
                # Handle level up
                new_xp = current_xp
                new_level = current_level
                
                while new_xp >= self.calculate_required_xp(new_level):
                    new_xp -= self.calculate_required_xp(new_level)
                    new_level += 1
                
                level_coins = self.settings.get('coins_per_level', 35) * (new_level - current_level)
                new_coins = updated_user['coins'] + level_coins
                
                logger.info(f"Voice activity caused level up for {username}: Level {current_level} -> {new_level}, +{level_coins} coins")
                
                self.cursor.execute('''
                    UPDATE users 
                    SET level = ?,
                        xp = ?,
                        coins = ?
                    WHERE user_id = ?
                ''', (new_level, new_xp, new_coins, user_id))
                self.conn.commit()
                
                final_user = self.get_user(user_id)
                if final_user is not None:
                    return final_user, xp_to_add, coins_to_add
            
            return updated_user, xp_to_add, coins_to_add
            
        except Exception as e:
            logger.error(f"Error updating voice activity for {username} ({user_id}): {e}")
            return user, 0, 0
    
    def add_image_share(self, user_id, username):
        """Add XP and coins for sharing an image and track image shares.
        
        Args:
            user_id (str): The user's Discord ID
            username (str): The user's Discord username
            
        Returns:
            tuple: (user_data, xp_gained, coins_gained)
        """
        if not self.settings.get('xp_enabled', 1):
            logger.info(f"Image XP gain is disabled globally for {username}")
            return self.get_user(user_id), 0, 0
            
        user = self.get_or_create_user(user_id, username)
        if user is None:
            logger.error(f"Failed to get or create user {username} ({user_id})")
            return None, 0, 0
            
        # Calculate XP to add
        xp_per_image = self.settings.get('image_xp', 30)
        
        # Get user's perk boosts
        perk_boosts = self.get_user_perk_boosts(user_id)
        image_xp_boost = perk_boosts.get('image_xp', 1.0)  # For image-specific boost
        general_xp_boost = perk_boosts.get('xp', 1.0)  # For general XP boost
        
        # Apply image XP boost and general XP boost
        xp_multiplier = 1.0
        if image_xp_boost > 1.0 or general_xp_boost > 1.0:
            xp_multiplier = image_xp_boost * general_xp_boost
            logger.info(f"Applied perk boosts for image sharing: image_xp_boost={image_xp_boost}x, general_xp_boost={general_xp_boost}x")
            logger.info(f"XP multiplier: {xp_multiplier}x")
            
        # Check if user has an active prestige boost
        current_time = int(time.time())
        boost_end_time = user.get('boost_end_time', 0)
        boost_multiplier = user.get('boost_multiplier', 1.0)
        
        has_active_boost = boost_end_time > current_time
        
        if has_active_boost:
            logger.info(f"User {username} has active prestige boost! ({boost_multiplier}x XP boost)")
            xp_multiplier *= boost_multiplier
            logger.info(f"Updated XP multiplier with prestige boost: {xp_multiplier}x")
        
        # Calculate total XP to add
        xp_to_add = round(xp_per_image * xp_multiplier)
        
        # Track image sharing
        current_images_shared = user.get('images_shared', 0)
        new_images_shared = current_images_shared + 1
        
        logger.info(f"Adding image share for {username} ({user_id}): +{xp_to_add} XP, total shares: {new_images_shared}")
        
        # Update user stats
        try:
            self.cursor.execute('''
                UPDATE users 
                SET images_shared = ?,
                    xp = xp + ?
                WHERE user_id = ?
            ''', (new_images_shared, xp_to_add, user_id))
                
            self.conn.commit()
            
            # Check for level ups after adding XP
            updated_user = self.get_user(user_id)
            if updated_user is None:
                logger.error(f"Failed to retrieve updated user after image share for {username} ({user_id})")
                return user, xp_to_add, 0
                
            current_xp = updated_user['xp']
            current_level = updated_user['level']
            required_xp = self.calculate_required_xp(current_level)
            
            if current_xp >= required_xp:
                # Handle level up
                new_xp = current_xp
                new_level = current_level
                
                while new_xp >= self.calculate_required_xp(new_level):
                    new_xp -= self.calculate_required_xp(new_level)
                    new_level += 1
                
                level_coins = self.settings.get('coins_per_level', 35) * (new_level - current_level)
                new_coins = updated_user['coins'] + level_coins
                
                logger.info(f"Image share caused level up for {username}: Level {current_level} -> {new_level}, +{level_coins} coins")
                
                self.cursor.execute('''
                    UPDATE users 
                    SET level = ?,
                        xp = ?,
                        coins = ?
                    WHERE user_id = ?
                ''', (new_level, new_xp, new_coins, user_id))
                self.conn.commit()
                
                final_user = self.get_user(user_id)
                if final_user is not None:
                    return final_user, xp_to_add, level_coins
                    
                # Fallback if we can't get the user
                return updated_user, xp_to_add, level_coins
            
            return updated_user, xp_to_add, 0
            
        except Exception as e:
            logger.error(f"Error updating image share for {username} ({user_id}): {e}")
            return user, 0, 0
        
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")