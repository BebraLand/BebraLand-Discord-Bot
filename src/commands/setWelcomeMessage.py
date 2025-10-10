import discord
from discord.ext import commands
import json
import os
from src.utils.localization import LocalizationManager
from src.utils.localization_helper import LocalizationHelper


class SetWelcomeMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_message_path = "src/languages/welcome_message.json"
        self.localization = LocalizationManager()
        self.loc_helper = LocalizationHelper(bot)

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
                embed = self.loc_helper.create_error_embed(
                    title_key="SET_WELCOME_JSON_VALIDATION_ERROR_TITLE",
                    description_key="SET_WELCOME_MISSING_FIELDS",
                    user_id=ctx.author.id,
                    missing_fields=', '.join(missing_fields)
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Validate JSON structure (optional fields)
            valid_optional_fields = ["fields", "image", "footer", "color", "thumbnail"]
            
            # Check if fields array has correct structure if present
            if "fields" in parsed_json:
                if not isinstance(parsed_json["fields"], list):
                    embed = self.loc_helper.create_error_embed(
                        title_key="SET_WELCOME_JSON_VALIDATION_ERROR_TITLE",
                        description_key="SET_WELCOME_FIELDS_MUST_BE_ARRAY",
                        user_id=ctx.author.id
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                for i, field in enumerate(parsed_json["fields"]):
                    if not isinstance(field, dict) or "name" not in field or "value" not in field:
                        embed = self.loc_helper.create_error_embed(
                            title_key="SET_WELCOME_JSON_VALIDATION_ERROR_TITLE",
                            description_key="SET_WELCOME_FIELD_INVALID",
                            user_id=ctx.author.id,
                            field_number=i+1
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
            embed = self.loc_helper.create_success_embed(
                title_key="SET_WELCOME_SUCCESS_TITLE",
                description_key="SET_WELCOME_SUCCESS_DESC",
                user_id=ctx.author.id
            )
            
            # Add a preview of the updated content (truncated if too long)
            preview = formatted_json[:1000] + "..." if len(formatted_json) > 1000 else formatted_json
            self.loc_helper.add_localized_field(
                embed=embed,
                name_key="SET_WELCOME_UPDATED_CONTENT",
                value=f"```json\n{preview}\n```",
                user_id=ctx.author.id,
                inline=False
            )
            
            await ctx.respond(embed=embed, ephemeral=True)
            
        except json.JSONDecodeError as e:
            embed = self.loc_helper.create_error_embed(
                title_key="SET_WELCOME_JSON_PARSE_ERROR_TITLE",
                description_key="SET_WELCOME_JSON_PARSE_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(e)
            )
            self.loc_helper.add_localized_field(
                embed=embed,
                name_key="SET_WELCOME_ERROR_DETAILS",
                value=f"Line {e.lineno}, Column {e.colno}" if hasattr(e, 'lineno') else self.localization.get("SET_WELCOME_CHECK_SYNTAX", ctx.author.id),
                user_id=ctx.author.id,
                inline=False
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except PermissionError:
            embed = self.loc_helper.create_error_embed(
                title_key="SET_WELCOME_FILE_PERMISSION_ERROR_TITLE",
                description_key="SET_WELCOME_FILE_PERMISSION_ERROR_DESC",
                user_id=ctx.author.id
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = self.loc_helper.create_error_embed(
                title_key="SET_WELCOME_UNEXPECTED_ERROR_TITLE",
                description_key="SET_WELCOME_UNEXPECTED_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(e)
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @set_welcome_message.error
    async def set_welcome_message_error(self, ctx: discord.ApplicationContext, error):
        """Handle command errors, especially permission errors."""
        if isinstance(error, commands.MissingPermissions):
            embed = self.loc_helper.create_error_embed(
                title_key="SET_WELCOME_PERMISSION_DENIED_TITLE",
                description_key="SET_WELCOME_PERMISSION_DENIED_DESC",
                user_id=ctx.author.id
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            embed = self.loc_helper.create_error_embed(
                title_key="SET_WELCOME_COMMAND_ERROR_TITLE",
                description_key="SET_WELCOME_COMMAND_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(error)
            )
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(SetWelcomeMessageCog(bot))