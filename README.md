# RemnaBuy — Telegram‑бот для SHFTVPN (покупка подписок + админ‑панель)

**Languages:** [English](README_EN.md)

RemnaBuy превращает Remnawave‑панель в **user‑facing витрину** для **SHFTVPN**: пользователь покупает подписку → получает конфиг‑ссылку, а администратор управляет инфраструктурой Remnawave в привычном интерфейсе бота.

## Возможности

- **Пользователям**:
  - **Покупка подписок** через Telegram Stars (1 / 3 / 6 / 12 месяцев)
  - **Пробная подписка** (кнопка “Активировать”)
  - **Промокоды** (скидка/бонусные дни)
  - **Реферальная программа**
  - **Моя подписка**: статус, срок, трафик, ссылка на конфиг
  - **RU/EN интерфейс**
- **Админам**:
  - Управление пользователями/нодами/хостами
  - Ресурсы (шаблоны/сниппеты/токены)
  - Биллинг/статистика

## Быстрый старт (Docker)

### Требования

- Docker + Docker Compose
- Telegram Bot Token от [@BotFather](https://t.me/BotFather)
- Доступ к Remnawave API (`API_BASE_URL`, `API_TOKEN`)

### Установка

```bash
git clone https://github.com/aeshtlv/RemnaShop_by_deadera.git
cd remnabuy
cp env.sample .env
nano .env
docker network create remnawave-network || true
docker compose up -d --build
docker compose logs -f bot
```

> `docker-compose.yml` автоматически читает `.env` через `env_file`, ничего дополнительно пробрасывать не нужно.

## Конфигурация (.env)

Все переменные перечислены в `env.sample`.

Ключевые:

- **`BOT_TOKEN`**: токен бота
- **`API_BASE_URL`**: базовый URL панели (например `https://panel.example.com`)
- **`API_TOKEN`**: токен доступа
- **`ADMINS`**: Telegram ID админов через запятую
- **`SUBSCRIPTION_STARS_*`**: цены (Stars)
- **`DEFAULT_INTERNAL_SQUADS` / `DEFAULT_EXTERNAL_SQUAD_UUID`**: squads для новых пользователей (важно для корректного конфига)

`DEFAULT_INTERNAL_SQUADS` поддерживает форматы:
- `uuid1,uuid2`
- `["uuid1","uuid2"]`

## Разработка

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или: .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp env.sample .env
python -m src.main
```

## Troubleshooting

- **Не меняются цены/сквады**: убедись, что правишь именно `.env` рядом с `docker-compose.yml`, затем `docker compose up -d --build`.
- **Временные ошибки Telegram (Bad Gateway/Connection reset)**: это сетевое; при частых проблемах нужен прокси/VPN на сервере.

## Поддержка

Issues: `https://github.com/aeshtlv/RemnaShop_by_deadera/issues`

## Лицензия

MIT — см. `LICENSE`.
