import discord

from config.config import config as bot_config
from src.features.applications.config import get_application_config_value
from src.features.applications.service import (
    build_application_client_embed,
    submit_application_answers,
)
from src.utils.database import get_db, get_language
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class ApplicationModal(discord.ui.Modal):
    def __init__(self, form_config: dict):
        self.form_config = form_config
        super().__init__(title=form_config.get("formTitle", "Application"))
        self._add_questions(form_config.get("questions", []))

    def _add_questions(self, questions: list[dict]) -> None:
        for index, question in enumerate(questions, start=1):
            style = (
                discord.InputTextStyle.short
                if question.get("type") == "text"
                else discord.InputTextStyle.long
            )
            self.add_item(
                discord.ui.InputText(
                    style=style,
                    label=question["question"],
                    placeholder=question.get("placeholder", ""),
                    required=question.get("required", True),
                    min_length=question.get("min", 1),
                    max_length=question.get("max", 900),
                    custom_id=f"application_q_{index}",
                )
            )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        db = await get_db()
        lang = await get_language(interaction.user.id)
        if interaction.user.bot:
            logger.info(
                f"Application submit blocked for bot user {interaction.user.id}"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.bots_cannot_apply",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not get_application_config_value("review_channel_id"):
            logger.info(
                f"Application submit blocked for {interaction.user.id}: review channel not configured"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.not_configured",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        existing = await db.get_pending_application_by_user(
            str(interaction.user.id), interaction.guild.id
        )
        if existing:
            logger.info(
                f"Application submit blocked for {interaction.user.id}: pending application #{existing['id']}"
            )
            embed = build_application_client_embed(
                "common.info",
                "applications.already_pending",
                lang,
                bot_config.embeds.info_color,
                interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        accepted = await db.get_application_by_user_status(
            str(interaction.user.id), interaction.guild.id, "accepted"
        )
        if accepted:
            logger.info(
                f"Application submit blocked for {interaction.user.id}: accepted application #{accepted['id']}"
            )
            embed = build_application_client_embed(
                "common.info",
                "applications.already_accepted",
                lang,
                bot_config.embeds.info_color,
                interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
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
                f"Application submit blocked for {interaction.user.id}: rejected application #{latest['id']} and reapply disabled"
            )
            embed = build_application_client_embed(
                "common.error",
                "applications.cannot_reapply",
                lang,
                bot_config.embeds.failed_color,
                interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        questions = self.form_config.get("questions", [])
        answers = []
        for index, child in enumerate(self.children):
            if not isinstance(child, discord.ui.InputText):
                continue
            question = questions[index] if index < len(questions) else {}
            answers.append(
                {
                    "question": question.get("question", child.label),
                    "value": child.value[:900],
                }
            )

        result = await submit_application_answers(
            interaction.guild, interaction.user, answers, interaction
        )

        await interaction.followup.send(
            embed=result.embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
