import json
import logging
import os

import httpx

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)

API_URL = "https://ws.audioscrobbler.com/2.0/"
DATA_FILE = os.path.join(os.getcwd(), "lastfm_users.json")


def _load_users() -> dict:
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        return {int(user_id): username for user_id, username in data.items()}
    except (OSError, ValueError):
        return {}


def _save_users(users: dict) -> None:
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=2)
    os.replace(tmp, DATA_FILE)


def _stored_username(user_id: int):
    return _load_users().get(user_id)


def _store_username(user_id: int, username: str) -> None:
    users = _load_users()
    users[user_id] = username
    _save_users(users)


async def _api_call(method: str, **params) -> dict:
    query = {
        "method": method,
        "api_key": config.LASTFM_API_KEY,
        "format": "json",
        **params,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(API_URL, params=query)
        response.raise_for_status()
        return response.json()


def _largest_image(images: list) -> str:
    for size in ("extralarge", "large", "medium", "small"):
        for image in images:
            if image.get("size") == size and image.get("#text"):
                return image["#text"]
    return None


def _format_number(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


async def _reply_api_error(update: Update, data: dict) -> bool:
    """Reply to a Last.fm API error payload. Returns True if there was an error."""
    if "error" not in data:
        return False
    if data["error"] == 6:
        await update.message.reply_text("Last.fm user not found.")
    else:
        await update.message.reply_text(f"Last.fm error: {data.get('message', 'unknown')}")
    return True


async def setlastfm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("Please provide a Last.fm username, e.g. /setlastfm SL0RD")
        return
    username = parts[1]
    _store_username(update.effective_user.id, username)
    await update.message.reply_text(f"Saved. Your Last.fm username is now: {username}")


async def np_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2:
        username = _stored_username(update.effective_user.id)
        if username is None:
            await update.message.reply_text(
                "I don't know your Last.fm username yet. Set it with /setlastfm <username> "
                "or pass one directly: /np <username>"
            )
            return
    else:
        username = parts[1]

    try:
        data = await _api_call("user.getrecenttracks", user=username, limit=1)
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.error("Failed to fetch now playing for %s: %s", username, e)
        await update.message.reply_text("Could not reach Last.fm. Please try again later.")
        return

    if await _reply_api_error(update, data):
        return

    tracks = data.get("recenttracks", {}).get("track", [])
    if not tracks:
        await update.message.reply_text(f"No scrobbles found for '{username}'.")
        return

    track = tracks[0]
    now_playing = "@attr" in track and track["@attr"].get("nowplaying") == "true"
    artist = track.get("artist", {}).get("#text", "Unknown artist")
    title = track.get("name", "Unknown track")
    album = track.get("album", {}).get("#text") or ""
    image = _largest_image(track.get("image", []))

    status = "Now playing" if now_playing else "Last scrobbled"
    line = f"{artist} — {title}"
    if album:
        line += f" ({album})"
    caption = f"{status} by {username}:\n{line}"

    if image:
        try:
            await update.message.reply_photo(photo=image, caption=caption)
            return
        except Exception as e:
            logger.warning("Failed to send album art: %s", e)
    await update.message.reply_text(caption)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("Please provide a Last.fm username, e.g. /stats SL0RD")
        return
    username = parts[1]

    try:
        data = await _api_call("user.getinfo", user=username)
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.error("Failed to fetch stats for %s: %s", username, e)
        await update.message.reply_text("Could not reach Last.fm. Please try again later.")
        return

    if await _reply_api_error(update, data):
        return

    user = data.get("user", {})
    lines = [f"Stats for {user.get('name', username)}:"]
    if user.get("playcount"):
        lines.append(f"Total scrobbles: {_format_number(user['playcount'])}")
    if user.get("artist_count"):
        lines.append(f"Artists: {_format_number(user['artist_count'])}")
    if user.get("track_count"):
        lines.append(f"Tracks: {_format_number(user['track_count'])}")
    await update.message.reply_text("\n".join(lines))
