import asyncio
import io
from datetime import datetime
from typing import Optional

import discord

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import (
    build_embed_from_data,
    build_news_placeholders,
    get_embed_icon,
    replace_placeholders,
)
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def scheduled_send_news_task(user_id: int, guild_id: int, payload: dict) -> None:
    """Entry point for APScheduler to send news without a live context."""
    from src.utils.bot_instance import get_bot

    bot = get_bot()
    if not bot:
        logger.error("Bot instance not available for scheduled_send_news_task")
        return

    guild = bot.get_guild(guild_id)
    if not guild:
        try:
            guild = await bot.fetch_guild(guild_id)
        except Exception as e:
            logger.error(f"Failed to fetch guild {guild_id}: {e}")
            return

    user = bot.get_user(user_id)
    if not user:
        try:
            user = await bot.fetch_user(user_id)
        except Exception as e:
            logger.error(f"Failed to fetch user {user_id}: {e}")

    # Reconstruct arguments from payload
    news_contents = payload.get("news_contents", {})
    embed_json = payload.get("embed_json")
    send_to_all_users = payload.get("send_to_all_users", False)
    role_id = payload.get("role_id")
    send_to_all_channels = payload.get("send_to_all_channels", False)
    send_ghost_ping = payload.get("send_ghost_ping", False)
    send_image_before_or_after_news = payload.get("image_position", "Before")

    # Reconstruct image if present in payload
    image_path = payload.get("image_path")
    image_filename = payload.get("image_filename")
    image_bytes = None

    if image_path:
        import os

        try:
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                # Optional: clean up the scheduled file after reading
                os.remove(image_path)
        except Exception as e:
            logger.error(f"Failed to read scheduled image {image_path}: {e}")

    logger.info(f"Executing scheduled news broadcast by user {user_id}")

    # We will simulate the send_news logic without ctx
    user_lang = await get_language(user_id)
    start_time = datetime.utcnow()

    def _content_for(locale: str) -> str:
        if isinstance(news_contents, dict):
            try:
                locale_short = str(locale).split("-")[0].split("_")[0].lower()
            except Exception:
                locale_short = str(locale).lower() if locale else ""
            return (
                news_contents.get(locale)
                or news_contents.get(locale_short)
                or news_contents.get("en")
                or ""
            )
        return str(news_contents)

    bot_user = bot.user
    bot_avatar = bot_user.avatar.url if bot_user.avatar else bot_user.default_avatar.url

    def _build_embed(
        content_text: str, include_image: bool, locale: str = None
    ) -> Optional[discord.Embed]:
        image_url = ""
        if include_image and image_filename:
            image_url = f"attachment://{image_filename}"
        replacements = build_news_placeholders(content_text, bot_avatar, image_url)
        locale_embed = None
        if isinstance(news_contents, dict) and locale:
            candidate = news_contents.get(locale)
            if isinstance(candidate, dict):
                locale_embed = candidate

        embed_source = (
            locale_embed
            if locale_embed is not None
            else (embed_json if isinstance(embed_json, dict) else None)
        )

        if embed_source and isinstance(embed_source, dict):
            try:
                processed = replace_placeholders(embed_source, replacements)
                if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                    processed["footer"] = {
                        "text": constants.DISCORD_MESSAGE_TRADEMARK,
                        "icon_url": guild.icon.url if guild.icon else "",
                    }
                return build_embed_from_data(processed)
            except Exception:
                return None

        try:
            default_data = {
                "description": content_text,
            }
            if image_url:
                default_data["image"] = {"url": image_url}
            if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                default_data["footer"] = {
                    "text": constants.DISCORD_MESSAGE_TRADEMARK,
                    "icon_url": guild.icon.url if guild.icon else "",
                }
            return build_embed_from_data(default_data)
        except Exception:
            return None

    success_count = 0
    fail_count = 0
    sent_channels: list[str] = []
    sent_users: list[str] = []

    failed_channels = []
    if send_to_all_channels:
        channels_to_send = [
            (getattr(constants, "NEWS_ENGLISH_CHANNEL_ID", None), "en"),
            (getattr(constants, "NEWS_RUSSIAN_CHANNEL_ID", None), "ru"),
            (getattr(constants, "NEWS_LITHUANIAN_CHANNEL_ID", None), "lt"),
        ]
        for channel_id, locale in channels_to_send:
            if not channel_id:
                continue
            channel = bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except Exception as e:
                    failed_channels.append((channel_id, str(e)))
                    fail_count += 1
                    continue
            try:
                embed = _build_embed(
                    _content_for(locale), include_image=False, locale=locale
                )

                if embed:
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await channel.send(embed=embed)
                    if image_bytes and send_image_before_or_after_news == "After":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                else:
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await channel.send(_content_for(locale))
                    if image_bytes and send_image_before_or_after_news == "After":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )

                if send_ghost_ping and locale == "en":
                    ping_msg = await channel.send("@everyone")
                    await ping_msg.delete()

                success_count += 1
                try:
                    sent_channels.append(
                        f"<#{channel.id}> ({getattr(channel, 'name', 'channel')}, {locale})"
                    )
                except Exception:
                    sent_channels.append(f"<#{channel.id}> ({locale})")
                await asyncio.sleep(1)
            except Exception as e:
                failed_channels.append((channel.id, str(e)))
                fail_count += 1

    failed_users = []
    if send_to_all_users or role_id:
        members = []
        if role_id:
            role = discord.utils.get(guild.roles, id=role_id)
            if role:
                members.extend(role.members)
        else:
            members.extend(guild.members)

        unique_members = {m.id: m for m in members if not m.bot}

        for member in unique_members.values():
            try:
                member_lang = await get_language(member.id)
                embed = _build_embed(
                    _content_for(member_lang), include_image=False, locale=member_lang
                )

                if embed:
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await member.send(embed=embed)
                    if image_bytes and send_image_before_or_after_news == "After":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                else:
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await member.send(_content_for(member_lang))
                    if image_bytes and send_image_before_or_after_news == "After":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )

                success_count += 1
                try:
                    sent_users.append(
                        f"<@{member.id}> ({getattr(member, 'name', 'user')})"
                    )
                except Exception:
                    sent_users.append(f"<@{member.id}>")
                await asyncio.sleep(1)
            except discord.Forbidden:
                failed_users.append((member.id, "Forbidden"))
                fail_count += 1
            except Exception as e:
                failed_users.append((member.id, str(e)))
                fail_count += 1

    elapsed_seconds = (datetime.utcnow() - start_time).total_seconds()

    # Send summary DM back to the user who scheduled it
    if user:
        try:
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} {_('news.sent_summary', user_lang)}",
                color=constants.SUCCESS_EMBED_COLOR,
            )
            embed.add_field(
                name=_("common.successful", user_lang),
                value=str(success_count),
                inline=True,
            )
            embed.add_field(
                name=_("common.failed", user_lang), value=str(fail_count), inline=True
            )
            embed.add_field(
                name=_("common.duration", user_lang),
                value=f"{elapsed_seconds:.2f}s",
                inline=True,
            )

            if sent_channels:
                max_show = 20
                display = ", ".join(sent_channels[:max_show])
                if len(sent_channels) > max_show:
                    display += _("news.and_more", user_lang)
                embed.add_field(
                    name=_("common.channels", user_lang), value=display, inline=False
                )
            if sent_users:
                max_show = 20
                display = ", ".join(sent_users[:max_show])
                if len(sent_users) > max_show:
                    display += _("news.and_more", user_lang)
                embed.add_field(
                    name=_("common.users", user_lang), value=display, inline=False
                )

            if fail_count > 0:
                if failed_channels:
                    ch_details = "\n".join(
                        [f"• {cid}: {err}" for cid, err in failed_channels[:10]]
                    )
                    embed.add_field(
                        name=_("news.failed_channels", user_lang),
                        value=ch_details,
                        inline=False,
                    )
                if failed_users:
                    user_details = "\n".join(
                        [f"• {uid}: {err}" for uid, err in failed_users[:10]]
                    )
                    embed.add_field(
                        name=_("news.failed_users", user_lang),
                        value=user_details,
                        inline=False,
                    )

            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=guild.icon.url if guild.icon else "",
            )

            await user.send(embed=embed)
        except Exception as e:
            logger.error(f"Could not send news summary DM to {user.id}: {e}")

    logger.info(
        f"Scheduled news broadcast completed: {success_count} sent, {fail_count} failed"
    )


