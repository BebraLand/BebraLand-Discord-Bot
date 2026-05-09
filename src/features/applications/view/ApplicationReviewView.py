import discord

from config.config import config as bot_config
from src.features.applications.config import get_application_config_value
from src.features.applications.service import (
    apply_application_roles,
    build_application_review_embed,
    get_guild_member,
    notify_application_decision,
)
from src.languages.localize import _
from src.utils.auth import is_admin
from src.utils.database import get_db, get_language
from src.utils.logger import get_cool_logger

from .ApplicationReasonModal import ApplicationReasonModal

logger = get_cool_logger(__name__)


class ApplicationReviewView(discord.ui.View):
    def __init__(self, application_id: int, disabled: bool = False):
        super().__init__(timeout=None)
        self.application_id = application_id
        self.accept_button.custom_id = f"application_accept_{application_id}"
        self.reject_button.custom_id = f"application_reject_{application_id}"
        self.accept_reason_button.custom_id = (
            f"application_accept_reason_{application_id}"
        )
        self.reject_reason_button.custom_id = (
            f"application_reject_reason_{application_id}"
        )
        if disabled:
            for item in self.children:
                item.disabled = True

    async def _can_review(self, interaction: discord.Interaction) -> bool:
        if is_admin(interaction.user.id):
            return True

        reviewer_role_id = get_application_config_value("reviewer_role_id")
        if reviewer_role_id and any(
            role.id == int(reviewer_role_id) for role in interaction.user.roles
        ):
            return True

        await interaction.response.send_message(
            "Only application reviewers can use these buttons.", ephemeral=True
        )
        return False

    async def decide(
        self,
        interaction: discord.Interaction,
        status: str,
        reason: str | None = None,
    ) -> None:
        if not await self._can_review(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        db = await get_db()
        application = await db.get_application(self.application_id)
        if not application:
            await interaction.followup.send("Application not found.", ephemeral=True)
            return

        if application["status"] != "pending":
            await interaction.followup.send(
                "This application was already reviewed.", ephemeral=True
            )
            return

        decided = await db.decide_application(
            self.application_id, status, str(interaction.user.id), reason
        )
        if not decided:
            await interaction.followup.send(
                "This application was already reviewed.", ephemeral=True
            )
            return

        guild = interaction.guild
        member = await get_guild_member(guild, int(application["user_id"]))
        user = member or await interaction.client.fetch_user(int(application["user_id"]))

        role_warning = ""
        if member:
            role_ok, role_error = await apply_application_roles(member, status)
            if not role_ok:
                role_warning = f"\nRole update warning: {role_error}"
        else:
            role_warning = "\nRole update warning: applicant is no longer in the server."

        await notify_application_decision(user, status, reason)

        updated = await db.get_application(self.application_id)
        embed = build_application_review_embed(updated, guild, user)
        await interaction.message.edit(
            embed=embed, view=ApplicationReviewView(self.application_id, disabled=True)
        )

        await interaction.followup.send(
            f"Application #{self.application_id} {status}.{role_warning}",
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )

        logger.info(
            f"Application #{self.application_id} {status} by {interaction.user.id}"
        )

    async def _default_decision_reason(self, status: str) -> str:
        db = await get_db()
        application = await db.get_application(self.application_id)
        if not application:
            return ""
        lang = await get_language(int(application["user_id"]))
        key = (
            "applications.decision.default_accept_reason"
            if status == "accepted"
            else "applications.decision.default_reject_reason"
        )
        return _(key, lang)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, row=0)
    async def accept_button(self, button: discord.ui.Button, interaction):
        await self.decide(
            interaction, "accepted", await self._default_decision_reason("accepted")
        )

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, row=0)
    async def reject_button(self, button: discord.ui.Button, interaction):
        await self.decide(
            interaction, "rejected", await self._default_decision_reason("rejected")
        )

    @discord.ui.button(
        label="Accept with reason", style=discord.ButtonStyle.success, row=1
    )
    async def accept_reason_button(self, button: discord.ui.Button, interaction):
        if not await self._can_review(interaction):
            return
        await interaction.response.send_modal(
            ApplicationReasonModal(self, "accepted")
        )

    @discord.ui.button(
        label="Reject with reason", style=discord.ButtonStyle.danger, row=1
    )
    async def reject_reason_button(self, button: discord.ui.Button, interaction):
        if not await self._can_review(interaction):
            return
        await interaction.response.send_modal(
            ApplicationReasonModal(self, "rejected")
        )
