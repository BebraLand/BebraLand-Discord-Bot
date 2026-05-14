import discord

from config.config import config as bot_config
from src.features.events.service import (
    build_event_notice_embed,
    build_event_response_embed,
    refresh_event_message,
)
from src.utils.database import get_db, get_language
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class EventRegistrationView(discord.ui.View):
    def __init__(
        self,
        event_id: int,
        disabled: bool = False,
        check_in_enabled: bool = False,
        check_in_open: bool = False,
    ):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.join_button.custom_id = f"event_join_{event_id}"
        self.leave_button.custom_id = f"event_leave_{event_id}"
        self.check_in_button.custom_id = f"event_check_in_{event_id}"
        self.join_button.disabled = disabled
        self.leave_button.disabled = disabled
        self.check_in_button.disabled = disabled or not check_in_open
        if not check_in_enabled:
            self.remove_item(self.check_in_button)

    @discord.ui.button(
        label="Join",
        style=discord.ButtonStyle.success,
        custom_id="event_join",
    )
    async def join_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=True)
        locale = await get_language(interaction.user.id)
        db = await get_db()
        status = await db.register_event_user(
            self.event_id,
            str(interaction.user.id),
        )

        if status == "exists":
            await interaction.followup.send(
                embed=build_event_response_embed(
                    "already_registered",
                    locale,
                    interaction,
                    tone="info",
                ),
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return
        if status is None:
            await interaction.followup.send(
                embed=build_event_response_embed(
                    "not_open",
                    locale,
                    interaction,
                    tone="failed",
                ),
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        await refresh_event_message(interaction.client, self.event_id)
        key = "joined_main" if status == "main" else "joined_backup"
        await interaction.followup.send(
            embed=build_event_response_embed(key, locale, interaction),
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(
            f"User {interaction.user.id} joined event {self.event_id} as {status}"
        )

    @discord.ui.button(
        label="Leave",
        style=discord.ButtonStyle.secondary,
        custom_id="event_leave",
    )
    async def leave_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=True)
        locale = await get_language(interaction.user.id)
        db = await get_db()
        result = await db.unregister_event_user(
            self.event_id,
            str(interaction.user.id),
        )

        if result is None:
            await interaction.followup.send(
                embed=build_event_response_embed(
                    "not_registered",
                    locale,
                    interaction,
                    tone="info",
                ),
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        await refresh_event_message(interaction.client, self.event_id)
        await interaction.followup.send(
            embed=build_event_response_embed("left", locale, interaction),
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )

        if result.isdigit():
            try:
                event = await db.get_event(self.event_id)
                if not event:
                    return
                user = await interaction.client.fetch_user(int(result))
                promoted_locale = await get_language(result)
                await user.send(
                    embed=build_event_notice_embed(
                        event,
                        promoted_locale,
                        "promoted_title",
                        "promoted_description",
                        interaction.client,
                        tone="success",
                    )
                )
            except discord.DiscordException:
                logger.info(
                    f"Could not notify promoted user {result} for event {self.event_id}"
                )

    @discord.ui.button(
        label="Check in",
        style=discord.ButtonStyle.primary,
        custom_id="event_check_in",
    )
    async def check_in_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=True)
        locale = await get_language(interaction.user.id)
        db = await get_db()
        result = await db.check_in_event_user(
            self.event_id,
            str(interaction.user.id),
        )

        if result in {"checked", "backup_checked"}:
            await refresh_event_message(interaction.client, self.event_id)
            key = "checked_in" if result == "checked" else "backup_checked_in"
            await interaction.followup.send(
                embed=build_event_response_embed(key, locale, interaction),
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        if result == "already":
            key = "already_checked_in"
            tone = "info"
        elif result == "not_registered":
            key = "not_registered"
            tone = "info"
        else:
            key = "check_in_not_open"
            tone = "failed"

        await interaction.followup.send(
            embed=build_event_response_embed(key, locale, interaction, tone=tone),
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
