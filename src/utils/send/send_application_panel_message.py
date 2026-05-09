from src.features.applications.view.ApplicationPanel import (
    ApplicationPanel,
    build_application_panel_embed,
)


async def send_application_panel_message(selected_channel):
    from src.utils.bot_instance import get_bot

    bot = get_bot()

    channel = bot.get_channel(selected_channel)
    if not channel:
        channel = await bot.fetch_channel(selected_channel)
    await channel.send(embed=build_application_panel_embed(bot), view=ApplicationPanel())
