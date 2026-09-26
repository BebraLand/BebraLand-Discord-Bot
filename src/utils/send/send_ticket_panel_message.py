import discord

from src.features.tickets.view.TicketPanel import TicketPanel, build_ticket_panel_embeds
from src.utils.database import get_db
from src.utils.embed_media import attach_remote_embed_media
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


def is_ticket_panel_message(message: discord.Message, bot_user_id: int) -> bool:
    if message.author.id != bot_user_id:
        return False
    return any(
        getattr(component, "custom_id", None) == "ticket_dropdown"
        for row in message.components
        for component in getattr(row, "children", [])
    )


async def refresh_ticket_panel_message(message: discord.Message) -> None:
    from src.utils.bot_instance import get_bot

    bot = get_bot()
    embeds = build_ticket_panel_embeds(bot)
    files = await attach_remote_embed_media(embeds)
    attachments = []
    if not files and message.attachments:
        attachments = message.attachments
        embeds[0].set_image(url=f"attachment://{attachments[0].filename}")
    await message.edit(
        embeds=embeds,
        attachments=attachments,
        files=files,
        view=TicketPanel(),
    )


async def send_ticket_panel_message(selected_channel):
    from src.utils.bot_instance import get_bot

    bot = get_bot()

    channel = bot.get_channel(selected_channel)
    if not channel:
        channel = await bot.fetch_channel(selected_channel)

    db = await get_db()
    panels = await db.get_ticket_panel_states(channel.guild.id)
    messages = []
    for panel in panels:
        if panel.get("channel_id") != channel.id:
            continue
        try:
            messages.append(await channel.fetch_message(panel["message_id"]))
        except discord.NotFound:
            await db.remove_ticket_panel_state(channel.guild.id, panel["message_id"])

    if not messages and bot.user:
        try:
            async for message in channel.history(limit=100):
                if is_ticket_panel_message(message, bot.user.id):
                    messages.append(message)
        except discord.Forbidden:
            logger.warning(
                f"Cannot inspect recent messages in channel {channel.id}; sending a new ticket panel"
            )

    if messages:
        for message in messages:
            await refresh_ticket_panel_message(message)
            if not await db.add_ticket_panel_state(
                channel.guild.id, channel.id, message.id
            ):
                logger.error(f"Failed to save ticket panel message {message.id}")
        logger.info(
            f"Updated {len(messages)} existing ticket panel(s) in channel {channel.id}"
        )
        return

    embeds = build_ticket_panel_embeds(bot)
    files = await attach_remote_embed_media(embeds)
    message = await channel.send(embeds=embeds, files=files, view=TicketPanel())
    if not await db.add_ticket_panel_state(
        channel.guild.id, channel.id, message.id
    ):
        logger.error(f"Failed to save ticket panel message {message.id}")
