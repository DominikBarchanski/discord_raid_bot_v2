import discord
from discord.ui import View, Button
from typing import Dict, List, Optional

from database import save_raid_to_db
from utils import ephemeral_response
from ui.buttons import CloseButton, MapButton, RoleButton, SendListButton, NotifyParticipantsButton
from ui.dropdowns import ClassDropdown, SPDropdown, PromoteReserveDropdown, RequiredSPDropdown, RoleSelectMenu, RaidTemplateSelectDropdown

class ClassSelectionView(View):
    """View for selecting a class."""

    def __init__(self, raid, participant_type: str):
        super().__init__()
        self.add_item(ClassDropdown(raid, participant_type))
        self.add_item(CloseButton())

class SPSelectionView(View):
    """View for selecting a specialization."""

    def __init__(self, raid, chosen_class: str, participant_type: str, chosen_sps=None):
        super().__init__()
        self.raid = raid
        self.chosen_class = chosen_class
        self.participant_type = participant_type
        self.chosen_sps = chosen_sps or []

        # Add SP dropdown
        self.add_item(SPDropdown(raid, chosen_class, self.chosen_sps))

        # Add buttons
        sign_up_button = Button(style=discord.ButtonStyle.success, label="Sign Up", custom_id="sign_up")
        sign_up_button.callback = lambda i, b=sign_up_button: self.sign_up(i, b)
        self.add_item(sign_up_button)

        add_sp_button = Button(style=discord.ButtonStyle.primary, label="Add SP", custom_id="add_sp")
        add_sp_button.callback = lambda i, b=add_sp_button: self.add_sp(i, b)
        self.add_item(add_sp_button)

        clear_sp_button = Button(style=discord.ButtonStyle.danger, label="Clear", custom_id="clear_sp")
        clear_sp_button.callback = lambda i, b=clear_sp_button: self.clear_sp(i, b)
        self.add_item(clear_sp_button)

        change_class_button = Button(style=discord.ButtonStyle.secondary, label="Change Class", custom_id="change_class")
        change_class_button.callback = lambda i, b=change_class_button: self.change_class(i, b)
        self.add_item(change_class_button)

    async def sign_up(self, interaction: discord.Interaction, button: Button):
        """Handle sign up button click."""
        if not self.chosen_sps:
            await interaction.response.send_message("Please select at least one specialization.", ephemeral=True)
            return

        # Add participant to raid
        success, message = self.raid.add_participant(
            user=interaction.user,
            sp=self.chosen_sps[0],  # Use the first selected SP
            desired_type=self.participant_type,
            ignore_required=False
        )

        if success:
            # Update the raid message
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=RaidManagementView(self.raid))

            # Save the raid to the database
            save_raid_to_db(self.raid)

        # Disable all components
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(content=message, view=self)

    async def add_sp(self, interaction: discord.Interaction, button: Button):
        """Handle add SP button click."""
        if not self.chosen_sps:
            await interaction.response.send_message("Please select at least one specialization.", ephemeral=True)
            return

        # Add participant to raid
        success, message = self.raid.add_participant(
            user=interaction.user,
            sp=self.chosen_sps[0],  # Use the first selected SP
            desired_type=self.participant_type,
            ignore_required=False
        )

        if success:
            # Update the raid message
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=RaidManagementView(self.raid))

            # Save the raid to the database
            save_raid_to_db(self.raid)

        await interaction.response.send_message(message, ephemeral=True)

    async def clear_sp(self, interaction: discord.Interaction, button: Button):
        """Handle clear SP button click."""
        self.chosen_sps = []
        await interaction.response.edit_message(content="Cleared selections. Please select specializations again.", view=self)

    async def change_class(self, interaction: discord.Interaction, button: Button):
        """Handle change class button click."""
        await interaction.response.edit_message(content="Please select a class:", view=ClassSelectionView(self.raid, self.participant_type))

