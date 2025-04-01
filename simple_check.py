import os
import discord
from dotenv import load_dotenv
import asyncio

async def main():
    load_dotenv()
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    print(f"Token available: {bool(TOKEN)}")
    
    if not TOKEN:
        print("No Discord token found! Please set the DISCORD_TOKEN environment variable.")
        return
    
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"Bot connected as {client.user.name} (ID: {client.user.id})")
        print(f"Connected to {len(client.guilds)} guilds")
        await client.close()
    
    try:
        print("Attempting to connect to Discord...")
        await client.start(TOKEN)
    except discord.errors.LoginFailure as e:
        print(f"Login failure: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()
        print("Connection closed")

if __name__ == "__main__":
    asyncio.run(main())