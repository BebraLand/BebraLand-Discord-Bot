import discord
from discord import ui
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

class RegionSelect(ui.Select):
    """Select menu for region."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        self.channel = channel
        self.owner_id = owner_id
        
        options = [
            discord.SelectOption(label="Automatic", value="auto", description="Let Discord choose the best region", emoji="🌐"),
            discord.SelectOption(label="US West", value="us-west", description="US West Coast", emoji="🇺🇸"),
            discord.SelectOption(label="US East", value="us-east", description="US East Coast", emoji="🇺🇸"),
            discord.SelectOption(label="US Central", value="us-central", description="US Central", emoji="🇺🇸"),
            discord.SelectOption(label="US South", value="us-south", description="US South", emoji="🇺🇸"),
            discord.SelectOption(label="Europe", value="europe", description="Europe", emoji="🇪🇺"),
            discord.SelectOption(label="Singapore", value="singapore", description="Singapore", emoji="🇸🇬"),
            discord.SelectOption(label="Russia", value="russia", description="Russia", emoji="🇷🇺"),
            discord.SelectOption(label="Japan", value="japan", description="Japan", emoji="🇯🇵"),
            discord.SelectOption(label="Brazil", value="brazil", description="Brazil", emoji="🇧🇷"),
            discord.SelectOption(label="Hong Kong", value="hongkong", description="Hong Kong", emoji="🇭🇰"),
            discord.SelectOption(label="Sydney", value="sydney", description="Sydney", emoji="🇦🇺"),
            discord.SelectOption(label="South Africa", value="southafrica", description="South Africa", emoji="🇿🇦"),
            discord.SelectOption(label="India", value="india", description="India", emoji="🇮🇳"),
        ]
        
        super().__init__(placeholder="Select a region", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change the region!", ephemeral=True)
            return

        try:
            region_value = None if self.values[0] == "auto" else self.values[0]
            await self.channel.edit(rtc_region=region_value)
            region_name = "Automatic" if region_value is None else self.values[0]
            await interaction.response.send_message(f"✅ Region set to: **{region_name}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)