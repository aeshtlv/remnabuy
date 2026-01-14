# Инструкция по обновлению после git pull

## Проблема: docker-compose не найден

Если команда `docker-compose` не найдена, используйте один из вариантов ниже.

## Вариант 1: Использовать `docker compose` (без дефиса)

В новых версиях Docker используется команда `docker compose` вместо `docker-compose`.

### Проверьте, установлен ли Docker:

```bash
docker --version
```

Если Docker установлен, попробуйте:

```bash
# Остановить контейнеры
docker compose down

# Пересобрать образ
docker compose build --no-cache

# Запустить контейнеры
docker compose up -d

# Посмотреть логи
docker compose logs -f bot
```

Или одной командой:

```bash
docker compose down && docker compose build --no-cache && docker compose up -d
```

## Вариант 2: Установить docker-compose

Если `docker compose` тоже не работает, установите docker-compose:

### Для Ubuntu/Debian:

```bash
# Установить docker-compose
apt update
apt install docker-compose -y
```

### Или установить через pip:

```bash
pip install docker-compose
```

### Или установить последнюю версию вручную:

```bash
# Скачать последнюю версию
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Сделать исполняемым
chmod +x /usr/local/bin/docker-compose

# Проверить
docker-compose --version
```

## Вариант 3: Использовать Docker напрямую

Если docker-compose не нужен, можно использовать Docker напрямую:

```bash
# Остановить контейнер
docker stop remnabuy-bot-1
docker rm remnabuy-bot-1

# Пересобрать образ
docker build -t remnabuy-bot .

# Запустить контейнер
docker run -d \
  --name remnabuy-bot \
  --env-file .env \
  --network remnawave-network \
  remnabuy-bot
```

## После установки/использования правильной команды

1. **Обновите .env файл** - добавьте настройки YooKassa:

```bash
nano .env
```

Добавьте:
```env
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_secret_key
SUBSCRIPTION_RUB_1MONTH=100.0
SUBSCRIPTION_RUB_3MONTHS=250.0
SUBSCRIPTION_RUB_6MONTHS=450.0
SUBSCRIPTION_RUB_12MONTHS=800.0
```

2. **Пересоберите и перезапустите**:

```bash
# Если используете docker compose (без дефиса)
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose logs -f bot

# Или если установили docker-compose (с дефисом)
docker-compose down
docker-compose build --no-cache
docker-compose up -d
docker-compose logs -f bot
```

## Проверка работы

В логах должны появиться:
```
✅ Database initialized
🔄 Renewal checker started
Starting bot
```

