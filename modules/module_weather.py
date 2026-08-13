import asyncio
import time

from telegram import Update
from telegram.ext import ContextTypes

import config
from pyowm import OWM

# Import modules for geolocation function
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

owm = OWM(config.OWM)
mgr = owm.weather_manager()

COUNTRY_CODES = ['CA','US']
STATE_CODES = ['AL','AK','AR','AZ','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IA','IN','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']
PROVINCE_CODES = ['NS','NB','PE','NL','QE','ON','SK','MB','AB','BC']

def get_coordinates(location_name, timeout=10, retries=3):

    geolocator = Nominatim(user_agent="location_geocoder")

    for attempt in range(retries):
        try:
            location = geolocator.geocode(location_name, timeout=timeout)

            if location:
                return (location.latitude, location.longitude)
            else:
                return None

        except GeocoderTimedOut:
            if attempt < retries -1:
                print(f"Timeout occured. Retrying in 1 second... (Attempt {attempt + 1}/{retries})")
                time.sleep(1)
            else:
                raise Exception(f"Geocoding service timed out after {retries} tries")

        except GeocoderServiceError as e:
            raise Exception(f"Geocoding service error: {e}")

    return None

async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get forecast for given location"""
    message = update.message.text
    if len(message.split()) > 1:
        location = await asyncio.to_thread(
            get_coordinates, " ".join(update.message.text.split()[1:])
        )
        if location != None:
            weather = await asyncio.to_thread(
                mgr.forecast_at_coords,
                lat=location[0],
                lon=location[1],
                interval='daily',
            )
            cur_forecast = ""
            for i in range(len(weather.forecast.weathers)):
                cur_forecast += f"{weather.forecast.weathers[i].reference_time(timeformat='iso')} - {weather.forecast.weathers[i].detailed_status} Temp: {weather.forecast.weathers[i].temperature('celsius')['day']}\n"

            await context.bot.send_message(update.message.chat_id, text=f"{cur_forecast}")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current weather for given location."""
    message = update.message.text
    if len(message.split()) > 1:
        if message.split()[1].isdigit():
            zipcode = message.split()[1]
            weather = (await asyncio.to_thread(mgr.weather_at_zip_code, zipcode, 'US')).weather
            temperature = weather.temperature('fahrenheit')
            wind = str(round(weather.wind(unit='miles_hour')['speed'],2)) + "mph"
            fltemp = str(temperature['feels_like']) + "\u00b0 F (" + str(round((temperature['feels_like']-32)/1.8)) + "\u00b0 C)"
            rtemp = str(temperature['temp']) + "\u00b0 F (" + str(round((temperature['temp']-32)/1.8)) + "\u00b0 C)"
            mintemp = str(temperature['temp_min']) + "\u00b0 F (" + str(round((temperature['temp_min']-32)/1.8)) + "\u00b0 C)"
            maxtemp = str(temperature['temp_max']) + "\u00b0 F (" + str(round((temperature['temp_max']-32)/1.8)) + "\u00b0 C)"
            humidity = str(weather.humidity)
            forcast = f"It is currently {weather.detailed_status} and feels like {fltemp}\n"\
                f"It will reach a high of {maxtemp}, with a low of {mintemp}\n"\
                f"The humidity is {humidity}%\n"\
                f"The actual temperature is: {rtemp} with a windspeed of {wind}\n"\
                f"The sun will set at {weather.sunset_time(timeformat='date')}"
            await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
        else:
            location = await asyncio.to_thread(
                get_coordinates, " ".join(update.message.text.split()[1:])
            )
            if location != None:
                weather = (await asyncio.to_thread(
                    mgr.weather_at_coords, lat=location[0], lon=location[1]
                )).weather
                temperature = weather.temperature('celsius')
                humidity = str(weather.humidity)
                wind = str(round((weather.wind()['speed'] * 3.6),2)) + "kph"
                fltemp = str(temperature['feels_like']) + "\u00b0 C (" + str(round(temperature['feels_like']*1.8)+32) + "\u00b0 F)"
                rtemp = str(temperature['temp']) + "\u00b0 C (" + str(round(temperature['temp']*1.8)+32) + "\u00b0 F)"
                mintemp = str(temperature['temp_min']) + "\u00b0 C (" + str(round(temperature['temp_min']*1.8)+32) + "\u00b0 F)"
                maxtemp = str(temperature['temp_max']) + "\u00b0 C (" + str(round(temperature['temp_max']*1.8)+32) + "\u00b0 F)"
                forcast = f"It's currently {weather.detailed_status} and feels like {fltemp}\n"\
                    f"It will reach a high of {maxtemp}, with a low of {mintemp}\n"\
                    f"The humidity is {humidity}%\n"\
                    f"The actual temperature is: {rtemp} with a windspeed of {wind}\n"\
                    f"The sun will set at {weather.sunset_time(timeformat='date').time().strftime('%H:%M:%S')}"
                await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
            else:
                await context.bot.send_message(update.message.chat_id, text=f"Error finding location")
    else:
        await context.bot.send_message(update.message.chat_id, text=f"Please include a location with your command")

