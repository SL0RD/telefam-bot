import asyncio
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from geopy.exc import GeocoderServiceError, GeocoderTimedOut

# Import modules for geolocation function
from geopy.geocoders import Nominatim
from pyowm import OWM as OWMClient
from telegram import Update
from telegram.ext import ContextTypes
from timezonefinder import TimezoneFinder

from settings import OWM

owm = OWMClient(OWM)
mgr = owm.weather_manager()

_TZ_FINDER = TimezoneFinder()

COUNTRY_CODES = ['CA','US']
STATE_CODES = [
    'AL','AK','AR','AZ','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IA',
    'IN','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH',
    'NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT',
    'VT','VA','WA','WV','WI','WY',
]
PROVINCE_CODES = ['NS','NB','PE','NL','QE','ON','SK','MB','AB','BC']


def _f_display(temp) -> str:
    return f"{temp}\u00b0 F ({round((temp - 32) / 1.8)}\u00b0 C)"


def _c_display(temp) -> str:
    return f"{temp}\u00b0 C ({round(temp * 1.8) + 32}\u00b0 F)"


def _local_display(dt_utc, lat, lon) -> str:
    """Render a naive-UTC datetime in local wall time, e.g. '7:42 PM ADT'."""
    tzname = _TZ_FINDER.timezone_at(lat=float(lat), lng=float(lon)) or "UTC"
    local = dt_utc.replace(tzinfo=UTC).astimezone(ZoneInfo(tzname))
    return local.strftime("%I:%M %p %Z").lstrip("0")


def _status_emoji(status: str) -> str:
    """Pick an emoji matching an OWM condition string like 'light rain'."""
    s = (status or "").lower()
    for key, emoji in (
        ("thunder", "\u26c8\ufe0f"),
        ("drizzle", "\ud83c\udf26\ufe0f"),
        ("rain", "\ud83c\udf27\ufe0f"),
        ("snow", "\ud83c\udf28\ufe0f"),
        ("sleet", "\ud83c\udf28\ufe0f"),
        ("hail", "\ud83c\udf28\ufe0f"),
        ("cloud", "\u2601\ufe0f"),
        ("fog", "\ud83c\udf2b\ufe0f"),
        ("mist", "\ud83c\udf2b\ufe0f"),
        ("haze", "\ud83c\udf2b\ufe0f"),
        ("clear", "\u2600\ufe0f"),
        ("sun", "\u2600\ufe0f"),
    ):
        if key in s:
            return emoji
    return "\ud83c\udf24\ufe0f"


def _forecast_line(iso_time: str, temp_c: float, status: str) -> str:
    """One forecast row: '☀️ Sun Aug 23 - Clear sky Temp: 21°C'."""
    when = datetime.fromisoformat(iso_time)
    return (
        f"{_status_emoji(status)} {when.strftime('%a %b %d')} - "
        f"{status.capitalize()} Temp: {temp_c:.0f}\u00b0C"
    )

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
            if attempt < retries - 1:
                print(f"Timeout occured. Retrying in 1 second... (Attempt {attempt + 1}/{retries})")
                time.sleep(1)
            else:
                raise Exception(
                    f"Geocoding service timed out after {retries} tries"
                ) from None

        except GeocoderServiceError as e:
            raise Exception(f"Geocoding service error: {e}") from e

    return None

async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get forecast for given location"""
    message = update.message.text
    if len(message.split()) > 1:
        location = await asyncio.to_thread(
            get_coordinates, " ".join(update.message.text.split()[1:])
        )
        if location is not None:
            weather = await asyncio.to_thread(
                mgr.forecast_at_coords,
                lat=location[0],
                lon=location[1],
                interval='daily',
            )
            cur_forecast = ""
            for day in weather.forecast.weathers:
                temp = day.temperature('celsius')['day']
                cur_forecast += (
                    _forecast_line(
                        day.reference_time(timeformat='iso'),
                        temp,
                        day.detailed_status,
                    )
                    + "\n"
                )

            await context.bot.send_message(update.message.chat_id, text=f"{cur_forecast}")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current weather for given location."""
    message = update.message.text
    if len(message.split()) > 1:
        if message.split()[1].isdigit():
            zipcode = message.split()[1]
            weather = (await asyncio.to_thread(mgr.weather_at_zip_code, zipcode, 'US')).weather
            temperature = weather.temperature('fahrenheit')
            wind = str(round(weather.wind(unit='miles_hour')['speed'], 2)) + "mph"
            fltemp = _f_display(temperature['feels_like'])
            rtemp = _f_display(temperature['temp'])
            mintemp = _f_display(temperature['temp_min'])
            maxtemp = _f_display(temperature['temp_max'])
            humidity = str(weather.humidity)
            sunset = _local_display(
                weather.sunset_time(timeformat='date'),
                weather.location.lat,
                weather.location.lon,
            )
            forcast = f"It is currently {weather.detailed_status} and feels like {fltemp}\n"\
                f"It will reach a high of {maxtemp}, with a low of {mintemp}\n"\
                f"The humidity is {humidity}%\n"\
                f"The actual temperature is: {rtemp} with a windspeed of {wind}\n"\
                f"The sun will set at {sunset}"
            await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
        else:
            location = await asyncio.to_thread(
                get_coordinates, " ".join(update.message.text.split()[1:])
            )
            if location is not None:
                weather = (await asyncio.to_thread(
                    mgr.weather_at_coords, lat=location[0], lon=location[1]
                )).weather
                temperature = weather.temperature('celsius')
                humidity = str(weather.humidity)
                wind = str(round((weather.wind()['speed'] * 3.6), 2)) + "kph"
                fltemp = _c_display(temperature['feels_like'])
                rtemp = _c_display(temperature['temp'])
                mintemp = _c_display(temperature['temp_min'])
                maxtemp = _c_display(temperature['temp_max'])
                sunset = _local_display(
                    weather.sunset_time(timeformat='date'), location[0], location[1]
                )
                forcast = f"It's currently {weather.detailed_status} and feels like {fltemp}\n"\
                    f"It will reach a high of {maxtemp}, with a low of {mintemp}\n"\
                    f"The humidity is {humidity}%\n"\
                    f"The actual temperature is: {rtemp} with a windspeed of {wind}\n"\
                    f"The sun will set at {sunset}"
                await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
            else:
                await context.bot.send_message(
                    update.message.chat_id, text="Error finding location"
                )
    else:
        await context.bot.send_message(
            update.message.chat_id,
            text="Please include a location with your command",
        )