async def send_news(
    bot: discord.Bot,
    ctx: discord.ApplicationContext,
    news_contents: dict,
    embed_json: dict,
    image: Optional[discord.Attachment],
    send_image_before_or_after_news: str,
    send_to_all_users: bool,
    sent_to_all_users_with_role: Optional[discord.Role],
    send_to_all_channels: bool,
    send_ghost_ping: bool,
) -> None:
    """Execute the news sending task and post a summary to the admin.

    This function mirrors the previous `_send_news_task` method, but extracted
    to a standalone module so the command file stays small and focused.
    """
    # Debug: log incoming contents to help diagnose locale selection issues
    try:
        if isinstance(news_contents, dict):
            logger.debug(
                f"send_news: news_contents keys={list(news_contents.keys())}, embed_json_present={bool(embed_json)}"
            )
        else:
            logger.debug(f"send_news: news_contents scalar: {str(news_contents)[:200]}")
    except Exception:
        logger.debug("send_news: failed to log news_contents")
    # Also log at INFO so it's visible with default logging level
    try:
        logger.info(
            f"send_news: news_contents={news_contents}, embed_json_present={bool(embed_json)}"
        )
    except Exception:
        logger.info("send_news: could not stringify news_contents")

    user_lang = await get_language(ctx.user.id)
    start_time = datetime.utcnow()

    # Helper to choose content for a locale, falling back to English
    def _content_for(locale: str) -> str:
        if isinstance(news_contents, dict):
            # Normalize locale: accept 'ru', 'ru_RU', 'ru-RU', etc.
            try:
                locale_short = str(locale).split("-")[0].split("_")[0].lower()
            except Exception:
                locale_short = str(locale).lower() if locale else ""
            return (
                news_contents.get(locale)
                or news_contents.get(locale_short)
                or news_contents.get("en")
                or ""
            )
        return str(news_contents)

    # Prepare bot avatar (no external template; we'll build a default embed)
    bot_user = getattr(ctx.bot, "user", None)
    bot_avatar = ""
    if bot_user:
        if bot_user.avatar:
            bot_avatar = bot_user.avatar.url
        else:
            bot_avatar = bot_user.default_avatar.url

    # Read image once if provided
    image_bytes = None
    image_filename = None
    if image:
        try:
            image_bytes = await image.read()
            image_filename = image.filename
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            image_bytes = None
            image_filename = None

    def _build_embed(
        content_text: str, include_image: bool, locale: str = None
    ) -> Optional[discord.Embed]:
        image_url = ""
        if include_image and image_filename:
            image_url = f"attachment://{image_filename}"
        replacements = build_news_placeholders(content_text, bot_avatar, image_url)
        # Prefer a locale-specific embed JSON if provided in news_contents
        locale_embed = None
        try:
            if isinstance(news_contents, dict) and locale:
                candidate = news_contents.get(locale)
                if isinstance(candidate, dict):
                    locale_embed = candidate
        except Exception:
            locale_embed = None

        embed_source = (
            locale_embed
            if locale_embed is not None
            else (embed_json if isinstance(embed_json, dict) else None)
        )

        # If an embed JSON source exists, use it preferentially
        if embed_source and isinstance(embed_source, dict):
            try:
                processed = replace_placeholders(embed_source, replacements)
                if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                    processed["footer"] = {
                        "text": constants.DISCORD_MESSAGE_TRADEMARK,
                        "icon_url": get_embed_icon(ctx),
                    }
                return build_embed_from_data(processed)
            except Exception:
                return None
        # Build a sensible default embed from content and optional image
        try:
            default_data = {
                "description": content_text,
            }
            if image_url:
                default_data["image"] = {"url": image_url}
            if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                default_data["footer"] = {
                    "text": constants.DISCORD_MESSAGE_TRADEMARK,
                    "icon_url": get_embed_icon(ctx),
                }
            return build_embed_from_data(default_data)
        except Exception:
            return None

    success_count = 0
    fail_count = 0
    # Track recipients for summary
    sent_channels: list[str] = []
    sent_users: list[str] = []

    # Send to configured language-specific channels
    failed_channels = []
    if send_to_all_channels:
        channels_to_send = [
            (getattr(constants, "NEWS_ENGLISH_CHANNEL_ID", None), "en"),
            (getattr(constants, "NEWS_RUSSIAN_CHANNEL_ID", None), "ru"),
            (getattr(constants, "NEWS_LITHUANIAN_CHANNEL_ID", None), "lt"),
        ]
        for channel_id, locale in channels_to_send:
            if not channel_id:
                continue
            # Log selection that will be used for this channel
            try:
                chosen = _content_for(locale)
                logger.info(
                    f"send_news: channel {channel_id} locale={locale} will use content_preview={str(chosen)[:60]}"
                )
            except Exception:
                logger.info(
                    f"send_news: channel {channel_id} locale={locale} could not determine content"
                )
            channel = bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except Exception as e:
                    logger.error(f"Failed to fetch channel {channel_id}: {e}")
                    failed_channels.append((channel_id, str(e)))
                    fail_count += 1
                    continue
            try:
                # Build embed and send; image is always a separate message
                embed = _build_embed(
                    _content_for(locale), include_image=False, locale=locale
                )

                if embed:
                    # Send image separately before the embed if requested
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await channel.send(embed=embed)
                    # Or send image after the embed if requested
                    if image_bytes and send_image_before_or_after_news == "After":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                else:
                    # Fallback to plain text
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await channel.send(_content_for(locale))
                    if image_bytes and send_image_before_or_after_news == "After":
                        await channel.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )

                # Send ghost ping after content (English channel only)
                if send_ghost_ping and locale == "en":
                    ping_msg = await channel.send("@everyone")
                    await ping_msg.delete()

                success_count += 1
                # Track channel recipient mention for summary
                try:
                    sent_channels.append(
                        f"<#{channel.id}> ({getattr(channel, 'name', 'channel')}, {locale})"
                    )
                except Exception:
                    sent_channels.append(f"<#{channel.id}> ({locale})")
                await asyncio.sleep(1)  # Rate limit protection
            except Exception as e:
                logger.error(f"Failed to send news to channel {channel.id}: {e}")
                failed_channels.append((channel.id, str(e)))
                fail_count += 1

    # Send to users (DMs)
    failed_users = []
    if send_to_all_users or sent_to_all_users_with_role:
        members = []
        if sent_to_all_users_with_role:
            # Role in the current guild only
            role = discord.utils.get(ctx.guild.roles, id=sent_to_all_users_with_role.id)
            if role:
                members.extend(role.members)
        else:
            # All members in the current guild
            members.extend(ctx.guild.members)

        # Remove duplicates and bots
        unique_members = {m.id: m for m in members if not m.bot}

        for member in unique_members.values():
            try:
                # Build embed and send via DM; image is always a separate message
                member_lang = await get_language(member.id)
                # Log which content will be used for this member
                try:
                    m_chosen = _content_for(member_lang)
                    logger.info(
                        f"send_news: DM to {member.id} lang={member_lang} will use content_preview={str(m_chosen)[:60]}"
                    )
                except Exception:
                    logger.info(
                        f"send_news: DM to {member.id} lang={member_lang} could not determine content"
                    )
                embed = _build_embed(
                    _content_for(member_lang), include_image=False, locale=member_lang
                )

                if embed:
                    # Send image separately before the embed if requested
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await member.send(embed=embed)
                    # Or send image after the embed if requested
                    if image_bytes and send_image_before_or_after_news == "After":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                else:
                    # Fallback to plain text
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )
                    await member.send(_content_for(member_lang))
                    if image_bytes and send_image_before_or_after_news == "After":
                        await member.send(
                            file=discord.File(
                                fp=io.BytesIO(image_bytes), filename=image_filename
                            )
                        )

                success_count += 1
                # Track user recipient mention for summary
                try:
                    sent_users.append(
                        f"<@{member.id}> ({getattr(member, 'name', 'user')})"
                    )
                except Exception:
                    sent_users.append(f"<@{member.id}>")
                await asyncio.sleep(1)  # Rate limit protection
            except discord.Forbidden:
                logger.debug(f"Cannot send DM to {member.name}({member.id})")
                failed_users.append((member.id, "Forbidden"))
                fail_count += 1
            except Exception as e:
                logger.error(f"Failed to send news to user {member.id}: {e}")
                failed_users.append((member.id, str(e)))
                fail_count += 1

    # Send summary as a rich embed with metrics
    elapsed_seconds = (datetime.utcnow() - start_time).total_seconds()
    try:
        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('news.sent_summary', user_lang)}",
            color=constants.SUCCESS_EMBED_COLOR,
        )
        embed.add_field(
            name=_("common.successful", user_lang),
            value=str(success_count),
            inline=True,
        )
        embed.add_field(
            name=_("common.failed", user_lang), value=str(fail_count), inline=True
        )
        embed.add_field(
            name=_("common.duration", user_lang),
            value=f"{elapsed_seconds:.2f}s",
            inline=True,
        )
        # Include recipients list (limit to avoid hitting embed size limits)
        if sent_channels:
            max_show = 20
            display = ", ".join(sent_channels[:max_show])
            if len(sent_channels) > max_show:
                display += _("news.and_more", user_lang)
            embed.add_field(
                name=_("common.channels", user_lang), value=display, inline=False
            )
        if sent_users:
            max_show = 20
            display = ", ".join(sent_users[:max_show])
            if len(sent_users) > max_show:
                display += _("news.and_more", user_lang)
            embed.add_field(
                name=_("common.users", user_lang), value=display, inline=False
            )

        # Include brief failure details (limit to 10 entries each)
        if fail_count > 0:
            if failed_channels:
                ch_details = "\n".join(
                    [f"• {cid}: {err}" for cid, err in failed_channels[:10]]
                )
                embed.add_field(
                    name=_("news.failed_channels", user_lang),
                    value=ch_details,
                    inline=False,
                )
            if failed_users:
                user_details = "\n".join(
                    [f"• {uid}: {err}" for uid, err in failed_users[:10]]
                )
                embed.add_field(
                    name=_("news.failed_users", user_lang),
                    value=user_details,
                    inline=False,
                )

        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx)
        )

        await ctx.followup.send(embed=embed, ephemeral=True)
    except Exception:
        # If context is no longer valid or embed fails, log instead
        logger.info(
            f"News sent: {success_count} successful, {fail_count} failed in {elapsed_seconds:.2f}s"
        )

    logger.info(
        f"News broadcast completed by {ctx.user.name}({ctx.user.id}): {success_count} sent, {fail_count} failed"
    )


