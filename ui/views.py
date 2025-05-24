import discord
from discord.ui import View, Button
from typing import List, Optional, Dict

from utils import ephemeral_response, safe_edit_message
from ui.buttons import CloseButton, NotifyParticipantsButton, SendListButton
from ui.selects import ClassDropdown, SPDropdown, RoleSelectMenu, RaidTemplateSelectDropdown, PromoteReserveDropdown, RequiredSPDropdown

class ClassSelectionView(View):
    """View for selecting a class."""
    
    def __init__(self, raid, participant_type: str):
        super().__init__(timeout=None)
        self.raid = raid
        self.participant_type = participant_type
        self.add_item(ClassDropdown(raid, participant_type))
        self.add_item(CloseButton())

class SPSelectionView(View):
    """View for selecting a specialization."""
    
    def __init__(self, raid, chosen_class: str, participant_type: str, chosen_sps=None):
        super().__init__(timeout=None)
        self.raid = raid
        self.chosen_class = chosen_class
        self.participant_type = participant_type
        self.chosen_sps = chosen_sps or []
        
        # Add dropdown with SP selection
        self.add_item(SPDropdown(raid, chosen_class, self.chosen_sps))
        self.add_item(CloseButton())
    
    @discord.ui.button(label="Sign Up", style=discord.ButtonStyle.green)
    async def sign_up(self, interaction: discord.Interaction, button: Button):
        """Handle sign up button click."""
        if not self.chosen_sps:
            # Use ephemeral message
            await ephemeral_response(interaction, "Please select at least one SP before signing up.")
            return
        
        user = interaction.user
        # Detect level_offset based on roles
        level_offset = 0
        # If user has "c90" role, set +90
        if any(r.name == "c90" for r in user.roles):
            level_offset = 90
        # If user has "c1-89" role, set -90
        elif any(r.name == "c1-89" for r in user.roles):
            level_offset = -90
        # Handle case where user has neither role
        else:
            # Use ephemeral message
            await ephemeral_response(interaction, "Nie posiadasz roli c90 ani c1-89. Wybierz role #💬-role")
            return
        
        sp_string = ", ".join(self.chosen_sps)
        success = self.raid.add_participant(
            user,
            sp_string,
            self.participant_type,
            ignore_required=True,
            level_offset=level_offset
        )
        
        if success and self.raid.raid_message:
            await safe_edit_message(self.raid.raid_message, content=self.raid.format_raid_list())
            try:
                # Use ephemeral message (auto-delete)
                await interaction.response.edit_message(delete_after=5)
            except discord.HTTPException:
                pass
        else:
            # Use ephemeral message
            await ephemeral_response(interaction, "Sign-up failed.")
    
    @discord.ui.button(label="Add Another SP", style=discord.ButtonStyle.blurple)
    async def add_sp(self, interaction: discord.Interaction, button: Button):
        """Handle add another SP button click."""
        # Use ephemeral message
        await interaction.response.edit_message(
            content="Pick another SP:",
            view=SPSelectionView(self.raid, self.chosen_class, self.participant_type, self.chosen_sps)
        )
    
    @discord.ui.button(label="Clear Selection", style=discord.ButtonStyle.red)
    async def clear_sp(self, interaction: discord.Interaction, button: Button):
        """Handle clear selection button click."""
        self.chosen_sps.clear()
        # Use ephemeral message
        await interaction.response.edit_message(
            content="SP cleared. Pick again:",
            view=SPSelectionView(self.raid, self.chosen_class, self.participant_type)
        )
    
    @discord.ui.button(label="Change Class", style=discord.ButtonStyle.secondary)
    async def change_class(self, interaction: discord.Interaction, button: Button):
        """Handle change class button click."""
        # Use ephemeral message
        await interaction.response.edit_message(
            content="Select class again:",
            view=ClassSelectionView(self.raid, self.participant_type)
        )

