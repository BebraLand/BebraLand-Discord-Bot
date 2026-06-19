import re

import discord
from discord import Option, OptionChoice
from discord.ext import commands
from pycord.multicog import subcommand

from config.config import config as bot_config
from src.languages import lang_constants
from src.languages.localize import _, locale_display_name
from src.utils.auth import require_admin
from src.utils.database import get_language, set_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

USER_ID_PATTERN = re.compile(r"(?<!\d)(\d{17,20})(?!\d)")
MAX_USERS_PER_COMMAND = 100


class AdminSetUsersLanguage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="set_users_language",
        description="Set language for one or more users",
    )
    async def set_users_language(
        self,
        ctx: discord.ApplicationContext,
        language=Option(
            str,
            description="Language to set",
            required=True,
            choices=[
                OptionChoice(name="English", value="en"),
                OptionChoice(name="Русский", value="ru"),
                OptionChoice(name="Lietuvių", value="lt"),
            ],
        ),
        user=Option(
            discord.Member,
            description="Select one user",
            required=False,
        ),
        users=Option(
            str,
            description="Extra user mentions or IDs, separated by spaces or commas",
            required=False,
            max_length=1000,
        ),
    ):
        if not await require_admin(ctx):
            return

        await ctx.defer(ephemeral=True)
        admin_language = await get_language(ctx.user.id)
        user_ids = {user.id} if user else set()
        if users:
            user_ids.update(int(value) for value in USER_ID_PATTERN.findall(users))

        if not user_ids:
            await self._respond(
                ctx,
                admin_language,
                "language.admin_bulk.no_users",
                error=True,
            )
            return

        if len(user_ids) > MAX_USERS_PER_COMMAND:
            await self._respond(
                ctx,
                admin_language,
                "language.admin_bulk.too_many",
                error=True,
                max_users=MAX_USERS_PER_COMMAND,
            )
            return

        changed = 0
        unchanged = 0
        failed = 0
        for user_id in user_ids:
            try:
                if await get_language(user_id) == language:
                    unchanged += 1
                    continue
                await set_language(user_id, language)
                changed += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Admin %s (%s) failed to set language for user %s",
                    ctx.user.name,
                    ctx.user.id,
                    user_id,
                )

        await self._respond(
            ctx,
            admin_language,
            "language.admin_bulk.result",
            language=locale_display_name(language),
            changed=changed,
            unchanged=unchanged,
            failed=failed,
        )
        logger.info(
            "Admin %s (%s) set language=%s for %s users; changed=%s unchanged=%s failed=%s",
            ctx.user.name,
            ctx.user.id,
            language,
            len(user_ids),
            changed,
            unchanged,
            failed,
        )

    async def _respond(
        self,
        ctx: discord.ApplicationContext,
        locale: str,
        key: str,
        *,
        error: bool = False,
        **format_values,
    ) -> None:
        embed = discord.Embed(
            title=(
                f"{lang_constants.ERROR_EMOJI} {_('common.error', locale)}"
                if error
                else f"{lang_constants.SUCCESS_EMOJI} {_('common.success', locale)}"
            ),
            description=_(key, locale).format(**format_values),
            color=(bot_config.embeds.failed_color if error else discord.Color.green()),
        )
        embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )


def setup(bot: commands.Bot):
    bot.add_cog(AdminSetUsersLanguage(bot))
