import re
import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from logger import setup_logger
from database import Database

logger = setup_logger('legacy_finder', 'bot.log')

class LegacyDataFinderCog(commands.Cog):
    """Cog for finding and migrating data from old bot commands in message history."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.is_scanning = False
        self.current_task = None
        logger.info("Legacy data finder cog initialized")
    
    @app_commands.command(
        name="findlegacydata", 
        description="Scan message history for old /rank commands and import the data (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def find_legacy_data(
        self, 
        interaction: discord.Interaction,
        days_to_scan: int = 30,
        channel: discord.TextChannel = None
    ):
        """
        Scan message history for old /rank commands and import the data.
        
        Parameters:
        - days_to_scan: How many days of history to scan (default: 30)
        - channel: Specific channel to scan (default: all channels)
        """

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return

        if self.is_scanning:
            await interaction.response.send_message(
                "A scan is already in progress. Please wait for it to complete.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)

        self.is_scanning = True
        
        try:

            embed = discord.Embed(
                title="🔍 Legacy Data Scan Started",
                description=f"Scanning the last {days_to_scan} days of message history for old rank commands...",
                color=discord.Color.blue()
            )
            
            if channel:
                embed.add_field(
                    name="Scan Location",
                    value=f"Channel: {channel.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Scan Location",
                    value="All text channels in the server",
                    inline=False
                )
            
            progress_message = await interaction.followup.send(embed=embed, ephemeral=True)

            self.current_task = asyncio.create_task(
                self.scan_message_history(
                    interaction.guild,
                    progress_message,
                    days_to_scan,
                    channel
                )
            )
            
        except Exception as e:
            logger.error(f"Error starting legacy data scan: {e}")
            self.is_scanning = False
            await interaction.followup.send(
                f"An error occurred when starting the scan: {str(e)}", 
                ephemeral=True
            )
    
    @app_commands.command(
        name="cancelscan", 
        description="Cancel an ongoing message history scan (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def cancel_scan(self, interaction: discord.Interaction):
        """Cancel an ongoing message history scan."""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )
            return

        if not self.is_scanning or self.current_task is None:
            await interaction.response.send_message(
                "No scan is currently running.", 
                ephemeral=True
            )
            return

        self.current_task.cancel()
        self.is_scanning = False
        
        await interaction.response.send_message(
            "Scan cancelled successfully.", 
            ephemeral=True
        )
        logger.info(f"Scan cancelled by {interaction.user.id}")
    
    async def scan_message_history(
        self, 
        guild, 
        progress_message, 
        days_to_scan=30, 
        specific_channel=None
    ):
        """
        Scan message history for old rank commands and import the data.
        
        Parameters:
        - guild: The Discord guild to scan
        - progress_message: Message to update with progress
        - days_to_scan: How many days of history to scan
        - specific_channel: Specific channel to scan (if None, scan all channels)
        """
        try:

            import datetime
            time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_to_scan)

            channels_scanned = 0
            total_channels = 0
            messages_scanned = 0
            rank_commands_found = 0
            users_imported = 0
            errors = 0

            rank_command_patterns = [

                r"(?:\/|!)rank",

                r"(?:\/|!)level",
                r"(?:\/|!)lvl",
                r"(?:\/|!)xp"
            ]

            data_patterns = {
                'level': r"(?:Level|LVL):\s*(\d+)",
                'xp': r"(?:XP|Experience):\s*(\d+)(?:\s*\/\s*\d+)?",
                'coins': r"(?:Coins|Money|Balance):\s*(\d+)",
                'prestige': r"(?:Prestige|Prestige Level):\s*(\d+)"
            }

            if specific_channel:
                channels = [specific_channel]
                total_channels = 1
            else:
                channels = [channel for channel in guild.text_channels 
                           if channel.permissions_for(guild.me).read_message_history]
                total_channels = len(channels)

            embed = discord.Embed(
                title="🔍 Legacy Data Scan In Progress",
                description=f"Scanning message history from the last {days_to_scan} days...",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Progress",
                value=f"Channels: 0/{total_channels}\nMessages scanned: 0\nRank commands found: 0\nUsers imported: 0",
                inline=False
            )
            
            await progress_message.edit(embed=embed)

            processed_users = set()
            found_data = {}  # User ID -> Data

            for channel in channels:
                channels_scanned += 1
                channel_messages_scanned = 0
                
                try:

                    if channels_scanned % 5 == 0 or channels_scanned == total_channels:
                        embed.set_field_at(
                            0,
                            name="Progress",
                            value=(
                                f"Channels: {channels_scanned}/{total_channels}\n"
                                f"Messages scanned: {messages_scanned}\n"
                                f"Rank commands found: {rank_commands_found}\n"
                                f"Users imported: {users_imported}"
                            ),
                            inline=False
                        )
                        await progress_message.edit(embed=embed)

                    async for message in channel.history(limit=None, after=time_limit):

                        if not self.is_scanning:
                            raise asyncio.CancelledError("Scan cancelled")
                        
                        messages_scanned += 1
                        channel_messages_scanned += 1

                        if messages_scanned % 1000 == 0:
                            embed.set_field_at(
                                0,
                                name="Progress",
                                value=(
                                    f"Channels: {channels_scanned}/{total_channels}\n"
                                    f"Messages scanned: {messages_scanned}\n"
                                    f"Rank commands found: {rank_commands_found}\n"
                                    f"Users imported: {users_imported}"
                                ),
                                inline=False
                            )
                            await progress_message.edit(embed=embed)

                        is_rank_command = False
                        for pattern in rank_command_patterns:
                            if re.search(pattern, message.content, re.IGNORECASE):
                                is_rank_command = True
                                break
                        
                        if is_rank_command:
                            rank_commands_found += 1

                            user_id = message.author.id

                            if user_id in processed_users:
                                continue

                            response_limit = 5
                            response_count = 0

                            user_data = {
                                'user_id': user_id,
                                'username': message.author.display_name,
                                'found_in_channel': channel.name,
                                'command_time': message.created_at.isoformat()
                            }
                            
                            try:
                                async for response in channel.history(
                                    limit=response_limit, 
                                    after=message.created_at
                                ):
                                    response_count += 1

                                    if response.author.bot:

                                        if response.embeds:
                                            for embed_obj in response.embeds:
                                                embed_dict = embed_obj.to_dict()

                                                embed_text = str(embed_dict)

                                                for data_type, pattern in data_patterns.items():
                                                    match = re.search(pattern, embed_text, re.IGNORECASE)
                                                    if match:
                                                        user_data[data_type] = int(match.group(1))

                                        for data_type, pattern in data_patterns.items():
                                            match = re.search(pattern, response.content, re.IGNORECASE)
                                            if match and data_type not in user_data:
                                                user_data[data_type] = int(match.group(1))

                                    if all(k in user_data for k in data_patterns.keys()):
                                        break

                                data_found = False
                                for key in data_patterns.keys():
                                    if key in user_data:
                                        data_found = True
                                        break
                                
                                if data_found:
                                    found_data[user_id] = user_data
                                    processed_users.add(user_id)
                            except Exception as e:
                                logger.error(f"Error processing responses for user {user_id}: {e}")
                                errors += 1
                
                except Exception as e:
                    logger.error(f"Error scanning channel {channel.name}: {e}")
                    errors += 1
                    continue

            for user_id, data in found_data.items():
                try:

                    level = data.get('level', 1)
                    xp = data.get('xp', 0)
                    coins = data.get('coins', 0)
                    prestige = data.get('prestige', 0)
                    username = data.get('username', f"User_{user_id}")

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
                    
                    users_imported += 1
                    
                except Exception as e:
                    logger.error(f"Error importing data for user {user_id}: {e}")
                    errors += 1

            self.db.conn.commit()

            final_embed = discord.Embed(
                title="✅ Legacy Data Scan Complete",
                description="Scan of message history has finished.",
                color=discord.Color.green()
            )
            
            final_embed.add_field(
                name="Scan Results",
                value=(
                    f"📊 Channels Scanned: {channels_scanned}/{total_channels}\n"
                    f"💬 Messages Scanned: {messages_scanned}\n"
                    f"🔍 Rank Commands Found: {rank_commands_found}\n"
                    f"👥 Users Imported: {users_imported}\n"
                    f"❌ Errors: {errors}"
                ),
                inline=False
            )

            if users_imported > 0:
                example_data = list(found_data.values())[:3]  # Up to 3 examples
                example_text = ""
                
                for i, user_data in enumerate(example_data, 1):
                    example_text += f"User {i}: Level {user_data.get('level', 'N/A')}, XP {user_data.get('xp', 'N/A')}, Coins {user_data.get('coins', 'N/A')}\n"
                
                final_embed.add_field(
                    name="Example Data (Sample)",
                    value=example_text,
                    inline=False
                )
            
            await progress_message.edit(embed=final_embed)
            logger.info(f"Legacy data scan completed. Found {rank_commands_found} commands, imported {users_imported} users.")
            
        except asyncio.CancelledError:
            logger.info("Legacy data scan was cancelled")

            cancelled_embed = discord.Embed(
                title="🛑 Legacy Data Scan Cancelled",
                description="The scan was cancelled before completion.",
                color=discord.Color.red()
            )
            
            cancelled_embed.add_field(
                name="Partial Results",
                value=(
                    f"📊 Channels Scanned: {channels_scanned}/{total_channels}\n"
                    f"💬 Messages Scanned: {messages_scanned}\n"
                    f"🔍 Rank Commands Found: {rank_commands_found}\n"
                    f"👥 Users Imported: {users_imported}\n"
                    f"❌ Errors: {errors}"
                ),
                inline=False
            )
            
            await progress_message.edit(embed=cancelled_embed)
            
        except Exception as e:
            logger.error(f"Error during legacy data scan: {e}")

            error_embed = discord.Embed(
                title="❌ Legacy Data Scan Error",
                description=f"An error occurred during the scan: {str(e)}",
                color=discord.Color.red()
            )
            
            error_embed.add_field(
                name="Partial Results",
                value=(
                    f"📊 Channels Scanned: {channels_scanned}/{total_channels}\n"
                    f"💬 Messages Scanned: {messages_scanned}\n"
                    f"🔍 Rank Commands Found: {rank_commands_found}\n"
                    f"👥 Users Imported: {users_imported}\n"
                    f"❌ Errors: {errors + 1}"
                ),
                inline=False
            )
            
            await progress_message.edit(embed=error_embed)
        
        finally:

            self.is_scanning = False

async def setup(bot):
    """Add the legacy data finder cog to the bot."""
    await bot.add_cog(LegacyDataFinderCog(bot))
    logger.info("Legacy data finder cog loaded")