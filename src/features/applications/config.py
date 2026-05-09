import json
from typing import Any

from config.config import config as bot_config

APPLICATION_ANSWER_MAX = 1900
APPLICATION_QUESTION_MAX = 25
REASON_MAX = 900


def _get_config_value(path: list[str], default: Any = None) -> Any:
    value = bot_config
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def get_application_module_config() -> dict[str, Any]:
    return _get_config_value(["modules", "applications"], {}) or {}


def get_application_config_value(key: str, default: Any = None) -> Any:
    return get_application_module_config().get(key, default)


def _normalize_question_options(raw_options: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_options, list):
        return []

    options = []
    for index, raw_option in enumerate(raw_options[:25], start=1):
        if isinstance(raw_option, str):
            label = raw_option
            option = {"label": label, "value": label}
        elif isinstance(raw_option, dict):
            label = str(raw_option.get("label", raw_option.get("value", f"Option {index}")))
            option = {
                "label": label,
                "value": str(raw_option.get("value", label)),
                "description": raw_option.get("description"),
                "emoji": raw_option.get("emoji"),
            }
        else:
            continue

        option["label"] = option["label"][:100]
        option["value"] = option["value"][:100]
        if option.get("description") is not None:
            option["description"] = str(option["description"])[:100]
        options.append(option)

    return options


def load_application_form_config() -> dict[str, Any]:
    with open("config/applications.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    questions = []
    for raw_question in data.get("questions", [])[:APPLICATION_QUESTION_MAX]:
        question = dict(raw_question)
        question["question"] = str(question.get("question", "Question"))[:256]
        question["placeholder"] = str(question.get("placeholder", ""))[:1000]
        question["type"] = question.get("type", "textarea")
        question["required"] = bool(question.get("required", True))
        question["min"] = max(0, int(question.get("min", 1)))
        question["max"] = min(
            APPLICATION_ANSWER_MAX, max(1, int(question.get("max", APPLICATION_ANSWER_MAX)))
        )
        if question["type"] == "text":
            question["max"] = min(question["max"], 100)
        question["options"] = _normalize_question_options(question.get("options"))
        questions.append(question)

    data["questions"] = questions
    data["formTitle"] = str(data.get("formTitle", "Application"))[:256]
    panel = data.get("panel", {})
    if not isinstance(panel, dict):
        panel = {}

    embeds = data.get("embeds", panel.get("embeds", []))
    if not isinstance(embeds, list):
        embeds = []

    button_link = data.get("buttonLink", panel.get("buttonLink"))
    has_link_button = bool(button_link)

    data["panel"] = {
        "title": str(panel.get("title", "Applications"))[:256],
        "description": str(panel.get("description", "Click Apply to submit an application."))[:3500],
        "buttonLabel": str(
            data.get("applyButtonLabel", panel.get("applyButtonLabel", "Apply"))
            if has_link_button
            else data.get("buttonLabel", panel.get("buttonLabel", "Apply"))
        )[:80],
        "linkButtonLabel": str(data.get("buttonLabel", panel.get("buttonLabel", "Open")))[:80],
        "buttonLink": str(button_link) if button_link else "",
        "embeds": [embed for embed in embeds[:10] if isinstance(embed, dict)],
    }
    return data
