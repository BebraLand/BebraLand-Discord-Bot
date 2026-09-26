import discord

from src.features.tickets.view.CloseTicketView import CloseTicketView
from src.features.tickets.view.TicketControlPanel import TicketControlPanel
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.send.send_ticket_panel_message import (
    is_ticket_panel_message,
    refresh_ticket_panel_message,
)

logger = get_cool_logger(__name__)


async def register_persistent_ticket_views(bot):
    try:
        db = await get_db()
        tickets = await db.get_all_tickets()
        registered = 0
        for t in tickets:
            channel_id = t.get("channel_id")
            if not channel_id:
                continue
            channel = bot.get_channel(channel_id)
            if not channel:
                continue
            try:
                user = channel.guild.get_member(
                    int(t.get("user_id"))
                ) or await bot.fetch_user(int(t.get("user_id")))
            except Exception:
                user = await bot.fetch_user(int(t.get("user_id")))

            if t.get("status") == "open":
                view = CloseTicketView(t.get("id"), user, t.get("issue") or "")
            else:
                view = TicketControlPanel(t.get("id"), user, t.get("issue") or "")

            bot.add_view(view)
            registered += 1

        logger.info(f"Registered persistent views for {registered} ticket(s)")

        refreshed = 0
        for guild in bot.guilds:
            panels = await db.get_ticket_panel_states(guild.id)
            if (
                not panels
                and not await db.ticket_panel_discovery_done(guild.id)
                and bot.user
            ):
                skipped_channels = 0
                discovered = 0
                saved_all = True
                for channel in guild.text_channels:
                    try:
                        async for message in channel.history(limit=100):
                            if is_ticket_panel_message(message, bot.user.id):
                                if await db.add_ticket_panel_state(
                                    guild.id, channel.id, message.id
                                ):
                                    discovered += 1
                                else:
                                    saved_all = False
                    except discord.Forbidden:
                        skipped_channels += 1
                    except discord.HTTPException as error:
                        saved_all = False
                        logger.warning(
                            f"Could not inspect ticket panel history in {channel.id}: {error}"
                        )

                if saved_all:
                    if not await db.mark_ticket_panel_discovery_done(guild.id):
                        logger.error(
                            f"Could not save ticket panel discovery state for guild {guild.id}"
                        )
                else:
                    logger.error(
                        f"Could not save every discovered ticket panel in guild {guild.id}; "
                        "will retry discovery on the next startup"
                    )
                logger.info(
                    f"Discovered {discovered} existing ticket panel(s) in guild {guild.id}; "
                    f"skipped {skipped_channels} channel(s) without history access"
                )

            for panel in await db.get_ticket_panel_states(guild.id):
                try:
                    channel = bot.get_channel(panel["channel_id"])
                    if channel is None:
                        channel = await bot.fetch_channel(panel["channel_id"])
                    message = await channel.fetch_message(panel["message_id"])
                    await refresh_ticket_panel_message(message)
                    refreshed += 1
                except discord.NotFound:
                    await db.remove_ticket_panel_state(guild.id, panel["message_id"])
                    logger.info(
                        f"Removed missing ticket panel {panel.get('message_id')}"
                    )
                except discord.Forbidden as error:
                    logger.warning(
                        f"Could not refresh ticket panel {panel.get('message_id')}: {error}"
                    )
                except Exception as error:
                    logger.error(
                        f"Could not refresh ticket panel {panel.get('message_id')}: {error}"
                    )

        logger.info(f"Refreshed {refreshed} ticket panel(s) from current config")
    except Exception as e:
        logger.error(f"Failed to register persistent ticket views: {e}")
