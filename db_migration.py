import os
import discord
from discord import app_commands
from discord.ext import commands
import logging
from logger import setup_logger
from database_handler import DatabaseHandler

logger = setup_logger('db_migration')

class DBMigrationCog(commands.Cog):
    """Cog for PostgreSQL database migration and management."""
    
    def __init__(self, bot):
        self.bot = bot
        # Connect to the correct database automatically
        self.db = DatabaseHandler()
        logger.info("DB Migration cog initialized")
    
    @app_commands.command(
        name="pgmigrate", 
        description="Migrate data to PostgreSQL for persistent storage across platforms (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def pg_migrate(self, interaction: discord.Interaction):
        """
        Migrate all user data from SQLite to PostgreSQL.
        This allows the bot to maintain data when moved between different platforms.
        """
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return
        
        # Check if PostgreSQL is available
        if not os.environ.get('DATABASE_URL'):
            await interaction.response.send_message(
                "❌ No PostgreSQL database configured. Please set the DATABASE_URL environment variable.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            if self.db.using_postgres:
                # Run migration
                migration_result = self.db.migrate_sqlite_to_postgres()
                
                if migration_result:
                    await interaction.followup.send(
                        "✅ Successfully migrated data to PostgreSQL database. Your bot's data will now persist across platforms.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Migration failed. Check the logs for details.",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    "❌ Could not initialize PostgreSQL database. Make sure the DATABASE_URL is correct.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in PG migration: {e}", exc_info=True)
            await interaction.followup.send(
                f"An error occurred during the migration: {str(e)}", 
                ephemeral=True
            )
    
    @app_commands.command(
        name="pgstatus", 
        description="Check the status of database connections (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def pg_status(self, interaction: discord.Interaction):
        """Check the status of SQLite and PostgreSQL database connections."""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check database connections
            status_lines = [
                "📊 **Database Status**",
                f"• Using PostgreSQL: {'✅ Yes' if self.db.using_postgres else '❌ No'}",
            ]
            
            if os.environ.get('DATABASE_URL'):
                status_lines.append("• PostgreSQL Configuration: ✅ Available")
            else:
                status_lines.append("• PostgreSQL Configuration: ❌ Missing (Set DATABASE_URL)")
            
            sqlite_path = "data/leveling.db"
            if os.path.exists(sqlite_path):
                status_lines.append(f"• SQLite Database: ✅ Found ({sqlite_path})")
            else:
                status_lines.append(f"• SQLite Database: ❌ Not found ({sqlite_path})")
            
            # Check json_data table if using PostgreSQL
            if self.db.using_postgres:
                try:
                    with self.db.pg_db.conn.cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM json_data")
                        json_count = cursor.fetchone()[0]
                        status_lines.append(f"• PostgreSQL JSON Data Types: {json_count}")
                except Exception as e:
                    status_lines.append(f"• PostgreSQL JSON Data: ❓ Error checking ({str(e)})")
            
            # User count
            try:
                user_count = len(self.db.get_top_users(limit=1000000))
                status_lines.append(f"• Users in Database: {user_count}")
            except Exception as e:
                status_lines.append(f"• Users in Database: ❓ Error checking ({str(e)})")
            
            # Create embed
            embed = discord.Embed(
                title="Database Status",
                description="\n".join(status_lines),
                color=0x3498DB
            )
            
            if not self.db.using_postgres and os.environ.get('DATABASE_URL'):
                embed.add_field(
                    name="🔀 Migration Recommended",
                    value="You have PostgreSQL configured but are still using SQLite. "
                          "Run `/pgmigrate` to transfer data and enable persistence.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in database status check: {e}", exc_info=True)
            await interaction.followup.send(
                f"An error occurred while checking database status: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    """Add the database migration cog to the bot."""
    await bot.add_cog(DBMigrationCog(bot))
    logger.info("Database migration cog loaded")