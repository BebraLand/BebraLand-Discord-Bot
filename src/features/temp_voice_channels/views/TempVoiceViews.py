from .KickUserSelect import KickUserSelect
from .InviteUserSelect import InviteUserSelect
from .RejectMentionableSelect import RejectMentionableSelect
from .PermitMentionableSelect import PermitMentionableSelect
from .TransferUserSelect import TransferUserSelect
import discord
from discord import ui
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class TransferView(ui.View):
    """View for the transfer select."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int, current_owner: discord.Member):
        super().__init__(timeout=300)
        self.add_item(TransferUserSelect(channel, owner_id, current_owner))


class PermitView(ui.View):
    """View for the permit select."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(PermitMentionableSelect(channel, owner_id))


class RejectView(ui.View):
    """View for the reject select."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(RejectMentionableSelect(channel, owner_id))


class InviteView(ui.View):
    """View for the invite button."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(InviteUserSelect(channel, owner_id))


class KickView(ui.View):
    """View for the kick button."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(KickUserSelect(channel, owner_id))
