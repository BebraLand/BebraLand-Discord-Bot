import json
from typing import Any

from config.config import config as bot_config

APPLICATION_ANSWER_MAX = 900
APPLICATION_QUESTION_MAX = 5
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


def load_application_form_config() -> dict[str, Any]:
    with open("config/applications.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    questions = []
    for raw_question in data.get("questions", [])[:APPLICATION_QUESTION_MAX]:
        question = dict(raw_question)
        question["question"] = str(question.get("question", "Question"))[:45]
        question["placeholder"] = str(question.get("placeholder", ""))[:100]
        question["type"] = question.get("type", "textarea")
        question["required"] = bool(question.get("required", True))
        question["min"] = max(0, int(question.get("min", 1)))
        question["max"] = min(
            APPLICATION_ANSWER_MAX, max(1, int(question.get("max", APPLICATION_ANSWER_MAX)))
        )
        if question["type"] == "text":
            question["max"] = min(question["max"], 100)
        questions.append(question)

    data["questions"] = questions
    data["formTitle"] = str(data.get("formTitle", "Application"))[:45]
    panel = data.get("panel", {})
    data["panel"] = {
        "title": str(panel.get("title", "Applications"))[:256],
        "description": str(panel.get("description", "Click Apply to submit an application."))[:3500],
        "buttonLabel": str(panel.get("buttonLabel", "Apply"))[:80],
    }
    return data
