import discord
from discord import ui
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon

logger = get_cool_logger(__name__)

class RejectMentionableSelect(ui.Select):
    """Mentionable select for rejecting users or roles from joining the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        # Use user_select if roles are disabled, otherwise use mentionable_select
        select_type = discord.ComponentType.user_select if not constants.TEMP_VOICE_REJECT_ROLES_ENABLED else discord.ComponentType.mentionable_select
        placeholder = "Select users to reject" if not constants.TEMP_VOICE_REJECT_ROLES_ENABLED else "Select users/roles to reject"
        super().__init__(placeholder=placeholder, min_values=1, max_values=10, select_type=select_type)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return

        try:
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            rejected_items = []
            
            for item in self.values:
                if isinstance(item, (discord.Member, discord.User)):
                    # Reject user
                    await self.channel.set_permissions(item, connect=False, view_channel=False)
                    rejected_items.append(item.mention)
                    
                    # # Disconnect if in channel
                    # if hasattr(item, 'voice') and item.voice and item.voice.channel == self.channel:
                    #     await item.move_to(None)
                    
                    # Store in database
                    if temp_vc:
                        rejected_users = temp_vc.get("rejected_users", [])
                        if item.id not in rejected_users:
                            rejected_users.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, rejected_users=rejected_users)
                            
                elif isinstance(item, discord.Role):
                    # Reject role
                    await self.channel.set_permissions(item, connect=False, view_channel=False)
                    rejected_items.append(item.mention)
                    
                    # Store in database
                    if temp_vc:
                        rejected_roles = temp_vc.get("rejected_roles", [])
                        if item.id not in rejected_roles:
                            rejected_roles.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, rejected_roles=rejected_roles)
            
            items_text = ", ".join(rejected_items)
            await interaction.response.edit_message(content=f"{lang_constants.SUCCESS_EMOJI} Rejected {items_text} from the channel!", embed=None, view=None, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
        except Exception as e:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)