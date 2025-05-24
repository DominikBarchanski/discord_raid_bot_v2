import json
import os
from typing import Dict, Optional

def ensure_db_table():
    """Ensure the database file exists."""
    if not os.path.exists("raids.json"):
        with open("raids.json", "w") as f:
            json.dump([], f)

def save_raid_to_db(raid):
    """Save a raid to the database."""
    raids = []
    if os.path.exists("raids.json"):
        with open("raids.json", "r") as f:
            raids = json.load(f)
    
    # Find and update existing raid or add new one
    found = False
    for i, r in enumerate(raids):
        if r.get("channel_id") == raid.channel_id and r.get("guild_id") == raid.guild_id:
            raids[i] = raid.to_dict()
            found = True
            break
    
    if not found:
        raids.append(raid.to_dict())
    
    with open("raids.json", "w") as f:
        json.dump(raids, f)

def load_all_raids_from_db(bot):
    """Load all raids from the database."""
    if not os.path.exists("raids.json"):
        return
    
    with open("raids.json", "r") as f:
        raids = json.load(f)
    
    for raid_data in raids:
        try:
            from raid import Raid
            raid_obj = Raid.from_dict(raid_data, bot)
            bot.raids[raid_obj.channel_id] = raid_obj
        except Exception as e:
            print(f"Error loading raid: {e}")

def remove_raid_from_db(channel_id: int, guild_id: int):
    """Remove a raid from the database."""
    if not os.path.exists("raids.json"):
        return
    
    with open("raids.json", "r") as f:
        raids = json.load(f)
    
    raids = [r for r in raids if not (r.get("channel_id") == channel_id and r.get("guild_id") == guild_id)]
    
    with open("raids.json", "w") as f:
        json.dump(raids, f)

def load_templates() -> Dict[str, dict]:
    """Load raid templates from the templates.json file."""
    if not os.path.exists("templates.json"):
        return {}
    
    try:
        with open("templates.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading templates: {e}")
        return {}