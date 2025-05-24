import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
from typing import Dict

from database import save_raid_to_db, remove_raid_from_db

class RaidBot(commands.Bot):
    """Discord bot for managing raids."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.raids = {}
        self.auto_promote_task = None
    
    async def setup_hook(self):
        """Set up the bot's hooks and tasks."""
        self.auto_promote_task = self.auto_promote_reserves.start()
        
        # Sync commands with Discord
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state updates."""
        # This is a placeholder for any voice state update handling
        # The original code didn't have any implementation here
        pass
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author.bot:
            return
        
        # Process commands
        await self.process_commands(message)
        
        # Check if message is in a raid channel
        if message.channel.id in self.raids:
            raid = self.raids[message.channel.id]
            if raid.raid_message and message.channel.last_message_id == message.id:
                try:
                    await raid.raid_message.delete()
                    raid.raid_message = await message.channel.send(content=raid.format_raid_list())
                except Exception as e:
                    print(f"Error updating raid message: {e}")
    
    async def on_ready(self):
        """Handle bot ready event."""
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        
        # Start cleanup task
        if not hasattr(self, "cleanup_task") or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(cleanup_ended_raids(self))
        
        # Update raid messages
        for raid in self.raids.values():
            try:
                channel = self.get_channel(raid.channel_id)
                if not channel:
                    continue
                
                if raid._stored_message_id:
                    try:
                        message = await channel.fetch_message(raid._stored_message_id)
                        raid.raid_message = message
                        from ui.views import RaidManagementView
                        await message.edit(content=raid.format_raid_list(), view=RaidManagementView(raid))
                    except Exception as e:
                        print(f"Error fetching message: {e}")
                        message = await channel.send(content=raid.format_raid_list())
                        raid.raid_message = message
                        raid._stored_message_id = message.id
                else:
                    message = await channel.send(content=raid.format_raid_list())
                    raid.raid_message = message
                    raid._stored_message_id = message.id
                
                save_raid_to_db(raid)
            except Exception as e:
                print(f"Error updating raid message: {e}")
    
    @tasks.loop(minutes=5.0)
    async def auto_promote_reserves(self):
        """Automatically promote reserves to main participants."""
        await self.before_auto_promote()
        
        for raid in list(self.raids.values()):
            try:
                if raid.is_full():
                    continue
                
                # Fill free slots from reserve
                promoted = raid.fill_free_slots_from_reserve()
                
                if promoted and raid.raid_message:
                    from ui.views import RaidManagementView
                    await raid.raid_message.edit(content=raid.format_raid_list(), view=RaidManagementView(raid))
                    save_raid_to_db(raid)
            except Exception as e:
                print(f"Error in auto_promote_reserves: {e}")
    
    async def before_auto_promote(self):
        """Wait until the bot is ready before auto-promoting."""
        await self.wait_until_ready()

async def cleanup_ended_raids(bot: RaidBot):
    """Clean up ended raids periodically."""
    while True:
        try:
            now = datetime.now()
            to_remove = []
            
            for channel_id, raid in bot.raids.items():
                if raid.raid_datetime < now - timedelta(hours=2):
                    to_remove.append(channel_id)
            
            for channel_id in to_remove:
                raid = bot.raids.pop(channel_id)
                remove_raid_from_db(channel_id, raid.guild_id)
                print(f"Removed ended raid: {raid.raid_name}")
        except Exception as e:
            print(f"Error in cleanup_ended_raids: {e}")
        
        await asyncio.sleep(3600)  # Check every hour