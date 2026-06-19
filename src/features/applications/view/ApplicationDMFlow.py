import asyncio
import time
from typing import Any

import discord

from config.config import config as bot_config
from src.features.applications.service import submit_application_answers
from src.utils.embeds import build_embeds_from_message_data
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

DEFAULT_TIMEOUT_MINUTES = 180
_ACTIVE_SESSIONS: dict[tuple[int, int], int] = {}


class ApplicationCancelled(Exception):
    pass


class ApplicationTimedOut(Exception):
    pass


def get_active_application_dm_channel(user_id: int, guild_id: int) -> int | None:
    return _ACTIVE_SESSIONS.get((user_id, guild_id))


def _set_active_application_session(
    user_id: int, guild_id: int, channel_id: int
) -> None:
    _ACTIVE_SESSIONS[(user_id, guild_id)] = channel_id


def _clear_active_application_session(user_id: int, guild_id: int) -> None:
    _ACTIVE_SESSIONS.pop((user_id, guild_id), None)


def _get_timeout_seconds(form_config: dict[str, Any]) -> int:
    timeout_minutes = form_config.get(
        "timeoutMinutes", form_config.get("timeout_minutes", DEFAULT_TIMEOUT_MINUTES)
    )
    try:
        return max(5, int(timeout_minutes) * 60)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_MINUTES * 60


def _disable_view(view: discord.ui.View) -> None:
    for child in view.children:
        child.disabled = True


def _build_dm_jump_view(channel_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label="Jump to application",
            style=discord.ButtonStyle.link,
            url=f"https://discord.com/channels/@me/{channel_id}",
        )
    )
    return view


def build_application_started_response(
    channel_id: int,
) -> tuple[discord.Embed, discord.ui.View]:
    embed = discord.Embed(
        title="Application started",
        description="Application has been started in your direct messages!",
        color=bot_config.embeds.success_color,
    )
    return embed, _build_dm_jump_view(channel_id)


def _question_replacements(
    form_config: dict[str, Any], question: dict[str, Any], index: int, total: int
) -> dict[str, str]:
    return {
        "{form_title}": form_config.get("formTitle", "Application"),
        "{index}": str(index),
        "{total}": str(total),
        "{question}": question.get("question", "Question"),
        "{placeholder}": question.get("placeholder", ""),
    }


def _build_default_question_embed(
    form_config: dict[str, Any],
    question: dict[str, Any],
    index: int,
    total: int,
    prompt: str,
) -> discord.Embed:
    description = f"**{index}/{total}. {question.get('question', 'Question')}**"
    placeholder = question.get("placeholder")
    if placeholder:
        description += f"\n\n{placeholder}"
    description += f"\n\n{prompt}"

    embed = discord.Embed(
        title=form_config.get("formTitle", "Application"),
        description=description,
        color=bot_config.embeds.info_color,
    )
    return embed


def _build_question_embeds(
    form_config: dict[str, Any],
    question: dict[str, Any],
    index: int,
    total: int,
    prompt: str,
) -> list[discord.Embed]:
    replacements = _question_replacements(form_config, question, index, total)
    embeds = build_embeds_from_message_data(
        question,
        replacements=replacements,
        default_color=None,
    )
    if embeds:
        return embeds

    return [_build_default_question_embed(form_config, question, index, total, prompt)]


def _build_intro_embed(form_config: dict[str, Any]) -> discord.Embed:
    timeout_minutes = _get_timeout_seconds(form_config) // 60
    embed = discord.Embed(
        title=form_config.get("formTitle", "Application"),
        description=(
            "Are you sure you want to apply?\n\n"
            "Once you start the application I will send you a series of questions. "
            f"You will have {timeout_minutes} minutes to complete the application. "
            "If you do not complete it in time, you will have to restart. "
            "You can cancel the application at any time."
        ),
        color=bot_config.embeds.info_color,
    )
    return embed


def _build_started_embed() -> discord.Embed:
    return discord.Embed(
        title="Application Started",
        description=(
            "Please answer the questions below, either by clicking the dropdown menus "
            "or sending a message to the bot."
        ),
        color=bot_config.embeds.success_color,
    )


def _build_cancelled_embed() -> discord.Embed:
    return discord.Embed(
        title="Application cancelled",
        description="Your application was cancelled. You can start again from the server panel.",
        color=bot_config.embeds.failed_color,
    )


def _build_timeout_embed() -> discord.Embed:
    return discord.Embed(
        title="Application timed out",
        description="Your application expired before it was completed. You can start again from the server panel.",
        color=bot_config.embeds.failed_color,
    )


