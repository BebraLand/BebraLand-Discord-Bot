import discord

# Expose a shared SlashCommandGroup for admin commands within the package
admin_group = discord.SlashCommandGroup(
    "admin",
    "Admin related commands",
    default_member_permissions=discord.Permissions(administrator=True),
    contexts={discord.InteractionContextType.guild},
)

__all__ = ["admin_group"]
