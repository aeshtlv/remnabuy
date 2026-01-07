import os
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
    default_internal_squads: list[str] = Field(default_factory=list, alias="DEFAULT_INTERNAL_SQUADS", json_schema_extra={"type": "string"})

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
    
    @field_validator("default_internal_squads", mode="before")
    @classmethod
    def parse_internal_squads(cls, value):
        """Парсит DEFAULT_INTERNAL_SQUADS в список UUID (через запятую)."""
        # Также проверяем переменную окружения напрямую (на случай если pydantic не подхватил)
        env_value = os.getenv("DEFAULT_INTERNAL_SQUADS")
        if env_value and (value is None or value == "" or (isinstance(value, list) and len(value) == 0)):
            value = env_value
        
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str):
            # Убираем пробелы и разбиваем по запятой
            parts = [x.strip() for x in value.split(",") if x.strip()]
            return parts
        return []
    
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


# Убрали @lru_cache чтобы изменения в .env применялись без перезапуска
# Принудительно перечитываем .env при каждом вызове
def get_settings() -> Settings:
    # Перечитываем .env файл перед созданием Settings
    if ENV_FILE.exists():
        env_vars = dotenv_values(ENV_FILE)
        for key, value in env_vars.items():
            if value is not None:
                os.environ[key] = value
    
    return Settings()
