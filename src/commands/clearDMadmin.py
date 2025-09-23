import discord
from discord.ext import commands
import asyncio
import time
from src.utils.localization import LocalizationManager
from src.utils.localization_helper import LocalizationHelper

class ConfirmationView(discord.ui.View):
	"""Confirmation view with Yes/No buttons for dangerous operations."""
	
	def __init__(self):
		super().__init__(timeout=30.0)  # 30 second timeout
		self.value = None
	
	@discord.ui.button(label="Yes, Clear All", style=discord.ButtonStyle.danger, emoji="⚠️")
	async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Confirm the bulk clear operation."""
		self.value = True
		self.stop()
		await interaction.response.defer()
	
	@discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
	async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Cancel the bulk clear operation."""
		self.value = False
		self.stop()
		await interaction.response.defer()

class ClearDMAdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = bot.localization
        self.loc_helper = LocalizationHelper(bot)

    @discord.slash_command(
        name="clear_dm_admin",
        description="Clear DM messages with a specific user, yourself, or all users (Admin only)",
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
        ),
        clear_all: discord.Option(
            bool,
            description="Clear DMs with ALL users (WARNING: This will clear all bot DM history)",
            required=False,
            default=False
        )
    ):
        """Clear DM messages with a specific user, yourself, or all users. Admin only command."""
        try:
            # Handle bulk clear all users
            if clear_all:
                # Show confirmation dialog for bulk operation
                confirmation_embed = self.loc_helper.create_warning_embed(
                    title_key="CLEAR_DM_ALL_CONFIRMATION_TITLE",
                    description_key="CLEAR_DM_ALL_CONFIRMATION_DESC",
                    user_id=ctx.author.id
                )
                confirmation_embed.set_footer(text="⚠️ This action cannot be undone!")
                
                # Create confirmation view with buttons
                view = ConfirmationView()
                await ctx.respond(embed=confirmation_embed, view=view, ephemeral=True)
                
                # Wait for user response
                await view.wait()
                
                if view.value is None:
                    # Timeout
                    timeout_embed = self.loc_helper.create_warning_embed(
                        title_key="CLEAR_DM_ALL_CONFIRMATION_TITLE",
                        description_key="CLEAR_DM_ALL_TIMEOUT",
                        user_id=ctx.author.id
                    )
                    await ctx.edit(embed=timeout_embed, view=None)
                    return
                elif not view.value:
                    # User cancelled
                    cancelled_embed = self.loc_helper.create_info_embed(
                        title_key="CLEAR_DM_ALL_CONFIRMATION_TITLE",
                        description_key="CLEAR_DM_ALL_CANCELLED",
                        user_id=ctx.author.id
                    )
                    await ctx.edit(embed=cancelled_embed, view=None)
                    return
                
                # User confirmed, proceed with bulk clear
                await self._clear_all_dms(ctx)
                return
            
            # If no user is provided, use the command author
            target_user = user if user is not None else ctx.author
            
            # Check if user is trying to clear DMs with the bot itself
            if target_user.id == self.bot.user.id:
                error_embed = self.loc_helper.create_error_embed(
                    title_key="CLEAR_DM_ERROR_TITLE",
                    description_key="CLEAR_DM_ADMIN_BOT_TARGET_ERROR",
                    user_id=ctx.author.id
                )
                error_embed.set_footer(text="Please select a different user")
                await ctx.respond(embed=error_embed, ephemeral=True)
                return
            
            # Send initial processing embed
            processing_embed = self.loc_helper.create_info_embed(
                title_key="CLEAR_DM_ADMIN_PROCESSING_TITLE",
                description_key="CLEAR_DM_ADMIN_PROCESSING_DESC",
                user_id=ctx.author.id,
                user=target_user.mention
            )
            self.loc_helper.add_localized_field(
                embed=processing_embed,
                name_key="CLEAR_DM_FIELD_TARGET_USER",
                value=f"{target_user.mention}",
                user_id=ctx.author.id,
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
                                title_key="CLEAR_DM_PROGRESS_TITLE",
                                description_key="CLEAR_DM_ADMIN_PROCESSING_DESC",
                                user_id=ctx.author.id,
                                user=target_user.mention
                            )
                            self.loc_helper.add_localized_field(
                                embed=progress_embed,
                                name_key="CLEAR_DM_FIELD_PROGRESS",
                                value_key="CLEAR_DM_STATISTICS_PROGRESS",
                                user_id=ctx.author.id,
                                deleted=deleted_count,
                                checked=total_checked,
                                inline=False
                            )
                            progress_embed.set_thumbnail(url=target_user.display_avatar.url)
                            progress_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_WAIT", user_id=ctx.author.id))
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
                    description_key="CLEAR_DM_ADMIN_SUCCESS",
                    user_id=ctx.author.id,
                    count=deleted_count,
                    user=target_user.mention
                )
                self.loc_helper.add_localized_field(
                    embed=success_embed,
                    name_key="CLEAR_DM_FIELD_STATISTICS",
                    value=f"{self.localization.get('CLEAR_DM_STATISTICS_DELETED', user_id=ctx.author.id, count=deleted_count)}\n{self.localization.get('CLEAR_DM_STATISTICS_CHECKED', user_id=ctx.author.id, count=total_checked)}",
                    user_id=ctx.author.id,
                    inline=False
                )
                success_embed.set_thumbnail(url=target_user.display_avatar.url)
                success_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_SUCCESS", user_id=ctx.author.id))
                await ctx.edit(embed=success_embed)
            else:
                no_messages_embed = self.loc_helper.create_info_embed(
                    title_key="CLEAR_DM_NO_DMS_TITLE",
                    description_key="CLEAR_DM_ADMIN_NO_DMS_DESC",
                    user_id=ctx.author.id,
                    user=target_user.mention
                )
                self.loc_helper.add_localized_field(
                    embed=no_messages_embed,
                    name_key="CLEAR_DM_FIELD_STATISTICS",
                    value_key="CLEAR_DM_STATISTICS_NO_DELETED",
                    user_id=ctx.author.id,
                    checked=total_checked,
                    inline=False
                )
                no_messages_embed.set_thumbnail(url=target_user.display_avatar.url)
                no_messages_embed.set_footer(text=self.localization.get("CLEAR_DM_FOOTER_NO_MESSAGES", user_id=ctx.author.id))
                await ctx.edit(embed=no_messages_embed)

        except Exception as e:
            print(f"Error in clear_dm_admin command: {e}")
            error_embed = self.loc_helper.create_error_embed(
                title_key="CLEAR_DM_ERROR_TITLE",
                description_key="CLEAR_DM_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(e)
            )
            self.loc_helper.add_localized_field(
                embed=error_embed,
                name_key="CLEAR_DM_FIELD_ERROR_DETAILS",
                value=f"```{str(e)[:1000]}```",
                user_id=ctx.author.id,
                inline=False
            )
            try:
                await ctx.edit(embed=error_embed)
            except:
                await ctx.respond(embed=error_embed, ephemeral=True)

    @clear_dm_admin.error
    async def clear_dm_admin_error(self, ctx, error):
        """Handle errors for the clear_dm_admin command."""
        if isinstance(error, commands.MissingPermissions):
            permission_denied_msg = self.localization.get("CLEAR_DM_ADMIN_PERMISSION_DENIED", user_id=ctx.author.id)
            await ctx.respond(permission_denied_msg, ephemeral=True)
        else:
            error_msg = self.localization.get("CLEAR_DM_ERROR", user_id=ctx.author.id)
            try:
                await ctx.respond(error_msg, ephemeral=True)
            except:
                pass

    async def _clear_all_dms(self, ctx):
        """Clear DM messages with all users that have DM channels with the bot."""
        print(f"🔍 Starting bulk DM clear operation by {ctx.author} ({ctx.author.id})")
        start_time = time.time()
        total_deleted = 0
        users_processed = 0
        
        # Get all DM channels
        dm_channels = []
        print(f"📊 Bot has {len(self.bot.private_channels)} private channels cached")
        
        for channel in self.bot.private_channels:
            print(f"🔍 Checking channel: {type(channel).__name__} - {channel}")
            if isinstance(channel, discord.DMChannel):
                dm_channels.append(channel)
                print(f"✅ Added DM channel with {channel.recipient}")
        
        print(f"📊 Found {len(dm_channels)} DM channels to process")
        
        # Alternative approach: Get DM channels from guild members who might have DMed the bot
        if not dm_channels:
            print("🔍 No cached DM channels found. Checking guild members...")
            guild_members = []
            for guild in self.bot.guilds:
                print(f"🏰 Checking guild: {guild.name} ({guild.id}) with {guild.member_count} members")
                guild_members.extend(guild.members)
            
            print(f"👥 Total guild members found: {len(guild_members)}")
            
            # Try to find DM channels by attempting to create them (this will only work if they already exist)
            for member in guild_members[:50]:  # Limit to first 50 members to avoid rate limits
                if member.bot:  # Skip other bots
                    continue
                try:
                    # This will only return existing DM channels, not create new ones
                    if member.dm_channel:
                        dm_channels.append(member.dm_channel)
                        print(f"✅ Found existing DM channel with {member}")
                except Exception as e:
                    print(f"❌ Error checking DM channel for {member}: {e}")
                    continue
        
        print(f"📊 Final DM channels to process: {len(dm_channels)}")
        
        if not dm_channels:
            print("❌ No DM channels found - this means no users have DMed the bot yet")
            # No DM channels found
            no_dms_embed = discord.Embed(
                title=self.localization.get("CLEAR_DM_ALL_NO_DMS_TITLE", user_id=ctx.author.id),
                description=self.localization.get("CLEAR_DM_ALL_NO_DMS_DESC", user_id=ctx.author.id) + "\n\n**Note:** Discord bots can only access DM channels where users have previously sent messages to the bot.",
                color=discord.Color.blue()
            )
            await ctx.edit(embed=no_dms_embed, view=None)
            return
        
        total_users = len(dm_channels)
        print(f"🚀 Starting to process {total_users} DM channels")
        
        # Initial processing embed
        processing_embed = discord.Embed(
            title=self.localization.get("CLEAR_DM_ALL_PROCESSING_TITLE", user_id=ctx.author.id),
            description=self.localization.get("CLEAR_DM_ALL_PROCESSING_DESC", user_id=ctx.author.id),
            color=discord.Color.orange()
        )
        processing_embed.add_field(
            name="Progress", 
            value=self.localization.get("CLEAR_DM_ALL_PROGRESS_USERS", user_id=ctx.author.id, current=0, total=total_users),
            inline=False
        )
        processing_embed.add_field(
            name="Messages", 
            value=self.localization.get("CLEAR_DM_ALL_PROGRESS_MESSAGES", user_id=ctx.author.id, deleted=0),
            inline=False
        )
        processing_embed.set_footer(text="This may take several minutes...")
        await ctx.edit(embed=processing_embed, view=None)
        
        # Process each DM channel
        for dm_channel in dm_channels:
            users_processed += 1
            user = dm_channel.recipient
            
            if not user:
                print(f"⚠️ DM channel has no recipient, skipping...")
                continue
            
            print(f"🔄 Processing DM channel with {user} ({user.id}) - {users_processed}/{total_users}")
            
            # Update progress embed
            if users_processed % 5 == 0 or users_processed == total_users:  # Update every 5 users or at the end
                progress_embed = discord.Embed(
                    title=self.localization.get("CLEAR_DM_ALL_PROCESSING_TITLE", user_id=ctx.author.id),
                    description=self.localization.get("CLEAR_DM_ALL_PROCESSING_DESC", user_id=ctx.author.id),
                    color=discord.Color.orange()
                )
                progress_embed.add_field(
                    name="Progress", 
                    value=self.localization.get("CLEAR_DM_ALL_PROGRESS_USERS", user_id=ctx.author.id, current=users_processed, total=total_users),
                    inline=False
                )
                progress_embed.add_field(
                    name="Messages", 
                    value=self.localization.get("CLEAR_DM_ALL_PROGRESS_MESSAGES", user_id=ctx.author.id, deleted=total_deleted),
                    inline=False
                )
                progress_embed.add_field(
                    name="Current User", 
                    value=self.localization.get("CLEAR_DM_ALL_CURRENT_USER", user_id=ctx.author.id, user=user.mention if user else "Unknown"),
                    inline=False
                )
                progress_embed.set_footer(text="Please wait...")
                await ctx.edit(embed=progress_embed)
            
            # Clear messages in this DM channel
            messages_in_channel = 0
            deleted_in_channel = 0
            try:
                async for message in dm_channel.history(limit=None):
                    messages_in_channel += 1
                    if message.author == self.bot.user:
                        try:
                            await message.delete()
                            total_deleted += 1
                            deleted_in_channel += 1
                            print(f"🗑️ Deleted message from {user} - Total deleted: {total_deleted}")
                            # Rate limiting - wait between deletions
                            await asyncio.sleep(0.1)
                        except (discord.NotFound, discord.Forbidden):
                            # Message already deleted or can't delete
                            print(f"⚠️ Could not delete message (NotFound/Forbidden)")
                            continue
                print(f"📊 Channel with {user}: {messages_in_channel} total messages, {deleted_in_channel} bot messages deleted")
            except discord.Forbidden:
                # Can't access this DM channel
                print(f"❌ Forbidden: Cannot access DM channel with {user}")
                continue
            except Exception as e:
                print(f"❌ Error processing DM with {user}: {e}")
                continue
        
        # Calculate elapsed time
        elapsed_time = int(time.time() - start_time)
        print(f"✅ Bulk clear completed: {total_deleted} messages deleted from {users_processed} users in {elapsed_time} seconds")
        
        # Final result embed
        if total_deleted > 0:
            success_embed = discord.Embed(
                title=self.localization.get("CLEAR_DM_ALL_SUCCESS_TITLE", user_id=ctx.author.id),
                description=self.localization.get("CLEAR_DM_ALL_SUCCESS_DESC", user_id=ctx.author.id),
                color=discord.Color.green()
            )
            success_embed.add_field(
                name="Statistics", 
                value=self.localization.get("CLEAR_DM_ALL_STATISTICS", user_id=ctx.author.id, users=users_processed, messages=total_deleted, time=elapsed_time),
                inline=False
            )
            success_embed.set_footer(text="Bulk clear operation completed successfully")
            await ctx.edit(embed=success_embed)
        else:
            no_messages_embed = discord.Embed(
                title=self.localization.get("CLEAR_DM_ALL_NO_DMS_TITLE", user_id=ctx.author.id),
                description="No bot messages found to delete in any DM channels.\n\n**This is normal if:**\n• The bot hasn't sent DMs to users yet\n• All bot messages were already deleted\n• Users haven't initiated DM conversations",
                color=discord.Color.blue()
            )
            no_messages_embed.add_field(
                name="Statistics", 
                value=f"📊 **{users_processed}** users checked\n🗑️ **0** messages deleted\n⏱️ **{elapsed_time}** seconds elapsed",
                inline=False
            )
            await ctx.edit(embed=no_messages_embed)

def setup(bot):
    bot.add_cog(ClearDMAdminCog(bot))