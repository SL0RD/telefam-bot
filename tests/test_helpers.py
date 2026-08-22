"""Tests for bot.py helper functions."""

import time
from types import SimpleNamespace

import bot


class TestSanitizeFilename:
    def test_keeps_word_characters(self):
        assert bot.sanitize_filename("Family Chat") == "Family Chat"

    def test_strips_special_characters(self):
        assert bot.sanitize_filename("bad/name:with*chars?") == "badnamewithchars"

    def test_empty_becomes_chat(self):
        assert bot.sanitize_filename("") == "chat"
        assert bot.sanitize_filename(None) == "chat"


class TestGetLogFilename:
    def test_uses_title_and_date(self):
        chat = SimpleNamespace(title="Fam", id=123)
        expected = f"Fam-{time.strftime('%Y%m%d')}.log"
        assert bot.get_log_filename(chat) == expected

    def test_falls_back_to_chat_id(self):
        chat = SimpleNamespace(title=None, id=555)
        filename = bot.get_log_filename(chat)
        assert filename.startswith("chat_555-")


class TestFormatLogLine:
    def test_none_user(self):
        line = bot.format_log_line("2026-01-01 00:00:00", None, "hello")
        assert line == "2026-01-01 00:00:00 <unknown> hello"

    def test_prefers_username(self):
        user = SimpleNamespace(id=7, username="sid", first_name="Sidney")
        line = bot.format_log_line("ts", user, "hi")
        assert line == "ts <sid (7)> hi"

    def test_falls_back_to_first_name_then_id(self):
        named = SimpleNamespace(id=7, username=None, first_name="Sidney")
        anonymous = SimpleNamespace(id=9, username=None, first_name=None)
        assert bot.format_log_line("ts", named, "x") == "ts <Sidney (7)> x"
        assert bot.format_log_line("ts", anonymous, "x") == "ts <9 (9)> x"


MEDIA_ATTRS = (
    "text", "photo", "video", "animation", "sticker",
    "audio", "voice", "video_note", "document",
)


def _message(**kwargs):
    defaults = {attr: None for attr in MEDIA_ATTRS}
    defaults["caption"] = None
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestRenderMessageContent:
    def test_text(self):
        msg = _message(text="hello", photo=None)
        assert bot.render_message_content(msg) == "hello"

    def test_media_placeholders(self):
        cases = [
            ({"photo": object()}, "[photo]"),
            ({"video": object()}, "[video]"),
            ({"animation": object()}, "[gif]"),
            ({"sticker": SimpleNamespace(emoji="🔥")}, "[sticker: 🔥]"),
            ({"audio": object()}, "[audio]"),
            ({"voice": object()}, "[voice]"),
        ]
        for overrides, expected in cases:
            kwargs = {k: None for k in
                      ("photo", "video", "animation", "sticker", "audio",
                       "voice", "video_note", "document")}
            kwargs["text"] = None
            kwargs.update(overrides)
            assert bot.render_message_content(_message(**kwargs)) == expected

    def test_fallback_for_unknown_content(self):
        msg = _message(text=None)
        assert bot.render_message_content(msg) == "[message]"

    def test_document_with_name(self):
        doc = SimpleNamespace(file_name="notes.txt")
        msg = _message(text=None, document=doc)
        assert bot.render_message_content(msg) == "[file: notes.txt]"

    def test_caption_appended(self):
        msg = _message(text="look", photo=object(), caption="my pic")
        assert bot.render_message_content(msg) == "look (my pic)"


class TestIsAdmin:
    def test_numeric_ids_take_precedence(self, monkeypatch):
        monkeypatch.setattr(bot, "ADMIN_IDS", {42})
        monkeypatch.setattr(bot, "ADMIN_USERNAME", "someone-else")
        admin = SimpleNamespace(id=42, username="not-admin")
        assert bot.is_admin(admin)

    def test_non_admin_rejected_when_ids_set(self, monkeypatch):
        monkeypatch.setattr(bot, "ADMIN_IDS", {42})
        outsider = SimpleNamespace(id=1, username="SL0RD")
        assert not bot.is_admin(outsider)

    def test_username_fallback_without_ids(self, monkeypatch):
        monkeypatch.setattr(bot, "ADMIN_IDS", set())
        monkeypatch.setattr(bot, "ADMIN_USERNAME", "SL0RD")
        assert bot.is_admin(SimpleNamespace(id=1, username="SL0RD"))
        assert not bot.is_admin(SimpleNamespace(id=1, username="random"))

    def test_no_user(self):
        assert not bot.is_admin(None)
