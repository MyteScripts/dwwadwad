import discord
from discord import app_commands
from discord.ext import commands
import json
import datetime
import logging
import os

logger = logging.getLogger(__name__)

class ReportingCog(commands.Cog):
    """Cog for handling user reports"""
    
    def __init__(self, bot):
        self.bot = bot
        self.report_channel_id = 1356731160704716991  # Channel ID for report logs
        self.reports_file = 'data/reports.json'
        self.reports = self.load_reports()
        
    def load_reports(self):
        """Load reports from JSON file"""
        if not os.path.exists('data'):
            os.makedirs('data')
            
        if os.path.exists(self.reports_file):
            try:
                with open(self.reports_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading reports file: {e}")
                return {'reports': []}
        else:
            return {'reports': []}
        
    def save_reports(self):
        """Save reports to JSON file"""
        try:
            with open(self.reports_file, 'w') as f:
                json.dump(self.reports, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving reports file: {e}")
            
    @app_commands.command(
        name="report",
        description="🚨 Report a user for breaking rules or inappropriate behavior"
    )
    @app_commands.describe(
        user="The user to report",
        reason="The reason for the report (be specific and include details)"
    )
    async def report_command(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        """Report a user for inappropriate behavior"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create the report data
            report_data = {
                'report_id': len(self.reports['reports']) + 1,
                'reporter_id': str(interaction.user.id),
                'reporter_name': interaction.user.display_name,
                'reported_user_id': str(user.id),
                'reported_user_name': user.display_name,
                'reason': reason,
                'server_id': str(interaction.guild.id),
                'server_name': interaction.guild.name,
                'timestamp': datetime.datetime.now().isoformat(),
                'status': 'pending'  # pending, reviewed, resolved, rejected
            }
            
            # Add to reports list
            self.reports['reports'].append(report_data)
            self.save_reports()
            
            # Send confirmation to the user
            await interaction.followup.send(
                f"✅ Thank you for your report about {user.mention}. Your report has been submitted to the moderation team.",
                ephemeral=True
            )
            
            # Create embed for report log
            embed = discord.Embed(
                title=f"🚨 New User Report #{report_data['report_id']}",
                description=f"**Reason:** {reason}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(
                name="Reported User",
                value=f"{user.mention} ({user.name}, ID: {user.id})",
                inline=False
            )
            
            embed.add_field(
                name="Reported By",
                value=f"{interaction.user.mention} ({interaction.user.name}, ID: {interaction.user.id})",
                inline=False
            )
            
            embed.set_footer(text=f"Server: {interaction.guild.name}")
            
            # Get the report channel and send the log
            report_channel = self.bot.get_channel(self.report_channel_id)
            if report_channel:
                try:
                    await report_channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Could not send report to channel: {e}")
                    await interaction.followup.send(
                        "⚠️ Your report was saved but could not be sent to the moderation team. A staff member will review it later.",
                        ephemeral=True
                    )
            else:
                logger.error(f"Could not find report channel with ID {self.report_channel_id}")
                
        except Exception as e:
            logger.error(f"Error in report command: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while submitting your report. Please try again later or contact a staff member directly.",
                ephemeral=True
            )

async def setup(bot):
    """Add the reporting cog to the bot"""
    await bot.add_cog(ReportingCog(bot))
    print("Reporting system loaded!")