import sqlite3
import os
import discord
from discord import app_commands
from discord.ext import commands
import logging
from logger import setup_logger
from database import Database

logger = setup_logger('migration', 'bot.log')

class MigrationCog(commands.Cog):
    """Cog for migrating user data from old databases."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        logger.info("Migration cog initialized")
    
    @app_commands.command(name="migratedata", description="Migrate user data from an old database (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def migrate_data(self, interaction: discord.Interaction, old_db_path: str = None):
        """Migrate user data from an old database file."""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not old_db_path:
            old_db_path = "old_leveling.db"
            logger.info(f"No database path provided, using default: {old_db_path}")

        if not os.path.dirname(old_db_path):
            old_db_path = os.path.join("data", old_db_path)

        if not os.path.exists(old_db_path):
            await interaction.followup.send(f"Error: Database file {old_db_path} not found. Please place the old database file in the data directory.", ephemeral=True)
            return
        
        try:

            old_conn = sqlite3.connect(old_db_path)
            old_conn.row_factory = sqlite3.Row
            old_cursor = old_conn.cursor()

            old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not old_cursor.fetchone():
                await interaction.followup.send("Error: The old database does not have a users table.", ephemeral=True)
                old_conn.close()
                return

            old_cursor.execute("PRAGMA table_info(users)")
            old_columns = [column[1] for column in old_cursor.fetchall()]

            required_columns = ['user_id']
            missing_columns = [col for col in required_columns if col not in old_columns]
            
            if missing_columns:
                await interaction.followup.send(f"Error: The old database is missing required columns: {', '.join(missing_columns)}", ephemeral=True)
                old_conn.close()
                return

            query = f"SELECT * FROM users"
            old_cursor.execute(query)
            old_users = old_cursor.fetchall()
            
            if not old_users:
                await interaction.followup.send("No users found in the old database.", ephemeral=True)
                old_conn.close()
                return

            migrated_count = 0
            skipped_count = 0
            error_count = 0

            for old_user in old_users:
                try:
                    user_id = old_user['user_id']

                    self.db.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                    current_user = self.db.cursor.fetchone()

                    username = old_user['username'] if 'username' in old_columns else f"User_{user_id}"
                    xp = old_user['xp'] if 'xp' in old_columns else 0
                    level = old_user['level'] if 'level' in old_columns else 1
                    coins = old_user['coins'] if 'coins' in old_columns else 0
                    prestige = old_user['prestige'] if 'prestige' in old_columns else 0
                    
                    if current_user:

                        self.db.cursor.execute('''
                            UPDATE users SET 
                                username = ?,
                                xp = ?,
                                level = ?,
                                coins = ?,
                                prestige = ?
                            WHERE user_id = ?
                        ''', (username, xp, level, coins, prestige, user_id))
                    else:

                        self.db.cursor.execute('''
                            INSERT INTO users (
                                user_id, username, xp, level, coins, prestige
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (user_id, username, xp, level, coins, prestige))
                    
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating user {old_user['user_id']}: {e}")
                    error_count += 1

            self.db.conn.commit()

            old_conn.close()

            embed = discord.Embed(
                title="✅ Data Migration Complete",
                description=f"Successfully migrated user data from {old_db_path}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Migration Results",
                value=(
                    f"👥 Total users processed: {len(old_users)}\n"
                    f"✅ Users migrated: {migrated_count}\n"
                    f"⚠️ Users skipped: {skipped_count}\n"
                    f"❌ Errors: {error_count}"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Data migration completed by {interaction.user.id}. Migrated: {migrated_count}, Skipped: {skipped_count}, Errors: {error_count}")
            
        except Exception as e:
            logger.error(f"Migration error: {e}")
            await interaction.followup.send(f"An error occurred during migration: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="importusers", description="Import data for specific users (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def import_users(self, interaction: discord.Interaction, user_data: str):
        """Import data for specific users in format: user_id,level,xp,coins,prestige;user_id,level,xp,coins,prestige"""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:

            user_entries = user_data.strip().split(';')
            
            if not user_entries:
                await interaction.followup.send("No user data provided.", ephemeral=True)
                return

            imported_count = 0
            error_count = 0
            results = []
            
            for entry in user_entries:
                try:

                    fields = entry.strip().split(',')
                    
                    if len(fields) < 2:
                        results.append(f"❌ Invalid entry: {entry}")
                        error_count += 1
                        continue

                    user_id = int(fields[0])

                    try:
                        member = await interaction.guild.fetch_member(user_id)
                        username = member.display_name
                    except:
                        username = f"User_{user_id}"

                    level = int(fields[1]) if len(fields) > 1 else 1
                    xp = int(fields[2]) if len(fields) > 2 else 0
                    coins = int(fields[3]) if len(fields) > 3 else 0
                    prestige = int(fields[4]) if len(fields) > 4 else 0

                    self.db.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                    current_user = self.db.cursor.fetchone()
                    
                    if current_user:

                        self.db.cursor.execute('''
                            UPDATE users SET 
                                username = ?,
                                xp = ?,
                                level = ?,
                                coins = ?,
                                prestige = ?
                            WHERE user_id = ?
                        ''', (username, xp, level, coins, prestige, user_id))
                    else:

                        self.db.cursor.execute('''
                            INSERT INTO users (
                                user_id, username, xp, level, coins, prestige
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (user_id, username, xp, level, coins, prestige))
                    
                    imported_count += 1
                    results.append(f"✅ {username}: Level {level}, XP {xp}, Coins {coins}, Prestige {prestige}")
                    
                except Exception as e:
                    logger.error(f"Error importing user data '{entry}': {e}")
                    results.append(f"❌ Error with entry '{entry}': {str(e)}")
                    error_count += 1

            self.db.conn.commit()

            embed = discord.Embed(
                title="✅ User Data Import Complete",
                description=f"Import results:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Summary",
                value=(
                    f"👥 Total entries: {len(user_entries)}\n"
                    f"✅ Users imported: {imported_count}\n"
                    f"❌ Errors: {error_count}"
                ),
                inline=False
            )

            result_chunks = [results[i:i+10] for i in range(0, len(results), 10)]
            for i, chunk in enumerate(result_chunks, 1):
                embed.add_field(
                    name=f"Details (Part {i}/{len(result_chunks)})",
                    value="\n".join(chunk),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"User data import completed by {interaction.user.id}. Imported: {imported_count}, Errors: {error_count}")
            
        except Exception as e:
            logger.error(f"Import error: {e}")
            await interaction.followup.send(f"An error occurred during import: {str(e)}", ephemeral=True)

async def setup(bot):
    """Add the migration cog to the bot."""
    await bot.add_cog(MigrationCog(bot))
    logger.info("Migration cog loaded")