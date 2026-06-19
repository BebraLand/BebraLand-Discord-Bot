import asyncio
import io
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import discord

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import (
    build_embeds_from_message_data,
    build_news_placeholders,
    get_embed_icon,
    replace_placeholders,
)
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


def _normalize_role_ids(role_source) -> list[int]:
    if not role_source:
        return []
    if isinstance(role_source, discord.Role):
        return [role_source.id]
    if isinstance(role_source, int):
        return [role_source]
    if isinstance(role_source, (list, tuple, set)):
        role_ids = []
        for item in role_source:
            if isinstance(item, discord.Role):
                role_ids.append(item.id)
            else:
                try:
                    role_ids.append(int(item))
                except (TypeError, ValueError):
                    continue
        return role_ids
    return []


def _ghost_ping_text(
    guild: discord.Guild,
    role_ids: list[int],
    send_to_all_users: bool,
) -> str:
    if role_ids and not send_to_all_users:
        mentions = []
        for role_id in role_ids:
            role = discord.utils.get(guild.roles, id=role_id)
            if role:
                mentions.append(role.mention)
        if mentions:
            return " ".join(mentions)
    return "@everyone"


def _ghost_ping_allowed_mentions(ping_text: str) -> discord.AllowedMentions:
    return discord.AllowedMentions(
        everyone="@everyone" in ping_text,
        roles="@everyone" not in ping_text,
        users=False,
    )


def _locale_short(locale: str) -> str:
    try:
        return str(locale).split("-")[0].split("_")[0].lower()
    except Exception:
        return str(locale).lower() if locale else ""


def _content_value_for(news_contents, locale: str):
    if isinstance(news_contents, dict):
        short = _locale_short(locale)
        return (
            news_contents.get(locale)
            or news_contents.get(short)
            or news_contents.get("en")
            or ""
        )
    return news_contents


def _content_text_for(news_contents, locale: str) -> str:
    value = _content_value_for(news_contents, locale)
    if isinstance(value, dict):
        description = value.get("description")
        return description if isinstance(description, str) else ""
    return str(value)


def _embed_json_for(news_contents, embed_json, locale: str):
    value = _content_value_for(news_contents, locale)
    if isinstance(value, dict):
        return value
    return embed_json if isinstance(embed_json, dict) else None


def _button_emoji_from_data(data: dict):
    emoji = data.get("emoji")
    if not isinstance(emoji, dict):
        return None
    emoji_id = emoji.get("id")
    emoji_name = emoji.get("name")
    if emoji_id:
        try:
            return discord.PartialEmoji(
                name=emoji_name or "",
                id=int(emoji_id),
                animated=bool(emoji.get("animated", False)),
            )
        except (TypeError, ValueError):
            return emoji_name
    return emoji_name


def _view_from_components(components) -> Optional[discord.ui.View]:
    if not isinstance(components, list):
        return None

    try:
        view = discord.ui.View()
    except RuntimeError:
        return None
    added = 0
    for row_index, row in enumerate(components[:5]):
        if not isinstance(row, dict) or row.get("type") != 1:
            continue
        row_components = row.get("components")
        if not isinstance(row_components, list):
            continue

        for component in row_components[:5]:
            if not isinstance(component, dict):
                continue
            if component.get("type") != 2 or component.get("style") != 5:
                continue
            label = component.get("label")
            url = component.get("url")
            if not isinstance(label, str) or not isinstance(url, str):
                continue

            view.add_item(
                discord.ui.Button(
                    label=label,
                    url=url,
                    emoji=_button_emoji_from_data(component),
                    row=row_index,
                )
            )
            added += 1

    return view if added else None


def _message_payload_for(
    news_contents,
    embed_json,
    locale: str,
    replacements: dict,
    fallback_image_url: str = "",
) -> tuple[str, list[discord.Embed], Optional[discord.ui.View]]:
    content_text = _content_text_for(news_contents, locale)
    embed_source = _embed_json_for(news_contents, embed_json, locale)

    if isinstance(embed_source, dict):
        try:
            processed = replace_placeholders(embed_source, replacements)
            content = processed.get("content")
            content = content if isinstance(content, str) else ""
            view = _view_from_components(processed.get("components"))

            embeds = build_embeds_from_message_data(processed, default_color=None)
            return content, embeds, view
        except Exception:
            logger.exception("Failed to build news JSON payload")

    default_data = {"description": content_text}
    if fallback_image_url:
        default_data["image"] = {"url": fallback_image_url}
    try:
        return "", build_embeds_from_message_data(default_data), None
    except Exception:
        return content_text, [], None