class RemoveAltView(View):
    """View for removing an alt."""

    def __init__(self, raid, user_id: int):
        super().__init__()
        self.raid = raid
        self.user_id = user_id

        # Get all alts for this user
        if user_id in raid.participants:
            alts = [p for p in raid.participants[user_id] if p.participant_type == "alt"]

            # Add a button for each alt
            for alt in alts:
                button = Button(style=discord.ButtonStyle.danger, label=f"Remove {alt.sp}", custom_id=f"remove_alt_{alt.sp}")
                button.callback = self.generate_callback(alt.sp)
                self.add_item(button)

        # Add close button
        self.add_item(CloseButton())

    def generate_callback(self, custom_id: str):
        """Generate a callback for a button."""
        async def callback(interaction: discord.Interaction):
            # Remove the alt
            success, message = self.raid.remove_alt_by_sp(self.user_id, custom_id)

            if success:
                # Update the raid message
                await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=RaidManagementView(self.raid))

                # Save the raid to the database
                save_raid_to_db(self.raid)

            # Disable all components
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(content=message, view=self)

        return callback

class RemoveUserView(View):
    """View for removing a user."""

    def __init__(self, raid, remover: discord.Member):
        super().__init__()
        self.raid = raid
        self.remover = remover

        # Add a button for each participant
        for user_id in raid.participants:
            user = raid.bot.get_user(user_id)
            if user:
                button = Button(style=discord.ButtonStyle.danger, label=f"Remove {user.display_name}", custom_id=f"remove_user_{user_id}")
                button.callback = lambda i, b=button: self.remove_user(i, b)
                self.add_item(button)

        # Add close button
        self.add_item(CloseButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user can interact with this view."""
        # Only the remover or raid creator can use this view
        if interaction.user.id != self.remover.id and interaction.user.id != self.raid.creator.id:
            await interaction.response.send_message("You cannot use this view.", ephemeral=True)
            return False

        # Check if the remover has permission to remove other users
        if interaction.user.id != self.raid.creator.id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to remove other users.", ephemeral=True)
            return False

        return True

    async def remove_user(self, interaction: discord.Interaction, button: Button):
        """Handle remove user button click."""
        user_id = int(button.custom_id.split("_")[-1])

        # Remove the user
        success, message = self.raid.remove_participant(user_id, self.remover)

        if success:
            # Update the raid message
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=RaidManagementView(self.raid))

            # Save the raid to the database
            save_raid_to_db(self.raid)

        # Disable all components
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(content=message, view=self)

class PromoteReserveDropdownView(View):
    """View for promoting a reserve player."""

    def __init__(self, raid):
        super().__init__()
        self.raid = raid

        # Add dropdown
        self.add_item(PromoteReserveDropdown(raid))

        # Add close button
        self.add_item(CloseButton())

class RequiredSPDropdownView(View):
    """View for selecting a required SP."""

    def __init__(self, raid):
        super().__init__()
        self.raid = raid

        # Add dropdown
        self.add_item(RequiredSPDropdown(raid))

        # Add close button
        self.add_item(CloseButton())

class TemplateOrganizerView(View):
    """View for organizing a raid template."""

    def __init__(self, raid, template_name: str, template_data: dict):
        super().__init__()
        self.raid = raid
        self.template_name = template_name
        self.template_data = template_data
        self.selected_map = None
        self.selected_roles = []
        self.role_assignments = {}

        # Add map buttons
        for map_name in template_data.get("maps", []):
            self.add_item(MapButton(map_name, self))

        # Add role buttons
        for role_name in template_data.get("roles", []):
            self.add_item(RoleButton(role_name, self))

        # Add send list button
        self.add_item(SendListButton(self))

        # Add close button
        self.add_item(CloseButton())

    def update_role_buttons(self):
        """Update the role buttons based on selection."""
        for item in self.children:
            if isinstance(item, RoleButton):
                if item.role_name in self.selected_roles:
                    item.style = discord.ButtonStyle.success
                else:
                    item.style = discord.ButtonStyle.secondary

    def get_preview(self):
        """Get a preview of the template."""
        lines = []

        if self.selected_map:
            lines.append(f"**Map: {self.selected_map}**")

        if self.selected_roles:
            lines.append("\n**Roles:**")
            for role in self.selected_roles:
                lines.append(f"- {role}")

        return "\n".join(lines)

    async def update_preview(self, interaction: discord.Interaction):
        """Update the preview."""
        await interaction.response.edit_message(content=self.get_preview(), view=self)

class RaidTemplateSelectView(View):
    """View for selecting a raid template."""

    def __init__(self, raid, templates: Dict[str, dict]):
        super().__init__()
        self.raid = raid
        self.templates = templates

        # Add dropdown
        options = [discord.SelectOption(label=name) for name in templates.keys()]
        self.add_item(RaidTemplateSelectDropdown(options))

        # Add close button
        self.add_item(CloseButton())

class RaidManagementView(View):
    """View for managing a raid."""

    def __init__(self, raid):
        super().__init__(timeout=None)  # No timeout for raid management views
        self.raid = raid

        # Add buttons
        join_main_button = Button(style=discord.ButtonStyle.primary, label="Join as Main", custom_id="join_main")
        join_main_button.callback = lambda i, b=join_main_button: self.join_main(i, b)
        self.add_item(join_main_button)

        if raid.allow_alts:
            join_alt_button = Button(style=discord.ButtonStyle.secondary, label="Join as Alt", custom_id="join_alt")
            join_alt_button.callback = lambda i, b=join_alt_button: self.join_alt(i, b)
            self.add_item(join_alt_button)

        sign_out_button = Button(style=discord.ButtonStyle.danger, label="Sign Out", custom_id="sign_out")
        sign_out_button.callback = lambda i, b=sign_out_button: self.sign_out_all(i, b)
        self.add_item(sign_out_button)

        remove_alt_button = Button(style=discord.ButtonStyle.danger, label="Remove Alt", custom_id="remove_alt")
        remove_alt_button.callback = lambda i, b=remove_alt_button: self.remove_single_alt(i, b)
        self.add_item(remove_alt_button)

        notify_button = Button(style=discord.ButtonStyle.primary, label="Notify", custom_id="notify")
        notify_button.callback = lambda i, b=notify_button: self.notify_participants(i, b)
        self.add_item(notify_button)

        # Add admin buttons in a new row
        remove_user_button = Button(style=discord.ButtonStyle.danger, label="Remove User", custom_id="remove_user", row=1)
        remove_user_button.callback = lambda i, b=remove_user_button: self.remove_any_user(i, b)
        self.add_item(remove_user_button)

        delete_raid_button = Button(style=discord.ButtonStyle.danger, label="Delete Raid", custom_id="delete_raid", row=1)
        delete_raid_button.callback = lambda i, b=delete_raid_button: self.delete_raid(i, b)
        self.add_item(delete_raid_button)

        promote_next_button = Button(style=discord.ButtonStyle.success, label="Promote Next", custom_id="promote_next", row=1)
        promote_next_button.callback = lambda i, b=promote_next_button: self.promote_next_fifo(i, b)
        self.add_item(promote_next_button)

        promote_pick_button = Button(style=discord.ButtonStyle.success, label="Promote Pick", custom_id="promote_pick", row=1)
        promote_pick_button.callback = lambda i, b=promote_pick_button: self.promote_pick_reserve(i, b)
        self.add_item(promote_pick_button)

    async def join_main(self, interaction: discord.Interaction, button: Button):
        """Handle join as main button click."""
        await interaction.response.send_message("Please select a class:", view=ClassSelectionView(self.raid, "main"), ephemeral=True)

    async def join_alt(self, interaction: discord.Interaction, button: Button):
        """Handle join as alt button click."""
        await interaction.response.send_message("Please select a class:", view=ClassSelectionView(self.raid, "alt"), ephemeral=True)

    async def sign_out_all(self, interaction: discord.Interaction, button: Button):
        """Handle sign out button click."""
        success, message = self.raid.remove_participant(interaction.user.id)

        if success:
            # Update the raid message
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=self)

            # Save the raid to the database
            save_raid_to_db(self.raid)

        await interaction.response.send_message(message, ephemeral=True)

    async def remove_single_alt(self, interaction: discord.Interaction, button: Button):
        """Handle remove alt button click."""
        if interaction.user.id not in self.raid.participants:
            await interaction.response.send_message("You are not in this raid.", ephemeral=True)
            return

        # Check if user has any alts
        alts = [p for p in self.raid.participants[interaction.user.id] if p.participant_type == "alt"]
        if not alts:
            await interaction.response.send_message("You don't have any alts in this raid.", ephemeral=True)
            return

        # Show alt removal view
        await interaction.response.send_message("Select an alt to remove:", view=RemoveAltView(self.raid, interaction.user.id), ephemeral=True)

    async def notify_participants(self, interaction: discord.Interaction, button: Button):
        """Handle notify button click."""
        # Add the notify participants button to a new view
        view = View()
        view.add_item(NotifyParticipantsButton())
        view.add_item(CloseButton())
        view.raid = self.raid

        await interaction.response.send_message("Notify participants?", view=view, ephemeral=True)

    async def remove_any_user(self, interaction: discord.Interaction, button: Button):
        """Handle remove user button click."""
        # Check if user is the raid creator or has manage messages permission
        if interaction.user.id != self.raid.creator.id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to remove other users.", ephemeral=True)
            return

        # Show user removal view
        await interaction.response.send_message("Select a user to remove:", view=RemoveUserView(self.raid, interaction.user), ephemeral=True)

    async def delete_raid(self, interaction: discord.Interaction, button: Button):
        """Handle delete raid button click."""
        # Check if user is the raid creator or has manage messages permission
        if interaction.user.id != self.raid.creator.id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to delete this raid.", ephemeral=True)
            return

        # Create confirmation view
        view = View()

        confirm_button = Button(style=discord.ButtonStyle.danger, label="Confirm Delete", custom_id="confirm_delete")

        async def confirm_callback(confirm_interaction: discord.Interaction):
            # Delete the raid
            channel_id = self.raid.channel_id
            guild_id = self.raid.guild_id

            # Remove from bot's raids
            if channel_id in self.raid.bot.raids:
                del self.raid.bot.raids[channel_id]

            # Remove from database
            from database import remove_raid_from_db
            remove_raid_from_db(channel_id, guild_id)

            # Delete the raid message
            try:
                await self.raid.raid_message.delete()
            except:
                pass

            # Disable all components
            for item in view.children:
                item.disabled = True

            await confirm_interaction.response.edit_message(content="Raid deleted.", view=view)

        confirm_button.callback = confirm_callback
        view.add_item(confirm_button)
        view.add_item(CloseButton())

        await interaction.response.send_message(f"Are you sure you want to delete the raid **{self.raid.raid_name}**?", view=view, ephemeral=True)

    async def promote_next_fifo(self, interaction: discord.Interaction, button: Button):
        """Handle promote next button click."""
        # Check if user is the raid creator or has manage messages permission
        if interaction.user.id != self.raid.creator.id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to promote reserves.", ephemeral=True)
            return

        # Promote the next reserve
        success, message = self.raid.force_promote_next_reserve()

        if success:
            # Update the raid message
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=self)

            # Save the raid to the database
            save_raid_to_db(self.raid)

        await interaction.response.send_message(message, ephemeral=True)

    async def promote_pick_reserve(self, interaction: discord.Interaction, button: Button):
        """Handle promote pick button click."""
        # Check if user is the raid creator or has manage messages permission
        if interaction.user.id != self.raid.creator.id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to promote reserves.", ephemeral=True)
            return

        # Check if there are any reserves
        reserves_exist = False
        for participants in self.raid.participants.values():
            if any(p.participant_type == "reserve" for p in participants):
                reserves_exist = True
                break

        if not reserves_exist:
            await interaction.response.send_message("No reserves to promote.", ephemeral=True)
            return

        # Show reserve promotion view
        await interaction.response.send_message("Select a reserve to promote:", view=PromoteReserveDropdownView(self.raid), ephemeral=True)
