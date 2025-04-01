import os
import json
from logger import setup_logger

logger = setup_logger('database_handler')

class DatabaseHandler:
    """
    Handler that manages database operations, automatically choosing between
    SQLite (for backward compatibility) and PostgreSQL (for persistent data storage).
    """
    
    def __init__(self):
        """Initialize the appropriate database backend."""
        self.pg_db = None
        self.sqlite_db = None
        
        # Check if we have a DATABASE_URL for PostgreSQL
        use_postgres = os.environ.get('DATABASE_URL') is not None
        
        if use_postgres:
            try:
                from pg_database import PGDatabase
                logger.info("Using PostgreSQL database")
                self.pg_db = PGDatabase()
                self.using_postgres = True
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL database: {e}", exc_info=True)
                use_postgres = False
        
        if not use_postgres:
            # Fall back to SQLite for backward compatibility
            from database import Database
            logger.info("Using SQLite database")
            self.sqlite_db = Database()
            self.using_postgres = False
    
    def get_db(self):
        """Get the active database backend."""
        return self.pg_db if self.using_postgres else self.sqlite_db
    
    # User data methods
    def get_user(self, user_id):
        """Get user data from the database."""
        return self.get_db().get_user(user_id)
    
    def create_user(self, user_id, username):
        """Create a new user in the database."""
        return self.get_db().create_user(user_id, username)
    
    def update_user(self, user_id, data):
        """Update user data in the database."""
        return self.get_db().update_user(user_id, data)
    
    def add_xp(self, user_id, username, xp_amount):
        """Add XP to a user and handle level ups."""
        return self.get_db().add_xp(user_id, username, xp_amount)
    
    def add_coins(self, user_id, username, amount):
        """Add coins to a user's balance."""
        return self.get_db().add_coins(user_id, username, amount)
    
    def remove_coins(self, user_id, username, amount):
        """Remove coins from a user's balance."""
        return self.get_db().remove_coins(user_id, username, amount)
    
    def get_top_users(self, limit=10, offset=0, by_xp=True):
        """Get the top users ranked by XP or coins."""
        return self.get_db().get_top_users(limit, offset, by_xp)
    
    def get_user_rank(self, user_id, by_xp=True):
        """Get a user's rank position."""
        return self.get_db().get_user_rank(user_id, by_xp)
    
    # Settings methods
    def get_settings(self):
        """Get settings for the leveling system."""
        return self.get_db().get_settings()
    
    def update_settings(self, settings):
        """Update settings for the leveling system."""
        return self.get_db().update_settings(settings)
    
    # Invite tracking methods
    def get_invite_stats(self, user_id):
        """Get invite statistics for a user."""
        return self.get_db().get_invite_stats(user_id)
    
    def update_invite_stats(self, user_id, stats):
        """Update invite statistics for a user."""
        return self.get_db().update_invite_stats(user_id, stats)
    
    # Mining system methods
    def get_mining_stats(self, user_id):
        """Get mining statistics for a user."""
        return self.get_db().get_mining_stats(user_id)
    
    def update_mining_stats(self, user_id, stats):
        """Update mining statistics for a user."""
        return self.get_db().update_mining_stats(user_id, stats)
    
    def get_mining_resources(self, user_id):
        """Get mining resources for a user."""
        return self.get_db().get_mining_resources(user_id)
    
    def update_mining_resource(self, user_id, resource_name, amount):
        """Update a mining resource amount for a user."""
        return self.get_db().update_mining_resource(user_id, resource_name, amount)
    
    def get_mining_items(self, user_id):
        """Get mining items for a user."""
        return self.get_db().get_mining_items(user_id)
    
    def update_mining_item(self, user_id, item_name, amount):
        """Update a mining item amount for a user."""
        return self.get_db().update_mining_item(user_id, item_name, amount)
    
    # Profile system methods
    def get_profile(self, user_id):
        """Get a user's profile data."""
        return self.get_db().get_profile(user_id)
    
    def create_or_update_profile(self, user_id, data):
        """Create or update a user's profile."""
        return self.get_db().create_or_update_profile(user_id, data)
    
    # JSON data methods (for PostgreSQL only)
    def get_json_data(self, data_type):
        """
        Get JSON data from the database.
        Falls back to file system if using SQLite.
        """
        if self.using_postgres:
            try:
                with self.pg_db.conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT content FROM json_data 
                        WHERE data_type = %s
                    """, (data_type,))
                    
                    result = cursor.fetchone()
                    if result:
                        return json.loads(result[0])
            except Exception as e:
                logger.error(f"Error getting JSON data for {data_type}: {e}", exc_info=True)
        
        # Fall back to file system
        file_path = f"data/{data_type}.json"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading JSON file {file_path}: {e}", exc_info=True)
        
        return {}
    
    def save_json_data(self, data_type, data):
        """
        Save JSON data to the database.
        Also saves to file system for backward compatibility.
        """
        # Always save to file for backward compatibility
        file_path = f"data/{data_type}.json"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing JSON file {file_path}: {e}", exc_info=True)
        
        # Save to PostgreSQL if available
        if self.using_postgres:
            try:
                with self.pg_db.conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO json_data (data_type, content)
                        VALUES (%s, %s)
                        ON CONFLICT (data_type) 
                        DO UPDATE SET content = %s, updated_at = CURRENT_TIMESTAMP
                    """, (data_type, json.dumps(data), json.dumps(data)))
            except Exception as e:
                logger.error(f"Error saving JSON data for {data_type}: {e}", exc_info=True)
    
    def migrate_sqlite_to_postgres(self, sqlite_db_path=None):
        """
        Migrate data from SQLite to PostgreSQL.
        This should be called when transitioning to PostgreSQL.
        """
        if not self.using_postgres:
            logger.error("Cannot migrate to PostgreSQL: No DATABASE_URL configured")
            return False
        
        if sqlite_db_path is None:
            sqlite_db_path = "data/leveling.db"
        
        try:
            from sqlite_to_postgres import migrate_sqlite_to_postgres
            return migrate_sqlite_to_postgres(sqlite_db_path)
        except Exception as e:
            logger.error(f"Error during migration: {e}", exc_info=True)
            return False