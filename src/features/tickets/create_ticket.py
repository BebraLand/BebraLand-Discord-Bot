import discord
import asyncio
import io
from datetime import datetime
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db, get_language
from src.languages.localize import translate
from src.languages import emoji_constants as emoji

logger = get_cool_logger(__name__)


async def send_dm_notification(user: discord.User, ticket_id: int, action: str, channel: discord.TextChannel = None, closed_by: discord.User = None, bot_user: discord.User = None):
    """Send DM notification to user about ticket action."""
    try:
        lang = await get_language(user.id)
        
        if action == "closed":
            closer_name = closed_by.name if closed_by else "Unknown"
            title = emoji.LOCK_EMOJI + " " + translate("Ticket Closed", lang)
            description = translate("Your ticket **#{ticket_id}** has been closed by **{closer_name}**.\nThank you for contacting support!", lang).format(ticket_id=ticket_id, closer_name=closer_name)
        elif action == "reopened":
            reopener_name = closed_by.name if closed_by else "support staff"
            title = emoji.UNLOCK_EMOJI + " " + translate("Ticket Reopened", lang)
            description = translate("Your ticket **#{ticket_id}** has been reopened by **{reopener_name}**.\nYou can continue the conversation.", lang).format(ticket_id=ticket_id, reopener_name=reopener_name)
            if channel:
                description += f"\n\n**Channel:** {channel.mention}"
        
        embed = discord.Embed(title=title, description=description, color=constants.DISCORD_EMBED_COLOR)
        # Prefer explicit bot_user's avatar for footer icon; fall back to channel guild bot avatar when available
        icon_url = None
        if bot_user:
            try:
                icon_url = bot_user.display_avatar.url
            except Exception:
                icon_url = None
        elif channel and getattr(channel, "guild", None) and channel.guild.me:
            try:
                icon_url = channel.guild.me.avatar.url
            except Exception:
                icon_url = None

        if icon_url:
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=icon_url)
        else:
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
        
        await user.send(embed=embed)
        logger.info(f"Sent DM notification to user {user.id} for ticket #{ticket_id} action: {action}")
    except discord.Forbidden:
        logger.warning(f"Could not send DM to user {user.id} - DMs are disabled")
    except Exception as e:
        logger.error(f"Error sending DM notification: {e}")