async def _send_news_payload(
    destination,
    content: str,
    embeds: list[discord.Embed],
    view: Optional[discord.ui.View],
):
    kwargs = {}
    if content:
        kwargs["content"] = content
    if embeds:
        kwargs["embeds"] = embeds[:10]
    if view:
        kwargs["view"] = view
    if kwargs:
        await destination.send(**kwargs)


@dataclass(frozen=True)
class NewsImage:
    data: bytes | None = None
    filename: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.data and self.filename)


@dataclass(frozen=True)
class NewsBroadcastConfig:
    news_contents: dict
    embed_json: dict | None
    image: NewsImage
    image_position: str
    send_to_all_users: bool
    role_ids: list[int]
    send_to_all_channels: bool
    send_ghost_ping: bool


@dataclass
class NewsBroadcastResult:
    success_count: int = 0
    fail_count: int = 0
    elapsed_seconds: float = 0
    sent_channels: list[str] = field(default_factory=list)
    sent_users: list[str] = field(default_factory=list)
    failed_channels: list[tuple[int | str, str]] = field(default_factory=list)
    failed_users: list[tuple[int | str, str]] = field(default_factory=list)

    def add_channel_failure(self, channel_id: int | str, error: str) -> None:
        self.failed_channels.append((channel_id, error))
        self.fail_count += 1

    def add_user_failure(self, user_id: int | str, error: str) -> None:
        self.failed_users.append((user_id, error))
        self.fail_count += 1


async def _read_attachment_image(image: Optional[discord.Attachment]) -> NewsImage:
    if not image:
        return NewsImage()
    try:
        return NewsImage(await image.read(), image.filename)
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return NewsImage()


async def _read_scheduled_image(payload: dict) -> NewsImage:
    image_path = payload.get("image_path")
    image_filename = payload.get("image_filename")
    if not image_path or not image_filename:
        return NewsImage()

    try:
        if not os.path.exists(image_path):
            return NewsImage()
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
        os.remove(image_path)
        return NewsImage(image_bytes, image_filename)
    except Exception as e:
        logger.error(f"Failed to read scheduled image {image_path}: {e}")
        return NewsImage()


def _log_news_input(source: str, news_contents: dict, embed_json: dict | None) -> None:
    try:
        if isinstance(news_contents, dict):
            logger.debug(
                f"{source}: news_contents keys={list(news_contents.keys())}, "
                f"embed_json_present={bool(embed_json)}"
            )
            return
        logger.debug(f"{source}: news_contents scalar: {str(news_contents)[:200]}")
    except Exception:
        logger.debug(f"{source}: failed to log news_contents")


def _bot_avatar_url(bot: discord.Client) -> str:
    bot_user = getattr(bot, "user", None)
    if not bot_user:
        return ""
    avatar = getattr(bot_user, "display_avatar", None)
    if avatar:
        return avatar.url
    avatar = getattr(bot_user, "avatar", None) or getattr(
        bot_user, "default_avatar", None
    )
    return avatar.url if avatar else ""


def _news_channel_targets() -> list[tuple[int, str]]:
    targets = [
        (bot_config.modules.news.english_channel_id, "en"),
        (bot_config.modules.news.russian_channel_id, "ru"),
        (bot_config.modules.news.lithuanian_channel_id, "lt"),
    ]
    return [(int(channel_id), locale) for channel_id, locale in targets if channel_id]


async def _resolve_channel(bot: discord.Client, channel_id: int):
    channel = bot.get_channel(int(channel_id))
    if channel is not None:
        return channel
    return await bot.fetch_channel(int(channel_id))


def _broadcast_members(
    guild: discord.Guild,
    role_ids: list[int],
    send_to_all_users: bool,
) -> dict[int, discord.Member]:
    members = []
    if role_ids:
        for role_id in role_ids:
            role = discord.utils.get(guild.roles, id=role_id)
            if role:
                members.extend(role.members)
    elif send_to_all_users:
        members.extend(guild.members)
    return {member.id: member for member in members if not member.bot}


def _build_broadcast_payload(
    config: NewsBroadcastConfig,
    bot_avatar: str,
    locale: str,
) -> tuple[str, str, list[discord.Embed], Optional[discord.ui.View]]:
    fallback_text = _content_text_for(config.news_contents, locale)
    replacements = build_news_placeholders(fallback_text, bot_avatar, "")
    content, embeds, view = _message_payload_for(
        config.news_contents,
        config.embed_json,
        locale,
        replacements,
    )
    return fallback_text, content, embeds, view


