"{guild_name}": member.guild.name
"{member_name}": member.display_name
"{member_mention}": member.mention
"{member_avatar}": member.avatar.url if member.avatar else member.default_avatar.url
"{bot_avatar}": self.bot.user.avatar.url if self.bot.user.avatar else None
"{member_count}": str(member.guild.member_count)
"{trademark}": trademark_text