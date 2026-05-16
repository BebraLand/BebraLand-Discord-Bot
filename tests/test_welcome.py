from types import SimpleNamespace

from src.utils.welcome import create_welcome_embeds


def _avatar(url):
    return SimpleNamespace(url=url)


def test_create_welcome_embeds_uses_welcome_json():
    member = SimpleNamespace(
        display_name="Aurum",
        mention="<@123>",
        avatar=_avatar("https://example.com/member.png"),
        default_avatar=_avatar("https://example.com/default-member.png"),
        guild=SimpleNamespace(name="BebraLand", member_count=42),
    )
    bot = SimpleNamespace(
        user=SimpleNamespace(
            avatar=_avatar("https://example.com/bot.png"),
            default_avatar=_avatar("https://example.com/default-bot.png"),
        )
    )

    embeds, error_message, error_path = create_welcome_embeds(member, bot)

    assert error_message is None
    assert error_path is None
    assert len(embeds) == 2
    assert embeds[1].title == "Welcome to BebraLand, Aurum!"
    assert embeds[1].thumbnail.url == "https://example.com/member.png"