async def preview_news(
    bot: discord.Bot,
    ctx: discord.ApplicationContext,
    news_contents: dict,
    embed_json: dict,
    image: Optional[discord.Attachment],
    send_image_before_or_after_news: str,
    send_to_all_users: bool,
    sent_to_all_users_with_role: Optional[discord.Role],
    send_to_all_channels: bool,
    send_ghost_ping: bool,
) -> None:
    """Show an ephemeral preview of what will be sent, and DM the invoker.

    Due to Discord limitations, ephemeral messages can only be shown to the
    invoking user in the current interaction context, not "in all channels".
    This preview composes sample embeds for locales and lists targets.
    """
    # Debug: log incoming contents for preview
    try:
        if isinstance(news_contents, dict):
            logger.debug(
                f"preview_news: news_contents keys={list(news_contents.keys())}, embed_json_present={bool(embed_json)}"
            )
        else:
            logger.debug(
                f"preview_news: news_contents scalar: {str(news_contents)[:200]}"
            )
    except Exception:
        logger.debug("preview_news: failed to log news_contents")

    user_lang = await get_language(ctx.user.id)

    # Helper to choose content for a locale, falling back to English
    def _content_for(locale: str) -> str:
        if isinstance(news_contents, dict):
            # Normalize locale: accept 'ru', 'ru_RU', 'ru-RU', etc.
            try:
                locale_short = str(locale).split("-")[0].split("_")[0].lower()
            except Exception:
                locale_short = str(locale).lower() if locale else ""
            return (
                news_contents.get(locale)
                or news_contents.get(locale_short)
                or news_contents.get("en")
                or ""
            )
        return str(news_contents)

    bot_user = getattr(ctx.bot, "user", None)
    bot_avatar = ""
    if bot_user:
        bot_avatar = bot_user.display_avatar.url

    # Read image once if provided
    image_bytes = None
    image_filename = None
    if image:
        try:
            image_bytes = await image.read()
            image_filename = image.filename
        except Exception:
            image_bytes = None
            image_filename = None

    def _make_embed_for(locale: str) -> Optional[discord.Embed]:
        content_text = _content_for(locale)
        replacements = build_news_placeholders(
            content_text,
            bot_avatar,
            f"attachment://{image_filename}" if image_filename else "",
        )
        if embed_json and isinstance(embed_json, dict):
            try:
                processed = replace_placeholders(embed_json, replacements)
                if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                    processed["footer"] = {
                        "text": constants.DISCORD_MESSAGE_TRADEMARK,
                        "icon_url": get_embed_icon(ctx),
                    }
                return build_embed_from_data(processed)
            except Exception:
                pass
        try:
            default_data = {"description": content_text}
            if image_filename:
                default_data["image"] = {"url": f"attachment://{image_filename}"}
            if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                default_data["footer"] = {
                    "text": constants.DISCORD_MESSAGE_TRADEMARK,
                    "icon_url": get_embed_icon(ctx),
                }
            return build_embed_from_data(default_data)
        except Exception:
            return None

    # Compose preview embeds for locales
    title = discord.Embed(
        title=f"{lang_constants.EYES_EMOJI} {_('news.preview', user_lang)}",
        description=_("news.preview_description", user_lang)
        + f"\n\n{constants.DISCORD_MESSAGE_TRADEMARK}",
        color=constants.INFO_EMBED_COLOR,
    )
    title.set_footer(
        text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx)
    )

    locale_embeds = [
        ("EN", _make_embed_for("en")),
        ("RU", _make_embed_for("ru")),
        ("LT", _make_embed_for("lt")),
    ]
    for label, e in locale_embeds:
        # Do not modify embed title; label will be sent as message content
        if e:
            pass

    # Targets summary
    channels = []
    if send_to_all_channels:
        if getattr(constants, "NEWS_ENGLISH_CHANNEL_ID", None):
            channels.append(f"<#{getattr(constants, 'NEWS_ENGLISH_CHANNEL_ID')}> (EN)")
        if getattr(constants, "NEWS_RUSSIAN_CHANNEL_ID", None):
            channels.append(f"<#{getattr(constants, 'NEWS_RUSSIAN_CHANNEL_ID')}> (RU)")
        if getattr(constants, "NEWS_LITHUANIAN_CHANNEL_ID", None):
            channels.append(
                f"<#{getattr(constants, 'NEWS_LITHUANIAN_CHANNEL_ID')}> (LT)"
            )
    members_count = 0
    if send_to_all_users or sent_to_all_users_with_role:
        members = []
        if sent_to_all_users_with_role:
            role = discord.utils.get(ctx.guild.roles, id=sent_to_all_users_with_role.id)
            if role:
                members.extend([m for m in role.members if not m.bot])
        else:
            members.extend([m for m in ctx.guild.members if not m.bot])
        # unique
        members_count = len({m.id for m in members})

    targets_embed = discord.Embed(
        title=_("news.targets", user_lang),
        color=constants.INFO_EMBED_COLOR,
    )
    if channels:
        targets_embed.add_field(
            name=_("common.channels", user_lang),
            value=", ".join(channels),
            inline=False,
        )
    targets_embed.add_field(
        name=_("common.users", user_lang), value=str(members_count), inline=True
    )
    targets_embed.add_field(
        name=_("news.ghost_ping", user_lang),
        value=str(bool(send_ghost_ping)),
        inline=True,
    )
    targets_embed.add_field(
        name=_("news.image_position", user_lang),
        value=send_image_before_or_after_news,
        inline=True,
    )

    def _make_image_file():
        if image_bytes and image_filename:
            return discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
        return None

    # Send multiple ephemeral messages in sequence
    try:
        await ctx.followup.send(embed=title, ephemeral=True)

        for label, e in locale_embeds:
            if not e:
                continue
            if image_filename and send_image_before_or_after_news == "Before":
                img = _make_image_file()
                if img:
                    await ctx.followup.send(file=img, ephemeral=True)
            await ctx.followup.send(content=f"[{label}]", embed=e, ephemeral=True)
            if image_filename and send_image_before_or_after_news == "After":
                img = _make_image_file()
                if img:
                    await ctx.followup.send(file=img, ephemeral=True)

        await ctx.followup.send(embed=targets_embed, ephemeral=True)
    except Exception:
        # Fallback path if followup fails; use respond
        await ctx.respond(embed=title, ephemeral=True)
        for label, e in locale_embeds:
            if not e:
                continue
            if image_filename and send_image_before_or_after_news == "Before":
                img = _make_image_file()
                if img:
                    await ctx.respond(file=img, ephemeral=True)
            await ctx.respond(content=f"[{label}]", embed=e, ephemeral=True)
            if image_filename and send_image_before_or_after_news == "After":
                img = _make_image_file()
                if img:
                    await ctx.respond(file=img, ephemeral=True)
        await ctx.respond(embed=targets_embed, ephemeral=True)
