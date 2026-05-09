import discord

from src.features.applications.config import REASON_MAX


class ApplicationReasonModal(discord.ui.Modal):
    def __init__(self, review_view, status: str):
        self.review_view = review_view
        self.status = status
        title = "Accept Application" if status == "accepted" else "Reject Application"
        super().__init__(title=title)
        self.reason = discord.ui.InputText(
            style=discord.InputTextStyle.long,
            label="Reason",
            placeholder="Reason shown to staff and sent to the applicant",
            required=True,
            min_length=1,
            max_length=REASON_MAX,
            custom_id="application_decision_reason",
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await self.review_view.decide(interaction, self.status, self.reason.value)
