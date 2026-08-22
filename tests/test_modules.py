"""Tests for module loading and command registration."""

import asyncio
import os
import types

import pytest
from telegram.ext import Application, CommandHandler

import bot


@pytest.fixture
def app():
    application = Application.builder().token("123456:TEST-TOKEN").build()
    bot.application = application
    yield application
    bot.application = None
    bot.modules = {}
    bot.commands.clear()
    bot.module_handlers.clear()


def make_module(name, commands):
    module = types.ModuleType(name)
    for command_name in commands:
        async def callback(update, context):
            pass

        callback.__name__ = f"{command_name}_command"
        setattr(module, f"{command_name}_command", callback)
    return module


class TestLoadModules:
    def test_loads_only_module_files(self, tmp_path, monkeypatch):
        (tmp_path / "module_good.py").write_text(
            "async def ping_command(update, context):\n    pass\n"
        )
        (tmp_path / "not_a_module.py").write_text("raise RuntimeError('should not load')\n")
        monkeypatch.setattr(bot, "MODULE_DIR", str(tmp_path))

        loaded = bot.load_modules()

        assert set(loaded) == {"module_good"}
        assert callable(loaded["module_good"].ping_command)

    def test_broken_module_isolated_and_previous_kept(self, tmp_path, monkeypatch):
        previous = make_module("module_broken", ["old"])
        monkeypatch.setattr(bot, "MODULE_DIR", str(tmp_path))
        monkeypatch.setattr(bot, "modules", {"module_broken": previous})

        (tmp_path / "module_good.py").write_text("VALUE = 1\n")
        (tmp_path / "module_broken.py").write_text("raise ImportError('boom')\n")

        loaded = bot.load_modules()

        assert loaded["module_good"].VALUE == 1  # healthy module loads fine
        assert loaded["module_broken"] is previous  # previous version retained

    def test_missing_directory_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bot, "MODULE_DIR", str(tmp_path / "nope"))
        assert bot.load_modules() == {}

    def test_reimport_gets_fresh_code(self, tmp_path, monkeypatch):
        module_file = tmp_path / "module_evolve.py"
        monkeypatch.setattr(bot, "MODULE_DIR", str(tmp_path))

        module_file.write_text("VALUE = 1\n")
        # Bytecode cache validates on mtime; give each version a distinct one.
        os.utime(module_file, (1000000, 1000000))
        first = bot.load_modules()["module_evolve"]

        module_file.write_text("VALUE = 2\n")
        os.utime(module_file, (2000000, 2000000))
        second = bot.load_modules()["module_evolve"]

        assert first.VALUE == 1
        assert second.VALUE == 2
        assert first is not second


class TestCommandRegistration:
    def test_registers_module_commands(self, app):
        bot.modules = {"module_alpha": make_module("module_alpha", ["ping", "pong"])}

        bot.loadcommands()

        registered = {
            h.callback.__name__[:-8]
            for group in app.handlers.values()
            for h in group
            if isinstance(h, CommandHandler)
        }
        assert {"ping", "pong"} <= registered
        assert set(bot.commands) >= {"ping", "pong"}

    def test_duplicate_commands_skipped(self, app):
        bot.modules = {
            "module_one": make_module("module_one", ["dup"]),
            "module_two": make_module("module_two", ["dup"]),
        }

        bot.loadcommands()

        dup_handlers = [
            h for group in app.handlers.values()
            for h in group if isinstance(h, CommandHandler) and "dup" in h.commands
        ]
        assert len(dup_handlers) == 1
        assert bot.commands.count("dup") == 1

    def test_unload_removes_handlers(self, app):
        bot.modules = {"module_alpha": make_module("module_alpha", ["ping"])}
        bot.loadcommands()
        before = sum(len(g) for g in app.handlers.values())

        bot.unload_module_commands()
        after = sum(len(g) for g in app.handlers.values())

        assert after == before - 1
        assert "ping" not in bot.commands


class TestHelpCommand:
    def test_lists_builtin_and_dynamic_commands(self):
        sent = []

        class FakeMessage:
            async def reply_text(self, text):
                sent.append(text)

        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=1, username="someone"),
            message=FakeMessage(),
        )
        original_commands = list(bot.commands)
        try:
            bot.commands[:] = ["weather", "cad"]
            asyncio.run(bot.help_command(update, None))
        finally:
            bot.commands[:] = original_commands

        text = sent[0]
        for cmd in ("start", "help", "cad", "weather"):
            assert f"/{cmd}" in text

    def test_rehash_shown_to_admins_only(self, monkeypatch):
        sent = []

        class FakeMessage:
            async def reply_text(self, text):
                sent.append(text)

        def make_update(user_id, username):
            return types.SimpleNamespace(
                effective_user=types.SimpleNamespace(id=user_id, username=username),
                message=FakeMessage(),
            )

        monkeypatch.setattr(bot, "ADMIN_IDS", {42})
        asyncio.run(bot.help_command(make_update(42, "other"), None))
        assert "/rehash" in sent[-1]
        asyncio.run(bot.help_command(make_update(1, "random"), None))
        assert "/rehash" not in sent[-1]

        monkeypatch.setattr(bot, "ADMIN_IDS", set())
        monkeypatch.setattr(bot, "ADMIN_USERNAME", "fallback-admin")
        asyncio.run(bot.help_command(make_update(1, "fallback-admin"), None))
        assert "/rehash" in sent[-1]


class TestRehashCommand:
    def test_non_admin_ignored(self, monkeypatch):
        called = []
        monkeypatch.setattr(bot, "ADMIN_IDS", {42})

        def fake_loadcommands(rehash=False):
            called.append(rehash)

        monkeypatch.setattr(bot, "loadcommands", fake_loadcommands)

        class FakeBot:
            async def send_message(self, chat_id, text):
                pass

        update = types.SimpleNamespace(effective_user=types.SimpleNamespace(id=1, username="x"))
        context = types.SimpleNamespace(bot=FakeBot())

        asyncio.run(bot.rehash_command(update, context))
        assert called == []
