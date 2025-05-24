import os
import re
import discord
from discord import app_commands
from discord.ext import commands

from keep_alive import keep_alive
from discord_bot import RaidBot, cleanup_ended_raids
from raid import Raid
from database import ensure_db_table, save_raid_to_db, load_all_raids_from_db, load_templates
from utils import ephemeral_response
from ui.views import RaidManagementView, RaidTemplateSelectView

# Set up the bot
bot = RaidBot()

# Get the token from environment variables
TOKEN = os.environ.get("DISCORD_TOKEN", "")

# Keep the bot alive using Flask
keep_alive()

@app_commands.command(name="raid", description="Create a new raid.")
async def raid_slash(interaction: discord.Interaction, 
                    raid_name: str = "Unnamed Raid", 
                    raid_date: str = "2025-01-01 20:00", 
                    max_players: int = 10, 
                    allow_alts: bool = False, 
                    max_alts: int = 0, 
                    priority: bool = False, 
                    prioritylist: str = "", 
                    priority_hours: int = 6, 
                    description: str = "", 
                    required_sps: str = "", 
                    timezone: str = "Europe/Warsaw"):
    """Create a new raid."""
    channel_id = interaction.channel_id

    # Check if there's already a raid in this channel
    if channel_id in bot.raids:
        await ephemeral_response(interaction, "There is already a raid in this channel.")
        return

    # Parse the raid date
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Try different date formats
        for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]:
            try:
                parsed_dt = datetime.strptime(raid_date, fmt)
                break
            except ValueError:
                continue
        else:
            await ephemeral_response(interaction, "Invalid date format. Please use YYYY-MM-DD HH:MM.")
            return

        # Set timezone
        try:
            parsed_dt = parsed_dt.replace(tzinfo=ZoneInfo(timezone))
        except Exception as e:
            await ephemeral_response(interaction, f"Invalid timezone: {timezone}. Error: {e}")
            return
    except Exception as e:
        await ephemeral_response(interaction, f"Error parsing date: {e}")
        return

    # Create the raid
    raid_obj = Raid(
        channel_id=channel_id,
        creator=interaction.user,
        raid_name=raid_name,
        raid_datetime=parsed_dt,
        max_players=max_players,
        allow_alts=allow_alts,
        max_alts=max_alts,
        priority=priority,
        prioritylist=prioritylist,
        priority_hours=priority_hours,
        description=description,
        bot=bot
    )

    # Parse required SPs
    req_dict = {}
    req_original = {}
    if required_sps.strip():
        segments = required_sps.split(",")
        for seg in segments:
            seg = seg.strip()
            if "=" in seg:
                key, value_str = seg.split("=", 1)
                key = key.strip()
                value_str = value_str.strip()
                if not re.fullmatch(r"[A-Za-z]+_[A-Za-z]+\d+", key):
                    continue
                if not re.fullmatch(r"\d+", value_str):
                    continue
                cnt = int(value_str)
                if cnt < 0:
                    cnt = 0
                req_dict[key.upper()] = cnt
                req_original[key.upper()] = key

    raid_obj.required_sps = req_dict
    raid_obj.required_sps_original = req_original
    bot.raids[channel_id] = raid_obj
    save_raid_to_db(raid_obj)

    await ephemeral_response(interaction,
                         (f"Raid **{raid_name}** created on {parsed_dt.strftime('%Y-%m-%d %H:%M %Z')}.\n"
                          f"Description: {description}\n"
                          f"Max={max_players}, Alts={allow_alts}, max_alts={max_alts}.\n"
                          f"Priority={priority}, prioritylist='{prioritylist}', hours={priority_hours}.\n"
                          f"Required SPs={req_dict}."))

    channel = interaction.channel
    msg = await channel.send(content=raid_obj.format_raid_list(), view=RaidManagementView(raid_obj))
    raid_obj.raid_message = msg
    raid_obj._stored_message_id = msg.id
    await raid_obj.mention_on_creation()

@app_commands.command(name="raids_list", description="List all active raids.")
async def raids_list_slash(interaction: discord.Interaction):
    """List all active raids."""
    if not bot.raids:
        await ephemeral_response(interaction, "No active raids.")
        return

    lines = []
    for r in bot.raids.values():
        lines.append(
            f"<#{r.channel_id}>: {r.raid_name}, {r.count_main_alt()}/{r.max_players} slots filled, Priority={r.priority}, prioritylist='{r.prioritylist_str}', reqSP={r.required_sps}"
        )

    await ephemeral_response(interaction, "\n".join(lines))

@app_commands.command(name="raid_template", description="Use a raid template to assign roles.")
async def raid_template_slash(interaction: discord.Interaction):
    """Use a raid template to assign roles."""
    channel_id = interaction.channel_id
    if channel_id not in bot.raids:
        await ephemeral_response(interaction, "No active raid in this channel.")
        return

    raid_obj = bot.raids[channel_id]
    if interaction.user != raid_obj.creator:
        await ephemeral_response(interaction, "Only the raid creator can use raid templates.")
        return

    templates = load_templates()
    if not templates:
        await ephemeral_response(interaction, "No templates available.")
        return

    await ephemeral_response(interaction, "Select a raid template:", view=RaidTemplateSelectView(raid_obj, templates),
                         wait_for_user_action=True)

# Register the slash commands
bot.tree.add_command(raid_slash)
bot.tree.add_command(raids_list_slash)
bot.tree.add_command(raid_template_slash)

if __name__ == "__main__":
    ensure_db_table()
    load_all_raids_from_db(bot)
    bot.run(TOKEN)
