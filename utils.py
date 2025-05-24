import discord
from discord.ui import View
from typing import Optional

async def safe_edit_message(message: discord.Message, **kwargs):
    """Safely edit a Discord message, handling potential errors."""
    try:
        await message.edit(**kwargs)
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        print(f"Error editing message: {e}")
        return False

async def ephemeral_response(interaction: discord.Interaction, content: str, view: Optional[View] = None, wait_for_user_action: bool = False):
    """Send an ephemeral response to an interaction."""
    try:
        if interaction.response.is_done():
            if view and wait_for_user_action:
                await interaction.followup.send(content, view=view, ephemeral=True, wait=True)
            else:
                await interaction.followup.send(content, view=view, ephemeral=True)
        else:
            if view and wait_for_user_action:
                await interaction.response.send_message(content, view=view, ephemeral=True, wait=True)
            else:
                await interaction.response.send_message(content, view=view, ephemeral=True)
        return True
    except Exception as e:
        print(f"Error sending ephemeral response: {e}")
        return False