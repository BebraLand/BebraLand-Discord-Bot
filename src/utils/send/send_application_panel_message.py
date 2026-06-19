from src.features.applications.view.ApplicationPanel import (
    ApplicationPanel,
    build_application_panel_embeds,
)
from src.utils.embed_media import attach_remote_embed_media


async def send_application_panel_message(selected_channel):
    from src.utils.bot_instance import get_bot

    bot = get_bot()

    channel = bot.get_channel(selected_channel)
    if not channel:
        channel = await bot.fetch_channel(selected_channel)
    embeds = build_application_panel_embeds()
    files = await attach_remote_embed_media(embeds)
    await channel.send(embeds=embeds, files=files, view=ApplicationPanel())
