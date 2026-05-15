import discord

from src.utils.embeds import build_embeds_from_message_data


def test_build_embeds_from_message_data_uses_embeds_list_and_placeholders():
    message = {
        "embeds": [
            {"description": "Hello {name}", "color": "#112233"},
            "skip me",
            {"title": "Second"},
        ]
    }

    embeds = build_embeds_from_message_data(
        message,
        replacements={"{name}": "Ada"},
        default_color=None,
    )

    assert len(embeds) == 2
    assert embeds[0].description == "Hello Ada"
    assert embeds[0].color == discord.Color(0x112233)
    assert embeds[1].title == "Second"


def test_build_embeds_from_message_data_uses_single_embed_key():
    embeds = build_embeds_from_message_data(
        {"embed": {"title": "{title}"}},
        replacements={"{title}": "Rules"},
        default_color=None,
    )

    assert len(embeds) == 1
    assert embeds[0].title == "Rules"


def test_build_embeds_from_message_data_uses_direct_embed_data():
    embeds = build_embeds_from_message_data(
        {"description": "Direct embed"},
        default_color=None,
    )

    assert len(embeds) == 1
    assert embeds[0].description == "Direct embed"


def test_build_embeds_from_message_data_uses_fallback_when_no_embed_data():
    embeds = build_embeds_from_message_data(
        {"embeds": ["skip me"]},
        default_color=None,
        fallback={"title": "Fallback"},
    )

    assert len(embeds) == 1
    assert embeds[0].title == "Fallback"


def test_build_embeds_from_message_data_ignores_non_embed_dict_without_fallback():
    embeds = build_embeds_from_message_data(
        {"question": "What is your name?", "type": "text"},
        default_color=None,
    )

    assert embeds == []
