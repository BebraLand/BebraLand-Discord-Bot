import io
import asyncio
from datetime import datetime
from typing import Optional

import discord

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_language
from src.languages.localize import _
from src.utils.embed_builder import build_embed_from_data, replace_placeholders
from src.utils.get_embed_icon import get_embed_icon
from src.features.news import NewsContent, BroadcastConfig, NewsBroadcaster


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

    This function now uses the centralized NewsBroadcaster for DRY implementation.
    """
    user_lang = await get_language(ctx.user.id)
    
    # Convert legacy dict to NewsContent model
    content = NewsContent.from_dict({
        "en": news_contents.get("en", ""),
        "ru": news_contents.get("ru"),
        "lt": news_contents.get("lt"),
        "embed_json": embed_json
    })
    
    # Create broadcast configuration
    config = BroadcastConfig(
        send_to_channels=send_to_all_channels,
        send_to_users=send_to_all_users,
        role_id=sent_to_all_users_with_role.id if sent_to_all_users_with_role else None,
        send_ghost_ping=send_ghost_ping,
        image_position=send_image_before_or_after_news
    )
    
    # Read image data if provided
    image_data = None
    image_filename = None
    if image:
        try:
            image_data = await image.read()
            image_filename = image.filename
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
    
    # Create broadcaster and execute
    broadcaster = NewsBroadcaster(
        bot=bot,
        guild_id=ctx.guild.id,
        content=content,
        config=config,
        image_data=image_data,
        image_filename=image_filename,
        ctx_for_footer=ctx
    )
    
    result = await broadcaster.broadcast()
    
    # Send summary embed to admin
    try:
        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('news.sent_summary', user_lang)}",
            color=constants.SUCCESS_EMBED_COLOR,
        )
        embed.add_field(name=_('common.successful', user_lang), value=str(result.success_count), inline=True)
        embed.add_field(name=_('common.failed', user_lang), value=str(result.fail_count), inline=True)
        embed.add_field(name=_('common.duration', user_lang), value=f"{result.duration_seconds:.2f}s", inline=True)
        
        # Include recipients list (limit to avoid hitting embed size limits)
        if result.sent_channels:
            max_show = 20
            display = ", ".join(result.sent_channels[:max_show])
            if len(result.sent_channels) > max_show:
                display += _("news.and_more", user_lang)
            embed.add_field(name=_("common.channels", user_lang), value=display, inline=False)
        
        if result.sent_users:
            max_show = 20
            display = ", ".join(result.sent_users[:max_show])
            if len(result.sent_users) > max_show:
                display += _("news.and_more", user_lang)
            embed.add_field(name=_("common.users", user_lang), value=display, inline=False)
        
        # Include brief failure details (limit to 10 entries each)
        if result.fail_count > 0:
            if result.failed_channels:
                ch_details = "\n".join([f"• {cid}: {err}" for cid, err in result.failed_channels[:10]])
                embed.add_field(name=_('news.failed_channels', user_lang), value=ch_details, inline=False)
            if result.failed_users:
                user_details = "\n".join([f"• {uid}: {err}" for uid, err in result.failed_users[:10]])
                embed.add_field(name=_('news.failed_users', user_lang), value=user_details, inline=False)
        
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
        
        await ctx.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to send summary: {e}")
        logger.info(f"News sent: {result.success_count} successful, {result.fail_count} failed in {result.duration_seconds:.2f}s")
    
    logger.info(
        f"News broadcast completed by {ctx.user.name}({ctx.user.id}): {result.success_count} sent, {result.fail_count} failed"
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
    """Show an ephemeral preview of what will be sent.

    This preview now uses the centralized NewsBroadcaster for consistent rendering.
    """
    user_lang = await get_language(ctx.user.id)
    
    # Convert legacy dict to NewsContent model
    content = NewsContent.from_dict({
        "en": news_contents.get("en", ""),
        "ru": news_contents.get("ru"),
        "lt": news_contents.get("lt"),
        "embed_json": embed_json
    })
    
    # Create broadcast configuration
    config = BroadcastConfig(
        send_to_channels=send_to_all_channels,
        send_to_users=send_to_all_users,
        role_id=sent_to_all_users_with_role.id if sent_to_all_users_with_role else None,
        send_ghost_ping=send_ghost_ping,
        image_position=send_image_before_or_after_news
    )
    
    # Read image data if provided
    image_data = None
    image_filename = None
    if image:
        try:
            image_data = await image.read()
            image_filename = image.filename
        except Exception:
            pass
    
    # Create broadcaster (won't actually send, just for building previews)
    broadcaster = NewsBroadcaster(
        bot=bot,
        guild_id=ctx.guild.id,
        content=content,
        config=config,
        image_data=image_data,
        image_filename=image_filename,
        ctx_for_footer=ctx
    )
    
    # Compose preview title embed
    title = discord.Embed(
        title=f"{lang_constants.EYES_EMOJI} {_('news.preview', user_lang)}",
        description=_('news.preview_description', user_lang) + f"\n\n{constants.DISCORD_MESSAGE_TRADEMARK}",
        color=constants.INFO_EMBED_COLOR,
    )
    title.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
    
    # Build preview embeds for each locale using broadcaster's method
    locale_embeds = [
        ("EN", broadcaster._build_embed("en", include_image_url=False)),
        ("RU", broadcaster._build_embed("ru", include_image_url=False)),
        ("LT", broadcaster._build_embed("lt", include_image_url=False)),
    ]
    
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
        members_count = len({m.id for m in members})
    
    targets_embed = discord.Embed(
        title=_('news.targets', user_lang),
        color=constants.INFO_EMBED_COLOR,
    )
    if channels:
        targets_embed.add_field(name=_('common.channels', user_lang), value=", ".join(channels), inline=False)
    targets_embed.add_field(name=_('common.users', user_lang), value=str(members_count), inline=True)
    targets_embed.add_field(name=_('news.ghost_ping', user_lang), value=str(bool(send_ghost_ping)), inline=True)
    targets_embed.add_field(name=_('news.image_position', user_lang), value=send_image_before_or_after_news, inline=True)
    
    # Send multiple ephemeral messages in sequence
    try:
        await ctx.followup.send(embed=title, ephemeral=True)
        
        for label, embed in locale_embeds:
            if not embed:
                continue
            
            # Send image before if configured
            if image_data and image_filename and send_image_before_or_after_news == "Before":
                image_file = broadcaster._make_image_file()
                if image_file:
                    await ctx.followup.send(file=image_file, ephemeral=True)
            
            await ctx.followup.send(content=f"[{label}]", embed=embed, ephemeral=True)
            
            # Send image after if configured
            if image_data and image_filename and send_image_before_or_after_news == "After":
                image_file = broadcaster._make_image_file()
                if image_file:
                    await ctx.followup.send(file=image_file, ephemeral=True)
        
        await ctx.followup.send(embed=targets_embed, ephemeral=True)
    except Exception:
        # Fallback path if followup fails
        await ctx.respond(embed=title, ephemeral=True)
        for label, embed in locale_embeds:
            if not embed:
                continue
            
            if image_data and image_filename and send_image_before_or_after_news == "Before":
                image_file = broadcaster._make_image_file()
                if image_file:
                    await ctx.respond(file=image_file, ephemeral=True)
            
            await ctx.respond(content=f"[{label}]", embed=embed, ephemeral=True)
            
            if image_data and image_filename and send_image_before_or_after_news == "After":
                image_file = broadcaster._make_image_file()
                if image_file:
                    await ctx.respond(file=image_file, ephemeral=True)
        
        await ctx.respond(embed=targets_embed, ephemeral=True)