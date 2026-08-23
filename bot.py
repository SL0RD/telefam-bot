#!/usr/bin/env python

import importlib.util
import logging
import os
import re
import sys
import time

from telegram import Update
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from settings import ADMIN_IDS, ADMIN_USERNAME, NOTIFY_CHAT_IDS, TOKEN

MODULE_DIR = os.path.join(os.getcwd(), "modules")
CHATLOG_DIR = os.environ.get("CHATLOG_DIR", "chatlogs")
GIT_SHA = os.environ.get("GIT_SHA", "")

modules = {}
commands = []
module_handlers = []
application = None

root = logging.getLogger()
root.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
root.addHandler(ch)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

os.makedirs(CHATLOG_DIR, exist_ok=True)


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name or "").strip()
    return cleaned if cleaned else "chat"


def get_log_filename(chat) -> str:
    title = sanitize_filename(chat.title or f"chat_{chat.id}")
    return f"{title}-{time.strftime('%Y%m%d')}.log"


def write_chat_log(logmsg: str, filename: str) -> None:
    with open(os.path.join(CHATLOG_DIR, filename), "a") as logfile:
        logfile.write(logmsg + "\n")


def render_message_content(message) -> str:
    """Return a human-readable representation of a message's content."""
    if message.text:
        content = message.text
    elif message.photo:
        content = "[photo]"
    elif message.video:
        content = "[video]"
    elif message.animation:
        content = "[gif]"
    elif message.sticker:
        content = f"[sticker: {message.sticker.emoji}]" if message.sticker.emoji else "[sticker]"
    elif message.audio:
        content = "[audio]"
    elif message.voice:
        content = "[voice]"
    elif message.video_note:
        content = "[video note]"
    elif message.document:
        fname = message.document.file_name
        content = f"[file: {fname}]" if fname else "[file]"
    else:
        content = "[message]"

    if message.caption:
        content += f" ({message.caption})"
    return content


def format_log_line(ts: str, user, content: str) -> str:
    if user is None:
        return f"{ts} <unknown> {content}"
    username = user.username or user.first_name or str(user.id)
    return f"{ts} <{username} ({user.id})> {content}"


def is_admin(user) -> bool:
    if not user:
        return False
    if ADMIN_IDS:
        return user.id in ADMIN_IDS
    return bool(user.username) and user.username == ADMIN_USERNAME


def update_notice_text(sha: str):
    """Human-readable deployment notice for a git SHA, or None if empty."""
    if not sha:
        return None
    return f"Updated to commit {sha[:7]} - back online."


async def send_update_notice(application: Application) -> None:
    """Announce a new deployment to configured chats before polling starts.

    Fires only for versioned builds (GIT_SHA set); silent otherwise.
    """
    text = update_notice_text(GIT_SHA)
    if not text or not NOTIFY_CHAT_IDS:
        return
    for chat_id in NOTIFY_CHAT_IDS:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.warning("Update notice to chat %s failed: %s", chat_id, e)


def load_modules() -> dict:
    """Load all module_*.py files from the modules directory.

    Returns the loaded modules keyed by name. If a module fails to load, its
    previous working version is kept when one exists. Never raises.
    """
    for name in list(sys.modules):
        if name.startswith("module_"):
            sys.modules.pop(name, None)

    try:
        filenames = sorted(os.listdir(MODULE_DIR))
    except OSError as e:
        logger.error("Cannot read modules directory: %s", e)
        return {}

    loaded = {}
    for filename in filenames:
        if not filename.endswith(".py") or not filename.startswith("module_"):
            continue

        module_name = filename[:-3]
        path = os.path.join(MODULE_DIR, filename)
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error("Failed to load module %s: %s", module_name, e, exc_info=True)
            sys.modules.pop(module_name, None)
            previous = modules.get(module_name)
            if previous is not None:
                logger.warning("Keeping previous version of module: %s", module_name)
                loaded[module_name] = previous
            continue
        loaded[module_name] = module
        logger.info("Loaded module: %s", module_name)

    return loaded


def unload_module_commands() -> None:
    """Remove handlers for dynamically loaded module commands."""
    global application, commands, module_handlers

    for handler in module_handlers:
        logger.info("Unloading command: %s", handler.callback.__name__[:-8])
        application.remove_handler(handler)

    module_handlers.clear()
    commands.clear()


def loadcommands(rehash: bool = False) -> None:
    """Register command handlers exported by modules."""
    global application, commands, module_handlers, modules

    if rehash:
        new_modules = load_modules()
        unload_module_commands()
        modules = new_modules

    for module_name, module in modules.items():
        logger.info("Loading commands from: %s", module_name)
        for name in dir(module):
            if not name.endswith("_command"):
                continue
            command = getattr(module, name)
            command_name = name[:-8]
            if command_name in commands or any(
                command_name in getattr(handler, "commands", ())
                for handler in application.handlers.get(0, ())
                if isinstance(handler, CommandHandler)
            ):
                logger.warning("Skipping duplicate command: %s", command_name)
                continue
            logger.info("Loading command: %s", command_name)
            handler = CommandHandler(command_name, command)
            application.add_handler(handler)
            module_handlers.append(handler)
            commands.append(command_name)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    builtin = ["start", "help"]
    lines = [f"/{cmd}" for cmd in sorted(set(builtin + commands))]
    if is_admin(update.effective_user):
        lines.append("/rehash")
    await update.message.reply_text("Available commands:\n" + "\n".join(lines))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(
        f"Your chat ID is: <code>{update.effective_chat.id}</code>"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


async def rehash_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user):
        return
    logger.info("Rehash command triggered")
    loadcommands(rehash=True)
    await context.bot.send_message(update.message.chat_id, text="Rehash successful")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    content = render_message_content(update.message)
    message = format_log_line(ts, update.effective_user, content)
    write_chat_log(message, get_log_filename(update.effective_chat))
    logger.debug(message)


async def log_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    member_update = update.chat_member
    if member_update.chat.type not in ("group", "supergroup"):
        return
    new_status = member_update.new_chat_member.status
    if new_status == "member":
        event = "joined the group"
    elif new_status in ("left", "kicked"):
        event = "left the group"
    else:
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    user = member_update.new_chat_member.user
    username = user.username or user.first_name or str(user.id)
    line = f"{ts} * {username} ({user.id}) {event}"
    write_chat_log(line, get_log_filename(member_update.chat))
    logger.debug(line)


def main() -> None:
    global application, modules

    modules = load_modules()

    application = Application.builder().token(TOKEN).post_init(send_update_notice).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rehash", rehash_command))

    loadcommands()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, echo))
    application.add_handler(ChatMemberHandler(log_member_update, ChatMemberHandler.CHAT_MEMBER))
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
