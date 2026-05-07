import discord

from config.config import config as bot_config
from src.languages import lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_language


class CloseTicketView(discord.ui.View):
    """View with Close Ticket button."""

    def __init__(self, ticket_id: int, user: discord.User, category_name: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user = user
        self.category_name = category_name
        self.close_button.custom_id = f"ticket_close_{ticket_id}"

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji=lang_constants.LOCK_EMOJI,
        custom_id="close_ticket_btn",
    )
    async def close_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        from src.features.tickets.view.ConfirmCloseView import ConfirmCloseView

        is_support = interaction.user.id in bot_config.modules.tickets.support_user_ids or (
            bot_config.modules.tickets.support_role_id
            and any(
                role.id == bot_config.modules.tickets.support_role_id
                for role in interaction.user.roles
            )
        )

        if interaction.user.id != self.user.id and not is_support:
            await interaction.response.send_message(
                lang_constants.ERROR_EMOJI
                + " Only the ticket creator or support staff can close this ticket.",
                ephemeral=True,
            )
            return

        lang = await get_language(interaction.user.id)
        confirm_title = _("tickets.confirm_close", lang)
        confirm_view = ConfirmCloseView(
            self.ticket_id, self.user, self.category_name, interaction.user, is_support
        )
        # Make the confirmation visible only to the user who clicked the close button
        # The confirm view will explicitly send the public control panel to the channel
        await interaction.response.send_message(
            confirm_title, view=confirm_view, ephemeral=True
        )
