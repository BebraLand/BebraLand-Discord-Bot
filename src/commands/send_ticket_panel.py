"""Ticket Panel Command
Admin command to send an interactive ticket panel with dropdown selection.
"""

from views.ticket_views import TicketCreationHandler, TicketCloseView
from utils.embed_helpers import (
    create_ticket_panel_embed, create_ticket_welcome_embed, create_ticket_log_embed,
    create_dm_notification_embed, create_success_embed, create_error_embed
)
from utils.ticket_helpers import (
    TicketData, create_ticket_channel, get_member_safely, is_staff_member,
    send_dm_safely, format_ticket_type_display, log_ticket_event, validate_ticket_config
)
import discord
import json
import logging
import time
from typing import Dict, Any

# Import helper functions
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Import views

# Set up logging
logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load configuration from config/config.json"""
    try:
        with open("config/config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")
        return {}


def load_localization(lang: str = "en") -> Dict[str, str]:
    """Load localization strings with fallback"""
    try:
        # Try to load requested language
        try:
            with open(f"src/languages/{lang}.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback to English
            with open("src/languages/en.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load localization: {e}")
        return {}


class TicketDropdown(discord.ui.Select):
    """Dropdown for selecting ticket category"""

    def __init__(self, config: Dict[str, Any], localization: Dict[str, str]):
        self.config = config
        self.localization = localization
        self.creation_handler = TicketCreationHandler(config, localization)

        # Get ticket categories from config
        ticket_categories = config.get("TICKET_CATEGORIES", {})

        # Create dropdown options
        options = []
        for category_key, category_data in ticket_categories.items():
            options.append(discord.SelectOption(
                label=category_data.get("name", category_key),
                description=category_data.get("description", ""),
                emoji=category_data.get("emoji", "🎫"),
                value=category_key
            ))

        super().__init__(
            placeholder=localization.get(
                "TICKET_PANEL_DROPDOWN_PLACEHOLDER", "Select a ticket category..."),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        start_time = time.time()

        # Log dropdown interaction start
        logger.info(
            f"🔵 TICKET DROPDOWN START | User: {interaction.user.name} ({interaction.user.id}) | Guild: {interaction.guild.name if interaction.guild else 'DM'} ({interaction.guild.id if interaction.guild else 'N/A'}) | Selection: {self.values[0]}")

        try:
            selected_category = self.values[0]

            # Create the ticket using our handler
            await self.creation_handler.create_ticket(interaction, selected_category)

            # Reset dropdown selection by updating the message with a fresh view
            try:
                # Create a new view with reset dropdown
                fresh_view = TicketPanelView(self.config, self.localization)
                await interaction.edit_original_response(view=fresh_view)
                logger.info(f"🔄 DROPDOWN RESET | User: {interaction.user.name} | Selection cleared")
            except Exception as reset_error:
                logger.warning(f"⚠️ Failed to reset dropdown: {reset_error}")

            # Log successful completion
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info(
                f"✅ TICKET DROPDOWN SUCCESS | User: {interaction.user.name} | Selection: {selected_category} | Duration: {duration}ms")

        except Exception as e:
            # Log error with full details
            duration = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"❌ TICKET DROPDOWN FAILED | User: {interaction.user.name} | Selection: {self.values[0] if self.values else 'None'} | Duration: {duration}ms | Error: {str(e)}")
            logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
            raise  # Re-raise for global error handler


class TicketPanelView(discord.ui.View):
    """View containing the ticket dropdown"""

    def __init__(self, config: Dict[str, Any], localization: Dict[str, str]):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(TicketDropdown(config, localization))


@discord.slash_command(
    name="send_ticket_panel",
    description="Send the ticket panel to the current channel (Admin only)",
    default_member_permissions=discord.Permissions(administrator=True),
    contexts={discord.InteractionContextType.guild}
)
async def send_ticket_panel(ctx: discord.ApplicationContext):
    """Send ticket panel command"""
    start_time = time.time()

    # Log command start with full context
    logger.info(
        f"🔵 COMMAND START | User: {ctx.user.name} ({ctx.user.id}) | Guild: {ctx.guild.name if ctx.guild else 'DM'} ({ctx.guild.id if ctx.guild else 'N/A'}) | Command: /send-ticket-panel")

    try:
        # Load configuration and localization
        config = load_config()
        localization = load_localization("en")  # Default to English for now

        # Validate guild context
        if not ctx.guild:
            await ctx.respond(
                embed=create_error_embed(
                    title=localization.get(
                        "TICKET_ERROR_NOT_IN_GUILD", "❌ Guild Only"),
                    description="This command can only be used in a server.",
                    bot_avatar=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
                ),
                ephemeral=True
            )
            return

        # Check admin permissions
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond(
                embed=create_error_embed(
                    title=localization.get(
                        "TICKET_ERROR_ADMIN_ONLY", "❌ Admin Only"),
                    description="Only administrators can use this command.",
                    bot_avatar=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
                ),
                ephemeral=True
            )
            return

        # Validate ticket system configuration
        validation_result = validate_ticket_config(config)
        if not validation_result["valid"]:
            await ctx.respond(
                embed=create_error_embed(
                    title=localization.get(
                        "TICKET_ERROR_CONFIG_INVALID", "❌ Configuration Error"),
                    description=f"Ticket system configuration is invalid: {validation_result['error']}",
                    bot_avatar=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
                ),
                ephemeral=True
            )
            return

        # Check if ticket system is enabled
        if not config.get("TICKET_SYSTEM_ENABLED", False):
            await ctx.respond(
                embed=create_error_embed(
                    title=localization.get(
                        "TICKET_ERROR_DISABLED", "❌ System Disabled"),
                    description="The ticket system is currently disabled.",
                    bot_avatar=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
                ),
                ephemeral=True
            )
            return

        # Create ticket panel embed
        panel_embed = create_ticket_panel_embed(
            bot_avatar=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
        )

        # Create ticket panel view
        panel_view = TicketPanelView(config, localization)

        # Send the ticket panel to the channel (not as a response)
        await ctx.channel.send(embed=panel_embed, view=panel_view)
        
        # Respond with success message (ephemeral)
        await ctx.respond(
            embed=create_success_embed(
                title=localization.get("TICKET_PANEL_SENT", "✅ Ticket Panel Sent"),
                description=localization.get("TICKET_PANEL_SENT_DESC", "The ticket panel has been sent to this channel."),
                bot_avatar=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
            ),
            ephemeral=True
        )

        # Log successful completion
        duration = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"✅ COMMAND SUCCESS | User: {ctx.user.name} | Command: /send-ticket-panel | Duration: {duration}ms")

    except Exception as e:
        # Log error with full details
        duration = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"❌ COMMAND FAILED | User: {ctx.user.name} | Command: /send-ticket-panel | Duration: {duration}ms | Error: {str(e)}")
        logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
        raise  # Re-raise for global error handler


def setup(bot):
    """Setup function for the command"""
    bot.add_application_command(send_ticket_panel)
