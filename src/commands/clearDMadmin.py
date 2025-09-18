import discord
from discord.ext import commands
import asyncio
from src.utils.localization import LocalizationManager

class ClearDMAdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = LocalizationManager()

    @discord.slash_command(
        name="clear_dm_admin",
        description="Clear DM messages with a specific user or yourself (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild}
    )
    @commands.has_permissions(administrator=True)
    async def clear_dm_admin(
        self, 
        ctx,
        user: discord.Option(
            discord.User,
            description="User to clear DMs with (leave empty to clear your own DMs)",
            required=False,
            default=None
        )
    ):
        """Clear DM messages with a specific user or yourself. Admin only command."""
        try:
            # If no user is provided, use the command author
            target_user = user if user is not None else ctx.author
            
            # Check if user is trying to clear DMs with the bot itself
            if target_user.id == self.bot.user.id:
                error_embed = discord.Embed(
                    title=self.localization.get("CLEAR_DM_ERROR_TITLE"),
                    description=self.localization.get("CLEAR_DM_ADMIN_BOT_TARGET_ERROR"),
                    color=discord.Color.red()
                )
                error_embed.set_footer(text="Please select a different user")
                await ctx.respond(embed=error_embed, ephemeral=True)
                return
            
            # Send initial processing embed
            processing_embed = discord.Embed(
                title=self.localization.get("CLEAR_DM_ADMIN_PROCESSING_TITLE"),
                description=self.localization.get("CLEAR_DM_ADMIN_PROCESSING_DESC", user=target_user.mention),
                color=discord.Color.orange()
            )
            processing_embed.add_field(
                name="Target User", 
                value=f"{target_user.mention}", 
                inline=False
            )
            processing_embed.set_thumbnail(url=target_user.display_avatar.url)
            processing_embed.set_footer(text="This may take a moment...")
            
            await ctx.respond(embed=processing_embed, ephemeral=True)

            # Get the DM channel with the target user
            dm_channel = target_user.dm_channel
            if not dm_channel:
                try:
                    dm_channel = await target_user.create_dm()
                except discord.Forbidden:
                    error_embed = discord.Embed(
                        title=self.localization.get("CLEAR_DM_ERROR_TITLE"),
                        description=self.localization.get("CLEAR_DM_PERMISSION_ERROR"),
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
                                title=self.localization.get("CLEAR_DM_PROGRESS_TITLE"),
                                description=self.localization.get("CLEAR_DM_ADMIN_PROCESSING_DESC", user=target_user.mention),
                                color=discord.Color.orange()
                            )
                            progress_embed.add_field(
                                name=self.localization.get("CLEAR_DM_FIELD_PROGRESS"), 
                                value=self.localization.get("CLEAR_DM_STATISTICS_PROGRESS", deleted=deleted_count, checked=total_checked), 
                                inline=False
                            )
                            progress_embed.set_thumbnail(url=target_user.display_avatar.url)
                            progress_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_WAIT"))
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
                    title=self.localization.get("CLEAR_DM_SUCCESS_TITLE"),
                    description=self.localization.get("CLEAR_DM_ADMIN_SUCCESS", count=deleted_count, user=target_user.mention),
                    color=discord.Color.green()
                )
                success_embed.add_field(
                    name=self.localization.get("CLEAR_DM_FIELD_STATISTICS"), 
                    value=f"{self.localization.get('CLEAR_DM_STATISTICS_DELETED', count=deleted_count)}\n{self.localization.get('CLEAR_DM_STATISTICS_CHECKED', count=total_checked)}", 
                    inline=False
                )
                success_embed.set_thumbnail(url=target_user.display_avatar.url)
                success_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_SUCCESS"))
                await ctx.edit(embed=success_embed)
            else:
                no_messages_embed = discord.Embed(
                    title=self.localization.get("CLEAR_DM_NO_DMS_TITLE"),
                    description=self.localization.get("CLEAR_DM_ADMIN_NO_DMS_DESC", user=target_user.mention),
                    color=discord.Color.blue()
                )
                no_messages_embed.add_field(
                    name=self.localization.get("CLEAR_DM_FIELD_STATISTICS"), 
                    value=self.localization.get("CLEAR_DM_STATISTICS_NO_DELETED", checked=total_checked), 
                    inline=False
                )
                no_messages_embed.set_thumbnail(url=target_user.display_avatar.url)
                no_messages_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_NO_MESSAGES"))
                await ctx.edit(embed=no_messages_embed)

        except Exception as e:
            print(f"Error in clear_dm_admin command: {e}")
            error_embed = discord.Embed(
                title=self.localization.get("CLEAR_DM_ERROR_TITLE"),
                description=self.localization.get("CLEAR_DM_ERROR_DESC", error=str(e)),
                color=discord.Color.red()
            )
            error_embed.add_field(name=self.localization.get("CLEAR_DM_FIELD_ERROR_DETAILS"), value=f"```{str(e)[:1000]}```", inline=False)
            error_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_ERROR"))
            try:
                await ctx.edit(embed=error_embed)
            except:
                await ctx.respond(embed=error_embed, ephemeral=True)

    @clear_dm_admin.error
    async def clear_dm_admin_error(self, ctx, error):
        """Handle errors for the clear_dm_admin command."""
        if isinstance(error, commands.MissingPermissions):
            permission_denied_msg = self.localization.get("CLEAR_DM_ADMIN_PERMISSION_DENIED")
            await ctx.respond(permission_denied_msg, ephemeral=True)
        else:
            error_msg = self.localization.get("CLEAR_DM_ERROR")
            try:
                await ctx.respond(error_msg, ephemeral=True)
            except:
                pass

def setup(bot):
    bot.add_cog(ClearDMAdminCog(bot))