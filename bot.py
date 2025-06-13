#!/usr/bin/env python

import logging
import sys
import os
import time
import requests

import config
from decimal import Decimal
from telegram import Update
from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
        )

from forex_python.converter import CurrencyRates
from pyowm import OWM
# from pyowm.utils import config as owmconfig
# from pyowm.utils import timestamps

TOKEN = config.TOKEN
MODULE_DIR = "{0}/modules/".format(os.getcwd())

COUNTRY_CODES = ['CA','US']
STATE_CODES = ['AL','AK','AR','AZ','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IA','IN','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

owm = OWM(config.OWM)
mgr = owm.weather_manager()
reg = owm.city_id_registry()
#zip = mgr.weather_at_zip_code()
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

def writechatLog(logmsg, file):
    fullpath = "chatlogs/" + file
    with open(fullpath, 'a') as logfile:
        logfile.write(logmsg + '\n')


def getLFName(groupname):
    strtime = time.strftime("%Y%m%d")
    filename = groupname.title + "-" + strtime + ".log"
    return filename


def getLocation(location):
    location = " ".join(location.split()[1:])
    if len(location.split()[-1]) == 2:
        country = location.split()[-1].upper()
        location = " ".join(location.split()[:-1])
        print(country)
        print("Found country code")
        if len(location.split()[-1]) == 2:
            print ("Found state code")
            state = location.split()[-1]
            print(state)
            location = " ".join(location.split()[:-1])
            print(location)
            locations = reg.locations_for(location, country=country, state=state, matching='exact')
        else:
            print(location)
            locations = reg.locations_for(location, country=country, matching='exact')
    else:
        print("Error: no Country code found.")
        country = ""

    
    if locations:
        return locations[0]
    else:
        return "Error, location not found"


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


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current weather for given location."""
    message = update.message.text
    if len(message.split()) > 1:
        if message.split()[1].isdigit():
            zipcode = message.split()[1]
            weather = mgr.weather_at_zip_code(zipcode,'US').weather
            print(weather)
            temperature = weather.temperature('fahrenheit')
            wind = str(round(weather.wind(unit='miles_hour')['speed'],2)) + "mph"
            fltemp = str(temperature['feels_like']) + "\u00b0 F"
            rtemp = str(temperature['temp']) + "\u00b0 F"

            forcast = "It is currently {0} and feels like {1}\n"\
                      "The actual temperature is: {2} with a windspeed of {3}\n"\
                      "The sun will set at {4}".format(weather.detailed_status,fltemp, rtemp, wind, weather.sunset_time(timeformat='date'))
            await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
        else:
            location = getLocation(update.message.text)
            if location != "Error, location not found":
                print(location)
                weather = mgr.weather_at_coords(lat=location.lat, lon=location.lon).weather
                if location.country == "US":
                    temperature = weather.temperature('fahrenheit')
                    wind = str(round(weather.wind(unit='miles_hour')['speed'],2)) + "mph"
                    fltemp = str(temperature['feels_like']) + "\u00b0 F"
                    rtemp = str(temperature['temp']) + "\u00b0 F"
                else:
                    temperature = weather.temperature('celsius')
                    wind = str(round((weather.wind()['speed'] * 3.6),2)) + "kph"
                    fltemp = str(temperature['feels_like']) + "\u00b0 C"
                    rtemp = str(temperature['temp']) + "\u00b0 C"
                forcast = "It is currently {0} and feels like {1}\n"\
                      "The actual temperature is: {2} with a windspeed of {3}\n"\
                      "The sun will set at {4}".format(weather.detailed_status,fltemp, rtemp, wind, weather.sunset_time(timeformat='date'))
                await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
            else:
                await context.bot.send_message(update.message.chat_id, text=f"Error finding location")
    else:
        await context.bot.send_message(update.message.chat_id, text=f"Please include a location with your command")


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
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cad", cad_command))
    application.add_handler(CommandHandler("usd", usd_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
