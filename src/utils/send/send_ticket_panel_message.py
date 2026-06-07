from src.features.tickets.view.TicketPanel import TicketPanel, build_ticket_panel_embeds
from src.utils.embed_media import attach_remote_embed_media


async def send_ticket_panel_message(selected_channel):
    from src.utils.bot_instance import get_bot

    bot = get_bot()

    channel = bot.get_channel(selected_channel)
    if not channel:
        channel = await bot.fetch_channel(selected_channel)
    embeds = build_ticket_panel_embeds(bot)
    files = await attach_remote_embed_media(embeds)
    await channel.send(embeds=embeds, files=files, view=TicketPanel())
