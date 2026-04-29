import discord
from discord import ui
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants
import config.constants as constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon

logger = get_cool_logger(__name__)


class TransferUserSelect(ui.Select):
    """User select for transferring channel ownership."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int, current_owner: discord.Member):
        # Create a filtered list of non-bot members
        super().__init__(
            placeholder="Select a user to transfer ownership to",
            min_values=1,
            max_values=1,
            select_type=discord.ComponentType.user_select
        )
        self.channel = channel
        self.owner_id = owner_id
        self.current_owner = current_owner

    async def callback(self, interaction: discord.Interaction):
        current_lang = await get_language(interaction.user.id)
        
        if interaction.user.id != self.owner_id:
            return

        selected_user = self.values[0]
        logger.info(f"User selected for transfer: {selected_user.id} in channel {self.channel.id} {selected_user.name}({selected_user.id})")
        
        # Check if selected user is a bot
        if selected_user.bot:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.info', current_lang)}",
                description=f"{_('temp_voice.errors.cannot_transfer_to_bot', current_lang)}", 
                color=constants.FAILED_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction.guild.me))
            await interaction.response.edit_message(embed=embed, view=None, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            return
        
        if selected_user.id == self.owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.info', current_lang)}",
                description=f"{_('temp_voice.errors.already_owner', current_lang)}", 
                color=constants.FAILED_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction.guild.me))
            await interaction.response.edit_message(embed=embed, view=None, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            return
        
        # Check if selected user is in the voice channel
        if not selected_user.voice or selected_user.voice.channel != self.channel:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.info', current_lang)}",
                description=_('temp_voice.errors.not_in_channel', current_lang).format(selected_user=selected_user.mention),
                color=constants.FAILED_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction.guild.me))
            await interaction.response.edit_message(embed=embed, view=None, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            return
        
        try:
            logger.info(f"Starting ownership transfer: channel {self.channel.id}, from {self.owner_id} to {selected_user.id}")
            
            # Update database
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            logger.info(f"Current temp_vc data: {temp_vc}")
            
            await storage.update_temp_voice_channel(self.channel.id, owner_id=selected_user.id)
            logger.info(f"Updated database with new owner_id: {selected_user.id}")
            
            # Verify update
            updated_vc = await storage.get_temp_voice_channel(self.channel.id)
            logger.info(f"Verified temp_vc data after update: {updated_vc}")
            
            # Update channel permissions
            # Remove manage permissions from old owner
            await self.channel.set_permissions(self.current_owner, manage_channels=None)
            logger.info(f"Removed manage permissions from old owner {self.current_owner.id}")
            
            # Grant manage permissions to new owner
            await self.channel.set_permissions(selected_user, manage_channels=True, connect=True, speak=True, view_channel=True)
            logger.info(f"Granted manage permissions to new owner {selected_user.id}")
            
            # Update channel name if it contains old owner's name
            if self.current_owner.display_name in self.channel.name:
                new_name = self.channel.name.replace(self.current_owner.display_name, selected_user.display_name)
                await self.channel.edit(name=new_name)
                logger.info(f"Updated channel name to: {new_name}")
            
            # Update control panel message with new owner
            if temp_vc and temp_vc.get("control_message_id"):
                try:
                    control_message = await self.channel.fetch_message(temp_vc["control_message_id"])
                    # Update embed to mention new owner
                    embed = control_message.embeds[0]
                    embed.description = f"Welcome to your temporary voice channel, {selected_user.mention}!\n\nUse the buttons below to control your channel."
                    await control_message.edit(embed=embed)
                    logger.info(f"Updated control panel message with new owner mention")
                except Exception as e:
                    logger.error(f"Error updating control panel message: {e}")
            

            text = _("temp_voice.transferred_ownership", constants.DEFAULT_LANGUAGE).format(selected_user = selected_user.mention)
            embed = discord.Embed(
                title=f"{lang_constants.INFO_EMOJI} {_('common.info', constants.DEFAULT_LANGUAGE)}",
                description=f"{lang_constants.CROWN_EMOJI} {text}", 
                color=constants.INFO_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction.guild.me))

            # Defer the response to acknowledge the interaction
            await interaction.response.defer(ephemeral=True)
            # Delete the original ephemeral message with the dropdown
            await interaction.delete_original_response()
            # Send new message to the voice channel that auto-deletes
            await self.channel.send(embed=embed, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            logger.info(f"{lang_constants.SUCCESS_EMOJI} Channel {self.channel.id} ownership transferred from {self.owner_id} to {selected_user.id}")
        except Exception as e:
            logger.error(f"Error transferring channel ownership: {e}")
            try:
                await interaction.response.edit_message(content=f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", embed=None, view=None)
            except:
                # If response already sent, use followup
                await interaction.followup.send(content=f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)