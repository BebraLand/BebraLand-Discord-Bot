import discord
from discord import ui
from src.utils.logger import get_cool_logger
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon
import src.languages.lang_constants as lang_constants

logger = get_cool_logger(__name__)

class InviteUserSelect(ui.Select):
    """User select for inviting users to the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select a user to invite", min_values=1, max_values=1, select_type=discord.ComponentType.user_select)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Only the channel owner can invite users!", ephemeral=True)
            return

        selected_user = self.values[0]

        # Check if selected user is a bot
        if selected_user.bot:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Cannot invite bots!", ephemeral=True)
            return
        
        if selected_user in self.channel.members:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} User is already in the voice channel!", ephemeral=True)
            return

        try:
            # Create invite
            invite = await self.channel.create_invite(max_age=3600, max_uses=1, reason=f"Invited by {interaction.user}")
            
            # Send DM to user
            embed = discord.Embed(
                title=f"{lang_constants.MIC_EMOJI} Voice Channel Invitation",
                description=f"{interaction.user.mention} has invited you to join their voice channel!",
                color=constants.DISCORD_EMBED_COLOR
            )
            embed.add_field(name="Channel", value=self.channel.mention, inline=False)
            embed.add_field(name="Invite Link", value=invite.url, inline=False)
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(self.channel.guild.me))
            
            try:
                await selected_user.send(embed=embed)
                logger.info(f"User {interaction.user.id} sent invite for channel {self.channel.id} to {selected_user.id}")
                await interaction.response.send_message(f"{lang_constants.SUCCESS_EMOJI} Sent invitation to {selected_user.mention}!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Could not send DM to {selected_user.mention}. They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending invite: {e}")
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)