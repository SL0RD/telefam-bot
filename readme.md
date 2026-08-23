# telefam-bot

A Telegram bot for family group chats. Handles currency conversion, weather lookups, group chat logging, and hot-reloadable command modules.

[![CI](https://github.com/SL0RD/telefam-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/SL0RD/telefam-bot/actions/workflows/ci.yml)

## Setup (local development)

1. Clone the repo and create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

2. Copy the example config and fill in your API keys:

```bash
cp example.conf.py config.py
```

Configuration is resolved from environment variables first, then from `config.py`:

| Env var | config.py key | Where to get it |
|---------|---------------|-----------------|
| `TELEGRAM_TOKEN` | `TOKEN` | [@BotFather](https://t.me/BotFather) |
| `OWM_API_KEY` | `OWM` | [OpenWeatherMap](https://openweathermap.org/api) |
| `EXCHANGERATE_API_KEY` | `er_api_key` | [ExchangeRate-API](https://www.exchangerate-api.com/) |
| `LASTFM_API_KEY` | `LASTFM_API_KEY` | [Last.fm](https://www.last.fm/api/account/create) |
| `ADMIN_IDS` | `ADMIN_IDS` | Comma-separated numeric Telegram user IDs |
| `ADMIN_USERNAME` | `ADMIN_USERNAME` | Fallback admin username |

3. Run the bot:

```bash
python bot.py
```

## Development

```bash
ruff check .   # lint
pytest         # run tests
```

## Deployment (CI/CD)

Pushes to `master` trigger the **Deploy** workflow: lint + tests must pass in CI, then the Docker image is pushed to GHCR (`ghcr.io/sl0rd/telefam-bot`) and a protected webhook redeploys the stack on the server.

### Topology

```
GitHub Actions ──POST /telefam/hook──▶ nginx VPS ──TLS──▶ Docker host (Portainer stack)
                     X-Hook-Secret       path-scoped        bot container
```

The nginx VPS exposes exactly one route, `/telefam/hook`, authenticated by a shared secret header. Portainer's UI and native API paths are never public.

### One-time setup

1. **Portainer (Docker host)** — create a stack from this repo's `docker-compose.yml` and set its environment variables (`TELEGRAM_TOKEN`, `OWM_API_KEY`, `EXCHANGERATE_API_KEY`, `LASTFM_API_KEY`, optional `ADMIN_IDS`). Enable **Webhooks** and note the `<id>` and `<token>` from the displayed webhook URL.
2. **Docker host firewall** — allow ports 9000/9443 only from the nginx VPS's IP; deny everyone else. Otherwise the proxy can be bypassed entirely.
3. **nginx VPS** — follow [`deploy/nginx-webhook.conf.example`](deploy/nginx-webhook.conf.example): expose `/telefam/hook`, protected by an `X-Hook-Secret` header (generate with `openssl rand -hex 32`). Portainer's native `/api/stacks/...` paths return 404.
4. **GHCR pull access** — either set the package to public, or store a GitHub PAT with `read:packages` in Portainer under **Registries**.
5. **GitHub secrets** (repository level):

   | Secret | Value |
   |--------|-------|
   | `PORTAINER_WEBHOOK_URL` | `https://<domain>/telefam/hook` |
   | `PORTAINER_HOOK_SECRET` | same hex string as in the nginx config |

### Verify

```bash
curl -i -X POST -H "X-Hook-Secret: <secret>" https://<domain>/telefam/hook  # 200, stack redeploys
curl -i -X POST https://<domain>/telefam/hook                               # 403, blocked at nginx
curl -i https://<domain>/api/state                                          # 404, internals closed
```

To deploy manually, push a commit to `master` or run the Deploy workflow via **Run workflow**.

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

All messages in groups and supergroups — text, commands, and media — are appended to the log directory (`chatlogs/`, override with `CHATLOG_DIR`), along with join/leave events. Each line includes a full timestamp and the sender's username and numeric user ID. Last.fm registrations persist to `lastfm_users.json` (override path with `LASTFM_DATA_FILE`). In Docker both live on named volumes (`bot-chatlogs`, `bot-data`).

## Security

- Never commit `config.py` — it is listed in `.gitignore`.
- Keep secrets in environment variables on the server; they are injected at runtime, never baked into the image.
- Rotate your API keys if they were ever exposed in git history or shared publicly.
