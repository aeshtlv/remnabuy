# RemnaBuy — Remnawave Telegram Bot (subscriptions + admin panel)

**Languages:** [Русский](README.md)

RemnaBuy turns your Remnawave panel into a **user‑facing storefront**: a user purchases a subscription → receives a config link, while admins keep full control of Remnawave from the bot.

## Features

- **User‑facing**:
  - Subscription purchase via **Telegram Stars** (1 / 3 / 6 / 12 months)
  - Trial subscription (manual activation button)
  - Promo codes (discount/bonus days)
  - Referral program
  - “My subscription”: status, expiry, traffic, config link
  - RU/EN UI
- **Admin**:
  - Users / nodes / hosts management
  - Resources (templates/snippets/tokens)
  - Billing & statistics

## Quick start (Docker)

### Requirements

- Docker + Docker Compose
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Remnawave API access (`API_BASE_URL`, `API_TOKEN`)

### Install

```bash
git clone https://github.com/aeshtlv/RemnaShop_by_deadera.git
cd remnabuy
cp env.sample .env
nano .env
docker network create remnawave-network || true
docker compose up -d --build
docker compose logs -f bot
```

> `docker-compose.yml` loads `.env` automatically via `env_file`.

## Configuration (.env)

See `env.sample` for the full list.

Key variables:

- **`BOT_TOKEN`**: bot token
- **`API_BASE_URL`**: panel base URL (e.g. `https://panel.example.com`)
- **`API_TOKEN`**: API token
- **`ADMINS`**: comma-separated Telegram user IDs
- **`SUBSCRIPTION_STARS_*`**: Stars prices
- **`DEFAULT_INTERNAL_SQUADS` / `DEFAULT_EXTERNAL_SQUAD_UUID`**: squads for newly created users (important)

`DEFAULT_INTERNAL_SQUADS` supports:
- `uuid1,uuid2`
- `["uuid1","uuid2"]`

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp env.sample .env
python -m src.main
```

## Troubleshooting

- **Prices/squads not updating**: ensure you edit `.env` next to `docker-compose.yml`, then `docker compose up -d --build`.
- **Telegram temporary errors** (Bad Gateway / connection reset): server networking issue; consider proxy/VPN if frequent.

## License

MIT — see `LICENSE`.

