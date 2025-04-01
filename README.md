# Discord Economy Bot

An advanced Discord bot with a comprehensive economy system, leveling, investments, mining, mini-games, and community features.

## Features

### Core Systems
- Advanced leveling and XP tracking
- Coin/currency system with multiple earning methods
- Investment system with businesses and passive income
- Mining system with resources and equipment upgrades
- Mini-games with rewards (Type Race, Memory Game, Reverse Spelling, True/False)
- User profiles with customization options

### Community Features
- Announcements and HowTo system
- Suggestion and feedback collection
- Bug reporting
- User reporting system
- Giveaways and community interaction commands

### Administrative Tools
- PostgreSQL database support for persistent data storage
- Database backup and restore for cross-host migration
- Permission-based command access
- Drop management for XP and coins
- Level and role management
- Activity monitoring

## Data Persistence and Cross-Host Migration

We offer two solutions for maintaining data when hosting your bot on different platforms:

### Option 1: PostgreSQL Database (Recommended)

The PostgreSQL solution provides seamless data persistence across platforms without manual migration.

#### PostgreSQL Commands

- `/pgmigrate`: Migrates all user data from SQLite to PostgreSQL for persistent storage
- `/pgstatus`: Shows the status of PostgreSQL configuration and migration

#### PostgreSQL Setup Process

1. Set up a PostgreSQL database on any hosting provider
2. Add the `DATABASE_URL` to your bot's environment variables
3. Run the `/pgmigrate` command to transfer existing data
4. The bot will automatically use PostgreSQL for all data operations

See `POSTGRES_MIGRATION.md` for detailed instructions.

### Option 2: Manual Database Backup and Restore

For environments without PostgreSQL, you can manually transfer data between hosts.

#### Manual Migration Commands

- `/dbsync`: Backs up all database and JSON files to the admin's DMs
- `/dbrestore`: Restores the database from a previously backed up file
- `/dbimportjson`: Imports JSON data files after a database restore

#### Manual Migration Process

1. In your source environment (e.g., Railway):
   - Run `/dbsync` to receive database backups in your DMs
   - Save these files to your computer

2. In your destination environment (e.g., Replit):
   - Ensure the bot is set up with the same token
   - Run `/dbrestore` and upload the database file
   - Run `/dbimportjson` and upload any JSON files
   
Both options ensure your user data, levels, coins, and other progress will be preserved!

See the `DOCUMENTATION.md` file for detailed instructions on database management and migration.

## Prerequisites

- Python 3.x
- Discord Developer account
- Discord Bot Token

## Setup

1. Clone this repository

2. Install required packages:
   ```
   pip install discord.py python-dotenv flask gunicorn
   ```

3. Create a `.env` file in the root directory with the following:
   ```
   DISCORD_TOKEN=your_discord_token_here
   ```

4. Run the bot:
   ```
   python main.py
   ```

## Web Dashboard

The bot includes a web dashboard for investment management and statistics. To start the web server:

```
python main_app.py
```

Or use the configured Replit workflow.

## Documentation

See the `DOCUMENTATION.md` file for a comprehensive guide to all commands and features.