def _make_news_file(image: NewsImage) -> discord.File | None:
    if not image.available:
        return None
    return discord.File(fp=io.BytesIO(image.data), filename=image.filename)


async def _send_image(destination, image: NewsImage) -> None:
    file = _make_news_file(image)
    if file:
        await destination.send(file=file)


async def _send_payload_with_image(
    destination,
    fallback_text: str,
    content: str,
    embeds: list[discord.Embed],
    view: Optional[discord.ui.View],
    image: NewsImage,
    image_position: str,
) -> None:
    if image_position == "Before":
        await _send_image(destination, image)

    if embeds or content:
        await _send_news_payload(destination, content, embeds, view)
    elif fallback_text:
        await destination.send(fallback_text)

    if image_position == "After":
        await _send_image(destination, image)


async def _send_ghost_ping(
    channel,
    guild: discord.Guild,
    role_ids: list[int],
    send_to_all_users: bool,
) -> None:
    ping_text = _ghost_ping_text(guild, role_ids, send_to_all_users)
    ping_msg = await channel.send(
        ping_text,
        allowed_mentions=_ghost_ping_allowed_mentions(ping_text),
    )
    await ping_msg.delete()


def _channel_summary(channel, locale: str) -> str:
    try:
        return f"<#{channel.id}> ({getattr(channel, 'name', 'channel')}, {locale})"
    except Exception:
        return f"<#{channel.id}> ({locale})"


def _user_summary(member: discord.Member) -> str:
    try:
        return f"<@{member.id}> ({getattr(member, 'name', 'user')})"
    except Exception:
        return f"<@{member.id}>"


async def _broadcast_news(
    bot: discord.Client,
    guild: discord.Guild,
    config: NewsBroadcastConfig,
) -> NewsBroadcastResult:
    result = NewsBroadcastResult()
    start_time = datetime.utcnow()
    bot_avatar = _bot_avatar_url(bot)

    if config.send_to_all_channels:
        for channel_id, locale in _news_channel_targets():
            try:
                logger.info(
                    "send_news: channel "
                    f"{channel_id} locale={locale} content_preview="
                    f"{_content_text_for(config.news_contents, locale)[:60]}"
                )
                channel = await _resolve_channel(bot, channel_id)
            except Exception as e:
                logger.error(f"Failed to fetch channel {channel_id}: {e}")
                result.add_channel_failure(channel_id, str(e))
                continue

            try:
                fallback_text, content, embeds, view = _build_broadcast_payload(
                    config,
                    bot_avatar,
                    locale,
                )
                await _send_payload_with_image(
                    channel,
                    fallback_text,
                    content,
                    embeds,
                    view,
                    config.image,
                    config.image_position,
                )
                if config.send_ghost_ping and locale == "en":
                    await _send_ghost_ping(
                        channel,
                        guild,
                        config.role_ids,
                        config.send_to_all_users,
                    )
                result.success_count += 1
                result.sent_channels.append(_channel_summary(channel, locale))
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to send news to channel {channel.id}: {e}")
                result.add_channel_failure(channel.id, str(e))

    for member in _broadcast_members(
        guild,
        config.role_ids,
        config.send_to_all_users,
    ).values():
        try:
            member_lang = await get_language(member.id)
            logger.info(
                f"send_news: DM to {member.id} lang={member_lang} content_preview="
                f"{_content_text_for(config.news_contents, member_lang)[:60]}"
            )
            fallback_text, content, embeds, view = _build_broadcast_payload(
                config,
                bot_avatar,
                member_lang,
            )
            await _send_payload_with_image(
                member,
                fallback_text,
                content,
                embeds,
                view,
                config.image,
                config.image_position,
            )
            result.success_count += 1
            result.sent_users.append(_user_summary(member))
            await asyncio.sleep(1)
        except discord.Forbidden:
            logger.debug(f"Cannot send DM to {member.name}({member.id})")
            result.add_user_failure(member.id, "Forbidden")
        except Exception as e:
            logger.error(f"Failed to send news to user {member.id}: {e}")
            result.add_user_failure(member.id, str(e))

    result.elapsed_seconds = (datetime.utcnow() - start_time).total_seconds()
    return result


