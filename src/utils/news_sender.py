import io
import asyncio
from datetime import datetime, timezone
from typing import Optional

import discord

import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_language
from src.languages.localize import translate
from src.utils.embed_builder import build_embed_from_data, replace_placeholders, build_news_embed, get_bot_avatar_url


logger = get_cool_logger(__name__)


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

    user_lang = await get_language(ctx.user.id)
    start_time = datetime.now(timezone.utc)

    # Helper to choose content for a locale, falling back to English
    def _content_for(locale: str) -> str:
        if isinstance(news_contents, dict):
            return news_contents.get(locale) or news_contents.get("en") or ""
        return str(news_contents)

    bot_avatar = get_bot_avatar_url(ctx.bot)

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

    def _build_embed(content_text: str, include_image: bool) -> Optional[discord.Embed]:
        image_url = ""
        if include_image and image_filename:
            image_url = f"attachment://{image_filename}"
        
        use_footer = getattr(constants, "NEWS_DEFAULT_FOOTER", False)
        return build_news_embed(
            content_text=content_text,
            bot=ctx.bot,
            embed_json=embed_json,
            image_url=image_url,
            use_default_footer=use_footer,
        )

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
                embed = _build_embed(_content_for(locale), include_image=False)

                if embed:
                    # Send image separately before the embed if requested
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await channel.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )
                    await channel.send(embed=embed)
                    # Or send image after the embed if requested
                    if image_bytes and send_image_before_or_after_news == "After":
                        await channel.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )
                else:
                    # Fallback to plain text
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await channel.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )
                    await channel.send(_content_for(locale))
                    if image_bytes and send_image_before_or_after_news == "After":
                        await channel.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )

                # Send ghost ping after content (English channel only)
                if send_ghost_ping and locale == "en":
                    ping_msg = await channel.send("@everyone")
                    await ping_msg.delete()

                success_count += 1
                # Track channel recipient mention for summary
                try:
                    sent_channels.append(f"<#{channel.id}> ({getattr(channel, 'name', 'channel')}, {locale})")
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
                embed = _build_embed(_content_for(member_lang), include_image=False)

                if embed:
                    # Send image separately before the embed if requested
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await member.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )
                    await member.send(embed=embed)
                    # Or send image after the embed if requested
                    if image_bytes and send_image_before_or_after_news == "After":
                        await member.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )
                else:
                    # Fallback to plain text
                    if image_bytes and send_image_before_or_after_news == "Before":
                        await member.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )
                    await member.send(_content_for(member_lang))
                    if image_bytes and send_image_before_or_after_news == "After":
                        await member.send(
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                        )

                success_count += 1
                # Track user recipient mention for summary
                try:
                    sent_users.append(f"<@{member.id}> ({getattr(member, 'name', 'user')})")
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
    elapsed_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
    try:
        embed = discord.Embed(
            title=f"✅ {translate('News sent summary', user_lang)}",
            color=discord.Color.green(),
        )
        embed.add_field(name=translate('Successful', user_lang), value=str(success_count), inline=True)
        embed.add_field(name=translate('Failed', user_lang), value=str(fail_count), inline=True)
        embed.add_field(name=translate('Duration', user_lang), value=f"{elapsed_seconds:.2f}s", inline=True)

        # Include recipients list (limit to avoid hitting embed size limits)
        if sent_channels:
            max_show = 20
            display = ", ".join(sent_channels[:max_show])
            if len(sent_channels) > max_show:
                display += translate(' and more...', user_lang)
            embed.add_field(name=translate('Channels', user_lang), value=display, inline=False)
        if sent_users:
            max_show = 20
            display = ", ".join(sent_users[:max_show])
            if len(sent_users) > max_show:
                display += translate(' and more...', user_lang)
            embed.add_field(name=translate('Users', user_lang), value=display, inline=False)

        # Include brief failure details (limit to 10 entries each)
        if fail_count > 0:
            if failed_channels:
                ch_details = "\n".join([f"• {cid}: {err}" for cid, err in failed_channels[:10]])
                embed.add_field(name=translate('Failed channels', user_lang), value=ch_details, inline=False)
            if failed_users:
                user_details = "\n".join([f"• {uid}: {err}" for uid, err in failed_users[:10]])
                embed.add_field(name=translate('Failed users', user_lang), value=user_details, inline=False)

        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=bot_avatar)

        await ctx.followup.send(
            embed=embed,
            ephemeral=True
        )
    except Exception:
        # If context is no longer valid or embed fails, log instead
        logger.info(f"News sent: {success_count} successful, {fail_count} failed in {elapsed_seconds:.2f}s")

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

    user_lang = await get_language(ctx.user.id)

    # Helper to choose content for a locale, falling back to English
    def _content_for(locale: str) -> str:
        if isinstance(news_contents, dict):
            return news_contents.get(locale) or news_contents.get("en") or ""
        return str(news_contents)

    bot_avatar = get_bot_avatar_url(ctx.bot)

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
        image_url = f"attachment://{image_filename}" if image_filename else ""
        use_footer = getattr(constants, "NEWS_DEFAULT_FOOTER", False)
        return build_news_embed(
            content_text=content_text,
            bot=ctx.bot,
            embed_json=embed_json,
            image_url=image_url,
            use_default_footer=use_footer,
        )

    # Compose preview embeds for locales
    title = discord.Embed(
        title=f"👀 {translate('Preview', user_lang)}",
        description=translate('This is how news will look per locale.', user_lang) + "\n\nBebraLand team 🚀🌍🎮",
        color=discord.Color.blurple(),
    )
    title.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=bot_avatar)

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
            channels.append(f"<#{getattr(constants, 'NEWS_LITHUANIAN_CHANNEL_ID')}> (LT)")
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
        title=translate('Targets', user_lang),
        color=discord.Color.blurple(),
    )
    if channels:
        targets_embed.add_field(name=translate('Channels', user_lang), value=", ".join(channels), inline=False)
    targets_embed.add_field(name=translate('Users', user_lang), value=str(members_count), inline=True)
    targets_embed.add_field(name=translate('Ghost ping', user_lang), value=str(bool(send_ghost_ping)), inline=True)
    targets_embed.add_field(name=translate('Image position', user_lang), value=send_image_before_or_after_news, inline=True)
    
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