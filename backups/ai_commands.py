"""AI Command module for Discord bot.
This module provides AI-based chat functionality for the bot.
"""
import re
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot')

# List of inappropriate words to filter (add more as needed)
INAPPROPRIATE_WORDS = [
    'porn', 'sex', 'nude', 'nsfw', 'dick', 'cock', 'pussy', 'fuck', 'shit', 
    'ass', 'boob', 'tits', 'penis', 'vagina', 'masturbate', 'cum', 'whore', 
    'bitch', 'slut', 'nazi', 'hitler', 'kill', 'murder', 'suicide', 'rape'
]

class AiCommandsCog(commands.Cog):
    """Cog containing AI command functionality."""
    
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
        self.bot = bot
        logger.info("AI Commands module initialized")
    
    def contains_inappropriate_content(self, text):
        """Check if the text contains inappropriate content.
        
        Args:
            text (str): The text to check
            
        Returns:
            bool: True if inappropriate content is found, False otherwise
        """
        text_lower = text.lower()
        
        # Check for exact words or substrings in words
        for word in INAPPROPRIATE_WORDS:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_lower):
                return True
            
        return False
        
    @app_commands.command(
        name="ai",
        description="Ask the AI assistant a question or request a response to your text"
    )
    async def ai_command(self, interaction: discord.Interaction, text: str):
        """AI command that responds to user text.
        
        Args:
            interaction: The Discord interaction
            text: The text to respond to
        """
        if self.contains_inappropriate_content(text):
            await interaction.response.send_message(
                "I can't respond to that message as it contains inappropriate content.",
                ephemeral=True
            )
            return
        
        # Log the clean user prompt
        logger.info(f"AI Command used by {interaction.user.name} ({interaction.user.id}): {text}")
        
        # For now we'll use a simple response system
        # This can be enhanced later with an actual AI API like OpenAI if desired
        
        # Set typing indicator to show the bot is "thinking"
        await interaction.response.defer(thinking=True)
        
        try:
            # Create a personalized response based on the user's message
            username = interaction.user.display_name
            
            if "hello" in text.lower() or "hi" in text.lower():
                response = f"Hello {username}! How can I assist you today?"
                
            elif "help" in text.lower():
                response = f"Hi {username}! I can help you with various things. Just ask me a question or tell me what you need!"
                
            elif any(word in text.lower() for word in ["what", "who", "where", "when", "how", "why"]):
                response = (
                    f"That's an interesting question, {username}! "
                    "I'm a simple AI assistant for this Discord server. "
                    "I can respond to your messages and try to be helpful. "
                    "My capabilities are currently limited, but I'll do my best to assist you!"
                )
                
            elif "thank" in text.lower():
                response = f"You're welcome, {username}! I'm happy to help anytime."
                
            else:
                responses = [
                    f"I see what you mean, {username}. That's an interesting perspective!",
                    f"Thanks for sharing that with me, {username}!",
                    f"I understand, {username}. Is there anything specific you'd like to know?",
                    f"That's fascinating, {username}. Would you like to tell me more?",
                    f"I appreciate your input, {username}. How can I assist you further?",
                    f"I hear you, {username}. What else would you like to discuss?",
                    f"That's a great point, {username}! I'd be happy to continue this conversation."
                ]
                import random
                response = random.choice(responses)
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.error(f"Error in AI command: {e}")
            await interaction.followup.send(
                "I encountered an error while processing your request. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    """Add the AI commands cog to the bot."""
    await bot.add_cog(AiCommandsCog(bot))
    logger.info("AI Commands cog added")