def _build_summary_embed(
    result: NewsBroadcastResult,
    user_lang: str,
    footer_icon_url: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{lang_constants.SUCCESS_EMOJI} {_('news.sent_summary', user_lang)}",
        color=bot_config.embeds.success_color,
    )
    embed.add_field(
        name=_("common.successful", user_lang),
        value=str(result.success_count),
        inline=True,
    )
    embed.add_field(
        name=_("common.failed", user_lang),
        value=str(result.fail_count),
        inline=True,
    )
    embed.add_field(
        name=_("common.duration", user_lang),
        value=f"{result.elapsed_seconds:.2f}s",
        inline=True,
    )
    _add_summary_list(embed, user_lang, "common.channels", result.sent_channels)
    _add_summary_list(embed, user_lang, "common.users", result.sent_users)
    _add_failure_list(embed, user_lang, "news.failed_channels", result.failed_channels)
    _add_failure_list(embed, user_lang, "news.failed_users", result.failed_users)
    embed.set_footer(text=bot_config.bot.trademark, icon_url=footer_icon_url)
    return embed


def _add_summary_list(
    embed: discord.Embed,
    user_lang: str,
    title_key: str,
    values: list[str],
) -> None:
    if not values:
        return
    max_show = 20
    display = ", ".join(values[:max_show])
    if len(values) > max_show:
        display += _("news.and_more", user_lang)
    embed.add_field(name=_(title_key, user_lang), value=display, inline=False)


def _add_failure_list(
    embed: discord.Embed,
    user_lang: str,
    title_key: str,
    values: list[tuple[int | str, str]],
) -> None:
    if not values:
        return
    details = "\n".join(f"- {target}: {error}" for target, error in values[:10])
    embed.add_field(name=_(title_key, user_lang), value=details, inline=False)


def _scheduled_config_from_payload(
    payload: dict, image: NewsImage
) -> NewsBroadcastConfig:
    return NewsBroadcastConfig(
        news_contents=payload.get("news_contents", {}),
        embed_json=payload.get("embed_json"),
        image=image,
        image_position=payload.get("image_position", "Before"),
        send_to_all_users=payload.get("send_to_all_users", False),
        role_ids=_normalize_role_ids(payload.get("role_ids") or payload.get("role_id")),
        send_to_all_channels=payload.get("send_to_all_channels", False),
        send_ghost_ping=payload.get("send_ghost_ping", False),
    )


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

    logger.info(f"Executing scheduled news broadcast by user {user_id}")
    user_lang = await get_language(user_id)
    image = await _read_scheduled_image(payload)
    config = _scheduled_config_from_payload(payload, image)
    result = await _broadcast_news(bot, guild, config)

    if user:
        try:
            footer_icon_url = guild.icon.url if guild.icon else ""
            await user.send(
                embed=_build_summary_embed(result, user_lang, footer_icon_url)
            )
        except Exception as e:
            logger.error(f"Could not send news summary DM to {user.id}: {e}")

    logger.info(
        f"Scheduled news broadcast completed: {result.success_count} sent, "
        f"{result.fail_count} failed"
    )


async def send_news(
    bot: discord.Bot,
    ctx: discord.ApplicationContext,
    news_contents: dict,
    embed_json: dict,
    image: Optional[discord.Attachment],
    send_image_before_or_after_news: str,
    send_to_all_users: bool,
    sent_to_all_users_with_role: Optional[discord.Role | list[discord.Role]],
    send_to_all_channels: bool,
    send_ghost_ping: bool,
) -> None:
    """Send news immediately and post a summary to the admin."""
    _log_news_input("send_news", news_contents, embed_json)

    user_lang = await get_language(ctx.user.id)
    config = NewsBroadcastConfig(
        news_contents=news_contents,
        embed_json=embed_json,
        image=await _read_attachment_image(image),
        image_position=send_image_before_or_after_news,
        send_to_all_users=send_to_all_users,
        role_ids=_normalize_role_ids(sent_to_all_users_with_role),
        send_to_all_channels=send_to_all_channels,
        send_ghost_ping=send_ghost_ping,
    )
    result = await _broadcast_news(bot, ctx.guild, config)

    try:
        await ctx.followup.send(
            embed=_build_summary_embed(result, user_lang, get_embed_icon(ctx)),
            ephemeral=True,
        )
    except Exception:
        logger.info(
            f"News sent: {result.success_count} successful, {result.fail_count} "
            f"failed in {result.elapsed_seconds:.2f}s"
        )

    logger.info(
        f"News broadcast completed by {ctx.user.name}({ctx.user.id}): "
        f"{result.success_count} sent, {result.fail_count} failed"
    )


