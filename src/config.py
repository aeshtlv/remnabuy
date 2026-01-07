import os
import logging
import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv, dotenv_values
from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Принудительно перечитываем .env при каждом импорте
if ENV_FILE.exists():
    # Перезагружаем переменные окружения из файла
    env_vars = dotenv_values(ENV_FILE)
    for key, value in env_vars.items():
        if value is not None:
            os.environ[key] = value
else:
    # Если .env не существует, используем переменные окружения процесса
    load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    api_base_url: AnyHttpUrl = Field(..., alias="API_BASE_URL")
    api_token: str | None = Field(default=None, alias="API_TOKEN")
    default_locale: str = Field("ru", alias="DEFAULT_LOCALE")
    admins: List[int] = Field(default_factory=list, alias="ADMINS", json_schema_extra={"type": "string"})
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    notifications_chat_id: int | None = Field(default=None, alias="NOTIFICATIONS_CHAT_ID")
    notifications_topic_id: int | None = Field(default=None, alias="NOTIFICATIONS_TOPIC_ID")
    # Настройки для Telegram Stars платежей
    # ВАЖНО: Если переменные не найдены в .env, будут использованы дефолтные значения ниже
    # Проверьте логи при запуске - там будет видно, откуда берутся значения
    subscription_stars_1month: int = Field(
        default=100, 
        alias="SUBSCRIPTION_STARS_1MONTH",
        description="Stars за 1 месяц (дефолт: 100, если не указано в .env)"
    )
    subscription_stars_3months: int = Field(
        default=250, 
        alias="SUBSCRIPTION_STARS_3MONTHS",
        description="Stars за 3 месяца (дефолт: 250, если не указано в .env)"
    )
    subscription_stars_6months: int = Field(
        default=450, 
        alias="SUBSCRIPTION_STARS_6MONTHS",
        description="Stars за 6 месяцев (дефолт: 450, если не указано в .env)"
    )
    subscription_stars_12months: int = Field(
        default=800, 
        alias="SUBSCRIPTION_STARS_12MONTHS",
        description="Stars за 12 месяцев (дефолт: 800, если не указано в .env)"
    )
    trial_days: int = Field(3, alias="TRIAL_DAYS")  # Дней пробной подписки
    # Дефолтные сквады для новых пользователей
    default_external_squad_uuid: str | None = Field(default=None, alias="DEFAULT_EXTERNAL_SQUAD_UUID")
    # Важно: pydantic-settings пытается парсить list[str] из env как JSON, поэтому храним сырой строкой
    # и уже потом парсим в list через property.
    default_internal_squads_raw: str | None = Field(default=None, alias="DEFAULT_INTERNAL_SQUADS")

    @field_validator("notifications_chat_id", mode="before")
    @classmethod
    def parse_notifications_chat_id(cls, value):
        """Парсит NOTIFICATIONS_CHAT_ID в int или возвращает None."""
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None
    
    @field_validator("notifications_topic_id", mode="before")
    @classmethod
    def parse_notifications_topic_id(cls, value):
        """Парсит NOTIFICATIONS_TOPIC_ID в int или возвращает None."""
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),  # Явно указываем путь как строку
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # Игнорируем пустые значения
        populate_by_name=True,  # Разрешаем использовать alias
        extra="ignore",
        case_sensitive=False,  # Не чувствительно к регистру
    )

    @property
    def allowed_admins(self) -> set[int]:
        return set(self.admins)

    @field_validator("admins", mode="before")
    @classmethod
    def parse_admins(cls, value):
        """Парсит список администраторов из строки, int или списка."""
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value] if value > 0 else []
        if isinstance(value, str):
            admins: list[int] = []
            for part in (x.strip() for x in value.split(",")):
                if not part:
                    continue
                try:
                    admin_id = int(part)
                    if admin_id > 0:
                        admins.append(admin_id)
                except ValueError:
                    continue
            return admins
        if isinstance(value, list):
            parsed: list[int] = []
            for x in value:
                try:
                    xi = int(x)
                    if xi > 0:
                        parsed.append(xi)
                except (TypeError, ValueError):
                    continue
            return parsed
        return []
    
    @property
    def default_internal_squads(self) -> list[str]:
        """Возвращает список внутренних squads.

        Поддерживает форматы:
        - "uuid1,uuid2"
        - '["uuid1","uuid2"]'
        """
        raw = self.default_internal_squads_raw
        if raw is None:
            raw = os.getenv("DEFAULT_INTERNAL_SQUADS")
        if not raw:
            return []
        raw = str(raw).strip()
        # JSON array
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                # fallback to comma split
                pass
        return [x.strip() for x in raw.split(",") if x.strip()]
    
    @model_validator(mode="after")
    def parse_admins_from_env(self):
        """Дополнительная проверка: если admins пустой, но ADMINS в окружении есть, парсим его."""
        if not self.admins:
            raw_env_value = os.getenv("ADMINS")
            if raw_env_value:
                parts = [x.strip() for x in raw_env_value.split(",")]
                admins = []
                for part in parts:
                    if not part:
                        continue
                    try:
                        admin_id = int(part)
                        if admin_id > 0:
                            admins.append(admin_id)
                    except ValueError:
                        continue
                if admins:
                    self.admins = admins
        return self


_settings_cache: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """Получить настройки приложения (с кешированием).
    
    Args:
        reload: Если True, принудительно перезагрузить настройки из .env
    """
    global _settings_cache
    
    # Если кеш есть и не требуется перезагрузка, возвращаем его
    if _settings_cache is not None and not reload:
        return _settings_cache
    
    # Принудительно перечитываем .env файл
    if ENV_FILE.exists():
        env_vars = dotenv_values(ENV_FILE)
        for key, value in env_vars.items():
            if value is not None:
                os.environ[key] = value
    
    # Создаем новый экземпляр Settings
    settings = Settings()
    _settings_cache = settings
    
    # Логируем настройки при первой загрузке или перезагрузке
    logger = logging.getLogger("remnabuy-config")
    logger.info("=" * 60)
    logger.info("SETTINGS LOADED")
    logger.info("=" * 60)
    
    # Логируем цены подписок
    logger.info("Subscription prices (Stars):")
    logger.info("  1 month:  %s stars (env: %s)", settings.subscription_stars_1month, os.getenv("SUBSCRIPTION_STARS_1MONTH", "NOT SET"))
    logger.info("  3 months: %s stars (env: %s)", settings.subscription_stars_3months, os.getenv("SUBSCRIPTION_STARS_3MONTHS", "NOT SET"))
    logger.info("  6 months: %s stars (env: %s)", settings.subscription_stars_6months, os.getenv("SUBSCRIPTION_STARS_6MONTHS", "NOT SET"))
    logger.info("  12 months: %s stars (env: %s)", settings.subscription_stars_12months, os.getenv("SUBSCRIPTION_STARS_12MONTHS", "NOT SET"))
    
    # Логируем сквады
    logger.info("Squads configuration:")
    logger.info("  External squad: %s (env: %s)", settings.default_external_squad_uuid, os.getenv("DEFAULT_EXTERNAL_SQUAD_UUID", "NOT SET"))
    logger.info("  Internal squads: %s (env: %s)", settings.default_internal_squads, os.getenv("DEFAULT_INTERNAL_SQUADS", "NOT SET"))
    logger.info("  Parsed internal squads count: %s", len(settings.default_internal_squads) if settings.default_internal_squads else 0)
    
    # Логируем админов
    logger.info("Admins: %s (env: %s)", settings.admins, os.getenv("ADMINS", "NOT SET"))
    
    logger.info("=" * 60)
    
    return settings
