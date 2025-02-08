# commands.py
import re
from datetime import datetime
from discord import app_commands
from config import DATETIME_FORMAT_1, DATETIME_FORMAT_2
from models import Raid
from db import save_raid_to_db, remove_raid_from_db
from views import RaidManagementView

@app_commands.command(name="raid", description="Create a raid in this channel.")
@app_commands.describe(
    raid_name="Name of the raid",
    raid_date="Date/time (HH:MM YYYY-MM-DD or YYYY-MM-DD HH:MM)",
    max_players="Max combined MAIN+ALT",
    allow_alts="Allow user alt sign-ups?",
    max_alts="Max ALTs per user",
    priority="If True, only roles from prioritylist can sign up as MAIN until time_left <= priority_hours",
    prioritylist="Comma-separated list of priority roles, e.g. 'Role1, Role2'",
    priority_hours="Time window (hours) for forced priority. Default = 6",
    required_sps="Comma-separated list, e.g. 'MAG_SP10=2, Arch_SP4=1'"
)
async def raid_slash(
    interaction,
    raid_name: str = "Unnamed Raid",
    raid_date: str = "2025-01-01 20:00",
    max_players: int = 10,
    allow_alts: bool = False,
    max_alts: int = 0,
    priority: bool = False,
    prioritylist: str = "",
    priority_hours: int = 6,
    required_sps: str = ""
):
    channel_id = interaction.channel_id
    if channel_id in interaction.client.raids:
        await interaction.response.send_message("A raid is already active in this channel!", ephemeral=True, delete_after=5)
        return
    parsed_dt = None
    for fmt in (DATETIME_FORMAT_1, DATETIME_FORMAT_2):
        try:
            parsed_dt = datetime.strptime(raid_date, fmt)
            break
        except:
            pass
    if not parsed_dt:
        await interaction.response.send_message("Could not parse date/time. Use a valid format.", ephemeral=True, delete_after=10)
        return
    raid = Raid(
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
        bot=interaction.client
    )
    # Parse and validate required_sps
    req_dict = {}
    if required_sps.strip():
        segments = required_sps.split(",")
        for seg in segments:
            seg = seg.strip()
            if "=" in seg:
                key, value_str = seg.split("=", 1)
                key = key.strip()
                value_str = value_str.strip()
                if not re.fullmatch(r"[A-Z]+_[A-Z]+\d+", key):
                    continue
                if not re.fullmatch(r"\d+", value_str):
                    continue
                cnt = int(value_str)
                req_dict[key] = cnt
    raid.required_sps = req_dict
    interaction.client.raids[channel_id] = raid
    save_raid_to_db(raid)
    await interaction.response.send_message(
        content=(f"Raid **{raid_name}** created on {parsed_dt.strftime('%Y-%m-%d %H:%M')}.\n"
                 f"Max={max_players}, Alts={allow_alts}, max_alts={max_alts}.\n"
                 f"priority={priority}, prioritylist='{prioritylist}', hours={priority_hours}.\n"
                 f"RequiredSps={req_dict}."),
        ephemeral=True, delete_after=5
    )
    channel = interaction.channel
    msg = await channel.send(content=raid.format_raid_list(), view=RaidManagementView(raid))
    raid.raid_message = msg
    raid._stored_message_id = msg.id
    await raid.mention_on_creation()

@app_commands.command(name="raids_list", description="List all active raids.")
async def raids_list_slash(interaction):
    if not interaction.client.raids:
        await interaction.response.send_message("No active raids.", ephemeral=True, delete_after=5)
        return
    lines = []
    for r in interaction.client.raids.values():
        lines.append(f"<#{r.channel_id}>: {r.raid_name}, {r.count_main_alt()}/{r.max_players} slots filled, "
                     f"priority={r.priority}, prioritylist='{r.prioritylist_str}', reqSP={r.required_sps}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True, delete_after=10)
