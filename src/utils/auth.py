import discord
import config.constants as constants
from src.languages.localize import translate
from src.utils.database import get_language
import src.languages.lang_constants as lang_constants
from src.utils.get_embed_icon import get_embed_icon


def is_admin(user_id: int) -> bool:
    return user_id in constants.ADMIN_LIST


async def require_admin(ctx) -> bool:
    if not is_admin(ctx.user.id):
        current_lang = await get_language(ctx.user.id)
        desc = translate("You are not authorized to use this command!", current_lang)
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {translate('Error', current_lang)}",
            description=desc,
            color=discord.Color.red(),
        )
        
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
        await ctx.respond(
            embed=embed,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )
        return False
    return True