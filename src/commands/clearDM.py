import discord
from discord.ext import commands
import asyncio
from src.utils.localization import LocalizationManager

class ClearDMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = LocalizationManager()

    @discord.slash_command(
        name="clear_dm",
        description="Clear your DM messages with the bot"
    )
    async def clear_dm(self, ctx):
        """Clear DM messages between the user and the bot."""
        try:
            # Send initial processing embed
            processing_embed = discord.Embed(
                title=self.localization.get_user_lang("CLEAR_DM_CLEARING_SELF_PROGRESS", ctx.author.id).split("...")[0] + "...",
                description=self.localization.get_user_lang("CLEAR_DM_CLEARING_SELF_PROGRESS", ctx.author.id),
                color=discord.Color.orange()
            )
            processing_embed.add_field(
                name="User", 
                value=f"{ctx.author.mention}", 
                inline=False
            )
            processing_embed.set_thumbnail(url=ctx.author.display_avatar.url)
            processing_embed.set_footer(text=self.localization.get_user_lang("CLEAR_DM_FOOTER_PROCESSING", ctx.author.id))
            
            await ctx.respond(embed=processing_embed, ephemeral=True, delete_after=120)

            # Get the DM channel with the user
            dm_channel = ctx.author.dm_channel
            if not dm_channel:
                try:
                    dm_channel = await ctx.author.create_dm()
                except discord.Forbidden:
                    error_embed = discord.Embed(
                        title=self.localization.get_user_lang("CLEAR_DM_ERROR_TITLE", ctx.author.id),
                        description=self.localization.get_user_lang("CLEAR_DM_PERMISSION_ERROR", ctx.author.id),
                        color=discord.Color.red()
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
                            progress_embed = discord.Embed(
                                title="🔄 Clearing Messages...",
                                description=self.localization.get_user_lang("CLEAR_DM_CLEARING_SELF_PROGRESS", ctx.author.id),
                                color=discord.Color.orange()
                            )
                            progress_embed.add_field(
                                name=self.localization.get_user_lang("CLEAR_DM_FIELD_PROGRESS", ctx.author.id), 
                                value=self.localization.get_user_lang("CLEAR_DM_STATISTICS_PROGRESS", ctx.author.id, deleted=deleted_count, checked=total_checked), 
                                inline=False
                            )
                            progress_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                            progress_embed.set_footer(text=self.localization.get_user_lang("CLEAR_DM_FOOTER_WAIT", ctx.author.id))
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
                success_embed = discord.Embed(
                    title="✅ Success!",
                    description=self.localization.get_user_lang("CLEAR_DM_SUCCESS", ctx.author.id, count=deleted_count),
                    color=discord.Color.green()
                )
                success_embed.add_field(
                    name=self.localization.get_user_lang("CLEAR_DM_FIELD_STATISTICS", ctx.author.id), 
                    value=f"{self.localization.get_user_lang('CLEAR_DM_STATISTICS_DELETED', ctx.author.id, count=deleted_count)}\n{self.localization.get_user_lang('CLEAR_DM_STATISTICS_CHECKED', ctx.author.id, count=total_checked)}", 
                    inline=False
                )
                success_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                success_embed.set_footer(text=self.localization.get_user_lang("CLEAR_DM_FOOTER_SUCCESS", ctx.author.id))
                await ctx.edit(embed=success_embed)
            else:
                no_messages_embed = discord.Embed(
                    title=self.localization.get_user_lang("CLEAR_DM_NO_DMS_TITLE", ctx.author.id),
                    description=self.localization.get_user_lang("CLEAR_DM_NO_DMS_SELF_DESC", ctx.author.id),
                    color=discord.Color.blue()
                )
                no_messages_embed.add_field(
                    name=self.localization.get_user_lang("CLEAR_DM_FIELD_STATISTICS", ctx.author.id), 
                    value=self.localization.get_user_lang("CLEAR_DM_STATISTICS_NO_DELETED", ctx.author.id, checked=total_checked), 
                    inline=False
                )
                no_messages_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                no_messages_embed.set_footer(text=self.localization.get_user_lang("CLEAR_DM_FOOTER_NO_MESSAGES", ctx.author.id))
                await ctx.edit(embed=no_messages_embed)

        except Exception as e:
            print(f"Error in clear_dm command: {e}")
            error_embed = discord.Embed(
                title=self.localization.get_user_lang("CLEAR_DM_ERROR_TITLE", ctx.author.id),
                description=self.localization.get_user_lang("CLEAR_DM_ERROR_DESC", ctx.author.id, error=str(e)),
                color=discord.Color.red()
            )
            error_embed.add_field(name=self.localization.get_user_lang("CLEAR_DM_FIELD_ERROR_DETAILS", ctx.author.id), value=f"```{str(e)[:1000]}```", inline=False)
            error_embed.set_footer(text=self.localization.get_user_lang("CLEAR_DM_FOOTER_ERROR", ctx.author.id))
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