import discord

from config.config import config as bot_config
from src.features.applications.config import (
    get_application_config_value,
    load_application_form_config,
)
from src.features.applications.service import (
    build_application_client_embed,
    build_application_panel_embed,
    build_application_panel_embeds,
)
from src.utils.database import get_db, get_language
from src.utils.logger import get_cool_logger

from .ApplicationDMFlow import (
    build_application_started_response,
    get_active_application_dm_channel,
    start_application_dm_flow,
)

logger = get_cool_logger(__name__)


class ApplicationPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        form_config = load_application_form_config()
        self.apply_button.label = form_config["panel"]["buttonLabel"]

    @discord.ui.button(
        label="Apply",
        style=discord.ButtonStyle.primary,
        custom_id="application_apply_button",
    )
    async def apply_button(self, button: discord.ui.Button, interaction):
        db = await get_db()
        lang = await get_language(interaction.user.id)
        if interaction.user.bot:
            logger.info(
                f"Application apply blocked for bot user {interaction.user.id}"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.bots_cannot_apply",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        enabled = await db.get_application_enabled(interaction.guild.id)
        if not enabled:
            logger.info(
                f"Application apply blocked for {interaction.user.id}: applications closed"
            )
            embed = build_application_client_embed(
                "common.info",
                "applications.closed",
                lang,
                bot_config.embeds.info_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not get_application_config_value("review_channel_id"):
            logger.info(
                f"Application apply blocked for {interaction.user.id}: review channel not configured"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.not_configured",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        existing = await db.get_pending_application_by_user(
            str(interaction.user.id), interaction.guild.id
        )
        if existing:
            logger.info(
                f"Application apply blocked for {interaction.user.id}: pending application #{existing['id']}"
            )
            embed = build_application_client_embed(
                "common.info",
                "applications.already_pending",
                lang,
                bot_config.embeds.info_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        accepted = await db.get_application_by_user_status(
            str(interaction.user.id), interaction.guild.id, "accepted"
        )
        if accepted:
            logger.info(
                f"Application apply blocked for {interaction.user.id}: accepted application #{accepted['id']}"
            )
            embed = build_application_client_embed(
                "common.info",
                "applications.already_accepted",
                lang,
                bot_config.embeds.info_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        latest = await db.get_latest_application_by_user(
            str(interaction.user.id), interaction.guild.id
        )
        if (
            latest
            and latest["status"] == "rejected"
            and not get_application_config_value("allow_reapply_after_reject", True)
        ):
            logger.info(
                f"Application apply blocked for {interaction.user.id}: rejected application #{latest['id']} and reapply disabled"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.cannot_reapply",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        form_config = load_application_form_config()
        if not form_config.get("questions"):
            logger.info(
                f"Application apply blocked for {interaction.user.id}: no application questions configured"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.not_configured",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        active_channel_id = get_active_application_dm_channel(
            interaction.user.id, interaction.guild.id
        )
        if active_channel_id:
            embed, view = build_application_started_response(active_channel_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            dm_channel = await start_application_dm_flow(interaction, form_config)
        except discord.Forbidden:
            logger.info(f"Application DM failed for user {interaction.user.id}")
            embed = discord.Embed(
                title="Could not send DM",
                description=(
                    "Please enable direct messages from this server, then press Apply again."
                ),
                color=bot_config.embeds.failed_color,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed, view = build_application_started_response(dm_channel.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


__all__ = [
    "ApplicationPanel",
    "build_application_panel_embed",
    "build_application_panel_embeds",
]
