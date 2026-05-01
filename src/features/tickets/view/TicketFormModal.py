import discord
from typing import Dict, Any
from src.utils.logger import get_cool_logger
from ..create_ticket import create_ticket

logger = get_cool_logger(__name__)


class TicketFormModal(discord.ui.Modal):
    def __init__(
        self,
        category_name: str,
        category_data: Dict[str, Any],
        original_message: discord.Message,
    ):
        """
        Initialize the ticket form modal.

        Args:
            category_name: Name of the ticket category
            category_data: Full category data including forms
            original_message: The original ticket panel message to reset after submission
        """
        self.category_name = category_name
        self.category_data = category_data
        self.original_message = original_message

        # Use formTitle if available, otherwise use category name
        form_title = category_data.get("formTitle", category_name)
        super().__init__(title=form_title)

        # Add form fields dynamically based on the configuration
        self.form_responses = {}
        self._add_form_fields(category_data.get("forms", []))

    def _add_form_fields(self, forms: list):
        """Add form fields to the modal based on configuration."""
        for index, form in enumerate(forms, start=1):
            form_type = form.get("type")
            question = form.get("question", "Input")
            placeholder = form.get("placeholder", "")
            required = form.get("required", False)
            min_length = form.get("min", 1)
            max_length = form.get("max", 4000)
            # Use a generated key so config "id" is optional.
            field_key = f"form_{index}"

            if form_type == "textarea":
                input_field = discord.ui.InputText(
                    style=discord.InputTextStyle.long,
                    label=question,
                    placeholder=placeholder,
                    required=required,
                    min_length=min_length,
                    max_length=max_length,
                    custom_id=field_key,
                )
            elif form_type == "text":
                input_field = discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    label=question,
                    placeholder=placeholder,
                    required=required,
                    min_length=min_length,
                    max_length=min(max_length, 100),  # Short text max 100 chars
                    custom_id=field_key,
                )
            else:
                logger.warning(f"Unknown form type: {form_type}")
                continue

            self.add_item(input_field)
            # Store reference for later retrieval
            self.form_responses[field_key] = {"question": question, "value": None}

    async def callback(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Collect all responses
        for child in self.children:
            if isinstance(child, discord.ui.InputText):
                if child.custom_id in self.form_responses:
                    self.form_responses[child.custom_id]["value"] = child.value

        # Defer the response as ticket creation might take a moment
        await interaction.response.defer(ephemeral=True)

        # Create the ticket with form responses
        success, message = await create_ticket(
            user=interaction.user,
            category_name=self.category_name,
            guild=interaction.guild,
            form_responses=self.form_responses,
        )

        # Send the response
        if isinstance(message, discord.Embed):
            await interaction.followup.send(embed=message, ephemeral=True)
        else:
            await interaction.followup.send(message, ephemeral=True)

        # Reset the dropdown selection by editing the original message with a fresh view
        # Import here to avoid circular import
        from .TicketPanel import TicketPanel

        try:
            await self.original_message.edit(view=TicketPanel())
        except:
            pass  # Ignore if message cannot be edited

        logger.info(
            f"Ticket with form created by {interaction.user.id} for category '{self.category_name}': "
            f"{'Success' if success else 'Failed'}"
        )
