#!/usr/bin/env python

import logging
import sys
import importlib
import os
import time
import requests

import config

from telegram import Update
from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
        )

global config, modules
config = config
TOKEN = config.TOKEN
MODULE_DIR = "{0}/modules/".format(os.getcwd())

modules = {}
commands = []
ERapiurl = f"https://v6.exchangerate-api.com/v6/{config.er_api_key}/latest/USD"

root = logging.getLogger()
root.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

os.makedirs("chatlogs", exist_ok = True)


def getLFName(messagedata):
    strtime = time.strftime("%Y%m%d")
    filename = messagedata.title + "-" + strtime + ".log"
    return filename


def writechatLog(logmsg, file):
    fullpath = "chatlogs/" + file
    with open(fullpath, 'a') as logfile:
        logfile.write(logmsg + '\n')

module_files = [f[:-3] for f in os.listdir(MODULE_DIR) if f.endswith(".py") and f.startswith("module_")]

for module_name in module_files:
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(MODULE_DIR, f"{module_name}.py"))
    module = importlib.util.module_from_spec(spec)
    #importlib.import_module(module_name)
    spec.loader.create_module(module)
    spec.loader.exec_module(module)
    modules[module_name] = module


for module in modules:
    print(module)

def loadcommands(rehash=False):
    """Load commands from modules"""
    global application, modules, commands
    if rehash:
        handlers = application.handlers
        for handler in handlers[0]:
            if isinstance(handler, CommandHandler):
                if handler.callback.__name__[:-8] in commands:
                    logger.info("Unloading command: {}".format(handler.callback.__name__[:-8]))
                    application.remove_handler(handler)
                    commands.remove(handler.callback.__name__[:-8])
        for module_name, module in modules.items():
            logger.info("Reloading module: {}".format(module_name))
    #        importlib.reload(module)
        
        time.sleep(5)
        
        for m, env in modules.items():
            myglobals, mylocals, = env
            commands = [(c, ref) for c, ref in mylocals.items()
                        if c.endswith("_command")]
            print(commands)
            for (t, f) in commands:
                print(f)
                logger.info("Unloading command: {}".format(t[:-8]))
                application.remove_handler(CommandHandler(t[:-8], f))
    for module_name, module in modules.items():
        logger.info("Loading commands from: {}".format(module_name))
        for c in (dir(module)):
            if c.endswith("_command"):
                command = getattr(module, c)
                logger.info("Loading command: {}".format(c[:-8]))
                application.add_handler(CommandHandler(c[:-8], command))
                commands.append(c[:-8])

def loadmodules():
    """Attempt to load modules from MODULE_DIR"""
    global modules
    modules = {}
    for module in findmodules():
        env = {}
        logging.info("Loading module - {}".format(module))
        exec(open(os.path.join(MODULE_DIR, module)).read(), env, env)
        modules[module] = (env, env)


async def usd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert CAD to USD"""
    response = requests.get(ERapiurl)
    data = response.json()
    cad = data['conversion_rates']['CAD']
    message = (update.message.text).split()[-1]
    resp = f"{message}CAD is {(float(message) / cad):.2f}USD"
    await context.bot.send_message(update.message.chat_id, text=resp)


async def cad_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert USD to CAD"""
    response = requests.get(ERapiurl)
    data = response.json()
    cad = data['conversion_rates']['CAD']
    message = (update.message.text).split()[-1]
    resp = f"{message}USD is {(float(message) * cad):.2f}CAD"
    await context.bot.send_message(update.message.chat_id, text=resp)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued"""
    await update.effective_message.reply_html(
        f"Your chat ID is: <code>{update.effective_chat.id}</code>"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log an error and send telegram message to bot dev"""
    logger.error("Exception while handling an update:", exc_info=context.error)


async def rehash_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.username == "SL0RD":
        logger.info("Rehash command triggered")
        loadcommands(rehash=True)
        await context.bot.send_message(update.message.chat_id, text=f"Rehash successfull")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process channel messages"""
    ts = time.strftime("%H:%M:%S")
    message = "{0} <{1}> {2}".format(ts,
                                     update.effective_user.username,
                                     update.message.text)
    if update.message.chat.type == "group":
        filename = getLFName(update.message.chat)
        writechatLog(message, filename)

        print("{0} <{1}> {2}".format(ts,
                                     update.effective_user.username,
                                     update.message.text))


def main() -> None:
    """Start the bot."""
    global application
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cad", cad_command))
    application.add_handler(CommandHandler("usd", usd_command))
    application.add_handler(CommandHandler("rehash", rehash_command))

    loadcommands()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    

if __name__ == '__main__':
    main()
