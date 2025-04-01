import os
import datetime
import time
import json
import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from logger import setup_logger

logger = setup_logger('pg_database')

class PGDatabase:
    """PostgreSQL database manager for user data that persists across hosting platforms."""
    
    def __init__(self):
        """Initialize the PostgreSQL database connection."""
        # Get DATABASE_URL from environment
        self.database_url = os.environ.get('DATABASE_URL')
        
        if not self.database_url:
            logger.error("DATABASE_URL not found in environment variables")
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.conn = None
        self.connect()
        self._create_tables()
        
        self.settings = self.get_settings()
        logger.info("PostgreSQL database initialized")
    
    def connect(self):
        """Establish a connection to the PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(self.database_url)
            self.conn.autocommit = True
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL database: {e}", exc_info=True)
            raise
    
    def ensure_connection(self):
        """Ensure the database connection is active, reconnect if needed."""
        try:
            # Test if connection is alive
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception:
            logger.warning("Database connection lost, reconnecting...")
            self.connect()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        self.ensure_connection()
        
        with self.conn.cursor() as cursor:
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    coins REAL DEFAULT 0,
                    prestige INTEGER DEFAULT 0,
                    last_xp_time BIGINT DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    voice_minutes INTEGER DEFAULT 0,
                    boost_end_time BIGINT DEFAULT 0,
                    boost_multiplier REAL DEFAULT 1.0,
                    streaming_minutes INTEGER DEFAULT 0,
                    images_shared INTEGER DEFAULT 0
                )
            ''')
            
            # Create settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    setting_id INTEGER PRIMARY KEY,
                    base_xp INTEGER DEFAULT 75,
                    xp_per_level INTEGER DEFAULT 75,
                    coins_per_level INTEGER DEFAULT 35,
                    min_xp_per_message INTEGER DEFAULT 15,
                    max_xp_per_message INTEGER DEFAULT 25,
                    xp_cooldown INTEGER DEFAULT 60,
                    voice_xp_per_minute INTEGER DEFAULT 2
                )
            ''')
            
            # Create invites table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invites (
                    user_id BIGINT PRIMARY KEY,
                    real INTEGER DEFAULT 0,
                    fake INTEGER DEFAULT 0,
                    left INTEGER DEFAULT 0,
                    bonus INTEGER DEFAULT 0
                )
            ''')
            
            # Create mining_stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mining_stats (
                    user_id BIGINT PRIMARY KEY,
                    money REAL DEFAULT 0,
                    prestige_level INTEGER DEFAULT 0,
                    tool TEXT DEFAULT 'Wooden Pickaxe',
                    auto_sell BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Create mining_resources table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mining_resources (
                    user_id BIGINT,
                    resource_name TEXT,
                    amount INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, resource_name)
                )
            ''')
            
            # Create mining_items table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mining_items (
                    user_id BIGINT,
                    item_name TEXT,
                    amount INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_name)
                )
            ''')
            
            # Create profiles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id BIGINT PRIMARY KEY,
                    mini_bio TEXT,
                    standing_level TEXT,
                    behavioral_stance TEXT,
                    timezone TEXT,
                    preferred_languages TEXT,
                    announcement_preferences TEXT,
                    infractions TEXT
                )
            ''')
            
            # Insert default settings if needed
            cursor.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO settings (
                        setting_id, base_xp, xp_per_level, coins_per_level, 
                        min_xp_per_message, max_xp_per_message, xp_cooldown, voice_xp_per_minute
                    ) VALUES (1, 75, 75, 35, 15, 25, 60, 2)
                ''')
    
    def get_user(self, user_id):
        """Get user data from the database."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                return dict(user_data)
            else:
                return None
    
    def create_user(self, user_id, username):
        """Create a new user in the database."""
        self.ensure_connection()
        
        with self.conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO users (user_id, username, xp, level, coins)
                VALUES (%s, %s, 0, 1, 0)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, username))
        
        return self.get_user(user_id) or {"user_id": user_id, "username": username, "xp": 0, "level": 1, "coins": 0}
    
    def update_user(self, user_id, data):
        """Update user data in the database."""
        self.ensure_connection()
        
        # Create column placeholders and values for SQL
        columns = []
        values = []
        for key, value in data.items():
            columns.append(sql.Identifier(key))
            values.append(value)
        
        # Add user_id to values
        values.append(user_id)
        
        # Construct the SQL query using psycopg2.sql to safely handle identifiers
        update_query = sql.SQL("UPDATE users SET {} WHERE user_id = %s").format(
            sql.SQL(', ').join(
                sql.SQL("{} = %s").format(column) 
                for column in columns
            )
        )
        
        with self.conn.cursor() as cursor:
            cursor.execute(update_query, values)
    
    def add_xp(self, user_id, username, xp_amount):
        """Add XP to a user and handle level ups."""
        self.ensure_connection()
        
        # Get or create user
        user_data = self.get_user(user_id)
        if not user_data:
            user_data = self.create_user(user_id, username)
        
        # Update XP
        current_xp = user_data.get('xp', 0)
        current_level = user_data.get('level', 1)
        
        new_xp = current_xp + xp_amount
        
        # Calculate if level up occurred
        base_xp = self.settings.get('base_xp', 75)
        xp_per_level = self.settings.get('xp_per_level', 75)
        coins_per_level = self.settings.get('coins_per_level', 35)
        
        xp_needed = base_xp + (current_level - 1) * xp_per_level
        
        coins_earned = 0
        new_level = current_level
        
        # Check for level ups (may be multiple)
        while new_xp >= xp_needed:
            new_xp -= xp_needed
            new_level += 1
            coins_earned += coins_per_level
            
            # Calculate next level's XP requirement
            xp_needed = base_xp + (new_level - 1) * xp_per_level
        
        # Update user data
        user_data['xp'] = new_xp
        user_data['level'] = new_level
        user_data['coins'] = user_data.get('coins', 0) + coins_earned
        user_data['last_xp_time'] = int(time.time())
        
        # Update in database
        self.update_user(user_id, {
            'xp': new_xp,
            'level': new_level,
            'coins': user_data['coins'],
            'last_xp_time': user_data['last_xp_time']
        })
        
        return {
            'new_xp': new_xp,
            'new_level': new_level,
            'leveled_up': new_level > current_level,
            'coins_earned': coins_earned
        }
    
    def add_coins(self, user_id, username, amount):
        """Add coins to a user's balance."""
        self.ensure_connection()
        
        # Get or create user
        user_data = self.get_user(user_id)
        if not user_data:
            user_data = self.create_user(user_id, username)
        
        # Update coins
        current_coins = user_data.get('coins', 0)
        new_coins = current_coins + amount
        
        # Update in database
        self.update_user(user_id, {'coins': new_coins})
        
        return {
            'old_balance': current_coins,
            'new_balance': new_coins,
            'amount_added': amount
        }
    
    def remove_coins(self, user_id, username, amount):
        """Remove coins from a user's balance."""
        self.ensure_connection()
        
        # Get or create user
        user_data = self.get_user(user_id)
        if not user_data:
            user_data = self.create_user(user_id, username)
        
        # Update coins
        current_coins = user_data.get('coins', 0)
        new_coins = max(0, current_coins - amount)  # Prevent negative balance
        
        # Update in database
        self.update_user(user_id, {'coins': new_coins})
        
        return {
            'old_balance': current_coins,
            'new_balance': new_coins,
            'amount_removed': current_coins - new_coins
        }
    
    def get_top_users(self, limit=10, offset=0, by_xp=True):
        """Get the top users ranked by XP or coins."""
        self.ensure_connection()
        
        order_by = "level DESC, xp DESC" if by_xp else "coins DESC"
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(f"SELECT * FROM users ORDER BY {order_by} LIMIT %s OFFSET %s", 
                          (limit, offset))
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_user_rank(self, user_id, by_xp=True):
        """Get a user's rank position."""
        self.ensure_connection()
        
        order_by = "level DESC, xp DESC" if by_xp else "coins DESC"
        
        with self.conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT position FROM (
                    SELECT user_id, ROW_NUMBER() OVER (ORDER BY {order_by}) as position
                    FROM users
                ) ranks
                WHERE user_id = %s
            """, (user_id,))
            
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_settings(self):
        """Get settings for the leveling system."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM settings WHERE setting_id = 1")
            settings = cursor.fetchone()
            
            if settings:
                return dict(settings)
            else:
                # Create default settings
                default_settings = {
                    'setting_id': 1,
                    'base_xp': 75,
                    'xp_per_level': 75,
                    'coins_per_level': 35,
                    'min_xp_per_message': 15,
                    'max_xp_per_message': 25,
                    'xp_cooldown': 60,
                    'voice_xp_per_minute': 2
                }
                
                columns = default_settings.keys()
                values = [default_settings[col] for col in columns]
                
                cursor.execute(f"""
                    INSERT INTO settings ({', '.join(columns)})
                    VALUES ({', '.join(['%s'] * len(values))})
                """, values)
                
                return default_settings
    
    def update_settings(self, settings):
        """Update settings for the leveling system."""
        self.ensure_connection()
        
        with self.conn.cursor() as cursor:
            # Remove setting_id from the dict for updates
            update_settings = settings.copy()
            if 'setting_id' in update_settings:
                del update_settings['setting_id']
            
            # Create column placeholders and values for SQL
            columns = []
            values = []
            for key, value in update_settings.items():
                columns.append(sql.Identifier(key))
                values.append(value)
            
            # Construct the SQL query
            update_query = sql.SQL("UPDATE settings SET {} WHERE setting_id = 1").format(
                sql.SQL(', ').join(
                    sql.SQL("{} = %s").format(column) 
                    for column in columns
                )
            )
            
            cursor.execute(update_query, values)
        
        # Update local settings cache
        self.settings = self.get_settings()
        return self.settings
    
    def get_invite_stats(self, user_id):
        """Get invite statistics for a user."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM invites WHERE user_id = %s", (user_id,))
            invite_data = cursor.fetchone()
            
            if invite_data:
                return dict(invite_data)
            else:
                # Create default invite stats
                default_stats = {
                    'user_id': user_id,
                    'real': 0,
                    'fake': 0,
                    'left': 0,
                    'bonus': 0
                }
                
                cursor.execute("""
                    INSERT INTO invites (user_id, real, fake, left, bonus)
                    VALUES (%s, 0, 0, 0, 0)
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id,))
                
                return default_stats
    
    def update_invite_stats(self, user_id, stats):
        """Update invite statistics for a user."""
        self.ensure_connection()
        
        # Get current stats
        current_stats = self.get_invite_stats(user_id)
        
        # Update stats
        for key in ['real', 'fake', 'left', 'bonus']:
            if key in stats:
                current_stats[key] = stats[key]
        
        # Save to database
        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE invites
                SET real = %s, fake = %s, left = %s, bonus = %s
                WHERE user_id = %s
            """, (
                current_stats['real'], 
                current_stats['fake'], 
                current_stats['left'], 
                current_stats['bonus'],
                user_id
            ))
        
        return current_stats
    
    def get_mining_stats(self, user_id):
        """Get mining statistics for a user."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM mining_stats WHERE user_id = %s", (user_id,))
            mining_data = cursor.fetchone()
            
            if mining_data:
                return dict(mining_data)
            else:
                # Create default mining stats
                default_stats = {
                    'user_id': user_id,
                    'money': 0,
                    'prestige_level': 0,
                    'tool': 'Wooden Pickaxe',
                    'auto_sell': False
                }
                
                cursor.execute("""
                    INSERT INTO mining_stats (user_id, money, prestige_level, tool, auto_sell)
                    VALUES (%s, 0, 0, 'Wooden Pickaxe', FALSE)
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id,))
                
                return default_stats
    
    def update_mining_stats(self, user_id, stats):
        """Update mining statistics for a user."""
        self.ensure_connection()
        
        # Get current stats
        current_stats = self.get_mining_stats(user_id)
        
        # Update stats
        for key in ['money', 'prestige_level', 'tool', 'auto_sell']:
            if key in stats:
                current_stats[key] = stats[key]
        
        # Save to database
        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE mining_stats
                SET money = %s, prestige_level = %s, tool = %s, auto_sell = %s
                WHERE user_id = %s
            """, (
                current_stats['money'], 
                current_stats['prestige_level'], 
                current_stats['tool'],
                current_stats['auto_sell'],
                user_id
            ))
        
        return current_stats
    
    def get_mining_resources(self, user_id):
        """Get mining resources for a user."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT resource_name, amount FROM mining_resources WHERE user_id = %s", (user_id,))
            rows = cursor.fetchall()
            
            resources = {}
            for row in rows:
                resources[row['resource_name']] = row['amount']
            
            return resources
    
    def update_mining_resource(self, user_id, resource_name, amount):
        """Update a mining resource amount for a user."""
        self.ensure_connection()
        
        with self.conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO mining_resources (user_id, resource_name, amount)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, resource_name) 
                DO UPDATE SET amount = %s
            """, (user_id, resource_name, amount, amount))
    
    def get_mining_items(self, user_id):
        """Get mining items for a user."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT item_name, amount FROM mining_items WHERE user_id = %s", (user_id,))
            rows = cursor.fetchall()
            
            items = {}
            for row in rows:
                items[row['item_name']] = row['amount']
            
            return items
    
    def update_mining_item(self, user_id, item_name, amount):
        """Update a mining item amount for a user."""
        self.ensure_connection()
        
        with self.conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO mining_items (user_id, item_name, amount)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, item_name) 
                DO UPDATE SET amount = %s
            """, (user_id, item_name, amount, amount))
    
    def get_profile(self, user_id):
        """Get a user's profile data."""
        self.ensure_connection()
        
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
            profile_data = cursor.fetchone()
            
            if profile_data:
                return dict(profile_data)
            else:
                return None
    
    def create_or_update_profile(self, user_id, data):
        """Create or update a user's profile."""
        self.ensure_connection()
        
        with self.conn.cursor() as cursor:
            # Check if profile exists
            cursor.execute("SELECT user_id FROM profiles WHERE user_id = %s", (user_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing profile
                columns = []
                values = []
                for key, value in data.items():
                    columns.append(sql.Identifier(key))
                    values.append(value)
                
                # Add user_id to values
                values.append(user_id)
                
                # Construct the SQL query
                update_query = sql.SQL("UPDATE profiles SET {} WHERE user_id = %s").format(
                    sql.SQL(', ').join(
                        sql.SQL("{} = %s").format(column) 
                        for column in columns
                    )
                )
                
                cursor.execute(update_query, values)
            else:
                # Create new profile
                data['user_id'] = user_id
                columns = data.keys()
                values = [data[col] for col in columns]
                
                query = f"""
                    INSERT INTO profiles ({', '.join(columns)})
                    VALUES ({', '.join(['%s'] * len(values))})
                """
                
                cursor.execute(query, values)
        
        return self.get_profile(user_id)
    
    def migrate_from_sqlite(self, sqlite_db_path):
        """Migrate data from SQLite database to PostgreSQL."""
        try:
            import sqlite3
            
            if not os.path.exists(sqlite_db_path):
                logger.error(f"SQLite database file not found: {sqlite_db_path}")
                return False
            
            sqlite_conn = sqlite3.connect(sqlite_db_path)
            sqlite_conn.row_factory = sqlite3.Row
            
            # Migrate users
            cursor = sqlite_conn.cursor()
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
            
            for user in users:
                user_dict = dict(user)
                user_id = user_dict.pop('user_id')
                username = user_dict.pop('username', 'Unknown')
                
                # Check if user exists
                with self.conn.cursor() as pg_cursor:
                    pg_cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                    if pg_cursor.fetchone() is None:
                        # User doesn't exist, insert
                        columns = ['user_id', 'username'] + list(user_dict.keys())
                        values = [user_id, username] + list(user_dict.values())
                        
                        placeholders = ', '.join(['%s'] * len(columns))
                        column_names = ', '.join(columns)
                        
                        pg_cursor.execute(f"""
                            INSERT INTO users ({column_names})
                            VALUES ({placeholders})
                        """, values)
                    else:
                        # User exists, update
                        updates = []
                        values = []
                        
                        for key, value in user_dict.items():
                            updates.append(f"{key} = %s")
                            values.append(value)
                        
                        values.append(user_id)  # For WHERE clause
                        
                        pg_cursor.execute(f"""
                            UPDATE users SET {', '.join(updates)}
                            WHERE user_id = %s
                        """, values)
            
            # Other tables to migrate
            tables = ['settings', 'invites', 'mining_stats', 'mining_resources', 'mining_items', 'profiles']
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        row_dict = dict(row)
                        
                        # Handle primary key for the table
                        if table == 'settings':
                            pk = 'setting_id'
                        elif table in ['mining_resources', 'mining_items']:
                            # These have composite primary keys
                            user_id = row_dict.get('user_id')
                            name_field = 'resource_name' if table == 'mining_resources' else 'item_name'
                            item_name = row_dict.get(name_field)
                            
                            with self.conn.cursor() as pg_cursor:
                                pg_cursor.execute(f"""
                                    INSERT INTO {table} 
                                    SELECT * FROM json_populate_record(null::{table}, %s)
                                    ON CONFLICT (user_id, {name_field}) DO UPDATE
                                    SET amount = EXCLUDED.amount
                                """, (json.dumps(row_dict),))
                            
                            continue
                        else:
                            pk = 'user_id'
                        
                        pk_value = row_dict.get(pk)
                        
                        with self.conn.cursor() as pg_cursor:
                            # Check if record exists
                            pg_cursor.execute(f"SELECT {pk} FROM {table} WHERE {pk} = %s", (pk_value,))
                            
                            if pg_cursor.fetchone() is None:
                                # Record doesn't exist, insert
                                columns = list(row_dict.keys())
                                values = list(row_dict.values())
                                
                                placeholders = ', '.join(['%s'] * len(columns))
                                column_names = ', '.join(columns)
                                
                                pg_cursor.execute(f"""
                                    INSERT INTO {table} ({column_names})
                                    VALUES ({placeholders})
                                """, values)
                            else:
                                # Record exists, update
                                updates = []
                                values = []
                                
                                for key, value in row_dict.items():
                                    if key != pk:  # Skip primary key in SET clause
                                        updates.append(f"{key} = %s")
                                        values.append(value)
                                
                                values.append(pk_value)  # For WHERE clause
                                
                                if updates:  # Only update if there are fields to update
                                    pg_cursor.execute(f"""
                                        UPDATE {table} SET {', '.join(updates)}
                                        WHERE {pk} = %s
                                    """, values)
                
                except sqlite3.OperationalError as e:
                    # Table might not exist in SQLite
                    logger.warning(f"Could not migrate table {table}: {e}")
            
            sqlite_conn.close()
            logger.info(f"Migration from SQLite database {sqlite_db_path} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating from SQLite database: {e}", exc_info=True)
            return False