class RemoveAltView(View):
    """View for removing an alt."""
    
    def __init__(self, raid, user_id: int):
        super().__init__(timeout=30)
        self.raid = raid
        self.user_id = user_id
        self.mapping = {}
        alt_entries = [p for p in raid.participants if p.user_id == user_id and (
            p.participant_type == "ALT" or (p.participant_type == "RESERVE" and p.reserve_for == "ALT")
        )]
        for i, p in enumerate(alt_entries):
            custom_id = f"remove_alt_{i}"
            self.mapping[custom_id] = p.sp
            btn = Button(label=f"Remove {p.sp}", style=discord.ButtonStyle.danger, custom_id=custom_id)
            btn.callback = self.generate_callback(custom_id)
            self.add_item(btn)
        self.add_item(CloseButton())
    
    def generate_callback(self, custom_id: str):
        """Generate callback for remove alt button."""
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.raid.creator and interaction.user.id != self.user_id:
                # Use ephemeral message
                await ephemeral_response(interaction, "Only the raid leader or the owner can remove roles.")
                return
            
            sp_to_remove = self.mapping.get(custom_id)
            if sp_to_remove is None:
                # Use ephemeral message
                await ephemeral_response(interaction, "Role not found.")
                return
            
            removed = self.raid.remove_alt_by_sp(self.user_id, sp_to_remove)
            if removed:
                # Use ephemeral message
                await ephemeral_response(interaction, "Role removed.")
                await safe_edit_message(
                    self.raid.raid_message,
                    content=self.raid.format_raid_list(),
                    view=RaidManagementView(self.raid)
                )
            else:
                # Use ephemeral message
                await ephemeral_response(interaction, "Failed to remove role.")
        
        return callback

