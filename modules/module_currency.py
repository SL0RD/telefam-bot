import logging

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from settings import ER_API_KEY

logger = logging.getLogger(__name__)

ER_API_URL = f"https://v6.exchangerate-api.com/v6/{ER_API_KEY}/latest/USD"


def parse_command_amount(text: str):
    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None


async def get_cad_rate():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(ER_API_URL)
            response.raise_for_status()
            return response.json()["conversion_rates"]["CAD"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.error("Failed to fetch exchange rate: %s", e)
        return None


async def usd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = parse_command_amount(update.message.text)
    if amount is None:
        await update.message.reply_text("Please provide a valid amount, e.g. /usd 100")
        return
    cad = await get_cad_rate()
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
    cad = await get_cad_rate()
    if cad is None:
        await update.message.reply_text("Could not fetch exchange rates. Please try again later.")
        return
    resp = f"{amount}USD is {(amount * cad):.2f}CAD"
    await context.bot.send_message(update.message.chat_id, text=resp)
