import discord
from discord.ext import commands
import json
import os
from src.utils.localization import LocalizationManager


class SetWelcomeMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_message_path = "src/languages/welcome_message.json"
        self.localization = LocalizationManager()

    @discord.slash_command(
        name="set_welcome_message",
        description="Set the welcome message JSON (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild}
    )
    @commands.has_permissions(administrator=True)
    async def set_welcome_message(
        self, 
        ctx: discord.ApplicationContext,
        content: discord.Option(
            str,
            description="JSON content for the welcome message",
            required=True
        )
    ):
        """
        Admin-only command to update the welcome message JSON.
        Validates JSON format and updates the welcome_message.json file.
        """
        try:
            # Parse and validate JSON
            parsed_json = json.loads(content)
            
            # Validate required fields
            required_fields = ["title", "description"]
            missing_fields = [field for field in required_fields if field not in parsed_json]
            
            if missing_fields:
                embed = discord.Embed(
                    title=self.localization.get("SET_WELCOME_JSON_VALIDATION_ERROR_TITLE"),
                    description=self.localization.get("SET_WELCOME_MISSING_FIELDS", missing_fields=', '.join(missing_fields)),
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Validate JSON structure (optional fields)
            valid_optional_fields = ["fields", "image", "footer", "color", "thumbnail"]
            
            # Check if fields array has correct structure if present
            if "fields" in parsed_json:
                if not isinstance(parsed_json["fields"], list):
                    embed = discord.Embed(
                        title=self.localization.get("SET_WELCOME_JSON_VALIDATION_ERROR_TITLE"),
                        description=self.localization.get("SET_WELCOME_FIELDS_MUST_BE_ARRAY"),
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                for i, field in enumerate(parsed_json["fields"]):
                    if not isinstance(field, dict) or "name" not in field or "value" not in field:
                        embed = discord.Embed(
                            title=self.localization.get("SET_WELCOME_JSON_VALIDATION_ERROR_TITLE"),
                            description=self.localization.get("SET_WELCOME_FIELD_INVALID", field_number=i+1),
                            color=discord.Color.red()
                        )
                        await ctx.respond(embed=embed, ephemeral=True)
                        return
            
            # Pretty format the JSON
            formatted_json = json.dumps(parsed_json, indent=2, ensure_ascii=False)
            
            # Write to file
            os.makedirs(os.path.dirname(self.welcome_message_path), exist_ok=True)
            with open(self.welcome_message_path, 'w', encoding='utf-8') as f:
                f.write(formatted_json)
            
            # Success response
            embed = discord.Embed(
                title=self.localization.get("SET_WELCOME_SUCCESS_TITLE"),
                description=self.localization.get("SET_WELCOME_SUCCESS_DESC"),
                color=discord.Color.green()
            )
            
            # Add a preview of the updated content (truncated if too long)
            preview = formatted_json[:1000] + "..." if len(formatted_json) > 1000 else formatted_json
            embed.add_field(
                name=self.localization.get("SET_WELCOME_UPDATED_CONTENT"),
                value=f"```json\n{preview}\n```",
                inline=False
            )
            
            await ctx.respond(embed=embed, ephemeral=True)
            
        except json.JSONDecodeError as e:
            embed = discord.Embed(
                title=self.localization.get("SET_WELCOME_JSON_PARSE_ERROR_TITLE"),
                description=self.localization.get("SET_WELCOME_JSON_PARSE_ERROR_DESC", error=str(e)),
                color=discord.Color.red()
            )
            embed.add_field(
                name=self.localization.get("SET_WELCOME_ERROR_DETAILS"),
                value=f"Line {e.lineno}, Column {e.colno}" if hasattr(e, 'lineno') else self.localization.get("SET_WELCOME_CHECK_SYNTAX"),
                inline=False
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except PermissionError:
            embed = discord.Embed(
                title=self.localization.get("SET_WELCOME_FILE_PERMISSION_ERROR_TITLE"),
                description=self.localization.get("SET_WELCOME_FILE_PERMISSION_ERROR_DESC"),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title=self.localization.get("SET_WELCOME_UNEXPECTED_ERROR_TITLE"),
                description=self.localization.get("SET_WELCOME_UNEXPECTED_ERROR_DESC", error=str(e)),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @set_welcome_message.error
    async def set_welcome_message_error(self, ctx: discord.ApplicationContext, error):
        """Handle command errors, especially permission errors."""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title=self.localization.get("SET_WELCOME_PERMISSION_DENIED_TITLE"),
                description=self.localization.get("SET_WELCOME_PERMISSION_DENIED_DESC"),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title=self.localization.get("SET_WELCOME_COMMAND_ERROR_TITLE"),
                description=self.localization.get("SET_WELCOME_COMMAND_ERROR_DESC", error=str(error)),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(SetWelcomeMessageCog(bot))