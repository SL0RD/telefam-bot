from telegram import Update
from telegram.ext import ContextTypes

import config
from pyowm import OWM
# from pyowm.utils import config as owmconfig
# from pyowm.utils import timestamps

config = config
owm = OWM(config.OWM)
mgr = owm.weather_manager()
reg = owm.city_id_registry()
#zip = mgr.weather_at_zip_code()

COUNTRY_CODES = ['CA','US']
STATE_CODES = ['AL','AK','AR','AZ','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IA','IN','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']


def getLocation(location):
    location = " ".join(location.split()[1:])
    if len(location.split()[-1]) == 2:
        country = location.split()[-1].upper()
        location = " ".join(location.split()[:-1])
#        print(country)
#        print("Found country code")
        if len(location.split()[-1]) == 2:
#            print ("Found state code")
            state = location.split()[-1]
#            print(state)
            location = " ".join(location.split()[:-1])
#            print(location)
            locations = reg.locations_for(location, country=country, state=state, matching='exact')
        else:
#            print(location)
            locations = reg.locations_for(location, country=country, matching='exact')
    else:
        logger.info("Error: no Country code found.")
        country = ""

    if locations:
        return locations[0]
    else:
        return "Error, location not found"

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current weather for given location."""
    message = update.message.text
    if len(message.split()) > 1:
        if message.split()[1].isdigit():
            zipcode = message.split()[1]
            weather = mgr.weather_at_zip_code(zipcode,'US').weather
#            print(weather)
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
#                print(location)
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
                    rtemp = str(temperature['temp']) + "\u00b0 C (" + str(round(temperature['temp']*1.8)+32) + "\u00b0 F)"
                forcast = "It'ss currently {0} and feels like {1}\n"\
                        "The actual temperature is: {2} with a windspeed of {3}\n"\
                        "The sun will set at {4}".format(weather.detailed_status,fltemp, rtemp, wind, weather.sunset_time(timeformat='date'))
                await context.bot.send_message(update.message.chat_id, text=f"{forcast}")
            else:
                await context.bot.send_message(update.message.chat_id, text=f"Error finding location")
    else:
        await context.bot.send_message(update.message.chat_id, text=f"Please include a location with your command")


