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
        description="Clear DM messages with a specific user (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True)
    )
    @commands.has_permissions(administrator=True)
    async def clear_dm_admin(
        self, 
        ctx,
        user: discord.Option(
            discord.User,
            description="User to clear DMs with",
            required=True
        )
    ):
        """Clear DM messages with a specific user. Admin only command."""
        try:
            # Use the provided user directly
            target_user = user
            
            # Check if user is trying to clear DMs with the bot itself
            if target_user.id == self.bot.user.id:
                error_embed = discord.Embed(
                    title="❌ Invalid Target",
                    description="You cannot clear DM messages with the bot itself!",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text="Please select a different user")
                await ctx.respond(embed=error_embed, ephemeral=True)
                return
            
            # Send initial processing embed
            processing_embed = discord.Embed(
                title="🔄 Processing...",
                description=f"Clearing DM messages with {target_user.mention}...",
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
                        title="❌ Permission Error",
                        description="Cannot access DM messages. Permission denied.",
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
                                description=f"Clearing DM messages with {target_user.mention}...",
                                color=discord.Color.orange()
                            )
                            progress_embed.add_field(
                                name="Progress", 
                                value=f"✅ **{deleted_count}** messages cleared\n📊 **{total_checked}** messages checked", 
                                inline=False
                            )
                            progress_embed.set_thumbnail(url=target_user.display_avatar.url)
                            progress_embed.set_footer(text="Please wait...")
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
                    description=f"Successfully cleared **{deleted_count}** messages with {target_user.mention}",
                    color=discord.Color.green()
                )
                success_embed.add_field(
                    name="Statistics", 
                    value=f"🗑️ **{deleted_count}** messages deleted\n📊 **{total_checked}** messages checked", 
                    inline=False
                )
                success_embed.set_thumbnail(url=target_user.display_avatar.url)
                success_embed.set_footer(text="Operation completed successfully")
                await ctx.edit(embed=success_embed)
            else:
                no_messages_embed = discord.Embed(
                    title="ℹ️ No Messages Found",
                    description=f"No messages found to clear with {target_user.mention}",
                    color=discord.Color.blue()
                )
                no_messages_embed.add_field(
                    name="Statistics", 
                    value=f"📊 **{total_checked}** messages checked\n🗑️ **0** messages deleted", 
                    inline=False
                )
                no_messages_embed.set_thumbnail(url=target_user.display_avatar.url)
                no_messages_embed.set_footer(text="No bot messages found in DMs")
                await ctx.edit(embed=no_messages_embed)

        except Exception as e:
            print(f"Error in clear_dm_admin command: {e}")
            error_embed = discord.Embed(
                title="❌ Error Occurred",
                description="An unexpected error occurred while clearing messages.",
                color=discord.Color.red()
            )
            error_embed.add_field(name="Error Details", value=f"```{str(e)[:1000]}```", inline=False)
            error_embed.set_footer(text="Please try again or contact support")
            try:
                await ctx.edit(embed=error_embed)
            except:
                await ctx.respond(embed=error_embed, ephemeral=True)

    @clear_dm_admin.error
    async def clear_dm_admin_error(self, ctx, error):
        """Handle errors for the clear_dm_admin command."""
        if isinstance(error, commands.MissingPermissions):
            permission_denied_msg = self.localization.get("CLEAR_DM_PERMISSION_DENIED")
            await ctx.respond(permission_denied_msg, ephemeral=True)
        else:
            error_msg = self.localization.get("CLEAR_DM_ERROR")
            try:
                await ctx.respond(error_msg, ephemeral=True)
            except:
                pass

def setup(bot):
    bot.add_cog(ClearDMAdminCog(bot))