class ApplicationStartView(discord.ui.View):
    def __init__(
        self,
        bot: discord.Bot,
        guild: discord.Guild,
        user: discord.abc.User,
        form_config: dict[str, Any],
        dm_channel: discord.DMChannel,
    ):
        super().__init__(timeout=_get_timeout_seconds(form_config))
        self.bot = bot
        self.guild = guild
        self.user = user
        self.form_config = form_config
        self.dm_channel = dm_channel
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def on_timeout(self) -> None:
        _clear_active_application_session(self.user.id, self.guild.id)
        if self.message:
            _disable_view(self)
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Start application", style=discord.ButtonStyle.success)
    async def start_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ) -> None:
        await interaction.response.edit_message(embed=_build_started_embed(), view=None)
        self.stop()

        session = ApplicationSession(
            bot=self.bot,
            guild=self.guild,
            user=self.user,
            form_config=self.form_config,
            dm_channel=self.dm_channel,
        )
        await session.run()

    @discord.ui.button(label="Cancel application", style=discord.ButtonStyle.danger)
    async def cancel_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ) -> None:
        _clear_active_application_session(self.user.id, self.guild.id)
        await interaction.response.edit_message(
            embed=_build_cancelled_embed(), view=None
        )
        self.stop()


class ApplicationQuestionView(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        timeout: float,
        allow_skip: bool = False,
        link_label: str | None = None,
        link_url: str | None = None,
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.answer: str | None = None
        self.cancelled = False
        self.skipped = False

        if link_label and link_url:
            self.add_item(
                discord.ui.Button(
                    label=link_label[:80],
                    style=discord.ButtonStyle.link,
                    url=link_url,
                    row=4,
                )
            )

        if allow_skip:
            skip_button = discord.ui.Button(
                label="Skip",
                style=discord.ButtonStyle.secondary,
                row=4,
            )
            skip_button.callback = self.skip_callback
            self.add_item(skip_button)

        cancel_button = discord.ui.Button(
            label="Cancel application",
            style=discord.ButtonStyle.danger,
            row=4,
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def skip_callback(self, interaction: discord.Interaction) -> None:
        self.skipped = True
        await interaction.response.defer()
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        self.cancelled = True
        await interaction.response.defer()
        self.stop()


class ApplicationChoiceSelect(discord.ui.Select):
    def __init__(self, question: dict[str, Any]):
        options = []
        for option in question.get("options", [])[:25]:
            kwargs = {
                "label": option["label"],
                "value": option["value"],
            }
            if option.get("description"):
                kwargs["description"] = option["description"]
            if option.get("emoji"):
                kwargs["emoji"] = option["emoji"]
            options.append(discord.SelectOption(**kwargs))

        min_values = 1
        max_values = min(
            len(options),
            max(
                min_values,
                int(question.get("max_values", question.get("maxValues", 1))),
            ),
        )
        super().__init__(
            placeholder=question.get("placeholder", "Select an option")[:150],
            min_values=min_values,
            max_values=max_values,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        value_to_label = {
            option.get("value"): option.get("label")
            for option in self.view.question.get("options", [])
        }
        self.view.answer = ", ".join(
            value_to_label.get(value, value) for value in self.values
        )
        await interaction.response.defer()
        self.view.stop()


class ApplicationChoiceView(ApplicationQuestionView):
    def __init__(
        self,
        user_id: int,
        question: dict[str, Any],
        timeout: float,
        use_buttons: bool = False,
    ):
        super().__init__(
            user_id=user_id,
            timeout=timeout,
            allow_skip=not question.get("required", True),
            link_label=question.get("buttonLabel"),
            link_url=question.get("buttonLink"),
        )
        self.question = question

        if use_buttons:
            for index, option in enumerate(question.get("options", [])[:20]):
                button = discord.ui.Button(
                    label=option["label"][:80],
                    style=discord.ButtonStyle.primary,
                    row=index // 5,
                )
                button.callback = self._build_button_callback(option["label"])
                self.add_item(button)
        else:
            self.add_item(ApplicationChoiceSelect(question))

    def _build_button_callback(self, answer: str):
        async def callback(interaction: discord.Interaction) -> None:
            self.answer = answer
            await interaction.response.defer()
            self.stop()

        return callback


class ApplicationSession:
    def __init__(
        self,
        bot: discord.Bot,
        guild: discord.Guild,
        user: discord.abc.User,
        form_config: dict[str, Any],
        dm_channel: discord.DMChannel,
    ):
        self.bot = bot
        self.guild = guild
        self.user = user
        self.form_config = form_config
        self.dm_channel = dm_channel
        self.deadline = time.monotonic() + _get_timeout_seconds(form_config)

    def remaining_timeout(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ApplicationTimedOut
        return remaining

    async def run(self) -> None:
        try:
            answers = []
            questions = self.form_config.get("questions", [])
            for index, question in enumerate(questions, start=1):
                answer = await self.ask_question(question, index, len(questions))
                answers.append(
                    {
                        "question": question.get("question", f"Question {index}"),
                        "value": answer,
                    }
                )

            result = await submit_application_answers(
                self.guild, self.user, answers, self.bot
            )
            await self.dm_channel.send(embed=result.embed)
        except ApplicationCancelled:
            await self.dm_channel.send(embed=_build_cancelled_embed())
        except ApplicationTimedOut:
            await self.dm_channel.send(embed=_build_timeout_embed())
        finally:
            _clear_active_application_session(self.user.id, self.guild.id)

    async def ask_question(
        self, question: dict[str, Any], index: int, total: int
    ) -> str:
        question_type = str(question.get("type", "textarea")).lower()
        if question_type in {"select", "dropdown", "choice"} and question.get(
            "options"
        ):
            return await self.ask_choice_question(
                question, index, total, use_buttons=False
            )
        if question_type in {"button", "buttons"} and question.get("options"):
            return await self.ask_choice_question(
                question, index, total, use_buttons=True
            )
        return await self.ask_text_question(question, index, total)

    async def ask_choice_question(
        self,
        question: dict[str, Any],
        index: int,
        total: int,
        use_buttons: bool,
    ) -> str:
        prompt = (
            "To answer this question, please click one of the buttons below."
            if use_buttons
            else "To answer this question, please select an option from the dropdown below."
        )
        embeds = _build_question_embeds(
            self.form_config, question, index, total, prompt
        )
        view = ApplicationChoiceView(
            self.user.id, question, self.remaining_timeout(), use_buttons=use_buttons
        )
        message = await self.dm_channel.send(embeds=embeds, view=view)
        timed_out = await view.wait()
        _disable_view(view)
        try:
            await message.edit(view=view)
        except discord.HTTPException:
            pass

        if timed_out:
            raise ApplicationTimedOut
        if view.cancelled:
            raise ApplicationCancelled
        if view.skipped:
            return "Skipped"
        if view.answer is None:
            raise ApplicationTimedOut
        return view.answer[:1900]

    async def ask_text_question(
        self, question: dict[str, Any], index: int, total: int
    ) -> str:
        while True:
            prompt = "To answer this question, please send a message to the bot."
            if not question.get("required", True):
                prompt += " Type `skip` to skip this question."

            embeds = _build_question_embeds(
                self.form_config, question, index, total, prompt
            )
            view = ApplicationQuestionView(
                self.user.id,
                self.remaining_timeout(),
                allow_skip=not question.get("required", True),
                link_label=question.get("buttonLabel"),
                link_url=question.get("buttonLink"),
            )
            prompt_message = await self.dm_channel.send(embeds=embeds, view=view)

            answer = await self.wait_for_text_answer(view)
            _disable_view(view)
            try:
                await prompt_message.edit(view=view)
            except discord.HTTPException:
                pass

            normalized = answer.strip()
            lowered = normalized.lower()
            if lowered in {"cancel", "stop"}:
                raise ApplicationCancelled
            if lowered == "skip" and not question.get("required", True):
                return "Skipped"

            error = self.validate_text_answer(normalized, question)
            if error:
                await self.dm_channel.send(error)
                continue

            return normalized[: question.get("max", 1900)]

    async def wait_for_text_answer(self, view: ApplicationQuestionView) -> str:
        def check(message: discord.Message) -> bool:
            return (
                message.author.id == self.user.id
                and message.channel.id == self.dm_channel.id
                and not message.author.bot
            )

        message_task = asyncio.create_task(
            self.bot.wait_for("message", check=check, timeout=self.remaining_timeout())
        )
        view_task = asyncio.create_task(view.wait())
        done, pending = await asyncio.wait(
            {message_task, view_task},
            timeout=self.remaining_timeout(),
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        if not done:
            raise ApplicationTimedOut
        if view_task in done:
            if view.cancelled:
                raise ApplicationCancelled
            if view.skipped:
                return "skip"
            raise ApplicationTimedOut

        try:
            message = message_task.result()
        except asyncio.TimeoutError as error:
            raise ApplicationTimedOut from error
        return message.content

    @staticmethod
    def validate_text_answer(answer: str, question: dict[str, Any]) -> str:
        if not answer and question.get("required", True):
            return "Answer is required. Please send a response."

        min_length = int(question.get("min", 1))
        max_length = int(question.get("max", 1900))
        if answer and len(answer) < min_length:
            return f"Answer is too short. Please use at least {min_length} characters."
        if len(answer) > max_length:
            return f"Answer is too long. Please use {max_length} characters or fewer."
        return ""


async def start_application_dm_flow(
    interaction: discord.Interaction, form_config: dict[str, Any]
) -> discord.DMChannel:
    dm_channel = await interaction.user.create_dm()
    view = ApplicationStartView(
        interaction.client,
        interaction.guild,
        interaction.user,
        form_config,
        dm_channel,
    )
    message = await dm_channel.send(embed=_build_intro_embed(form_config), view=view)
    view.message = message
    _set_active_application_session(
        interaction.user.id, interaction.guild.id, dm_channel.id
    )
    logger.info(
        f"Started application DM flow for user {interaction.user.id} in guild {interaction.guild.id}"
    )
    return dm_channel
