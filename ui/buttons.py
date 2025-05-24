import discord
from discord.ui import Button, View

class CloseButton(Button):
    """Button to close a view."""
    
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Close", custom_id="close_button")
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        if self.view:
            # Check if the user who clicked is the same as the one who triggered the original interaction
            if hasattr(self.view, "original_user") and self.view.original_user != interaction.user.id:
                await interaction.response.send_message("You cannot use this button.", ephemeral=True)
                return
            
            # Disable all components and update the message
            for item in self.view.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self.view)

class MapButton(Button):
    """Button for selecting a map in a template organizer."""
    
    def __init__(self, map_name: str, organizer):
        super().__init__(style=discord.ButtonStyle.primary, label=map_name)
        self.map_name = map_name
        self.organizer = organizer
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        self.organizer.selected_map = self.map_name
        await self.organizer.update_preview(interaction)

class RoleButton(Button):
    """Button for selecting a role in a template organizer."""
    
    def __init__(self, role_name: str, organizer):
        super().__init__(style=discord.ButtonStyle.secondary, label=role_name)
        self.role_name = role_name
        self.organizer = organizer
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        if self.role_name in self.organizer.selected_roles:
            self.organizer.selected_roles.remove(self.role_name)
            self.style = discord.ButtonStyle.secondary
        else:
            self.organizer.selected_roles.append(self.role_name)
            self.style = discord.ButtonStyle.success
        
        self.organizer.update_role_buttons()
        await self.organizer.update_preview(interaction)

class SendListButton(Button):
    """Button to send a template list."""
    
    def __init__(self, organizer):
        super().__init__(style=discord.ButtonStyle.primary, label="Send List")
        self.organizer = organizer
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        if not self.organizer.selected_map or not self.organizer.selected_roles:
            await interaction.response.send_message("Please select a map and at least one role.", ephemeral=True)
            return
        
        # Get the raid
        raid = self.organizer.raid
        
        # Get the template data
        template_data = self.organizer.template_data
        
        # Send the list to the channel
        channel = interaction.channel
        await channel.send(self.organizer.get_preview())
        
        # Close the view
        for item in self.view.children:
            item.disabled = True
        
        await interaction.response.edit_message(content="Template sent!", view=self.view)

class NotifyParticipantsButton(Button):
    """Button to notify raid participants."""
    
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Notify Participants")
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        # Check if user is the raid creator
        raid = self.view.raid
        if interaction.user.id != raid.creator.id:
            await interaction.response.send_message("Only the raid creator can notify participants.", ephemeral=True)
            return
        
        # Get all participants
        mentions = []
        for user_id in raid.participants:
            mentions.append(f"<@{user_id}>")
        
        if not mentions:
            await interaction.response.send_message("No participants to notify.", ephemeral=True)
            return
        
        # Calculate time until raid
        now = discord.utils.utcnow()
        raid_time = raid.raid_datetime
        
        if raid_time < now:
            time_str = "now"
        else:
            time_until = raid_time - now
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            time_str = ""
            if hours > 0:
                time_str += f"{hours} hour{'s' if hours != 1 else ''} "
            if minutes > 0:
                time_str += f"{minutes} minute{'s' if minutes != 1 else ''}"
            
            if not time_str:
                time_str = "less than a minute"
        
        # Send notification
        channel = interaction.channel
        await channel.send(f"**{raid.raid_name}** is starting in {time_str}! {' '.join(mentions)}")
        
        await interaction.response.send_message("Participants notified.", ephemeral=True)