async def preview_news(
    bot: discord.Bot,
    ctx: discord.ApplicationContext,
    news_contents: dict,
    embed_json: dict,
    image: Optional[discord.Attachment],
    send_image_before_or_after_news: str,
    send_to_all_users: bool,
    sent_to_all_users_with_role: Optional[discord.Role | list[discord.Role]],
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

    def _make_payload_for(
        locale: str,
    ) -> tuple[str, list[discord.Embed], Optional[discord.ui.View]]:
        content_text = _content_text_for(news_contents, locale)
        image_url = f"attachment://{image_filename}" if image_filename else ""
        replacements = build_news_placeholders(
            content_text,
            bot_avatar,
            image_url,
        )
        return _message_payload_for(
            news_contents,
            embed_json,
            locale,
            replacements,
            image_url,
        )

    # Compose preview embeds for locales
    title = discord.Embed(
        title=f"{lang_constants.EYES_EMOJI} {_('news.preview', user_lang)}",
        description=_("news.preview_description", user_lang),
        color=bot_config.embeds.info_color,
    )
    title.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))

    locale_payloads = [
        ("EN", *_make_payload_for("en")),
        ("RU", *_make_payload_for("ru")),
        ("LT", *_make_payload_for("lt")),
    ]

    # Targets summary
    channels = []
    if send_to_all_channels:
        if bot_config.modules.news.english_channel_id:
            channels.append(f"<#{bot_config.modules.news.english_channel_id}> (EN)")
        if bot_config.modules.news.russian_channel_id:
            channels.append(f"<#{bot_config.modules.news.russian_channel_id}> (RU)")
        if bot_config.modules.news.lithuanian_channel_id:
            channels.append(f"<#{bot_config.modules.news.lithuanian_channel_id}> (LT)")
    members_count = 0
    role_ids = _normalize_role_ids(sent_to_all_users_with_role)
    if send_to_all_users or role_ids:
        members = []
        if role_ids:
            for role_id in role_ids:
                role = discord.utils.get(ctx.guild.roles, id=role_id)
                if role:
                    members.extend([m for m in role.members if not m.bot])
        else:
            members.extend([m for m in ctx.guild.members if not m.bot])
        # unique
        members_count = len({m.id for m in members})

    targets_embed = discord.Embed(
        title=_("news.targets", user_lang),
        color=bot_config.embeds.info_color,
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
        value=(
            _ghost_ping_text(ctx.guild, role_ids, send_to_all_users)
            if send_ghost_ping
            else "False"
        ),
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

    async def _send_preview_message(
        sender,
        label: str,
        content: str,
        embeds: list,
        view: Optional[discord.ui.View],
    ):
        label_content = f"[{label}]"
        if content:
            label_content = f"{label_content}\n{content}"
        kwargs = {"content": label_content, "ephemeral": True}
        if embeds:
            kwargs["embeds"] = embeds[:10]
        if view:
            kwargs["view"] = view
        await sender(**kwargs)

    # Send multiple ephemeral messages in sequence
    try:
        await ctx.followup.send(embed=title, ephemeral=True)

        for label, content, embeds, view in locale_payloads:
            if not content and not embeds:
                continue
            if image_filename and send_image_before_or_after_news == "Before":
                img = _make_image_file()
                if img:
                    await ctx.followup.send(file=img, ephemeral=True)
            await _send_preview_message(ctx.followup.send, label, content, embeds, view)
            if image_filename and send_image_before_or_after_news == "After":
                img = _make_image_file()
                if img:
                    await ctx.followup.send(file=img, ephemeral=True)

        await ctx.followup.send(embed=targets_embed, ephemeral=True)
    except Exception:
        # Fallback path if followup fails; use respond
        await ctx.respond(embed=title, ephemeral=True)
        for label, content, embeds, view in locale_payloads:
            if not content and not embeds:
                continue
            if image_filename and send_image_before_or_after_news == "Before":
                img = _make_image_file()
                if img:
                    await ctx.respond(file=img, ephemeral=True)
            await _send_preview_message(ctx.respond, label, content, embeds, view)
            if image_filename and send_image_before_or_after_news == "After":
                img = _make_image_file()
                if img:
                    await ctx.respond(file=img, ephemeral=True)
        await ctx.respond(embed=targets_embed, ephemeral=True)
