#!/usr/bin/env python

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import logging
import sys
import os
import pickle
import time
import random

TOKEN = "CHANGEME"
MODULE_DIR = "{0}/modules/".format(os.getcwd())
dp = ""


def help(bot, update):
    bot.sendMessage(update.message.chat_id, text="IM BACK BITCHES, no commands yet.")


def main():
    global dp

    updater = Updater(token=TOKEN)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("help", help))

    updater.start_polling(timeout=5)

    while True:
        text = raw_input()

        if text == "stop":
            updater.stop()
            break


if __name__ == '__main__':
    main()
