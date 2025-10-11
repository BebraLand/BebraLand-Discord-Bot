import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.languages.localize import translate
from src.utils.database import get_language
from src.utils.auth import require_admin
import config.constants as constants
from src.utils.clear_dm_messages import clear_dm_messages, clear_all_dm_messages
from pycord.multicog import subcommand


logger = get_cool_logger(__name__)


class adminClearDm(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    
    @subcommand("admin")
    @discord.slash_command(
        name="clear_dm_admin",
        description="Clear all messages in the DM with the user",
        description_localizations={
            "ru": "Очистить все сообщения в DM с пользователем",
            "lt": "Išvalyti visus pranešimus šio kanalo"
        }
    )
    async def clear_dm_admin(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User = Option(
            discord.User,
            name="user",
            name_localizations={
                "ru": "пользователь",
                "lt": "naudotojas"
            },
            description="Target user",
            description_localizations={
                "ru": "Целевой пользователь",
                "lt": "Tikslo naudotojas"
            },
            required=False
        ),
        clear_all_users: bool = Option(
            bool,
            name="clear-all-users",
            name_localizations={
                "ru": "очистить-всех-пользователей",
                "lt": "išvalyti-visus-naudotojus"
            },
            description="Clear DMs with all users",
            description_localizations={
                "ru": "Очистить DM со всеми пользователями",
                "lt": "Išvalyti DM su visais naudotojais"
            },
            default=False
        ),
    ):
        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        current_lang = await get_language(ctx.user.id)

        target_user = user or ctx.user

        if clear_all_users:
            total_deleted = await clear_all_dm_messages(ctx)
            description_text = translate(
                "Removed {count} messages across all DMs.", current_lang,
            ).format(count=total_deleted)
            embed = discord.Embed(
                title=f"✅ {translate('Success', current_lang)}",
                description=description_text,
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=ctx.bot.user.display_avatar.url,
            )
            await ctx.respond(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            logger.info(
                f"Admin {ctx.user.name}({ctx.user.id}) cleared ALL DMs; deleted={total_deleted}"
            )
            return

        if target_user.bot:
            embed = discord.Embed(
                title=f"❌ {translate('Error', current_lang)}",
                description=translate(
                    "I can't clear a bot's DM.", current_lang),
                color=discord.Color.red(),
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=ctx.bot.user.display_avatar.url,
            )
            await ctx.respond(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            return

        deleted_count = await clear_dm_messages(ctx, target_user=target_user)

        if deleted_count > 0:
            description_text = translate(
                "Removed {count} messages from DM of {user}.",
                current_lang,
            ).format(count=deleted_count, user=target_user.mention)
        else:
            description_text = translate(
                "No messages from DM of {user}.", current_lang).format(user=target_user.mention)

        embed = discord.Embed(
            title=f"✅ {translate('Success', current_lang)}",
            description=description_text,
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=ctx.bot.user.display_avatar.url,
        )
        await ctx.respond(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) cleared DM for {target_user.name}({target_user.id}); deleted={deleted_count}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(adminClearDm(bot))