# telefam-bot

A Telegram bot for family group chats. Handles currency conversion, weather lookups, group chat logging, and hot-reloadable command modules.

## Setup

1. Clone the repo and create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy the example config and fill in your API keys:

```bash
cp example.conf.py config.py
```

| Key | Where to get it |
|-----|-----------------|
| `TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram |
| `OWM` | [OpenWeatherMap](https://openweathermap.org/api) |
| `er_api_key` | [ExchangeRate-API](https://www.exchangerate-api.com/) |

3. Run the bot:

```bash
python bot.py
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show your chat ID |
| `/help` | List available commands |
| `/cad <amount>` | Convert USD to CAD |
| `/usd <amount>` | Convert CAD to USD |
| `/weather <location\|zip>` | Current weather for a city or US zip code |
| `/forecast <location>` | Daily forecast for a city |
| `/rehash` | Reload modules without restarting (admin only) |

## Modules

Place files named `module_*.py` in the `modules/` directory. Each module can export async functions named `*_command`; they are registered automatically as Telegram commands.

Example:

```python
from telegram import Update
from telegram.ext import ContextTypes

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")
```

This registers `/ping`. After adding or editing a module, run `/rehash` to reload without restarting the bot.

## Chat logging

All messages in groups and supergroups — text, commands, and media — are appended to `chatlogs/<chat-title>-<YYYYMMDD>.log`, along with join/leave events. Each line includes a full timestamp and the sender's username and numeric user ID.

## Security

- Never commit `config.py` — it is listed in `.gitignore`.
- Rotate your API keys if they were ever exposed in git history or shared publicly.
