# models.py
import json
from datetime import datetime
from typing import Optional, List, Dict
from config import DATETIME_FORMAT_1, DATETIME_FORMAT_2
from db import save_raid_to_db

class Participant:
    """Stores a single user's sign-up data."""
    def __init__(self, user_id: int, sp: str, participant_type: str,
                 reserve_for: Optional[str] = None, is_required_sp: bool = False):
        self.user_id = user_id
        self.sp = sp
        self.participant_type = participant_type
        self.reserve_for = reserve_for
        self.is_required_sp = is_required_sp

class Raid:
    def __init__(self, channel_id: int, creator, raid_name: str,
                 raid_datetime: datetime, max_players: int, allow_alts: bool,
                 max_alts: int, priority: bool, prioritylist: str, priority_hours: int,
                 bot):
        self.channel_id = channel_id
        self.creator = creator
        self.guild = creator.guild
        self.raid_name = raid_name
        self.raid_datetime = raid_datetime
        self.max_players = max_players
        self.allow_alts = allow_alts
        self.max_alts = max_alts
        self.priority = priority
        self.prioritylist_str = prioritylist
        self.priority_hours = priority_hours
        self.priority_roles: List[int] = []
        if self.priority and prioritylist.strip():
            for nm in prioritylist.split(","):
                nm = nm.strip()
                if nm:
                    role_obj = self.guild.get_role_by_name(nm) or None  # Możesz użyć innej metody, np. discord.utils.get
                    if role_obj:
                        self.priority_roles.append(role_obj.id)
        self.bot = bot
        self.participants: List[Participant] = []
        self.raid_message = None
        self.tracked_messages: List[int] = []
        self.required_sps: Dict[str, int] = {}
        self.emoji_map = {}  # Ustawiane w głównym kodzie, np. przez iterację po emoji z serwera
        self._stored_message_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild.id,
            "channel_id": self.channel_id,
            "creator_id": self.creator.id,
            "raid_name": self.raid_name,
            "raid_datetime": self.raid_datetime.isoformat(),
            "max_players": self.max_players,
            "allow_alts": self.allow_alts,
            "max_alts": self.max_alts,
            "priority": self.priority,
            "prioritylist_str": self.prioritylist_str,
            "priority_hours": self.priority_hours,
            "participants": [vars(p) for p in self.participants],
            "required_sps": self.required_sps,
            "raid_message_id": self.raid_message.id if self.raid_message else self._stored_message_id
        }

    @classmethod
    def from_dict(cls, data: dict, bot) -> Optional["Raid"]:
        guild = bot.get_guild(data["guild_id"])
        if guild is None:
            return None
        creator = guild.get_member(data["creator_id"])
        if creator is None:
            return None
        raid_datetime = datetime.fromisoformat(data["raid_datetime"])
        raid = cls(
            channel_id=data["channel_id"],
            creator=creator,
            raid_name=data["raid_name"],
            raid_datetime=raid_datetime,
            max_players=data["max_players"],
            allow_alts=data["allow_alts"],
            max_alts=data["max_alts"],
            priority=data["priority"],
            prioritylist=data["prioritylist_str"],
            priority_hours=data["priority_hours"],
            bot=bot
        )
        raid.participants = [Participant(**p) for p in data["participants"]]
        raid.required_sps = data["required_sps"]
        raid._stored_message_id = data.get("raid_message_id")
        return raid