async def create_transcript(channel: discord.TextChannel) -> io.BytesIO:
    """Create a text transcript of all messages in a channel."""
    transcript = io.StringIO()
    transcript.write(f"Transcript of #{channel.name}\n")
    transcript.write(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    transcript.write("=" * 80 + "\n\n")
    
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages.append(message)
    
    for message in messages:
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        transcript.write(f"[{timestamp}] {message.author.name} (ID: {message.author.id})\n")
        if message.content:
            transcript.write(f"{message.content}\n")
        if message.attachments:
            transcript.write("Attachments:\n")
            for attachment in message.attachments:
                transcript.write(f"  - {attachment.filename} ({attachment.url})\n")
        if message.embeds:
            transcript.write(f"[{len(message.embeds)} embed(s)]\n")
        transcript.write("\n")
    
    transcript.write("=" * 80 + "\n")
    transcript.write(f"End of transcript - Total messages: {len(messages)}\n")
    
    transcript_bytes = io.BytesIO(transcript.getvalue().encode('utf-8'))
    transcript_bytes.seek(0)
    return transcript_bytes


class TicketControlPanel(discord.ui.View):
    """Control panel for closed tickets with Transcript, Reopen, and Delete buttons."""
    
    def __init__(self, ticket_id: int, user: discord.User, category_name: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user = user
        self.category_name = category_name
        self.transcript_button.custom_id = f"ticket_transcript_{ticket_id}"
        self.reopen_button.custom_id = f"ticket_reopen_{ticket_id}"
        self.delete_button.custom_id = f"ticket_delete_{ticket_id}"
    
    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="transcript_btn")
    async def transcript_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            transcript_file = await create_transcript(interaction.channel)
            file = discord.File(transcript_file, filename=f"ticket-{self.ticket_id}-transcript.txt")
            
            if constants.TICKET_LOG_CHANNEL_ID:
                log_channel = interaction.guild.get_channel(constants.TICKET_LOG_CHANNEL_ID)
                if log_channel:
                    embed = discord.Embed(
                        title=emoji.TRANSCRIPT_EMOJI + " Ticket Transcript",
                        description=f"**Ticket ID:** {self.ticket_id}\n**User:** {self.user.mention}\n**Category:** {self.category_name}\n**Generated by:** {interaction.user.mention}",
                        color=constants.DISCORD_EMBED_COLOR
                    )
                    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
                    await log_channel.send(embed=embed, file=file)
            
            transcript_file.seek(0)
            user_file = discord.File(transcript_file, filename=f"ticket-{self.ticket_id}-transcript.txt")
            await interaction.followup.send(emoji.CHECK_EMOJI + " Transcript created and sent to log channel!", file=user_file, ephemeral=True)
            logger.info(f"Transcript created for ticket #{self.ticket_id} by {interaction.user.id}")
        except Exception as e:
            logger.error(f"Error creating transcript: {e}")
            await interaction.followup.send(emoji.CROSS_EMOJI + " Failed to create transcript.", ephemeral=True)
    
    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.success, emoji="🔓", custom_id="reopen_btn")
    async def reopen_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        is_support = (
            interaction.user.id in constants.TICKET_SUPPORT_USER_IDS or
            (constants.TICKET_SUPPORT_ROLE_ID and any(role.id == constants.TICKET_SUPPORT_ROLE_ID for role in interaction.user.roles))
        )
        
        if not is_support:
            await interaction.response.send_message(emoji.CROSS_EMOJI + " Only support staff can reopen tickets.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            db = await get_db()
            if not await db.reopen_ticket(self.ticket_id):
                await interaction.followup.send(emoji.CROSS_EMOJI + " Failed to reopen ticket.", ephemeral=True)
                return
            
            # Restore user permissions
            await interaction.channel.set_permissions(
                self.user,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True
            )
            
            # Delete the control panel message
            await interaction.message.delete()
            
            # Send new message with close button
            embed = discord.Embed(
                title=emoji.UNLOCK_EMOJI + " Ticket Reopened",
                description=f"This ticket has been reopened by {interaction.user.mention}.\n{self.user.mention} can now continue the conversation.",
                color=0x00FF00
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
            
            close_view = CloseTicketView(self.ticket_id, self.user, self.category_name)
            await interaction.channel.send(embed=embed, view=close_view)
            
            # Log the reopen
            if constants.TICKET_LOG_CHANNEL_ID:
                log_channel = interaction.guild.get_channel(constants.TICKET_LOG_CHANNEL_ID)
                if log_channel:
                    log_embed = discord.Embed(
                        title=emoji.UNLOCK_EMOJI + " Ticket Reopened",
                        description=f"**Ticket ID:** {self.ticket_id}\n**User:** {self.user.mention}\n**Category:** {self.category_name}\n**Reopened by:** {interaction.user.mention}",
                        color=0x00FF00
                    )
                    log_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
                    await log_channel.send(embed=log_embed)
            
            # Send DM to user with channel link
            await send_dm_notification(self.user, self.ticket_id, "reopened", interaction.channel, interaction.user, interaction.client.user)
            logger.info(f"Ticket #{self.ticket_id} reopened by {interaction.user.id}")
        except Exception as e:
            logger.error(f"Error reopening ticket: {e}")
            await interaction.followup.send(emoji.CROSS_EMOJI + " Failed to reopen ticket.", ephemeral=True)
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete_btn")
    async def delete_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        is_support = (
            interaction.user.id in constants.TICKET_SUPPORT_USER_IDS or
            (constants.TICKET_SUPPORT_ROLE_ID and any(role.id == constants.TICKET_SUPPORT_ROLE_ID for role in interaction.user.roles))
        )
        
        if not is_support:
            await interaction.response.send_message(emoji.CROSS_EMOJI + " Only support staff can delete tickets.", ephemeral=True)
            return
        
        lang = await get_language(interaction.user.id)
        delete_msg = translate("This ticket will be deleted in 5 seconds...", lang)
        
        embed = discord.Embed(
            title=emoji.TRASH_EMOJI + " " + translate("Deleting Ticket", lang),
            description=delete_msg,
            color=0xFF0000
        )
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
        # Log the deletion
        if constants.TICKET_LOG_CHANNEL_ID:
            log_channel = interaction.guild.get_channel(constants.TICKET_LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title=emoji.TRASH_EMOJI + " Ticket Deleted",
                    description=f"**Ticket ID:** {self.ticket_id}\n**User:** {self.user.mention}\n**Category:** {self.category_name}\n**Deleted by:** {interaction.user.mention}",
                    color=0xFF0000
                )
                log_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
                await log_channel.send(embed=log_embed)
        
        await asyncio.sleep(5)
        
        # Delete ticket from database
        try:
            db = await get_db()
            await db.delete_ticket(self.ticket_id)
        except Exception as e:
            logger.error(f"Failed to delete ticket from database: {e}")
        
        await interaction.channel.delete(reason=f"Ticket #{self.ticket_id} deleted by {interaction.user.name}")
        logger.info(f"Ticket #{self.ticket_id} deleted by {interaction.user.id}")


class CloseTicketView(discord.ui.View):
    """View with Close Ticket button."""
    
    def __init__(self, ticket_id: int, user: discord.User, category_name: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user = user
        self.category_name = category_name
        self.close_button.custom_id = f"ticket_close_{ticket_id}"
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        is_support = (
            interaction.user.id in constants.TICKET_SUPPORT_USER_IDS or
            (constants.TICKET_SUPPORT_ROLE_ID and any(role.id == constants.TICKET_SUPPORT_ROLE_ID for role in interaction.user.roles))
        )
        
        if interaction.user.id != self.user.id and not is_support:
            await interaction.response.send_message(emoji.CROSS_EMOJI + " Only the ticket creator or support staff can close this ticket.", ephemeral=True)
            return
        
        lang = await get_language(interaction.user.id)
        confirm_title = translate("Are you sure you would like to close this ticket?", lang)
        confirm_view = ConfirmCloseView(self.ticket_id, self.user, self.category_name, interaction.user, is_support)
        # Make the confirmation visible only to the user who clicked the close button
        # The confirm view will explicitly send the public control panel to the channel
        await interaction.response.send_message(confirm_title, view=confirm_view, ephemeral=True)


class ConfirmCloseView(discord.ui.View):
    """Confirmation view for closing tickets."""
    
    def __init__(self, ticket_id: int, ticket_owner: discord.User, category_name: str, closer: discord.User, is_support: bool):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.ticket_owner = ticket_owner
        self.category_name = category_name
        self.closer = closer
        self.is_support = is_support
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Acknowledge the interaction as ephemeral (we'll delete the ephemeral confirmation later)
        await interaction.response.defer(ephemeral=True)
        
        try:
            db = await get_db()
            if not await db.close_ticket(self.ticket_id):
                await interaction.followup.send(emoji.CROSS_EMOJI + " Failed to close ticket. Please try again.", ephemeral=True)
                return
            
            # Remove user's access to the channel
            await interaction.channel.set_permissions(self.ticket_owner, read_messages=False, send_messages=False)
            
            # Create control panel embed (always in English for admins)
            embed = discord.Embed(
                title=emoji.LOCK_EMOJI + f" Ticket Closed by {self.closer.name}",
                description="Support team ticket controls",
                color=0xFF0000
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
            
            control_panel = TicketControlPanel(self.ticket_id, self.ticket_owner, self.category_name)
            # Always send the control panel publicly in the ticket channel so staff can use it.
            try:
                await interaction.channel.send(embed=embed, view=control_panel)
            except Exception as e:
                logger.error(f"Failed to send control panel message: {e}")

            # Delete the ephemeral confirmation message (if present) to avoid "This interaction failed"
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
            
            # Log the closure
            if constants.TICKET_LOG_CHANNEL_ID:
                log_channel = interaction.guild.get_channel(constants.TICKET_LOG_CHANNEL_ID)
                if log_channel:
                    log_embed = discord.Embed(
                        title=emoji.LOCK_EMOJI + " Ticket Closed",
                        description=f"**Ticket ID:** {self.ticket_id}\n**User:** {self.ticket_owner.mention}\n**Category:** {self.category_name}\n**Closed by:** {self.closer.mention}",
                        color=0xFF0000
                    )
                    log_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.avatar.url)
                    await log_channel.send(embed=log_embed)
            
            # Send DM to user if closed by admin (not by themselves)
            if self.closer.id != self.ticket_owner.id:
                await send_dm_notification(self.ticket_owner, self.ticket_id, "closed", None, self.closer, interaction.client.user)
            
            logger.info(f"Ticket #{self.ticket_id} closed by {self.closer.id}")
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            await interaction.followup.send(emoji.CROSS_EMOJI + " Failed to close ticket. Please try again.", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Acknowledge then delete the original ephemeral confirmation message.
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.delete_original_response()
        except Exception:
            pass


async def create_ticket(user: discord.User, category_name: str, guild: discord.Guild) -> tuple[bool, str]:
    """Create a ticket for a user."""
    db = await get_db()
    lang = await get_language(user.id)
    
    ticket_count = await db.ticket_count(str(user.id))
    if ticket_count >= constants.MAX_TICKETS_PER_USER:
        logger.info(f"User {user.id} has reached the maximum number of tickets ({ticket_count}/{constants.MAX_TICKETS_PER_USER})")
        error_msg = emoji.CROSS_EMOJI + " " + translate("You already have {ticket_count} open ticket(s). Please close an existing ticket before creating a new one. (Maximum: {max})", lang).format(ticket_count=ticket_count, max=constants.MAX_TICKETS_PER_USER)
        return False, error_msg
    
    ticket_id = await db.create_ticket(str(user.id), category_name)
    if not ticket_id:
        logger.error(f"Failed to create ticket in database for user {user.id}")
        return False, emoji.CROSS_EMOJI + " " + translate("Failed to create ticket. Please try again later.", lang)
    
    category = guild.get_channel(constants.TICKET_CATEGORY)
    if not category or not isinstance(category, discord.CategoryChannel):
        logger.error(f"Ticket category {constants.TICKET_CATEGORY} not found or is not a category")
        return False, emoji.CROSS_EMOJI + " " + translate("Ticket system is not properly configured. Please contact an administrator.", lang)
    
    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_messages=True)
        }
        
        if constants.TICKET_SUPPORT_ROLE_ID:
            support_role = guild.get_role(constants.TICKET_SUPPORT_ROLE_ID)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True)
        
        if constants.TICKET_SUPPORT_USER_IDS:
            for support_user_id in constants.TICKET_SUPPORT_USER_IDS:
                support_user = guild.get_member(support_user_id)
                if support_user:
                    overwrites[support_user] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True, manage_messages=True)
        
        channel = await category.create_text_channel(
            name=f"ticket-{ticket_id}-{user.name}",
            overwrites=overwrites,
            topic=f"Ticket #{ticket_id} | User: {user.name} | Category: {category_name}"
        )
        
        await db.update_ticket_channel(ticket_id, channel.id)
        
        # Welcome message always in English
        embed = discord.Embed(
            title=f"{emoji.TICKET_EMOJI} Ticket #{ticket_id}",
            description=f"Welcome {user.mention}!\n\n**Category:** {category_name}\n\nPlease describe your issue or question. A staff member will assist you shortly.\n\nTo close this press the close button",
            color=constants.DISCORD_EMBED_COLOR
        )
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=guild.me.avatar.url)
        
        close_view = CloseTicketView(ticket_id, user, category_name)
        await channel.send(embed=embed, view=close_view)
        
        # Log the ticket creation
        if constants.TICKET_LOG_CHANNEL_ID:
            log_channel = guild.get_channel(constants.TICKET_LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title=f"{emoji.TICKET_EMOJI} New Ticket Created",
                    description=f"**Ticket ID:** {ticket_id}\n**User:** {user.mention}\n**Category:** {category_name}\n**Channel:** {channel.mention}",
                    color=0x00FF00
                )
                log_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=guild.me.avatar.url)
                await log_channel.send(embed=log_embed)
        
        logger.info(f"Created ticket #{ticket_id} for user {user.id} in channel {channel.id}")
        
        # Return success embed instead of plain text
        success_embed = discord.Embed(
            title=emoji.CHECK_EMOJI + " " + translate("Ticket Created", lang),
            description=translate("Your ticket has been created: {channel}", lang).format(channel=channel.mention),
            color=0x00FF00
        )
        success_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
        return True, success_embed
        
    except Exception as e:
        logger.error(f"Failed to create ticket channel: {e}")
        await db.close_ticket(ticket_id)
        return False, emoji.CROSS_EMOJI + " " + translate("Failed to create ticket channel. Please try again later.", lang)
