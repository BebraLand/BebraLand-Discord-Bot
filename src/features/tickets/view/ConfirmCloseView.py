import discord
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.languages import lang_constants as lang_constants
from src.utils.embeds import get_embed_icon


logger = get_cool_logger(__name__)


class ConfirmCloseView(discord.ui.View):
    """Confirmation view for closing tickets."""

    def __init__(
        self,
        ticket_id: int,
        ticket_owner: discord.User,
        category_name: str,
        closer: discord.User,
        is_support: bool,
    ):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.ticket_owner = ticket_owner
        self.category_name = category_name
        self.closer = closer
        self.is_support = is_support

    @discord.ui.button(
        label="Close", style=discord.ButtonStyle.danger, emoji=lang_constants.LOCK_EMOJI
    )
    async def confirm_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        from src.features.tickets.view.TicketControlPanel import TicketControlPanel
        from src.features.tickets.send_dm_notification import send_dm_notification

        # Acknowledge the interaction as ephemeral (we'll delete the ephemeral confirmation later)
        await interaction.response.defer(ephemeral=True)

        try:
            db = await get_db()
            if not await db.close_ticket(self.ticket_id):
                await interaction.followup.send(
                    lang_constants.ERROR_EMOJI
                    + " Failed to close ticket. Please try again.",
                    ephemeral=True,
                )
                return

            # Remove user's access to the channel
            await interaction.channel.set_permissions(
                self.ticket_owner, read_messages=False, send_messages=False
            )

            # Create control panel embed (always in English for admins)
            embed = discord.Embed(
                title=lang_constants.LOCK_EMOJI
                + f" Ticket Closed by {self.closer.name}",
                description="Support team ticket controls",
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )

            control_panel = TicketControlPanel(
                self.ticket_id, self.ticket_owner, self.category_name
            )
            # Always send the control panel publicly in the ticket channel so staff can use it.
            try:
                await interaction.channel.send(embed=embed, view=control_panel)
            except Exception as e:
                logger.error(f"Failed to send control panel message: {e}")

            # Delete the ephemeral confirmation message (if present) to avoid "This interaction failed"
            try:
                await interaction.delete_original_response()
            except Exception:
                pass

            # Log the closure
            if constants.TICKET_LOG_CHANNEL_ID:
                log_channel = interaction.guild.get_channel(
                    constants.TICKET_LOG_CHANNEL_ID
                )
                if log_channel:
                    log_embed = discord.Embed(
                        title=lang_constants.LOCK_EMOJI + " Ticket Closed",
                        description=f"**Ticket ID:** {self.ticket_id}\n**User:** {self.ticket_owner.mention}\n**Category:** {self.category_name}\n**Closed by:** {self.closer.mention}",
                        color=constants.FAILED_EMBED_COLOR,
                    )
                    log_embed.set_footer(
                        text=constants.DISCORD_MESSAGE_TRADEMARK,
                        icon_url=get_embed_icon(interaction),
                    )
                    await log_channel.send(embed=log_embed)

            # Send DM to user if closed by admin (not by themselves)
            if self.closer.id != self.ticket_owner.id:
                await send_dm_notification(
                    self.ticket_owner,
                    self.ticket_id,
                    "closed",
                    None,
                    self.closer,
                    interaction.client.user,
                )

            logger.info(f"Ticket #{self.ticket_id} closed by {self.closer.id}")
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            await interaction.followup.send(
                lang_constants.ERROR_EMOJI
                + " Failed to close ticket. Please try again.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji=lang_constants.ERROR_EMOJI,
    )
    async def cancel_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        # Acknowledge then delete the original ephemeral confirmation message.
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.delete_original_response()
        except Exception:
            pass
