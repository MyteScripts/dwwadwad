# PostgreSQL Database Migration Guide

This guide explains how to migrate your Discord bot data from SQLite to PostgreSQL for persistent data storage across different hosting platforms.

## Why Use PostgreSQL?

When hosting your bot on different platforms like Railway and Replit, using SQLite can lead to data loss because:

1. SQLite stores data in local files
2. Different hosting platforms have separate filesystems
3. When you move your bot, the local database doesn't move with it

PostgreSQL solves this by storing your data in a central database that both platforms can access.

## Migration Process

### Step 1: Set Up PostgreSQL Database

First, you need a PostgreSQL database. This can be:
- A PostgreSQL add-on in Railway
- A PostgreSQL database in Replit
- An external PostgreSQL provider like ElephantSQL, Neon, etc.

After setting up, you'll have a `DATABASE_URL` connection string.

### Step 2: Add Your Database URL

Add your database URL to your bot's environment:

1. Create or edit the `.env` file
2. Add the following line:
   ```
   DATABASE_URL=postgresql://username:password@hostname:port/database
   ```
3. Make sure this file is loaded by your bot

### Step 3: Migrate Your Data

Use the bot's built-in migration command:

1. Start your bot
2. As an administrator, run the `/pgmigrate` command in Discord
3. The bot will migrate all user data from SQLite to PostgreSQL
4. Once complete, your bot will automatically use PostgreSQL for all operations

### Step 4: Verify Migration

To check if the migration was successful:

1. Run the `/pgstatus` command in Discord
2. Confirm that "Using PostgreSQL" shows "✅ Yes"
3. Check that your user data is displayed correctly

## Technical Details

The migration system includes:

- `pg_database.py`: PostgreSQL database handler
- `sqlite_to_postgres.py`: Migration utility
- `database_handler.py`: Smart handler that can work with both SQLite and PostgreSQL
- `db_migration.py`: Discord commands for migration management

## Troubleshooting

If you encounter issues:

1. Check your `DATABASE_URL` is correct and accessible
2. Ensure your PostgreSQL database is running
3. Make sure the bot has permissions to create tables
4. If tables already exist with different structures, you may need to drop them first

For detailed logs, check the bot's console output during migration.

## Data Transferred

The migration includes:
- User levels, XP, and coins
- Mining system data
- User profiles
- Invite statistics
- Bot settings
- JSON data for various systems (investments, tournaments, etc.)

## Development Notes

The system is designed to maintain backward compatibility with SQLite, allowing for a smooth transition period. Once all users are migrated to PostgreSQL, the SQLite support can be removed in future versions.