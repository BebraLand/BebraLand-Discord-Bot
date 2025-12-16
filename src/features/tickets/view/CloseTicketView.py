import discord
import config.constants as constants
from src.utils.database import get_language
from src.languages.localize import translate
from src.languages import emoji_constants as emoji


class CloseTicketView(discord.ui.View):
    """View with Close Ticket button."""

    def __init__(self, ticket_id: int, user: discord.User, category_name: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user = user
        self.category_name = category_name
        self.close_button.custom_id = f"ticket_close_{ticket_id}"

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        from src.features.tickets.view.ConfirmCloseView import ConfirmCloseView
        is_support = (
            interaction.user.id in constants.TICKET_SUPPORT_USER_IDS or
            (constants.TICKET_SUPPORT_ROLE_ID and any(
                role.id == constants.TICKET_SUPPORT_ROLE_ID for role in interaction.user.roles))
        )

        if interaction.user.id != self.user.id and not is_support:
            await interaction.response.send_message(emoji.CROSS_EMOJI + " Only the ticket creator or support staff can close this ticket.", ephemeral=True)
            return

        lang = await get_language(interaction.user.id)
        confirm_title = translate(
            "Are you sure you would like to close this ticket?", lang)
        confirm_view = ConfirmCloseView(
            self.ticket_id, self.user, self.category_name, interaction.user, is_support)
        # Make the confirmation visible only to the user who clicked the close button
        # The confirm view will explicitly send the public control panel to the channel
        await interaction.response.send_message(confirm_title, view=confirm_view, ephemeral=True)
