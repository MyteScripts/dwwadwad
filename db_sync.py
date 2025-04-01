import discord
from discord import app_commands
from discord.ext import commands
import os
import shutil
import datetime
import logging
import aiohttp
import asyncio
import sqlite3
from logger import setup_logger

logger = setup_logger('db_sync', 'bot.log')

class DBSyncCog(commands.Cog):
    """Cog for syncing database files to DMs for backup and restoring database from uploads."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("DB Sync cog initialized")
    
    @app_commands.command(
        name="dbsync", 
        description="Send database and data files as a backup to your DMs (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def db_sync(self, interaction: discord.Interaction):
        """
        Send database and data files as attachments to the user's DMs for backup.
        """

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:

            search_dirs = ['data', '.', 'logs']
            for directory in search_dirs:
                os.makedirs(directory, exist_ok=True)

            db_files = []
            for directory in search_dirs:

                db_files.extend([os.path.join(directory, file) for file in os.listdir(directory) 
                                if file.endswith(('.db', '.sqlite', '.sqlite3'))])

                if directory == 'data' or directory == '.':  # Include JSON files from data and root directories
                    db_files.extend([os.path.join(directory, file) for file in os.listdir(directory) 
                                    if file.endswith('.json')])
            
            if not db_files:
                await interaction.followup.send(
                    "No database files found in any of the project directories.", 
                    ephemeral=True
                )
                return

            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = f'backup_{timestamp}'
            os.makedirs(backup_dir, exist_ok=True)

            files_copied = []
            for src_path in db_files:

                file_name = os.path.basename(src_path)
                dst_path = os.path.join(backup_dir, file_name)

                try:
                    shutil.copy2(src_path, dst_path)
                    files_copied.append(dst_path)
                    logger.info(f"Copied {src_path} to {dst_path}")
                except Exception as e:
                    logger.error(f"Error copying {src_path}: {e}")
            
            if not files_copied:

                shutil.rmtree(backup_dir, ignore_errors=True)
                await interaction.followup.send(
                    "Failed to create backup copies of database files.", 
                    ephemeral=True
                )
                return

            try:

                dm_channel = await interaction.user.create_dm()
                await dm_channel.send("**📦 Database Backup**\nHere are the database and data files you requested:")

                files_sent = 0
                for file_path in files_copied:
                    filename = os.path.basename(file_path)
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # size in MB

                    file = discord.File(file_path, filename=filename)
                    await dm_channel.send(
                        f"📄 **{filename}** - Size: {file_size:.2f} MB",
                        file=file
                    )
                    files_sent += 1

                await dm_channel.send(
                    f"✅ **Backup Complete**\nSent {files_sent} database files.\n"
                    f"This includes database files (.db) and data files (.json) with user data.\n"
                    f"Keep these files safe to restore your bot's data if needed."
                )

                await interaction.followup.send(
                    f"✅ Database backup complete! {files_sent} files have been sent to your DMs.", 
                    ephemeral=True
                )
                
                logger.info(f"DB sync completed by {interaction.user.id}. Sent {files_sent} files.")
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I couldn't send you a DM. Please make sure your DM settings allow messages from server members.", 
                    ephemeral=True
                )
                logger.error(f"Failed to send DM to {interaction.user.id}")

            shutil.rmtree(backup_dir, ignore_errors=True)
            
        except Exception as e:
            logger.error(f"Error in DB sync: {e}")
            await interaction.followup.send(
                f"An error occurred during the database sync: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(
        name="dbrestore", 
        description="Restore database from an uploaded file (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def db_restore(self, interaction: discord.Interaction):
        """
        Restore database from an uploaded file.
        The file must be uploaded as an attachment to a reply to this command.
        """
        owner_id = "1308527904497340467"  # Replace with your user ID
        
        if str(interaction.user.id) != owner_id:
            await interaction.response.send_message(
                "⚠️ This command can only be used by the bot owner due to security considerations.", 
                ephemeral=True
            )
            return
            
        await interaction.response.send_message(
            "📤 Please upload your database file (.db) as a reply to this message.\n"
            "⚠️ **WARNING**: This will replace your current database and restart the bot.\n"
            "All current data will be lost if not backed up.\n\n"
            "Reply with 'cancel' to abort this operation.",
            ephemeral=False
        )
        
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
            
        try:
            reply_msg = await self.bot.wait_for('message', check=check, timeout=300)  # 5 minute timeout
            
            if reply_msg.content.lower() == 'cancel':
                await interaction.followup.send("Database restore cancelled.", ephemeral=True)
                return
                
            if not reply_msg.attachments:
                await interaction.followup.send(
                    "No attachments found. Please upload a database file.", 
                    ephemeral=True
                )
                return
                
            attachment = reply_msg.attachments[0]
            if not attachment.filename.endswith(('.db', '.sqlite', '.sqlite3')):
                await interaction.followup.send(
                    "The attached file is not a database file. Please upload a .db, .sqlite, or .sqlite3 file.", 
                    ephemeral=True
                )
                return
                
            # Create backup of current database first
            os.makedirs('backup', exist_ok=True)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'backup/leveling_{timestamp}.db'
            
            try:
                if os.path.exists('data/leveling.db'):
                    shutil.copy2('data/leveling.db', backup_path)
                    logger.info(f"Created backup of database at {backup_path}")
            except Exception as e:
                logger.error(f"Error creating backup: {e}")
                await interaction.followup.send(
                    f"Failed to create backup of current database: {str(e)}\nRestore operation aborted.", 
                    ephemeral=True
                )
                return
                
            # Download and validate the attachment
            try:
                await interaction.followup.send("⏳ Downloading and validating database file...", ephemeral=False)
                
                os.makedirs('data', exist_ok=True)
                download_path = f'data/temp_restore_{timestamp}.db'
                
                await attachment.save(download_path)
                logger.info(f"Downloaded database file to {download_path}")
                
                # Validate the database
                try:
                    conn = sqlite3.connect(download_path)
                    cursor = conn.cursor()
                    
                    # Check for required tables
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    required_tables = ['users', 'settings']
                    missing_tables = [table for table in required_tables if table not in tables]
                    
                    if missing_tables:
                        conn.close()
                        os.remove(download_path)
                        await interaction.followup.send(
                            f"Invalid database file. Missing required tables: {', '.join(missing_tables)}", 
                            ephemeral=True
                        )
                        return
                        
                    conn.close()
                    
                except Exception as e:
                    logger.error(f"Error validating database: {e}")
                    os.remove(download_path)
                    await interaction.followup.send(
                        f"Failed to validate database file: {str(e)}", 
                        ephemeral=True
                    )
                    return
                    
                # Replace the current database with the uploaded one
                try:
                    if os.path.exists('data/leveling.db'):
                        os.remove('data/leveling.db')
                    
                    shutil.copy2(download_path, 'data/leveling.db')
                    os.remove(download_path)
                    
                    logger.info("Database successfully restored")
                    
                    await interaction.followup.send(
                        "✅ Database successfully restored! The bot will restart in 5 seconds...",
                        ephemeral=False
                    )
                    
                    # Give users time to read the message before restarting
                    await asyncio.sleep(5)
                    
                    # Restart the bot
                    await self.bot.close()
                    
                except Exception as e:
                    logger.error(f"Error restoring database: {e}")
                    await interaction.followup.send(
                        f"Failed to restore database: {str(e)}\nYour original database has been preserved.", 
                        ephemeral=True
                    )
                    
            except Exception as e:
                logger.error(f"Error downloading attachment: {e}")
                await interaction.followup.send(
                    f"Failed to download database file: {str(e)}", 
                    ephemeral=True
                )
                
        except asyncio.TimeoutError:
            await interaction.followup.send("Database restore timed out.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in DB restore: {e}")
            await interaction.followup.send(
                f"An error occurred during the database restore: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(
        name="dbimportjson", 
        description="Import data from JSON files (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def db_import_json(self, interaction: discord.Interaction):
        """
        Import data from JSON files to synchronize between environments.
        """
        owner_id = "1308527904497340467"  # Replace with your user ID
        
        if str(interaction.user.id) != owner_id:
            await interaction.response.send_message(
                "⚠️ This command can only be used by the bot owner due to security considerations.", 
                ephemeral=True
            )
            return
            
        await interaction.response.send_message(
            "📤 Please upload your JSON data files as a reply to this message.\n"
            "You can upload multiple files at once.\n"
            "⚠️ **WARNING**: This will merge this data with your current database.\n\n"
            "Reply with 'cancel' to abort this operation.",
            ephemeral=False
        )
        
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
            
        try:
            reply_msg = await self.bot.wait_for('message', check=check, timeout=300)  # 5 minute timeout
            
            if reply_msg.content.lower() == 'cancel':
                await interaction.followup.send("Data import cancelled.", ephemeral=True)
                return
                
            if not reply_msg.attachments:
                await interaction.followup.send(
                    "No attachments found. Please upload JSON files.", 
                    ephemeral=True
                )
                return
            
            json_files = [attachment for attachment in reply_msg.attachments if attachment.filename.endswith('.json')]
            if not json_files:
                await interaction.followup.send(
                    "No JSON files found. Please upload files with .json extension.", 
                    ephemeral=True
                )
                return
            
            await interaction.followup.send(f"⏳ Processing {len(json_files)} JSON files...", ephemeral=False)
            
            import_dir = 'data/json_import'
            os.makedirs(import_dir, exist_ok=True)
            
            imported_files = []
            for attachment in json_files:
                try:
                    file_path = os.path.join(import_dir, attachment.filename)
                    await attachment.save(file_path)
                    imported_files.append(file_path)
                    logger.info(f"Downloaded JSON file to {file_path}")
                except Exception as e:
                    logger.error(f"Error downloading {attachment.filename}: {e}")
            
            if not imported_files:
                await interaction.followup.send("Failed to download any JSON files.", ephemeral=True)
                return
            
            # Copy JSON files to their proper locations
            for file_path in imported_files:
                filename = os.path.basename(file_path)
                destination = os.path.join('data', filename)
                
                try:
                    shutil.copy2(file_path, destination)
                    logger.info(f"Copied {filename} to data directory")
                except Exception as e:
                    logger.error(f"Error copying {filename}: {e}")
            
            # Clean up import directory
            try:
                shutil.rmtree(import_dir)
            except Exception as e:
                logger.error(f"Error cleaning up import directory: {e}")
            
            await interaction.followup.send(
                f"✅ Successfully imported {len(imported_files)} JSON files! The bot will restart in 5 seconds...",
                ephemeral=False
            )
            
            # Give users time to read the message before restarting
            await asyncio.sleep(5)
            
            # Restart the bot
            await self.bot.close()
            
        except asyncio.TimeoutError:
            await interaction.followup.send("Data import timed out.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in DB import: {e}")
            await interaction.followup.send(
                f"An error occurred during the data import: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    """Add the db sync cog to the bot."""
    await bot.add_cog(DBSyncCog(bot))
    logger.info("DB Sync cog loaded")