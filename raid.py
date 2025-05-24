import discord
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo

from utils import safe_edit_message

class Participant:
    """Class representing a raid participant."""

    def __init__(self, user_id: int, sp: str, participant_type: str, 
                 reserve_for: Optional[str] = None, is_required_sp: bool = False, 
                 level_offset: int = 0, required_sp_list: Optional[List[str]] = None):
        self.user_id = user_id
        self.sp = sp
        self.participant_type = participant_type  # "main", "alt", "reserve"
        self.reserve_for = reserve_for  # For reserves, this is the SP they want to join as
        self.is_required_sp = is_required_sp  # Whether this participant fills a required SP slot
        self.level_offset = level_offset  # For sorting reserves
        self.required_sp_list = required_sp_list or []  # List of required SPs this participant can fill

class Raid:
    """Class representing a raid event."""

    def __init__(self, channel_id: int, creator: discord.Member, raid_name: str, 
                 raid_datetime: datetime, max_players: int, allow_alts: bool, 
                 max_alts: int, priority: bool, prioritylist: str, 
                 priority_hours: int, bot, description: str = ""):
        self.channel_id = channel_id
        self.guild_id = creator.guild.id
        self.creator = creator
        self.raid_name = raid_name
        self.raid_datetime = raid_datetime
        self.max_players = max_players
        self.allow_alts = allow_alts
        self.max_alts = max_alts
        self.priority = priority
        self.prioritylist = []
        self.prioritylist_str = prioritylist
        self.priority_hours = priority_hours
        self.description = description
        self.bot = bot

        # Parse prioritylist
        if prioritylist:
            for role_id_str in prioritylist.split(","):
                try:
                    role_id = int(role_id_str.strip())
                    self.prioritylist.append(role_id)
                except ValueError:
                    pass

        # Participants
        self.participants = {}  # user_id -> [Participant]
        self.raid_message = None
        self._stored_message_id = None
        self._tracked_messages = []

        # Required SPs
        self.required_sps = {}  # SP name -> count
        self.required_sps_original = {}  # SP name -> original name with case preserved

    def to_dict(self):
        """Convert raid to dictionary for storage."""
        participants_dict = {}
        for user_id, participants in self.participants.items():
            participants_dict[str(user_id)] = [
                {
                    "user_id": p.user_id,
                    "sp": p.sp,
                    "participant_type": p.participant_type,
                    "reserve_for": p.reserve_for,
                    "is_required_sp": p.is_required_sp,
                    "level_offset": p.level_offset,
                    "required_sp_list": p.required_sp_list
                }
                for p in participants
            ]

        return {
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "creator_id": self.creator.id,
            "raid_name": self.raid_name,
            "raid_datetime": self.raid_datetime.isoformat(),
            "max_players": self.max_players,
            "allow_alts": self.allow_alts,
            "max_alts": self.max_alts,
            "priority": self.priority,
            "prioritylist": self.prioritylist,
            "prioritylist_str": self.prioritylist_str,
            "priority_hours": self.priority_hours,
            "description": self.description,
            "participants": participants_dict,
            "message_id": self._stored_message_id,
            "required_sps": self.required_sps,
            "required_sps_original": self.required_sps_original
        }

    @classmethod
    def from_dict(cls, data: dict, bot):
        """Create a raid from a dictionary."""
        try:
            creator = bot.get_guild(data["guild_id"]).get_member(data["creator_id"])
            if not creator:
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
                prioritylist=data.get("prioritylist_str", ""),
                priority_hours=data.get("priority_hours", 6),
                bot=bot,
                description=data.get("description", "")
            )

            raid.prioritylist = data.get("prioritylist", [])
            raid._stored_message_id = data.get("message_id")
            raid.required_sps = data.get("required_sps", {})
            raid.required_sps_original = data.get("required_sps_original", {})

            # Load participants
            for user_id_str, participants_data in data.get("participants", {}).items():
                user_id = int(user_id_str)
                raid.participants[user_id] = []
                for p_data in participants_data:
                    participant = Participant(
                        user_id=p_data["user_id"],
                        sp=p_data["sp"],
                        participant_type=p_data["participant_type"],
                        reserve_for=p_data.get("reserve_for"),
                        is_required_sp=p_data.get("is_required_sp", False),
                        level_offset=p_data.get("level_offset", 0),
                        required_sp_list=p_data.get("required_sp_list", [])
                    )
                    raid.participants[user_id].append(participant)

            return raid
        except Exception as e:
            print(f"Error creating raid from dict: {e}")
            return None

    def track_bot_message(self, msg: discord.Message):
        """Track a bot message for later deletion."""
        self._tracked_messages.append(msg)

    def delete_all_tracked_messages(self):
        """Delete all tracked messages."""
        for msg in self._tracked_messages:
            try:
                asyncio.create_task(msg.delete())
            except Exception as e:
                print(f"Error deleting tracked message: {e}")
        self._tracked_messages = []

    def _has_role_by_name(self, user_id: int, role_name: str):
        """Check if a user has a role by name."""
        member = self.bot.get_guild(self.guild_id).get_member(user_id)
        return member and any(role.name == role_name for role in member.roles)

    def _has_role_id(self, user_id: int, role_id: int):
        """Check if a user has a role by ID."""
        member = self.bot.get_guild(self.guild_id).get_member(user_id)
        return member and any(role.id == role_id for role in member.roles)

    def is_marato(self, user_id: int):
        """Check if a user has the Marato role."""
        return self._has_role_by_name(user_id, "Marato")

    def is_in_priority(self, user_id: int, role_list: List[int]):
        """Check if a user has any of the priority roles."""
        return any(self._has_role_id(user_id, role_id) for role_id in role_list)

    def is_czlonek(self, user_id: int):
        """Check if a user has the Czlonek role."""
        return self._has_role_by_name(user_id, "Czlonek")

    def is_mlody_czlonek(self, user_id: int):
        """Check if a user has the Mlody Czlonek role."""
        return self._has_role_by_name(user_id, "Mlody Czlonek")

    def has_alt_role(self, user_id: int):
        """Check if a user has the Alt role."""
        return self._has_role_by_name(user_id, "Alt")

    def user_in_priority_roles(self, user_id: int):
        """Check if a user is in any priority roles."""
        if not self.priority:
            return False
        return self.is_in_priority(user_id, self.prioritylist)

    def count_main_alt(self):
        """Count the number of main and alt participants."""
        count = 0
        for participants in self.participants.values():
            for p in participants:
                if p.participant_type in ["main", "alt"]:
                    count += 1
        return count

    def is_full(self):
        """Check if the raid is full."""
        return self.count_main_alt() >= self.max_players

    def has_real_main(self, user_id: int):
        """Check if a user has a main participant."""
        return user_id in self.participants and any(p.participant_type == "main" for p in self.participants[user_id])

    def has_main_or_reserve_for_main(self, user_id: int):
        """Check if a user has a main participant or a reserve for main."""
        return (user_id in self.participants and 
                any(p.participant_type in ["main", "reserve"] for p in self.participants[user_id]))

    def count_alts_for_user(self, user_id: int):
        """Count the number of alts for a user."""
        if user_id not in self.participants:
            return 0
        return sum(1 for p in self.participants[user_id] if p.participant_type == "alt")

    def count_reserve(self):
        """Count the number of reserve participants."""
        count = 0
        for participants in self.participants.values():
            for p in participants:
                if p.participant_type == "reserve":
                    count += 1
        return count

    def get_unfilled_required_sps(self):
        """Get a list of unfilled required SPs."""
        result = []
        for sp_name, count in self.required_sps.items():
            if count > 0:
                result.append(sp_name)
        return result

    def any_required_sp_needed(self):
        """Check if any required SPs are needed."""
        return any(count > 0 for count in self.required_sps.values())

    def decrement_required_sp(self, sp_name: str):
        """Decrement the count of a required SP."""
        sp_name = sp_name.upper()
        if sp_name in self.required_sps and self.required_sps[sp_name] > 0:
            self.required_sps[sp_name] -= 1
            return True
        return False

    def increment_required_sp(self, sp_name: str):
        """Increment the count of a required SP."""
        sp_name = sp_name.upper()
        if sp_name in self.required_sps:
            self.required_sps[sp_name] += 1
            return True
        return False

    def add_participant(self, user: discord.Member, sp: str, desired_type: str, ignore_required: bool = True, level_offset: int = 0):
        """Add a participant to the raid."""
        user_id = user.id

        # Initialize user's participant list if not exists
        if user_id not in self.participants:
            self.participants[user_id] = []

        # Check if user already has this SP
        for p in self.participants[user_id]:
            if p.sp == sp and p.participant_type == desired_type:
                return False, f"You are already signed up as {sp} ({desired_type})."

        # Check if raid is full for main/alt
        if desired_type in ["main", "alt"] and self.is_full():
            # If raid is full, add as reserve instead
            desired_type = "reserve"

        # Check alt limits
        if desired_type == "alt":
            if not self.allow_alts:
                return False, "Alts are not allowed in this raid."

            if not self.has_real_main(user_id) and not self.has_alt_role(user_id):
                return False, "You need to sign up with a main character first or have the Alt role."

            if self.count_alts_for_user(user_id) >= self.max_alts:
                return False, f"You can only have {self.max_alts} alts in this raid."

        # Check if SP fills a required slot
        is_required_sp = False
        if not ignore_required and desired_type in ["main", "alt"]:
            sp_upper = sp.upper()
            for req_sp in list(self.required_sps.keys()):
                if sp_upper == req_sp and self.required_sps[req_sp] > 0:
                    is_required_sp = True
                    self.required_sps[req_sp] -= 1
                    break

        # Create participant
        participant = Participant(
            user_id=user_id,
            sp=sp,
            participant_type=desired_type,
            reserve_for=sp if desired_type == "reserve" else None,
            is_required_sp=is_required_sp,
            level_offset=level_offset
        )

        # Add participant
        self.participants[user_id].append(participant)

        # Return success message
        if desired_type == "reserve":
            return True, f"You have been added to the reserve list as {sp}."
        else:
            return True, f"You have been added to the raid as {sp} ({desired_type})."

    async def send_promotion_notification(self, user_id: int):
        """Send a notification to a user when they are promoted from reserve."""
        try:
            user = self.bot.get_user(user_id)
            if user:
                channel = self.bot.get_channel(self.channel_id)
                await user.send(f"You have been promoted from reserve to main in raid '{self.raid_name}' in {channel.mention}!")
        except Exception as e:
            print(f"Error sending promotion notification: {e}")

    def fill_free_slots_from_reserve(self):
        """Fill free slots from reserve participants."""
        if self.is_full():
            return False

        # Count available slots
        available_slots = self.max_players - self.count_main_alt()
        if available_slots <= 0:
            return False

        # Get all reserves
        all_reserves = []
        for user_id, participants in self.participants.items():
            for p in participants:
                if p.participant_type == "reserve":
                    all_reserves.append((user_id, p))

        if not all_reserves:
            return False

        # Define a function to check if a user can be promoted
        def can_promote(uid: int):
            # Check if user already has a main
            if any(p.participant_type == "main" for p in self.participants.get(uid, [])):
                return False
            return True

        # Sort reserves by priority, then by level offset
        all_reserves.sort(key=lambda x: (
            not self.user_in_priority_roles(x[0]),  # Priority users first
            x[1].level_offset,  # Then by level offset
            x[0]  # Then by user ID for consistent ordering
        ))

        promoted = False
        for user_id, reserve in all_reserves:
            if not can_promote(user_id):
                continue

            # Check if we need specific SPs
            if self.any_required_sp_needed():
                reserve_sp = reserve.sp.upper()
                if reserve_sp not in self.required_sps or self.required_sps[reserve_sp] <= 0:
                    continue

            # Remove from reserve
            self.participants[user_id].remove(reserve)

            # Add as main
            new_participant = Participant(
                user_id=user_id,
                sp=reserve.sp,
                participant_type="main",
                is_required_sp=True if self.any_required_sp_needed() else False
            )
            self.participants[user_id].append(new_participant)

            # Decrement required SP count if needed
            if self.any_required_sp_needed():
                self.decrement_required_sp(reserve.sp)

            # Send notification
            asyncio.create_task(self.send_promotion_notification(user_id))

            promoted = True
            available_slots -= 1
            if available_slots <= 0:
                break

        return promoted

    def force_promote_next_reserve(self):
        """Force promote the next reserve participant."""
        if self.is_full():
            return False, "Raid is already full."

        # Get all reserves
        all_reserves = []
        for user_id, participants in self.participants.items():
            for p in participants:
                if p.participant_type == "reserve":
                    all_reserves.append((user_id, p))

        if not all_reserves:
            return False, "No reserves to promote."

        # Sort reserves by priority, then by level offset
        all_reserves.sort(key=lambda x: (
            not self.user_in_priority_roles(x[0]),  # Priority users first
            x[1].level_offset,  # Then by level offset
            x[0]  # Then by user ID for consistent ordering
        ))

        # Promote first reserve
        user_id, reserve = all_reserves[0]

        # Remove from reserve
        self.participants[user_id].remove(reserve)

        # Add as main
        new_participant = Participant(
            user_id=user_id,
            sp=reserve.sp,
            participant_type="main"
        )
        self.participants[user_id].append(new_participant)

        # Send notification
        asyncio.create_task(self.send_promotion_notification(user_id))

        return True, f"Promoted <@{user_id}> from reserve to main as {reserve.sp}."

    def force_promote_reserve_user(self, user_id: int):
        """Force promote a specific reserve user."""
        if self.is_full():
            return False, "Raid is already full."

        if user_id not in self.participants:
            return False, "User not found in raid."

        # Find reserve participant
        reserve = None
        for p in self.participants[user_id]:
            if p.participant_type == "reserve":
                reserve = p
                break

        if not reserve:
            return False, "User is not in reserve."

        # Check if user already has a main
        if any(p.participant_type == "main" for p in self.participants[user_id]):
            return False, "User already has a main character in the raid."

        # Remove from reserve
        self.participants[user_id].remove(reserve)

        # Add as main
        new_participant = Participant(
            user_id=user_id,
            sp=reserve.sp,
            participant_type="main"
        )
        self.participants[user_id].append(new_participant)

        # Send notification
        asyncio.create_task(self.send_promotion_notification(user_id))

        return True, f"Promoted <@{user_id}> from reserve to main as {reserve.sp}."

    def remove_participant(self, user_id: int, remover: discord.Member = None):
        """Remove a participant from the raid."""
        if user_id not in self.participants:
            return False, "User not found in raid."

        # Check permissions if remover is not the user or creator
        if remover and remover.id != user_id and remover.id != self.creator.id:
            # Check if remover has manage messages permission
            if not remover.guild_permissions.manage_messages:
                return False, "You don't have permission to remove other users."

        # Get all participants for this user
        participants = self.participants[user_id]

        # Check for required SPs
        for p in participants:
            if p.is_required_sp and p.participant_type in ["main", "alt"]:
                # Increment the required SP count
                sp_upper = p.sp.upper()
                for req_sp in self.required_sps:
                    if sp_upper == req_sp:
                        self.required_sps[req_sp] += 1
                        break

        # Remove all participants for this user
        del self.participants[user_id]

        # Fill free slots from reserve
        self.fill_free_slots_from_reserve()

        return True, f"Removed <@{user_id}> from the raid."

    def remove_alt_by_sp(self, user_id: int, sp: str):
        """Remove a specific alt by SP."""
        if user_id not in self.participants:
            return False, "User not found in raid."

        # Find the alt participant
        alt = None
        for p in self.participants[user_id]:
            if p.participant_type == "alt" and p.sp == sp:
                alt = p
                break

        if not alt:
            return False, f"Alt {sp} not found."

        # Check for required SP
        if alt.is_required_sp:
            # Increment the required SP count
            sp_upper = alt.sp.upper()
            for req_sp in self.required_sps:
                if sp_upper == req_sp:
                    self.required_sps[req_sp] += 1
                    break

        # Remove the alt
        self.participants[user_id].remove(alt)

        # If no participants left for this user, remove the user
        if not self.participants[user_id]:
            del self.participants[user_id]

        # Fill free slots from reserve
        self.fill_free_slots_from_reserve()

        return True, f"Removed alt {sp} from the raid."

    async def send_notification_if_needed(self):
        """Send a notification if the raid is about to start."""
        now = datetime.now(ZoneInfo("UTC"))
        raid_time = self.raid_datetime.astimezone(ZoneInfo("UTC"))

        # Check if raid is within 15 minutes
        if raid_time - now <= timedelta(minutes=15) and raid_time > now:
            await self.notify_participants()
            return True

        # Check if raid is within 1 hour
        if raid_time - now <= timedelta(hours=1) and raid_time > now:
            await self.notify_participants()
            return True

        return False

    async def send_final_reminder(self):
        """Send a final reminder when the raid starts."""
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            mentions = []
            for user_id in self.participants:
                mentions.append(f"<@{user_id}>")

            if mentions:
                await channel.send(f"**{self.raid_name}** is starting now! {' '.join(mentions)}")

    async def notify_participants(self):
        """Notify all participants about the raid."""
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            mentions = []
            for user_id in self.participants:
                mentions.append(f"<@{user_id}>")

            if mentions:
                time_until = self.raid_datetime - datetime.now(self.raid_datetime.tzinfo)
                hours, remainder = divmod(time_until.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                time_str = ""
                if hours > 0:
                    time_str += f"{hours} hour{'s' if hours != 1 else ''} "
                if minutes > 0:
                    time_str += f"{minutes} minute{'s' if minutes != 1 else ''}"

                await channel.send(f"**{self.raid_name}** is starting in {time_str}! {' '.join(mentions)}")

    def emojify_text(self, text: str):
        """Convert text to emoji format."""
        def rep(m):
            char = m.group(1).lower()
            return f":regional_indicator_{char}:" if char.isalpha() else char

        return re.sub(r"([a-zA-Z])", rep, text)

    def format_raid_list(self):
        """Format the raid list for display."""
        lines = []

        # Raid header
        raid_time_str = self.raid_datetime.strftime("%Y-%m-%d %H:%M %Z")
        lines.append(f"**{self.emojify_text(self.raid_name)}** - {raid_time_str}")

        if self.description:
            lines.append(f"*{self.description}*")

        lines.append(f"Created by <@{self.creator.id}>")
        lines.append(f"Max players: {self.count_main_alt()}/{self.max_players}")

        if self.priority:
            priority_roles = []
            for role_id in self.prioritylist:
                role = discord.utils.get(self.creator.guild.roles, id=role_id)
                if role:
                    priority_roles.append(role.name)

            if priority_roles:
                lines.append(f"Priority for: {', '.join(priority_roles)} (first {self.priority_hours} hours)")

        if self.required_sps:
            req_sp_strs = []
            for sp_name, count in self.required_sps.items():
                if count > 0:
                    original_name = self.required_sps_original.get(sp_name, sp_name)
                    req_sp_strs.append(f"{original_name}={count}")

            if req_sp_strs:
                lines.append(f"Required SPs: {', '.join(req_sp_strs)}")

        # Main participants
        lines.append("\n**Main participants:**")
        main_count = 0
        for user_id, participants in self.participants.items():
            for p in participants:
                if p.participant_type == "main":
                    main_count += 1
                    lines.append(f"{main_count}. <@{user_id}> - {p.sp}")

        # Fill remaining slots with placeholders
        for i in range(main_count, self.max_players):
            lines.append(f"{i+1}. *Empty slot*")

        # Alt participants
        if self.allow_alts:
            alt_lines = []
            for user_id, participants in self.participants.items():
                user_alts = [p for p in participants if p.participant_type == "alt"]
                if user_alts:
                    alt_lines.append(f"<@{user_id}>: {', '.join(p.sp for p in user_alts)}")

            if alt_lines:
                lines.append("\n**Alts:**")
                lines.extend(alt_lines)

        # Reserve participants
        reserve_lines = []
        for user_id, participants in self.participants.items():
            user_reserves = [p for p in participants if p.participant_type == "reserve"]
            if user_reserves:
                reserve_lines.append(f"<@{user_id}>: {', '.join(p.sp for p in user_reserves)}")

        if reserve_lines:
            lines.append("\n**Reserve list:**")
            lines.extend(reserve_lines)

        return "\n".join(lines)

    async def mention_on_creation(self):
        """Mention users when the raid is created."""
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        # Get all members with Czlonek or Mlody Czlonek roles
        members = []
        for member in channel.guild.members:
            if self.is_czlonek(member.id) or self.is_mlody_czlonek(member.id):
                members.append(member)

        if not members:
            return

        # Split into chunks to avoid Discord's mention limit
        chunk_size = 20
        for i in range(0, len(members), chunk_size):
            chunk = members[i:i+chunk_size]
            mentions = " ".join(member.mention for member in chunk)
            await channel.send(f"New raid created: **{self.raid_name}** on {self.raid_datetime.strftime('%Y-%m-%d %H:%M %Z')}! {mentions}")
