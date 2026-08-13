#!/usr/bin/env python

import importlib.util
import logging
import os
import re
import sys
import time

import config
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = config.TOKEN
MODULE_DIR = os.path.join(os.getcwd(), "modules")
ADMIN_IDS = set(getattr(config, "ADMIN_IDS", []))
ADMIN_USERNAME = getattr(config, "ADMIN_USERNAME", "SL0RD")
ER_API_URL = f"https://v6.exchangerate-api.com/v6/{config.er_api_key}/latest/USD"

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

os.makedirs("chatlogs", exist_ok=True)


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name or "").strip()
    return cleaned if cleaned else "chat"


def get_log_filename(chat) -> str:
    title = sanitize_filename(chat.title or f"chat_{chat.id}")
    return f"{title}-{time.strftime('%Y%m%d')}.log"


def write_chat_log(logmsg: str, filename: str) -> None:
    with open(os.path.join("chatlogs", filename), "a") as logfile:
        logfile.write(logmsg + "\n")


def is_admin(user) -> bool:
    if not user:
        return False
    if ADMIN_IDS:
        return user.id in ADMIN_IDS
    return bool(user.username) and user.username == ADMIN_USERNAME


def load_modules() -> None:
    """Load all module_*.py files from the modules directory."""
    global modules
    modules = {}

    for filename in sorted(os.listdir(MODULE_DIR)):
        if not filename.endswith(".py") or not filename.startswith("module_"):
            continue

        module_name = filename[:-3]
        path = os.path.join(MODULE_DIR, filename)
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[module_name] = module
        logger.info("Loaded module: %s", module_name)


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
    global application, commands, module_handlers

    if rehash:
        unload_module_commands()
        load_modules()

    for module_name, module in modules.items():
        logger.info("Loading commands from: %s", module_name)
        for name in dir(module):
            if not name.endswith("_command"):
                continue
            command = getattr(module, name)
            command_name = name[:-8]
            if command_name in commands or any(
                command_name in getattr(handler, "commands", ())
                for handler in application.handlers[0]
                if isinstance(handler, CommandHandler)
            ):
                logger.warning("Skipping duplicate command: %s", command_name)
                continue
            logger.info("Loading command: %s", command_name)
            handler = CommandHandler(command_name, command)
            application.add_handler(handler)
            module_handlers.append(handler)
            commands.append(command_name)


def parse_command_amount(text: str):
    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None


def get_cad_rate():
    try:
        response = requests.get(ER_API_URL, timeout=10)
        response.raise_for_status()
        return response.json()["conversion_rates"]["CAD"]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.error("Failed to fetch exchange rate: %s", e)
        return None


async def usd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = parse_command_amount(update.message.text)
    if amount is None:
        await update.message.reply_text("Please provide a valid amount, e.g. /usd 100")
        return
    cad = get_cad_rate()
    if cad is None:
        await update.message.reply_text("Could not fetch exchange rates. Please try again later.")
        return
    resp = f"{amount}CAD is {(amount / cad):.2f}USD"
    await context.bot.send_message(update.message.chat_id, text=resp)


async def cad_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = parse_command_amount(update.message.text)
    if amount is None:
        await update.message.reply_text("Please provide a valid amount, e.g. /cad 100")
        return
    cad = get_cad_rate()
    if cad is None:
        await update.message.reply_text("Could not fetch exchange rates. Please try again later.")
        return
    resp = f"{amount}USD is {(amount * cad):.2f}CAD"
    await context.bot.send_message(update.message.chat_id, text=resp)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    builtin = ["start", "cad", "usd", "help"]
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
    if update.message.chat.type != "group":
        return
    ts = time.strftime("%H:%M:%S")
    user = update.effective_user
    username = user.username or user.first_name or str(user.id)
    message = f"{ts} <{username}> {update.message.text}"
    write_chat_log(message, get_log_filename(update.message.chat))
    logger.debug(message)


def main() -> None:
    global application

    load_modules()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cad", cad_command))
    application.add_handler(CommandHandler("usd", usd_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rehash", rehash_command))

    loadcommands()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
