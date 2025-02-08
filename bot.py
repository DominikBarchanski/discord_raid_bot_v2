# bot.py
import discord
from discord.ext import commands, tasks
from config import TOKEN
from models import Raid
from db import load_all_raids_from_db
from views import RaidManagementView
from commands import raid_slash, raids_list_slash  # Upewnij się, że te komendy są importowane, żeby były zarejestrowane

class RaidBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="/", intents=intents)
        self.raids = {}
        self.auto_promote_reserves_loop = self.auto_promote_reserves

    async def setup_hook(self):
        self.tree.add_command(raid_slash)
        self.tree.add_command(raids_list_slash)
        await self.tree.sync()
        self.auto_promote_reserves_loop.start()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        load_all_raids_from_db(self)
        for raid in self.raids.values():
            channel = self.get_channel(raid.channel_id)
            if not channel:
                continue
            if hasattr(raid, "_stored_message_id") and raid._stored_message_id:
                try:
                    raid.raid_message = await channel.fetch_message(raid._stored_message_id)
                except Exception as e:
                    new_msg = await channel.send(content=raid.format_raid_list())
                    raid.raid_message = new_msg
                    raid._stored_message_id = new_msg.id
                    from db import save_raid_to_db
                    save_raid_to_db(raid)
            else:
                new_msg = await channel.send(content=raid.format_raid_list())
                raid.raid_message = new_msg
                raid._stored_message_id = new_msg.id
                from db import save_raid_to_db
                save_raid_to_db(raid)
            # Rejestracja persistent view
            self.add_view(RaidManagementView(raid))
        print("Bot is ready.")

    @tasks.loop(minutes=5)
    async def auto_promote_reserves(self):
        for raid in list(self.raids.values()):
            old = raid.count_main_alt()
            changed = raid.fill_free_slots_from_reserve()
            new = raid.count_main_alt()
            if changed or (new != old):
                if raid.raid_message:
                    try:
                        await raid.raid_message.edit(content=raid.format_raid_list())
                    except Exception:
                        pass

    @auto_promote_reserves.before_loop
    async def before_auto_promote(self):
        await self.wait_until_ready()

bot = RaidBot()

def run_bot():
    bot.run(TOKEN)
