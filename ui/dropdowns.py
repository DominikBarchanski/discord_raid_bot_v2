import discord
from discord.ui import Select

class ClassDropdown(Select):
    """Dropdown for selecting a class."""
    
    def __init__(self, raid, participant_type: str):
        options = [
            discord.SelectOption(label="Warrior", emoji="⚔️"),
            discord.SelectOption(label="Paladin", emoji="🛡️"),
            discord.SelectOption(label="Hunter", emoji="🏹"),
            discord.SelectOption(label="Rogue", emoji="🗡️"),
            discord.SelectOption(label="Priest", emoji="✝️"),
            discord.SelectOption(label="Shaman", emoji="🌩️"),
            discord.SelectOption(label="Mage", emoji="🔮"),
            discord.SelectOption(label="Warlock", emoji="🔥"),
            discord.SelectOption(label="Druid", emoji="🌿")
        ]
        super().__init__(placeholder="Choose your class", options=options)
        self.raid = raid
        self.participant_type = participant_type
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        from ui.views import SPSelectionView
        await interaction.response.send_message(
            f"You selected {self.values[0]}. Now choose your specialization:",
            view=SPSelectionView(self.raid, self.values[0], self.participant_type),
            ephemeral=True
        )

class SPDropdown(Select):
    """Dropdown for selecting a specialization."""
    
    def __init__(self, raid, chosen_class: str, chosen_sps: list):
        self.class_specs = {
            "Warrior": ["Arms", "Fury", "Protection"],
            "Paladin": ["Holy", "Protection", "Retribution"],
            "Hunter": ["Beast Mastery", "Marksmanship", "Survival"],
            "Rogue": ["Assassination", "Combat", "Subtlety"],
            "Priest": ["Discipline", "Holy", "Shadow"],
            "Shaman": ["Elemental", "Enhancement", "Restoration"],
            "Mage": ["Arcane", "Fire", "Frost"],
            "Warlock": ["Affliction", "Demonology", "Destruction"],
            "Druid": ["Balance", "Feral", "Restoration"]
        }
        
        options = []
        for spec in self.class_specs.get(chosen_class, []):
            options.append(discord.SelectOption(
                label=spec,
                value=f"{chosen_class}_{spec}",
                default=f"{chosen_class}_{spec}" in chosen_sps
            ))
        
        super().__init__(placeholder="Choose your specialization", options=options, min_values=1, max_values=len(options))
        self.raid = raid
        self.chosen_class = chosen_class
        self.chosen_sps = chosen_sps
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        self.view.chosen_sps = self.values
        await interaction.response.edit_message(content=f"Selected specializations: {', '.join(self.values)}", view=self.view)

class PromoteReserveDropdown(Select):
    """Dropdown for promoting a reserve player."""
    
    def __init__(self, raid):
        options = []
        
        # Get all reserves
        all_reserves = []
        for user_id, participants in raid.participants.items():
            for p in participants:
                if p.participant_type == "reserve":
                    all_reserves.append((user_id, p))
        
        # Sort reserves by priority, then by level offset
        all_reserves.sort(key=lambda x: (
            not raid.user_in_priority_roles(x[0]),  # Priority users first
            x[1].level_offset,  # Then by level offset
            x[0]  # Then by user ID for consistent ordering
        ))
        
        # Add options for each reserve
        for user_id, reserve in all_reserves:
            user = raid.bot.get_user(user_id)
            if user:
                options.append(discord.SelectOption(
                    label=f"{user.display_name} - {reserve.sp}",
                    value=str(user_id),
                    description=f"Priority: {'Yes' if raid.user_in_priority_roles(user_id) else 'No'}"
                ))
        
        super().__init__(placeholder="Choose a reserve to promote", options=options)
        self.raid = raid
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        user_id = int(self.values[0])
        
        # Promote the selected reserve
        success, message = self.raid.force_promote_reserve_user(user_id)
        
        if success:
            # Update the raid message
            from ui.views import RaidManagementView
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=RaidManagementView(self.raid))
            
            # Save the raid to the database
            from database import save_raid_to_db
            save_raid_to_db(self.raid)
            
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

class RequiredSPDropdown(Select):
    """Dropdown for selecting a required SP."""
    
    def __init__(self, raid):
        options = []
        
        # Add options for each unfilled required SP
        for sp_name in raid.get_unfilled_required_sps():
            original_name = raid.required_sps_original.get(sp_name, sp_name)
            options.append(discord.SelectOption(
                label=f"{original_name} ({raid.required_sps[sp_name]} needed)",
                value=sp_name
            ))
        
        super().__init__(placeholder="Choose a required SP", options=options)
        self.raid = raid
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        sp_name = self.values[0]
        
        # Decrement the required SP count
        if self.raid.decrement_required_sp(sp_name):
            # Update the raid message
            from ui.views import RaidManagementView
            await self.raid.raid_message.edit(content=self.raid.format_raid_list(), view=RaidManagementView(self.raid))
            
            # Save the raid to the database
            from database import save_raid_to_db
            save_raid_to_db(self.raid)
            
            await interaction.response.send_message(f"Decremented required SP count for {sp_name}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to decrement required SP count for {sp_name}.", ephemeral=True)

class RoleSelectMenu(Select):
    """Dropdown for selecting a role in a template organizer."""
    
    def __init__(self, role_name: str, options: list, organizer):
        super().__init__(placeholder=f"Choose {role_name}", options=options)
        self.role_name = role_name
        self.organizer = organizer
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        # Update the selected user for this role
        self.organizer.role_assignments[self.role_name] = self.values[0]
        
        # Update the preview
        await self.organizer.update_preview(interaction)

class RaidTemplateSelectDropdown(Select):
    """Dropdown for selecting a raid template."""
    
    def __init__(self, options: list):
        super().__init__(placeholder="Choose a template", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        template_name = self.values[0]
        
        # Get the template data
        template_data = self.view.templates.get(template_name, {})
        
        if not template_data:
            await interaction.response.send_message(f"Template {template_name} not found.", ephemeral=True)
            return
        
        # Create the template organizer view
        from ui.views import TemplateOrganizerView
        await interaction.response.edit_message(
            content=f"Organizing template: {template_name}",
            view=TemplateOrganizerView(self.view.raid, template_name, template_data)
        )