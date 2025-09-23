import discord
import logging
from discord.ext import commands
import asyncio
from src.utils.localization import LocalizationManager
from src.utils.localization_helper import LocalizationHelper

class ClearDMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = bot.localization
        self.loc_helper = LocalizationHelper(bot)

    @discord.slash_command(
        name="clear_dm",
        description="Clear your DM messages with the bot"
    )
    async def clear_dm(self, ctx):
        """Clear DM messages between the user and the bot."""
        try:
            # Send initial processing embed
            processing_embed = self.loc_helper.create_info_embed(
                title_key="CLEAR_DM_CLEARING_SELF_PROGRESS",
                description_key="CLEAR_DM_CLEARING_SELF_PROGRESS",
                user_id=ctx.author.id
            )
            processing_embed.add_field(
                name="User", 
                value=f"{ctx.author.mention}", 
                inline=False
            )
            processing_embed.set_thumbnail(url=ctx.author.display_avatar.url)
            
            await ctx.respond(embed=processing_embed, ephemeral=True, delete_after=120)

            # Get the DM channel with the user
            dm_channel = ctx.author.dm_channel
            if not dm_channel:
                try:
                    dm_channel = await ctx.author.create_dm()
                except discord.Forbidden:
                    error_embed = self.loc_helper.create_error_embed(
                        title_key="CLEAR_DM_ERROR_TITLE",
                        description_key="CLEAR_DM_PERMISSION_ERROR",
                        user_id=ctx.author.id
                    )
                    await ctx.edit(embed=error_embed)
                    return

            # Count and delete bot messages with progress updates
            deleted_count = 0
            total_checked = 0
            last_update = 0
            
            async for message in dm_channel.history(limit=None):
                total_checked += 1
                if message.author == self.bot.user:
                    try:
                        await message.delete()
                        deleted_count += 1
                        # Add a small delay to avoid rate limits
                        await asyncio.sleep(0.1)
                        
                        # Update progress every 10 deletions
                        if deleted_count - last_update >= 10:
                            progress_embed = self.loc_helper.create_info_embed(
                                title="🔄 Clearing Messages...",
                                description_key="CLEAR_DM_CLEARING_SELF_PROGRESS",
                                user_id=ctx.author.id
                            )
                            self.loc_helper.add_localized_field(
                                progress_embed,
                                name_key="CLEAR_DM_FIELD_PROGRESS",
                                value_key="CLEAR_DM_STATISTICS_PROGRESS",
                                user_id=ctx.author.id,
                                deleted=deleted_count,
                                checked=total_checked,
                                inline=False
                            )
                            progress_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                            await ctx.edit(embed=progress_embed)
                            last_update = deleted_count
                            
                    except discord.NotFound:
                        # Message already deleted
                        continue
                    except discord.Forbidden:
                        # Can't delete this message
                        continue

            # Send final result embed
            if deleted_count > 0:
                success_embed = self.loc_helper.create_success_embed(
                    title_key="CLEAR_DM_SUCCESS_TITLE",
                    description_key="CLEAR_DM_SUCCESS_DESCRIPTION",
                    user_id=ctx.author.id
                )
                self.loc_helper.add_localized_field(
                    success_embed,
                    name_key="CLEAR_DM_FIELD_STATISTICS",
                    value_key="CLEAR_DM_STATISTICS_FINAL",
                    user_id=ctx.author.id,
                    deleted=deleted_count,
                    checked=total_checked,
                    inline=False
                )
                success_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                await ctx.edit(embed=success_embed)
            else:
                no_messages_embed = self.loc_helper.create_info_embed(
                    title_key="CLEAR_DM_NO_MESSAGES_TITLE",
                    description_key="CLEAR_DM_NO_MESSAGES_DESCRIPTION",
                    user_id=ctx.author.id,
                    user_mention=ctx.author.mention
                )
                self.loc_helper.add_localized_field(
                    no_messages_embed,
                    name_key="CLEAR_DM_FIELD_STATISTICS",
                    value_key="CLEAR_DM_STATISTICS_CHECKED",
                    user_id=ctx.author.id,
                    count=total_checked,
                    user_mention=ctx.author.mention,
                    inline=False
                )
                no_messages_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                await ctx.edit(embed=no_messages_embed)

        except Exception as e:
            print(f"Error in clear_dm command: {e}")
            error_embed = self.loc_helper.create_error_embed(
                title_key="CLEAR_DM_ERROR_TITLE",
                description_key="CLEAR_DM_UNEXPECTED_ERROR",
                user_id=ctx.author.id,
                error=str(e)
            )
            try:
                await ctx.edit(embed=error_embed)
            except:
                await ctx.respond(embed=error_embed, ephemeral=True)

    @clear_dm.error
    async def clear_dm_error(self, ctx, error):
        """Handle errors for the clear_dm command."""
        error_msg = self.localization.get_user_lang("CLEAR_DM_ERROR", ctx.author.id)
        try:
            await ctx.respond(error_msg, ephemeral=True)
        except:
            pass

def setup(bot):
    bot.add_cog(ClearDMCog(bot))