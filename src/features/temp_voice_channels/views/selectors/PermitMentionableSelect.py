import discord
from discord import ui
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
import config.constants as constants
import src.languages.lang_constants as lang_constants

logger = get_cool_logger(__name__)

class PermitMentionableSelect(ui.Select):
    """Mentionable select for permitting users or roles to join the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        # Use user_select if roles are disabled, otherwise use mentionable_select
        select_type = discord.ComponentType.user_select if not constants.TEMP_VOICE_PERMIT_ROLES_ENABLED else discord.ComponentType.mentionable_select
        placeholder = "Select users to permit" if not constants.TEMP_VOICE_PERMIT_ROLES_ENABLED else "Select users/roles to permit"
        super().__init__(placeholder=placeholder, min_values=1, max_values=10, select_type=select_type)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return

        try:
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            permitted_items = []
            
            for item in self.values:
                if isinstance(item, (discord.Member, discord.User)):
                    # Permit user
                    await self.channel.set_permissions(item, connect=True, view_channel=True)
                    permitted_items.append(item.mention)
                    
                    # Store in database
                    if temp_vc:
                        permitted_users = temp_vc.get("permitted_users", [])
                        if item.id not in permitted_users:
                            permitted_users.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, permitted_users=permitted_users)
                            
                elif isinstance(item, discord.Role):
                    # Permit role
                    await self.channel.set_permissions(item, connect=True, view_channel=True)
                    permitted_items.append(item.mention)
                    
                    # Store in database
                    if temp_vc:
                        permitted_roles = temp_vc.get("permitted_roles", [])
                        if item.id not in permitted_roles:
                            permitted_roles.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, permitted_roles=permitted_roles)
            
            items_text = ", ".join(permitted_items)
            await interaction.response.edit_message(content=f"{lang_constants.SUCCESS_EMOJI} Permitted {items_text} to join the channel!", embed=None, view=None, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
        except Exception as e:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)