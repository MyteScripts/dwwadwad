import os
import json
import argparse
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from logger import setup_logger

logger = setup_logger('sqlite_to_postgres')

def migrate_sqlite_to_postgres(sqlite_db_path):
    """Migrate data from SQLite database to PostgreSQL."""
    
    if not os.path.exists(sqlite_db_path):
        logger.error(f"SQLite database file not found: {sqlite_db_path}")
        return False
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not found in environment variables")
        return False
    
    try:
        # Connect to PostgreSQL
        logger.info(f"Connecting to PostgreSQL database")
        pg_conn = psycopg2.connect(database_url)
        pg_conn.autocommit = True
        
        # Connect to SQLite
        logger.info(f"Connecting to SQLite database: {sqlite_db_path}")
        sqlite_conn = sqlite3.connect(sqlite_db_path)
        sqlite_conn.row_factory = sqlite3.Row
        
        # Migrate users table
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='users',
            primary_key='user_id'
        )
        
        # Migrate settings table
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='settings',
            primary_key='setting_id'
        )
        
        # Migrate invites table
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='invites',
            primary_key='user_id'
        )
        
        # Migrate mining_stats table
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='mining_stats',
            primary_key='user_id'
        )
        
        # Migrate mining_resources table (composite primary key)
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='mining_resources',
            primary_key=('user_id', 'resource_name')
        )
        
        # Migrate mining_items table (composite primary key)
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='mining_items',
            primary_key=('user_id', 'item_name')
        )
        
        # Migrate profiles table
        migrate_table(
            source_conn=sqlite_conn,
            dest_conn=pg_conn, 
            table_name='profiles',
            primary_key='user_id'
        )
        
        # Migrate JSON data files
        migrate_json_files(pg_conn)
        
        sqlite_conn.close()
        pg_conn.close()
        
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration error: {e}", exc_info=True)
        return False

def migrate_table(source_conn, dest_conn, table_name, primary_key):
    """Migrate a table from SQLite to PostgreSQL."""
    
    try:
        # Check if table exists in SQLite
        source_cursor = source_conn.cursor()
        source_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not source_cursor.fetchone():
            logger.warning(f"Table {table_name} not found in SQLite database, skipping")
            return
        
        # Get all rows from SQLite
        source_cursor.execute(f"SELECT * FROM {table_name}")
        rows = source_cursor.fetchall()
        
        if not rows:
            logger.info(f"No data found in {table_name} table, skipping")
            return
        
        row_count = len(rows)
        logger.info(f"Migrating {row_count} rows from {table_name} table")
        
        # Prepare destination cursor
        dest_cursor = dest_conn.cursor()
        
        # Process each row
        for i, row in enumerate(rows):
            row_dict = dict(row)
            
            if isinstance(primary_key, tuple):
                # Composite primary key
                pk_values = [row_dict.get(pk) for pk in primary_key]
                
                # Check if record exists
                pk_conditions = " AND ".join([f"{pk} = %s" for pk in primary_key])
                dest_cursor.execute(f"SELECT 1 FROM {table_name} WHERE {pk_conditions}", pk_values)
                exists = dest_cursor.fetchone() is not None
                
                if exists:
                    # Record exists, update
                    updates = []
                    values = []
                    
                    for key, value in row_dict.items():
                        if key not in primary_key:  # Skip primary key fields in SET clause
                            updates.append(f"{key} = %s")
                            values.append(value)
                    
                    # Add primary key values for WHERE clause
                    values.extend(pk_values)
                    
                    if updates:  # Only update if there are fields to update
                        dest_cursor.execute(f"""
                            UPDATE {table_name} SET {', '.join(updates)}
                            WHERE {pk_conditions}
                        """, values)
                else:
                    # Record doesn't exist, insert
                    columns = list(row_dict.keys())
                    values = list(row_dict.values())
                    
                    placeholders = ', '.join(['%s'] * len(columns))
                    column_names = ', '.join(columns)
                    
                    dest_cursor.execute(f"""
                        INSERT INTO {table_name} ({column_names})
                        VALUES ({placeholders})
                    """, values)
            else:
                # Single primary key
                pk_value = row_dict.get(primary_key)
                
                # Check if record exists
                dest_cursor.execute(f"SELECT {primary_key} FROM {table_name} WHERE {primary_key} = %s", (pk_value,))
                exists = dest_cursor.fetchone() is not None
                
                if exists:
                    # Record exists, update
                    updates = []
                    values = []
                    
                    for key, value in row_dict.items():
                        if key != primary_key:  # Skip primary key in SET clause
                            updates.append(f"{key} = %s")
                            values.append(value)
                    
                    values.append(pk_value)  # For WHERE clause
                    
                    if updates:  # Only update if there are fields to update
                        dest_cursor.execute(f"""
                            UPDATE {table_name} SET {', '.join(updates)}
                            WHERE {primary_key} = %s
                        """, values)
                else:
                    # Record doesn't exist, insert
                    columns = list(row_dict.keys())
                    values = list(row_dict.values())
                    
                    placeholders = ', '.join(['%s'] * len(columns))
                    column_names = ', '.join(columns)
                    
                    dest_cursor.execute(f"""
                        INSERT INTO {table_name} ({column_names})
                        VALUES ({placeholders})
                    """, values)
            
            # Log progress for large tables
            if (i + 1) % 100 == 0 or i + 1 == row_count:
                logger.info(f"Migrated {i + 1}/{row_count} rows for table {table_name}")
        
        logger.info(f"Successfully migrated {row_count} rows for table {table_name}")
        
    except Exception as e:
        logger.error(f"Error migrating table {table_name}: {e}", exc_info=True)
        raise

def migrate_json_files(pg_conn):
    """Migrate data from JSON files to PostgreSQL tables."""
    json_files = [
        ('data/investments.json', 'investments'),
        ('data/tournaments.json', 'tournaments'),
        ('data/tournament_votes.json', 'tournament_votes'),
        ('data/tickets.json', 'tickets'),
        ('data/giveaways.json', 'giveaways')
    ]
    
    cursor = pg_conn.cursor()
    
    # Create a table to store JSON data if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS json_data (
            id SERIAL PRIMARY KEY,
            data_type VARCHAR(50) NOT NULL UNIQUE,
            content JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for file_path, data_type in json_files:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                        
                        # Store as JSON in PostgreSQL
                        cursor.execute("""
                            INSERT INTO json_data (data_type, content)
                            VALUES (%s, %s)
                            ON CONFLICT (data_type) 
                            DO UPDATE SET content = %s, updated_at = CURRENT_TIMESTAMP
                        """, (data_type, json.dumps(data), json.dumps(data)))
                        
                        logger.info(f"Successfully migrated {file_path} to PostgreSQL json_data table")
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in {file_path}, skipping")
            else:
                logger.warning(f"JSON file {file_path} not found, skipping")
        except Exception as e:
            logger.error(f"Error migrating JSON file {file_path}: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-db", default="data/leveling.db", help="Path to SQLite database file")
    
    args = parser.parse_args()
    
    if migrate_sqlite_to_postgres(args.sqlite_db):
        print("Migration completed successfully!")
    else:
        print("Migration failed. See logs for details.")