from src.features.tickets.view.TicketPanel import TicketPanel, build_ticket_panel_embed


async def send_ticket_panel_message(selected_channel):
    from src.utils.bot_instance import get_bot

    bot = get_bot()

    channel = bot.get_channel(selected_channel)
    if not channel:
        channel = await bot.fetch_channel(selected_channel)
    await channel.send(embed=build_ticket_panel_embed(bot), view=TicketPanel())
