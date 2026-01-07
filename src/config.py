import os
import logging
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
        raw_env_value = os.getenv("NOTIFICATIONS_CHAT_ID", "NOT_SET")
        print(f"DEBUG parse_notifications_chat_id: value={repr(value)}, type={type(value)}, raw_env={repr(raw_env_value)}")
        
        if value is None or value == "":
            print(f"DEBUG parse_notifications_chat_id: value is None or empty, returning None")
            return None
        if isinstance(value, int):
            print(f"DEBUG parse_notifications_chat_id: value is already int={value}, returning {value}")
            return value
        if isinstance(value, str):
            try:
                result = int(value)
                print(f"DEBUG parse_notifications_chat_id: parsed string '{value}' to int={result}")
                return result
            except ValueError:
                print(f"DEBUG parse_notifications_chat_id: failed to parse '{value}' as int, returning None")
                return None
        print(f"DEBUG parse_notifications_chat_id: value type not handled, returning None")
        return None
    
    @field_validator("notifications_topic_id", mode="before")
    @classmethod
    def parse_notifications_topic_id(cls, value):
        """Парсит NOTIFICATIONS_TOPIC_ID в int или возвращает None."""
        raw_env_value = os.getenv("NOTIFICATIONS_TOPIC_ID", "NOT_SET")
        print(f"DEBUG parse_notifications_topic_id: value={repr(value)}, type={type(value)}, raw_env={repr(raw_env_value)}")
        
        if value is None or value == "":
            print(f"DEBUG parse_notifications_topic_id: value is None or empty, returning None")
            return None
        if isinstance(value, int):
            print(f"DEBUG parse_notifications_topic_id: value is already int={value}, returning {value}")
            return value
        if isinstance(value, str):
            try:
                result = int(value)
                print(f"DEBUG parse_notifications_topic_id: parsed string '{value}' to int={result}")
                return result
            except ValueError:
                print(f"DEBUG parse_notifications_topic_id: failed to parse '{value}' as int, returning None")
                return None
        print(f"DEBUG parse_notifications_topic_id: value type not handled, returning None")
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
        raw_env_value = os.getenv("ADMINS", "NOT_SET")
        print(f"DEBUG parse_admins: raw_env_value={repr(raw_env_value)}, value={repr(value)}, type={type(value)}")
        
        if value is None or value == "":
            print("DEBUG parse_admins: value is None or empty, returning []")
            return []
        
        # Если значение уже int (pydantic-settings иногда преобразует строку в int)
        if isinstance(value, int):
            print(f"DEBUG parse_admins: value is already int={value}, returning [{value}]")
            return [value] if value > 0 else []
        
        if isinstance(value, str):
            # Разделяем по запятой и убираем пробелы
            parts = [x.strip() for x in value.split(",")]
            print(f"DEBUG parse_admins: parts after split={parts}")
            # Фильтруем только цифры и конвертируем в int
            admins = []
            for part in parts:
                if not part:  # Пропускаем пустые строки
                    continue
                try:
                    admin_id = int(part)
                    if admin_id > 0:  # Telegram user IDs всегда положительные
                        admins.append(admin_id)
                except ValueError:
                    # Игнорируем нечисловые значения
                    print(f"DEBUG parse_admins: failed to parse part={repr(part)}")
                    continue
            print(f"DEBUG parse_admins: final admins={admins}")
            return admins
        
        if isinstance(value, list):
            result = [int(x) for x in value if isinstance(x, (int, str)) and (isinstance(x, int) or str(x).isdigit())]
            print(f"DEBUG parse_admins: value is list, result={result}")
            return result
        
        print(f"DEBUG parse_admins: value type not handled, returning []")
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
                print(f"DEBUG parse_admins_from_env: admins is empty, but ADMINS env var exists: {repr(raw_env_value)}")
                # Парсим из окружения напрямую
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
                    print(f"DEBUG parse_admins_from_env: parsed admins={admins}, setting self.admins")
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
    
    settings = Settings()
    
    # Логируем, откуда берутся значения (для отладки)
    # ВАЖНО: не импортируем src.utils.logger здесь, иначе будет циклический импорт
    logger = logging.getLogger("remnabuy-config")
    
    # Проверяем цены подписок - сравниваем с дефолтными значениями
    stars_vars = {
        "SUBSCRIPTION_STARS_1MONTH": (settings.subscription_stars_1month, 100),
        "SUBSCRIPTION_STARS_3MONTHS": (settings.subscription_stars_3months, 250),
        "SUBSCRIPTION_STARS_6MONTHS": (settings.subscription_stars_6months, 450),
        "SUBSCRIPTION_STARS_12MONTHS": (settings.subscription_stars_12months, 800),
    }
    
    for var_name, (current_value, default_value) in stars_vars.items():
        env_value = os.getenv(var_name)
        if env_value:
            try:
                env_int = int(env_value)
                if env_int == current_value:
                    logger.info("✓ %s = %s (read from .env)", var_name, current_value)
                else:
                    logger.error(
                        "❌ MISMATCH: %s in .env is %s, but Settings has %s. "
                        "This means .env is NOT being read correctly!",
                        var_name, env_int, current_value
                    )
            except ValueError:
                logger.error("❌ Invalid value for %s in .env: %s (must be integer)", var_name, env_value)
        else:
            if current_value == default_value:
                logger.warning(
                    "⚠️ %s not found in .env, using DEFAULT value from config.py: %s",
                    var_name, current_value
                )
            else:
                logger.info("✓ %s = %s (from .env, not default)", var_name, current_value)
    
    # Проверяем сквады
    internal_squads_env = os.getenv("DEFAULT_INTERNAL_SQUADS")
    if internal_squads_env:
        logger.debug("✓ DEFAULT_INTERNAL_SQUADS found in .env: %s", internal_squads_env)
        logger.debug("  Parsed as: %s (type=%s, len=%s)", 
                    settings.default_internal_squads,
                    type(settings.default_internal_squads).__name__,
                    len(settings.default_internal_squads) if settings.default_internal_squads else 0)
    else:
        logger.warning("⚠️ DEFAULT_INTERNAL_SQUADS not found in .env, using default: %s", 
                      settings.default_internal_squads)
    
    return settings
