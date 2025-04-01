# Discord Bot Documentation

This document provides detailed information about the Discord bot, its features, and how to use it.

## Table of Contents

1. [Introduction](#introduction)
2. [Setup](#setup)
3. [Commands](#commands)
4. [Admin Commands](#admin-commands)
   - [Bot Status Management](#bot-status-management)
   - [Drop Management](#drop-management)
   - [Coin Management](#coin-management)
   - [Level Management](#level-management)
5. [Systems](#systems)
   - [Bot Status System](#bot-status-system)
   - [Unified Drop Management](#unified-drop-management)
   - [Coin Drops](#coin-drops)
   - [XP Drops](#xp-drops)
   - [Investment System](#investment-system)
   - [Community Interaction System](#community-interaction-system)
   - [Tournament System](#tournament-system)
   - [Ticket System](#ticket-system)
6. [Migration Utilities](#migration-utilities)
7. [Database Management](#database-management)

## Introduction

This bot provides a comprehensive suite of features for Discord servers, including:
- Leveling and XP system
- Coin/currency system
- Investment system with businesses and passive income
- Mining system with resources and equipment upgrades
- Tournament system with team management and brackets
- Countdowns for events
- Game voting
- Invite tracking
- Community interaction (giveaways, suggestions, feedback, bug reports)
- User reporting system
- Ticket system for support and issue tracking
- Data migration tools
- Dedicated admin commands for easy management

## Setup

1. Ensure the `.env` file is properly configured with the following variables:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `DATABASE_URL`: PostgreSQL database URL (if using PostgreSQL)

2. Directory structure:
   - The main database (`leveling.db`) is stored in the `data/` directory
   - Investment data is stored in `investments.json` in the `data/` directory
   - Tournament data is stored in `tournaments.json` and `tournament_votes.json` in the `data/` directory
   - Ticket data is stored in `tickets.json` in the `data/` directory, with transcripts in `data/transcripts/`
   - Giveaway data is stored in `giveaways.json` in the `data/` directory
   - Logs are stored in the `logs/` directory

3. Run the bot using one of these methods:
   - `python main.py` to run the bot directly
   - Using the configured workflow

## Commands

### General Commands

- `/rank`: Display your current level, XP, and coins
- `/leaderboard`: Show the server's top users by level
- `/editleveling`: Admin command to edit leveling system settings

### Countdown System

- `/countdown`: Opens a panel to create or manage countdown timers for events

### Game Voting

- `/gamevote`: Opens a panel to start or end a game voting session
  - Features:
    - Start a regular game vote with custom duration
    - Start a tournament game vote (Admin only) with up to 4 game options
    - End active votes with automatic result calculation
    - Interactive buttons for easy voting
    - Real-time vote count updates in the embed

### Invite Tracking

- `/invites`: Check your invite count
- `/invitepanel`: Admin command to manage invites and logs

### Investment System

- `/invest`: Browse and purchase luxury properties
  - Features:
    - See a catalog of available properties with details
    - Purchase properties using your coins
    - View investment details and expected returns

- `/business`: Manage your luxury property portfolio
  - Features:
    - View your current properties and their status
    - Collect accumulated income from properties
    - Perform maintenance to keep properties efficient
    - Repair properties affected by risk events
    - Sell properties you no longer want

- `/reset_properties`: Reset accumulated income for all users' properties (Admin only)
  - Features:
    - Resets the accumulated income counters for all properties
    - Useful for troubleshooting or economy balance

- `/edit_property`: Edit an existing property's parameters (Admin only)
  - Features:
    - Modify price, hourly income, maximum accumulation
    - Adjust maintenance cost and decay rate
    - Fine-tune property economics for game balance

- `/add_property`: Add a new property to the investment system (Admin only)
  - Features:
    - Create entirely new property types with custom parameters
    - Define risk factors and description
    - Add variety to the investment options

### Mining System

- `/mine`: Begin mining for resources
  - Features:
    - Various resource types with different rarities and values
    - Equipment-based mining multipliers
    - Cooldown system with prestige-based reductions
    - Chance-based mining outcomes with item bonuses

- `/balance`: Check your mining balance and resources
  - Features:
    - Display current coin balance
    - List all owned resources and their values
    - Show current equipment and items
    - Display prestige level and bonuses

- `/upgrade`: Improve your mining equipment
  - Features:
    - Various pickaxe tiers with increasing multipliers
    - Progressive upgrade system with higher costs
    - Visual confirmation of upgrades with stats

- `/sell <resource>`: Convert resources to coins
  - Features:
    - Sell individual resources or all at once
    - Automatic value calculation based on resource rarity
    - Detailed transaction summary

- `/mining_shop`: Browse items that enhance mining
  - Features:
    - Various items with different mining benefits
    - Clear descriptions of item effects
    - Interactive purchase interface

- `/mining_buy <item>`: Purchase an item from the mining shop
  - Features:
    - Direct purchase command for shop items
    - Automatic balance check and update
    - Ownership verification to prevent duplicates

- `/prestige`: Reset progress for permanent bonuses
  - Features:
    - Sacrifices current resources and money for permanent bonuses
    - Each prestige level increases mining rewards and reduces cooldowns
    - Confirmation system to prevent accidental resets
    - Keeps purchased shop items across prestiges
  
- `/lb`: Display the mining leaderboard
  - Features:
    - Rankings based on total wealth (money + prestige value)
    - Shows top miners on the server
    - Displays prestige levels alongside coin balance

### Tournament Commands

- `/createtournament`: Create a new tournament
  - Features:
    - Set game type, max participants, start time
    - Configure team count and players per team
    - Define prize information
    - Automatically generates a unique 5-character ID

- `/tournament`: View tournament information
  - Features:
    - View details of a specific tournament using its ID
    - See list of all active tournaments
    - Join tournaments via button interface
    - Access team and bracket information

- `/managetournament`: Admin-only tournament management
  - Features:
    - View complete list of participants with join timestamps
    - Form teams from participants
    - Generate tournament brackets
    - Rename teams for better identification
    - Update match results and record scores
    - Delete tournaments if needed

- `/jointournament`: Join a tournament using its ID
  - Features:
    - Alternative to the join button
    - Register for a tournament directly via command

- `/leavetournament`: Leave a tournament you joined
  - Features:
    - Remove yourself from participant list
    - Only works before team formation phase

### Community Commands

- **Mass Messaging Commands**:
  - `/sendtoall`: Send an embedded message to all server members via DM (Admin only)
    - Features:
      - Create fully customizable embedded messages with interactive buttons
      - Add fields, footer, and images to your message
      - Set filters to target specific roles for sending messages
      - Preview messages before sending to verify appearance
      - Real-time progress tracking during message sending
      - Shows success/failure statistics after completion
      - Uses the same permission system as `/addlevel`

- **Giveaway Commands**:
  - `/giveaway`: Create a new giveaway with custom settings (Admin only)
    - Features:
      - Create giveaways through an intuitive modal interface
      - Set prize description, number of winners, and duration
      - Select the channel where the giveaway will appear
      - Unique ID generation for each giveaway
  
  - `/endgiveaway <giveaway_id>`: End a giveaway immediately (Admin only)
    - Features:
      - Immediately selects and announces winners
      - Updates the giveaway embed to show completion
      - Notifies participants of the early ending
  
  - `/cancelgiveaway <giveaway_id>`: Cancel a giveaway without winners (Admin only)
    - Features:
      - Cancels the giveaway completely without selecting winners
      - Updates the giveaway embed to show cancellation
      - Notifies participants of the cancellation
  
  - `/listgiveaways`: List all active giveaways (Admin only)
    - Features:
      - Shows all current giveaways with their IDs, prizes, and end times
      - Displays direct links to jump to each giveaway message
      - Helps admins track and manage multiple giveaways
  
  - `/rerollgiveaway <giveaway_id> [winners_count]`: Select new winners (Admin only)
    - Features:
      - Randomly selects new winners from original participants
      - Optional parameter to specify how many winners to select
      - Announces the new winners in the original giveaway channel

- `/suggest`: Submit a suggestion for the server
  - Features:
    - Title and detailed body for structured suggestions
    - Automatic sending to a designated suggestions channel
    - Admin review buttons for easy management

- `/report`: Report a user for breaking rules
  - Features:
    - Simple user selection
    - Detailed reason field for explanation
    - Reports sent to designated channel for staff review

- `/bug`: Report a bug in the bot or server features
  - Features:
    - Structured bug reporting with title, description, and steps to reproduce
    - Expected behavior field for clarifying the issue
    - Reports organized for easier troubleshooting

- `/feedback`: Provide general feedback about the server or bot
  - Features:
    - Free-form text field for detailed feedback
    - Anonymous feedback collection in a dedicated channel

- `/rules`: Receive the server rules via DM
  - Features:
    - Formatted embed with clearly numbered rules
    - Privacy-respecting delivery via direct message

- `/set_channel`: Configure channels for community features (Admin only)
  - Features:
    - Set channels for suggestions, reports, bugs, feedback, and giveaways
    - Simple channel ID input

- `/view_channels`: View current channel settings (Admin only)
  - Features:
    - Overview of all configured channels for community features
    - Shows channel mentions and IDs for easy reference

### Ticket System Commands

- `/ticket`: Create a new support ticket
  - Features:
    - Subject and description fields for detailed issue reporting
    - Creates a private channel for communications
    - Automatically notifies support staff
    - Includes a close button for easy resolution

- `/ticket_close`: Close a support ticket (ticket creator or Admin)
  - Features:
    - Reason field to document resolution
    - Generates a transcript of the ticket conversation
    - Notifies the user via DM about ticket closure
    - Archives transcript for future reference

- `/ticket_setup`: Configure the ticket system (Admin only)
  - Features:
    - Set up category for ticket channels
    - Define log channel for ticket actions
    - Assign support role that can access tickets
    - Simple ID-based configuration

- `/add_to_ticket`: Add a user to the current ticket (Admin or Support only)
  - Features:
    - Add specific users to an existing ticket
    - Provides access control for sensitive tickets
    - Maintains privacy for other users

- `/remove_from_ticket`: Remove a user from the current ticket (Admin or Support only)
  - Features:
    - Remove users that are no longer needed in a ticket
    - Preserves ticket security and privacy
    - Prevents channel clutter

## Admin Commands

### Bot Status Management

- `/status`
  - Description: Manage the bot's status (online, maintenance, offline)
  - Features:
    - Set the status log channel to receive notifications
    - Change status with reason tracking
    - View current status and last update details
  - Status Types:
    - Online: Bot is fully operational
    - Maintenance: Bot is undergoing maintenance but is still responsive
    - Offline: Bot is marked as offline (commands may still work but users are informed of offline status)

### Drop Management

- `/dropedit`
  - Description: Unified panel to manage both XP and coin drops
  - Features:
    - View current status of both drop systems simultaneously
    - Configure XP drop settings (channel, min/max XP, frequency)
    - Configure coin drop settings (channel, min/max coins, frequency)
    - Activate/deactivate XP drops
    - Activate/deactivate coin drops
    - Real-time status updates and status refresh

### Coin Management

The following commands are available for managing coins:

- `/addcoins`
  - Description: Add coins to a specific user
  - Parameters:
    - `user`: The user to add coins to
    - `amount`: The number of coins to add

- `/removecoins`
  - Description: Remove coins from a specific user
  - Parameters:
    - `user`: The user to remove coins from
    - `amount`: The number of coins to remove

- `/setcoindrops`
  - Description: Configure automatic coin drops
  - Parameters:
    - `channel`: The channel where drops will appear
    - `min_coins`: Minimum coins per drop (default: 10)
    - `max_coins`: Maximum coins per drop (default: 50)
    - `duration`: How often drops occur (default: 1)
    - `time_unit`: Time unit (minute, hour, day)

- `/startcoindrops`
  - Description: Start automatic coin drops
  - Note: Requires coin drops to be configured first

- `/stopcoindrops`
  - Description: Stop automatic coin drops

### Level Management

The following commands are available for managing levels and XP:

- `/addxp`
  - Description: Add XP to a specific user
  - Parameters:
    - `user`: The user to add XP to
    - `amount`: The amount of XP to add

- `/setlevel`
  - Description: Set a user's level directly
  - Parameters:
    - `user`: The user to set level for
    - `level`: The level to set
    - `xp`: Optional: The XP to set (defaults to middle of level)

- `/setxpdrops`
  - Description: Configure automatic XP drops
  - Parameters:
    - `channel`: The channel where drops will appear
    - `min_xp`: Minimum XP per drop (default: 20)
    - `max_xp`: Maximum XP per drop (default: 100)
    - `duration`: How often drops occur (default: 1)
    - `time_unit`: Time unit (minute, hour, day)

- `/startxpdrops`
  - Description: Start automatic XP drops
  - Note: Requires XP drops to be configured first

- `/stopxpdrops`
  - Description: Stop automatic XP drops

- `/editleveling`
  - Description: Configure global leveling system settings

## Systems

### Mining System

The mining system provides a complete resource-gathering and economy mini-game within the Discord bot. Key features include:

1. **Resource Collection**
   - 8 different resources with varying rarities and values
   - Stone (common), Coal, Iron, Silver, Gold, Diamond, Emerald, Ruby (rare)
   - Random chance-based mining with equipment multipliers
   - Cooldown system with prestige-based reductions

2. **Equipment Progression**
   - 8 tiers of pickaxes with increasing multipliers
   - Wooden (starter) to Obsidian (end-game)
   - Each upgrade provides greater mining efficiency
   - Progressive cost scaling for balanced progression

3. **Shop System**
   - Various utility items that enhance mining capabilities
   - Mining Helmet: Increases mining success rate
   - Mining Gloves: Increases resource amount
   - Resource Bag: Increases storage capacity
   - Energy Drink: Reduces mining cooldown
   - Metal Detector: Chance to find rare resources
   - Dynamite Pack: Chance to double resources

4. **Prestige System**
   - Reset progress in exchange for permanent bonuses
   - Each prestige level provides increased mining rewards
   - Progressive cooldown reduction with higher prestige
   - Increasing cost for each prestige level
   - Ownership of shop items persists through prestige

5. **Leaderboard**
   - Server-wide competition for top miners
   - Rankings based on total wealth and prestige level
   - Visual display of progress for motivation

The mining system integrates with the existing economy, providing an alternative method for earning coins through resource collection and sales, rather than relying solely on message activity or coin drops.

### Bot Status System

The bot status system allows administrators to manage the bot's operational state and inform users about its availability. The system includes three status types:

1. **Online**
   - The bot is fully operational
   - Default status indicator: 🟢
   - Bot presence is set to online

2. **Maintenance**
   - The bot is undergoing maintenance but is still responsive
   - Status indicator: 🟠
   - Bot presence is set to idle with "Maintenance Mode" activity

3. **Offline**
   - The bot is marked as offline (though commands may still work)
   - Status indicator: 🔴
   - Bot presence is set to do not disturb

Status changes are logged to a designated channel (configurable through the status panel) with time, reason, and who made the change. This allows server members to stay informed about the bot's status and any planned maintenance or downtime.

### Unified Drop Management

The drop management system allows administrators to control both XP and coin drops from a single interface:

- View real-time status of both systems simultaneously
- Configure settings for both systems in one place
- Activate/deactivate each system independently
- See detailed configuration information
- Get visual indicators of active state and setup status

This streamlined approach reduces the need to use multiple separate commands to manage the drop systems, making administration more efficient.

### Coin Drops

Coin drops are scheduled events where a message appears in a designated channel. Users can react to the message for a chance to win coins. Only one user (chosen randomly from those who reacted) will receive the coins.

Configuration options:
- Channel: Where drops will appear
- Min/Max Coins: Range of random coin amounts
- Interval: How often drops occur (minutes, hours, or days)

### XP Drops

Similar to coin drops, XP drops allow users to gain XP by reacting to messages that appear in a designated channel.

Configuration options:
- Channel: Where drops will appear
- Min/Max XP: Range of random XP amounts
- Interval: How often drops occur (minutes, hours, or days)

### Investment System

The investment system allows users to spend their coins on businesses that generate passive income. The system features:

1. **Business Purchase**
   - Various businesses available at different price points
   - Each business has different hourly income rates
   - Risk levels affect potential for random events

2. **Maintenance System**
   - Businesses require regular maintenance to function optimally
   - Maintenance costs approximately 50% of daily income
   - Maintenance levels decrease over time (roughly 50% per day)
   - Low maintenance (0-50%) triggers reminder alerts
   - Maintenance can only be performed when levels drop to 50% or below
   - Businesses with low maintenance generate less income
   - At 0% maintenance, businesses become inactive until repaired

3. **Income Collection**
   - Income accumulates hourly based on business type and maintenance level
   - Users can collect income at any time
   - Income is added directly to the user's coin balance

4. **Risk Events**
   - Random events can occur based on business risk level
   - Events may reduce maintenance levels or cause temporary loss of income
   - Higher risk businesses offer better income but face more frequent events

5. **Admin Management Commands**
   - `/reset_properties`: Reset accumulated income for all users' properties (Admin only)
   - `/edit_property`: Edit an existing property's parameters (price, income, maintenance cost, etc.) (Admin only)
   - `/add_property`: Add a new property to the investment system with custom parameters (Admin only)

The investment system provides an engaging way for users to spend their accumulated coins and establish passive income streams, adding depth to the economy system.

### Community Interaction System

The community interaction system provides a set of tools for server members to engage with the server and staff in structured, organized ways. The system includes:

1. **Mass Messaging System**
   - Allows administrators to send customized embedded messages to all server members via DM
   - Features include:
     - Intuitive button-based message builder interface
     - Support for fields, footer text, images, and thumbnails
     - Role filters to target specific groups of members
     - Real-time progress tracking during the message sending process
     - Success/failure statistics for detailed reporting
     - Message preview functionality before sending
   - Uses the same permission system as other administrative commands
   - Respects Discord's rate limits to prevent API timeouts
   - Access through the `/sendtoall` command

2. **Giveaway System**
   - Staff can create structured giveaways with customizable settings:
     - Prize description
     - Number of winners (single or multiple)
     - Duration in hours
     - Channel selection
   - Members join by clicking a single button or reacting with 🎁
   - Automatic winner selection and announcement when time expires
   - Color-coded embeds for visual distinction:
     - Green: Active giveaway
     - Gold: Completed giveaway with winners
     - Red: Cancelled or ended without participants
   - Admin commands for giveaway management:
     - `/giveaway`: Create a new giveaway via modal interface
     - `/endgiveaway`: End a giveaway immediately and select winners
     - `/cancelgiveaway`: Cancel a giveaway without selecting winners
     - `/listgiveaways`: View all active giveaways with details
     - `/rerollgiveaway`: Select new winners for a completed giveaway
   - Persistent giveaway participation across bot restarts
   - Unique IDs for each giveaway for easy reference and management

3. **Suggestions**
   - Members can submit formal suggestions with title and detailed description
   - Suggestions appear in a dedicated channel with admin review buttons
   - Staff can easily mark suggestions as "acted on" or "passed"
   - Provides transparency in the suggestion review process

4. **User Reporting**
   - Simple interface for reporting rule violations
   - Reports include user identification and detailed reason
   - All reports centralized in a dedicated staff channel
   - Maintains privacy for the reporter

5. **Bug Reporting**
   - Structured format captures all necessary debugging information
   - Includes title, description, steps to reproduce, and expected behavior
   - Organizes reports for easier troubleshooting by developers
   - Reduces back-and-forth questions with comprehensive initial reports

6. **Feedback Collection**
   - Open-ended feedback option for general comments
   - Anonymous collection in a dedicated channel
   - Provides an outlet for opinions that don't fit other categories

7. **Rules Distribution**
   - On-demand access to server rules via direct message
   - Formatted embed with clearly numbered rules
   - Privacy-respecting delivery mechanism

All community interaction features use dedicated channels configurable by administrators through the `/set_channel` command. This ensures proper organization and makes it easy for staff to monitor and respond to member interactions.

## Migration Utilities

### Data Migration

- Command: `/migratedata`
- Description: Import user data from an older database

### Legacy Data Finder

- Command: `/findlegacydata`
- Description: Scans message history for old `/rank` command usage to extract and import user stats

## Database Management

### Database Backup and Restore

These commands allow you to transfer user data between different hosting environments (like UptimeRobot and Replit).

#### Database Backup

- Command: `/dbsync`
- Description: Sends database files to the admin's DMs for safekeeping
- Usage: Run this command periodically to back up your data
- Note: Only administrators can use this command
- Files backed up include:
  - `data/leveling.db`: Main database with user data, levels, and mining stats
  - `.json` files: Configuration and state files, including:
    - `data/investments.json`: Investment properties and user investments
    - `data/tournaments.json`: Tournament configurations and data
    - `data/tournament_votes.json`: Game voting data for tournaments
    - `data/tickets.json`: Ticket system configuration and active tickets
    - `data/giveaways.json`: Giveaway data including active and past giveaways

#### Database Restore

- Command: `/dbrestore`
- Description: Restores the database from a previously backed up file
- Usage: Use when moving the bot to a new hosting environment
- Process:
  1. Use `/dbsync` in the previous environment to back up
  2. Run `/dbrestore` in the new environment
  3. Upload the saved `leveling.db` file when prompted
  4. Bot will validate and import the database, then restart
- Note: This will replace all current user data with the uploaded data
- Security: Only the bot owner can use this command

#### JSON Data Import

- Command: `/dbimportjson`
- Description: Import JSON files to synchronize additional data
- Usage: After restoring the main database, import any JSON files
- Process:
  1. Run `/dbimportjson` in the new environment
  2. Upload JSON files for different systems:
     - `investments.json` for investment data
     - `tournaments.json` for tournament configurations
     - `tournament_votes.json` for game vote data
     - `tickets.json` for ticket system configuration
     - `giveaways.json` for giveaway data
  3. Bot will copy these files to the appropriate locations
- Note: This complements the database restore by importing other data files

#### PostgreSQL Database Migration

- Command: `/pgmigrate`
- Description: Migrates all user data from SQLite to PostgreSQL for persistent storage
- Usage: Use to enable data persistence across different hosting platforms
- Process:
  1. Set up a PostgreSQL database and add the DATABASE_URL to your .env file
  2. Run the `/pgmigrate` command as an administrator
  3. The bot will migrate all data from SQLite to PostgreSQL
  4. Once complete, the bot will automatically use PostgreSQL for all operations
- Note: This is the recommended approach for persistent data storage
- Security: Only administrators can use this command

#### PostgreSQL Status Check

- Command: `/pgstatus`
- Description: Checks the status of the database connection and migration
- Usage: Use to verify if PostgreSQL is properly configured
- Information provided:
  - Whether the bot is using PostgreSQL
  - PostgreSQL configuration status
  - SQLite database status
  - Number of JSON data types in PostgreSQL
  - User count in the database
- Note: If PostgreSQL is configured but not being used, the command will recommend running the migration
- Security: Only administrators can use this command

For detailed information about PostgreSQL migration, see the `POSTGRES_MIGRATION.md` file.

### Cross-Host Data Migration Guide

If you need to move the bot between hosting environments (e.g., from UptimeRobot to Replit), follow these steps:

1. **Backup data from the source environment:**
   - Run `/dbsync` to receive database files in your DMs
   - Save all files to your local computer

2. **Prepare the destination environment:**
   - Ensure the bot is set up with the same token and basic configuration
   - Start the bot to initialize the database with default values

3. **Restore the database:**
   - Run `/dbrestore` in the destination environment
   - Upload the `leveling.db` file when prompted
   - Wait for the bot to restart after the restore completes

4. **Import JSON data:**
   - Run `/dbimportjson` in the destination environment
   - Upload any JSON files you received from the backup
   - Wait for the bot to restart after the import completes

5. **Verify the migration:**
   - Test basic commands like `/rank` or `/mine` to confirm user data is present
   - Check investments, tournaments, and other systems for proper functionality
   - Verify existing tournaments are accessible via the `/tournament` command

This process ensures all user progress, levels, coins, and other data are preserved when moving between hosting environments.

### Database Structure

The bot supports two database backends:

#### SQLite Database
The traditional database (`leveling.db`) used for backward compatibility.

#### PostgreSQL Database
A persistent database that allows data to be accessible across different hosting platforms. This is the recommended database for production use.

For detailed information about PostgreSQL migration, see the `POSTGRES_MIGRATION.md` file.

Both database backends contain the following tables:
- `users`: Stores user information including XP, level, prestige, and coins
- `settings`: Global settings for the leveling system
- `invites`: Tracking of user invites (real, fake, bonus, left)
- `mining_stats`: User mining statistics (money, prestige level, equipment)
- `mining_resources`: Resources gathered through mining
- `mining_items`: Items purchased to enhance mining
- `activity_events`: Records of activity events and their settings
- `activity_participants`: User participation data for activity events

The investments system stores data in a separate JSON file (`investments.json`), which contains:
- Business definitions (cost, income rates, risk levels)
- User-owned businesses
- Purchase timestamps
- Maintenance levels
- Income collection history

The tournament system stores data in separate JSON files:
- `tournaments.json`: Contains tournament definitions, participants, teams, brackets, and match results
- `tournament_votes.json`: Contains game vote data for selecting tournament games

### Tournament System

The tournament system integrates with the enhanced Game Vote system, allowing administrators to create specialized tournament game votes:

- Access via the "Start Tournament Vote" button in the `/gamevote` command
- Admin-only functionality to ensure proper tournament planning
- Up to 4 custom game options per vote
- Configurable voting duration in hours
- Real-time vote counting and display
- Persistent votes that survive bot restarts
- Unique vote IDs for easy reference
- Results automatically saved for tournament planning

The tournament system allows admins to organize gaming competitions on the server with team formation, brackets, and match tracking. The system uses short, alphanumeric IDs (like "a7b3c") for easier reference and management.

1. **Tournament Creation**
   - Admins can create tournaments with customizable settings:
     - Game type (any game)
     - Maximum participants
     - Start time and date
     - Team count and size
     - Prize description
   - Each tournament gets assigned a unique 5-character ID for easy reference
   - Participants can join via a button or command

2. **Participant Management**
   - View complete list of all tournament participants with join timestamps
   - Sorted participant display with usernames and IDs
   - Easily monitor registration progress with participant counter

3. **Team Management**
   - Automatic or manual team formation
   - Teams are randomly generated from participants
   - Team names can be customized
   - Balanced team sizes based on tournament settings

4. **Bracket Generation**
   - Automatic bracket creation based on team count
   - Support for non-power-of-2 team counts with byes
   - Match ID system for tracking progress
   - Visual bracket display in embeds

5. **Tournament Status Tracking**
   - Multiple status stages: recruiting, team_formation, in_progress, completed
   - Status-specific commands and options
   - Detailed tournament information accessible via commands

6. **Match Management**
   - Admins can update match results
   - Score tracking for each match
   - Automatic advancement of winners to next rounds
   - Statistics tracking for teams (wins/losses)

7. **Game Voting Integration**
   - Pre-tournament voting to decide which game to play
   - Multiple game options with timed voting
   - Results automatically tallied
   - Used for determining tournament games

Tournament data is stored in JSON files (`tournaments.json` and `tournament_votes.json`), which contain:
- Tournament definitions (ID, settings, start time)
- Participant lists
- Team compositions and names
- Bracket structures
- Match results and scores

### Ticket System

The ticket system provides a structured way for users to get support, report issues, or communicate privately with server staff. The system features private channels, transcripts, and role-based permissions.

1. **Ticket Creation**
   - Users can create tickets with subject and description in two ways:
     - Using the `/ticket` command directly
     - Using interactive buttons from a ticket panel
   - Each ticket gets its own private channel automatically
   - Channels are created in a dedicated category
   - Channel permissions are set for the ticket creator and support staff
   - Initial welcome message contains ticket information and controls

2. **Support Staff Controls**
   - Add or remove users from tickets as needed
   - Close tickets with reason documentation
   - Transcript generation for closed tickets
   - Log entries for ticket actions

3. **Ticket Configuration**
   - Customizable category for ticket channels
   - Dedicated log channel for ticket actions
   - Support role assignment for permissions
   - Simple setup via ID-based configuration

4. **Ticket Panel System**
   - Create interactive panels with buttons using `/ticketpanel` command
   - Customizable panel title and description
   - Persistent buttons that work even after bot restarts
   - User-friendly interface for ticket creation
   - Automatically opens a form for users to enter ticket details

5. **Ticket Lifecycle**
   - Creation: User creates ticket with subject and description
   - Communication: Private discussion in the ticket channel
   - Resolution: Staff or creator can close the ticket
   - Archive: Transcript saved and channel deleted

6. **Data Management**
   - Ticket data stored in `data/tickets.json`
   - Transcripts saved in `data/transcripts/` directory
   - Tracking of ticket counter for sequential IDs
   - Configuration stored in `settings.json`

The ticket system provides a streamlined support experience with privacy controls, allowing staff to manage multiple support requests efficiently while maintaining proper documentation.