class RemoveUserView(View):
    """View for removing a user."""
    
    def __init__(self, raid, remover: discord.Member):
        super().__init__(timeout=30)
        self.raid = raid
        self.remover = remover
        for i, p in enumerate(raid.participants):
            mem = raid.guild.get_member(p.user_id)
            disp_name = mem.display_name if mem else f"User-{p.user_id}"
            t = p.participant_type
            if t == "RESERVE":
                t += f"({p.reserve_for})"
            label_txt = f"{disp_name} [{t}] {p.sp}"
            btn = Button(label=label_txt, style=discord.ButtonStyle.danger, custom_id=f"remove_user_{p.user_id}_{i}")
            self.add_item(btn)
        self.add_item(CloseButton())
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if interaction is valid."""
        if interaction.user != self.raid.creator:
            # Use ephemeral message
            await ephemeral_response(interaction, "Only the raid leader can remove others.")
            return False
        
        cid = interaction.data.get("custom_id")
        if cid and cid.startswith("remove_user_"):
            parts = cid.split("_")
            if len(parts) >= 3:
                try:
                    user_id = int(parts[2])
                except ValueError:
                    return False
                
                await self.raid.remove_participant(user_id, remover=self.remover)
                # Use ephemeral message
                await ephemeral_response(interaction, "User removed.")
                return True
        
        return False

class PromoteReserveDropdownView(View):
    """View for promoting a user from reserve."""
    
    def __init__(self, raid):
        super().__init__(timeout=30)
        self.raid = raid
        self.add_item(PromoteReserveDropdown(raid))
        self.add_item(CloseButton())

class RequiredSPDropdownView(View):
    """View for selecting a required SP."""
    
    def __init__(self, raid):
        super().__init__(timeout=30)
        self.raid = raid
        self.add_item(RequiredSPDropdown(raid))
        self.add_item(CloseButton())

class RaidTemplateSelectView(View):
    """View for selecting a raid template."""
    
    def __init__(self, raid, templates: Dict[str, dict]):
        super().__init__(timeout=60)
        self.raid = raid
        self.templates = templates
        options = [discord.SelectOption(label=name, value=name) for name in templates.keys()]
        self.add_item(RaidTemplateSelectDropdown(options))
        self.add_item(CloseButton())

class TemplateOrganizerView(View):
    """View for organizing a template."""
    
    def __init__(self, raid, template_name: str, template_data: dict):
        super().__init__(timeout=300)
        self.raid = raid
        self.template_name = template_name
        self.template_data = template_data
        self.assignments = {}
        self.selected_map = None
        self.selected_roles = []
        
        # Add map buttons if available
        if "maps" in self.template_data:
            maps = list(self.template_data["maps"].keys())
            self.selected_map = maps[0]
            for map_name in maps:
                self.add_item(Button(label=map_name, style=discord.ButtonStyle.primary, custom_id=f"map_{map_name}"))
        
        # Add role buttons
        self.update_role_buttons()
        
        # Add send list button
        self.add_item(SendListButton(self))
        self.add_item(CloseButton())
    
    def update_role_buttons(self):
        """Update role buttons based on selected map."""
        # Remove existing role buttons
        items_to_remove = [item for item in self.children if hasattr(item, "custom_id") and item.custom_id.startswith("role_")]
        for item in items_to_remove:
            self.remove_item(item)
        
        # Add new role buttons
        if self.selected_map and "maps" in self.template_data:
            roles = list(self.template_data["maps"][self.selected_map].keys())
        elif "placeholders" in self.template_data:
            roles = list(self.template_data["placeholders"].keys())
        else:
            roles = []
        
        for role in roles:
            btn = Button(
                label=role,
                style=discord.ButtonStyle.success if role in self.selected_roles else discord.ButtonStyle.secondary,
                custom_id=f"role_{role}"
            )
            self.add_item(btn)
    
    def get_preview(self) -> str:
        """Get preview of template assignments."""
        preview = f"Template **{self.template_name}** assignments preview (leader view):\n"
        for role, data in self.assignments.items():
            preview += f"**{role}**: {data['display']}\n"
        return preview
    
    async def update_preview(self, interaction: discord.Interaction):
        """Update preview of template assignments."""
        content = self.get_preview()
        # Use ephemeral message
        await interaction.response.edit_message(content=content, view=self)

class RaidManagementView(View):
    """View for managing a raid."""
    
    def __init__(self, raid):
        super().__init__(timeout=None)
        self.raid = raid
    
    @discord.ui.button(label="Join (Main)", style=discord.ButtonStyle.green, row=0, custom_id="raidmgmt_join_main")
    async def join_main(self, interaction: discord.Interaction, button: Button):
        """Handle join main button click."""
        try:
            if not interaction.response.is_done():
                # Use ephemeral message
                await interaction.response.send_message(
                    "Select class for MAIN:",
                    ephemeral=True,
                    view=ClassSelectionView(self.raid, "MAIN")
                )
            else:
                # Use ephemeral message
                await interaction.followup.send(
                    "Select class for MAIN:",
                    ephemeral=True,
                    view=ClassSelectionView(self.raid, "MAIN")
                )
        except discord.errors.NotFound:
            # Use ephemeral message
            await interaction.followup.send(
                "Select class for MAIN:",
                ephemeral=True,
                view=ClassSelectionView(self.raid, "MAIN")
            )
    
    @discord.ui.button(label="Sign Up (Alt)", style=discord.ButtonStyle.green, row=0, custom_id="raidmgmt_join_alt")
    async def join_alt(self, interaction: discord.Interaction, button: Button):
        """Handle join alt button click."""
        # Use ephemeral message
        await interaction.response.send_message(
            "Select class for ALT:",
            ephemeral=True,
            view=ClassSelectionView(self.raid, "ALT")
        )
    
    @discord.ui.button(label="Sign Out (All)", style=discord.ButtonStyle.red, row=0, custom_id="raidmgmt_sign_out_all")
    async def sign_out_all(self, interaction: discord.Interaction, button: Button):
        """Handle sign out all button click."""
        uid = interaction.user.id
        removed = await self.raid.remove_participant(uid, remover=interaction.user)
        if removed and self.raid.raid_message:
            await safe_edit_message(self.raid.raid_message, content=self.raid.format_raid_list())
        
        msg = "You were removed from the raid." if removed else "You're not in this raid."
        # Use ephemeral message
        await ephemeral_response(interaction, msg)
    
    @discord.ui.button(label="Remove Single Alt", style=discord.ButtonStyle.gray, row=1, custom_id="raidmgmt_remove_single_alt")
    async def remove_single_alt(self, interaction: discord.Interaction, button: Button):
        """Handle remove single alt button click."""
        uid = interaction.user.id
        alt_entries = [p for p in self.raid.participants if p.user_id == uid and (
            p.participant_type == "ALT" or (p.participant_type == "RESERVE" and p.reserve_for == "ALT")
        )]
        
        if not alt_entries:
            # Use ephemeral message
            await ephemeral_response(interaction, "You have no ALTs in this raid.")
            return
        
        # Use ephemeral message
        await interaction.response.send_message(
            "Remove one of your ALTs:",
            ephemeral=True,
            view=RemoveAltView(self.raid, uid)
        )
    
    @discord.ui.button(label="Notify Participants", style=discord.ButtonStyle.primary, row=0, custom_id="raidmgmt_notify")
    async def notify_participants(self, interaction: discord.Interaction, button: Button):
        """Handle notify participants button click."""
        # Use the NotifyParticipantsButton callback
        notify_button = NotifyParticipantsButton()
        notify_button.view = self
        await notify_button.callback(interaction)
    
    @discord.ui.button(label="Remove Any User", style=discord.ButtonStyle.blurple, row=1, custom_id="raidmgmt_remove_any_user")
    async def remove_any_user(self, interaction: discord.Interaction, button: Button):
        """Handle remove any user button click."""
        if interaction.user != self.raid.creator:
            # Use ephemeral message
            await ephemeral_response(interaction, "Only the raid leader can remove others!")
            return
        
        # Use ephemeral message
        await interaction.response.send_message(
            "Select a participant to remove:",
            ephemeral=True,
            view=RemoveUserView(self.raid, remover=interaction.user)
        )
    
    @discord.ui.button(label="Delete Raid", style=discord.ButtonStyle.danger, row=1, custom_id="raidmgmt_delete_raid")
    async def delete_raid(self, interaction: discord.Interaction, button: Button):
        """Handle delete raid button click."""
        if interaction.user != self.raid.creator:
            # Use ephemeral message
            await ephemeral_response(interaction, "Only the raid creator can delete this raid.")
            return
        
        channel = self.raid.bot.get_channel(self.raid.channel_id)
        if channel:
            # Send direct messages to participants (ephemeral-like)
            for p in self.raid.participants:
                member = self.raid.guild.get_member(p.user_id)
                if member:
                    try:
                        await member.send(f"Raid **{self.raid.raid_name}** has been cancelled.")
                    except Exception as e:
                        print(f"Error sending cancellation DM to {member}: {e}")
            
            # Also send to channel for reference
            mentions = []
            for p in self.raid.participants:
                member = self.raid.guild.get_member(p.user_id)
                if member:
                    mentions.append(member.mention)
                else:
                    mentions.append(f"<@{p.user_id}>")
            
            if mentions:
                cancel_message = "This raid has been cancelled: " + " ".join(mentions)
                await channel.send(cancel_message)
        
        # Import here to avoid circular imports
        from db import remove_raid_from_db
        
        try:
            del self.raid.bot.raids[self.raid.channel_id]
        except KeyError:
            pass
        
        remove_raid_from_db(self.raid.channel_id, self.raid.guild.id)
        
        if self.raid.raid_message:
            try:
                await self.raid.raid_message.delete()
            except discord.HTTPException:
                pass
        
        await self.raid.delete_all_tracked_messages()
        
        # Use ephemeral message
        await ephemeral_response(interaction, "Raid deleted and all participants have been notified.")
    
    @discord.ui.button(label="Promote Next (FIFO)", style=discord.ButtonStyle.gray, row=2, custom_id="raidmgmt_promote_next_fifo")
    async def promote_next_fifo(self, interaction: discord.Interaction, button: Button):
        """Handle promote next FIFO button click."""
        if interaction.user != self.raid.creator:
            # Use ephemeral message
            await ephemeral_response(interaction, "Only the raid creator can force-promote!")
            return
        
        promoted_user = self.raid.force_promote_next_reserve()
        if promoted_user and self.raid.raid_message:
            await safe_edit_message(self.raid.raid_message, content=self.raid.format_raid_list())
            
            # Send direct message to promoted user (ephemeral-like)
            member = self.raid.guild.get_member(promoted_user)
            if member:
                try:
                    await member.send(f"You have been promoted from reserve in raid **{self.raid.raid_name}**!")
                except Exception as e:
                    print(f"Error sending promotion DM to {member}: {e}")
            
            # Also send to channel for reference
            channel = self.raid.bot.get_channel(self.raid.channel_id)
            if channel:
                await channel.send(f"<@{promoted_user}> has been promoted from reserve!")
        
        msg = f"Promoted <@{promoted_user}> from reserve!" if promoted_user else "No valid Reserve participant to promote."
        # Use ephemeral message
        await ephemeral_response(interaction, msg)
    
    @discord.ui.button(label="Promote from Reserve (Pick)", style=discord.ButtonStyle.gray, row=2, custom_id="raidmgmt_promote_pick_reserve")
    async def promote_pick_reserve(self, interaction: discord.Interaction, button: Button):
        """Handle promote pick reserve button click."""
        if interaction.user != self.raid.creator:
            # Use ephemeral message
            await ephemeral_response(interaction, "Only the raid creator can force-promote!")
            return
        
        reserves = [p for p in self.raid.participants if p.participant_type == "RESERVE"]
        if not reserves:
            # Use ephemeral message
            await ephemeral_response(interaction, "No one is on Reserve!")
            return
        
        # Use ephemeral message
        await interaction.response.send_message(
            "Pick a user from Reserve to promote:",
            ephemeral=True,
            view=PromoteReserveDropdownView(self.raid)
        )