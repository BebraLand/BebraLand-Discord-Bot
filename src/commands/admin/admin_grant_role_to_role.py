import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

from config.config import config as bot_config
from src.languages import lang_constants
from src.languages.localize import _
from src.utils.auth import require_admin
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class AdminGrantRoleToRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="grant_role_to_role",
        description="Give a role to every member with another role",
    )
    async def grant_role_to_role(
        self,
        ctx: discord.ApplicationContext,
        source_role: discord.Role = Option(
            discord.Role,
            description="Members with this role will receive the target role",
            required=True,
        ),
        target_role: discord.Role = Option(
            discord.Role,
            description="Role to give to matching members",
            required=True,
        ),
        remove_role: discord.Role = Option(
            discord.Role,
            description="Optional role to remove after granting the target role",
            required=False,
        ),
    ):
        if not await require_admin(ctx):
            return

        await ctx.defer(ephemeral=True)
        locale = await get_language(ctx.user.id)
        guild = ctx.guild
        bot_member = guild.me if guild else None

        if not bot_member or not bot_member.guild_permissions.manage_roles:
            await self._respond(ctx, locale, "role_grant.manage_roles_missing", error=True)
            return

        if target_role.managed or target_role >= bot_member.top_role:
            await self._respond(ctx, locale, "role_grant.target_not_assignable", error=True)
            return

        if remove_role and (
            remove_role.managed or remove_role >= bot_member.top_role
        ):
            await self._respond(ctx, locale, "role_grant.remove_not_assignable", error=True)
            return

        if remove_role == target_role:
            await self._respond(ctx, locale, "role_grant.same_target_and_remove", error=True)
            return

        matching_members = list(source_role.members)
        granted = 0
        already_has_role = 0
        removed = 0
        did_not_have_remove_role = 0
        failed = 0

        for member in matching_members:
            if target_role in member.roles:
                already_has_role += 1
            else:
                try:
                    await member.add_roles(
                        target_role,
                        reason=(
                            f"Admin {ctx.user} ({ctx.user.id}) granted role to members "
                            f"with {source_role} ({source_role.id})"
                        ),
                    )
                    granted += 1
                except discord.HTTPException:
                    failed += 1
                    logger.exception(
                        "Could not grant role %s (%s) to %s (%s)",
                        target_role.name,
                        target_role.id,
                        member.name,
                        member.id,
                    )
                    continue

            if remove_role:
                if remove_role not in member.roles:
                    did_not_have_remove_role += 1
                    continue

                try:
                    await member.remove_roles(
                        remove_role,
                        reason=(
                            f"Admin {ctx.user} ({ctx.user.id}) replaced role "
                            f"for members with {source_role} ({source_role.id})"
                        ),
                    )
                    removed += 1
                except discord.HTTPException:
                    failed += 1
                    logger.exception(
                        "Could not remove role %s (%s) from %s (%s)",
                        remove_role.name,
                        remove_role.id,
                        member.name,
                        member.id,
                    )

        await self._respond(
            ctx,
            locale,
            "role_grant.result",
            source_role=source_role.mention,
            target_role=target_role.mention,
            matched=len(matching_members),
            granted=granted,
            already_has_role=already_has_role,
            remove_summary=(
                _("role_grant.no_role_removed", locale)
                if not remove_role
                else _("role_grant.remove_summary", locale).format(
                    remove_role=remove_role.mention,
                    removed=removed,
                    did_not_have=did_not_have_remove_role,
                )
            ),
            failed=failed,
        )
        logger.info(
            "Admin %s (%s) granted role %s (%s) to members with %s (%s): "
            "matched=%s granted=%s already_has_role=%s removed=%s failed=%s",
            ctx.user.name,
            ctx.user.id,
            target_role.name,
            target_role.id,
            source_role.name,
            source_role.id,
            len(matching_members),
            granted,
            already_has_role,
            removed,
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
    bot.add_cog(AdminGrantRoleToRole(bot))
