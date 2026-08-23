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

Pushes to `master` trigger the **Deploy** workflow: lint + tests must pass in CI, then the Docker image is pushed to GHCR (`ghcr.io/sl0rd/telefam-bot`) and deployed over SSH.

### Topology

```
GitHub Actions ──build & push──▶ ghcr.io/sl0rd/telefam-bot
       │
       └──SSH (forced command)──▶ Docker host: /opt/telefam-bot
                                   docker compose pull && up -d
```

The runtime stack is plain `docker compose`, owned by `/opt/telefam-bot/` on the host. Portainer (if used) watches it read-only as an external stack — no Portainer features are required.

### Server setup (one-time)

1. On the Docker host, create `/opt/telefam-bot/` containing the repo's `docker-compose.yml`, a `.env` file, and [`deploy/deploy.sh`](deploy/deploy.sh):

   ```dotenv
   # .env — root:deploy, mode 0640
   TELEGRAM_TOKEN=...
   OWM_API_KEY=...
   EXCHANGERATE_API_KEY=...
   LASTFM_API_KEY=...
   ADMIN_IDS=123456789,987654321
   ```

   ```bash
   sudo chown root:root deploy.sh && sudo chmod 755 deploy.sh
   ```

2. Dedicated CI account and key pair:

   ```bash
   sudo useradd -m -s /bin/bash deploy
   sudo usermod -aG docker deploy
   ssh-keygen -t ed25519 -N "" -C telefam-ci -f telefam_deploy_key
   ```

3. `/home/deploy/.ssh/authorized_keys` uses a **forced command** so the CI key can only ever run the deploy script — no shell, no tunnels:

   ```
   command="/opt/telefam-bot/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... telefam-ci
   ```

### GitHub repository secrets

| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | Docker host hostname or IP |
| `DEPLOY_SSH_KEY` | contents of the **private** key (`telefam_deploy_key`) |
| `DEPLOY_HOST_KEY` | verbatim output of `ssh-keyscan -t ed25519 <host>` |

### GHCR pull access

Either set the package to public, or on the Docker host run `echo "<PAT>" | docker login ghcr.io -u SL0RD --password-stdin` with a PAT that has `read:packages`.

### Verify

```bash
ssh -i telefam_deploy_key deploy@<host>    # runs deploy.sh immediately; no shell prompt = forced command working
cd /opt/telefam-bot && docker compose ps   # container Up
docker logs telefam-bot --tail 20          # modules load, polling starts
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
