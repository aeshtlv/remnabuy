"""База данных для пользователей бота, промокодов и рефералов."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "bot_data.db"


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Инициализирует базу данных."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей бота
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'ru',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_used BOOLEAN DEFAULT 0,
                referrer_id INTEGER,
                remnawave_user_uuid TEXT,
                FOREIGN KEY (referrer_id) REFERENCES bot_users(telegram_id)
            )
        """)
        
        # Таблица промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                bonus_days INTEGER,
                max_uses INTEGER,
                current_uses INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Таблица использования промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_code_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                user_id INTEGER,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code) REFERENCES promo_codes(code),
                FOREIGN KEY (user_id) REFERENCES bot_users(telegram_id)
            )
        """)
        
        # Таблица рефералов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                bonus_days INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES bot_users(telegram_id),
                FOREIGN KEY (referred_id) REFERENCES bot_users(telegram_id),
                UNIQUE(referrer_id, referred_id)
            )
        """)
        
        # Таблица платежей (Telegram Stars)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stars INTEGER,
                status TEXT DEFAULT 'pending',
                remnawave_user_uuid TEXT,
                invoice_payload TEXT,
                subscription_days INTEGER,
                promo_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES bot_users(telegram_id)
            )
        """)


class BotUser:
    """Модель пользователя бота."""
    
    @staticmethod
    def get_or_create(telegram_id: int, username: Optional[str] = None) -> dict:
        """Получает или создает пользователя."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bot_users WHERE telegram_id = ?",
                (telegram_id,)
            )
            user = cursor.fetchone()
            
            if user:
                return dict(user)
            
            # Создаем нового пользователя
            cursor.execute("""
                INSERT INTO bot_users (telegram_id, username)
                VALUES (?, ?)
            """, (telegram_id, username))
            
            cursor.execute(
                "SELECT * FROM bot_users WHERE telegram_id = ?",
                (telegram_id,)
            )
            return dict(cursor.fetchone())
    
    @staticmethod
    def update_language(telegram_id: int, language: str):
        """Обновляет язык пользователя."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE bot_users SET language = ? WHERE telegram_id = ?",
                (language, telegram_id)
            )
    
    @staticmethod
    def set_trial_used(telegram_id: int):
        """Отмечает пробную подписку как использованную."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE bot_users SET trial_used = 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
    
    @staticmethod
    def set_referrer(telegram_id: int, referrer_id: int):
        """Устанавливает реферера для пользователя."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE bot_users SET referrer_id = ? WHERE telegram_id = ?",
                (referrer_id, telegram_id)
            )
    
    @staticmethod
    def set_remnawave_uuid(telegram_id: int, uuid: str):
        """Сохраняет UUID пользователя в Remnawave."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE bot_users SET remnawave_user_uuid = ? WHERE telegram_id = ?",
                (uuid, telegram_id)
            )


class PromoCode:
    """Модель промокода."""
    
    @staticmethod
    def create(
        code: str,
        discount_percent: Optional[int] = None,
        bonus_days: Optional[int] = None,
        max_uses: Optional[int] = None,
        expires_at: Optional[datetime] = None
    ):
        """Создает промокод."""
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO promo_codes (code, discount_percent, bonus_days, max_uses, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (code.upper(), discount_percent, bonus_days, max_uses, expires_at))
    
    @staticmethod
    def get(code: str) -> Optional[dict]:
        """Получает промокод."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
                (code.upper(),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def can_use(code: str) -> tuple[bool, Optional[str]]:
        """Проверяет, можно ли использовать промокод."""
        promo = PromoCode.get(code)
        if not promo:
            return False, "Промокод не найден"
        
        if promo.get("expires_at"):
            expires = datetime.fromisoformat(promo["expires_at"])
            if datetime.now() > expires:
                return False, "Промокод истек"
        
        if promo.get("max_uses"):
            if promo["current_uses"] >= promo["max_uses"]:
                return False, "Промокод больше недействителен"
        
        return True, None
    
    @staticmethod
    def use(code: str, user_id: int) -> bool:
        """Использует промокод."""
        can_use, error = PromoCode.can_use(code)
        if not can_use:
            return False
        
        with get_db_connection() as conn:
            # Увеличиваем счетчик использования
            conn.execute("""
                UPDATE promo_codes 
                SET current_uses = current_uses + 1 
                WHERE code = ?
            """, (code.upper(),))
            
            # Записываем использование
            conn.execute("""
                INSERT INTO promo_code_usage (code, user_id)
                VALUES (?, ?)
            """, (code.upper(), user_id))
            
        return True


class Referral:
    """Модель реферальной программы."""
    
    @staticmethod
    def create(referrer_id: int, referred_id: int, bonus_days: int = 0):
        """Создает реферальную запись."""
        with get_db_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO referrals (referrer_id, referred_id, bonus_days)
                    VALUES (?, ?, ?)
                """, (referrer_id, referred_id, bonus_days))
                return True
            except sqlite3.IntegrityError:
                # Уже существует
                return False
    
    @staticmethod
    def get_referrals_count(referrer_id: int) -> int:
        """Получает количество рефералов."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                (referrer_id,)
            )
            return cursor.fetchone()[0]
    
    @staticmethod
    def get_bonus_days(referrer_id: int) -> int:
        """Получает общее количество бонусных дней от рефералов."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT SUM(bonus_days) FROM referrals WHERE referrer_id = ?",
                (referrer_id,)
            )
            result = cursor.fetchone()[0]
            return result if result else 0
    
    @staticmethod
    def grant_bonus(referrer_id: int, referred_id: int, bonus_days: int) -> bool:
        """Начисляет бонусные дни за реферала (обновляет запись)."""
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE referrals 
                SET bonus_days = bonus_days + ?, bonus_granted_at = ?
                WHERE referrer_id = ? AND referred_id = ?
            """, (bonus_days, datetime.now().isoformat(), referrer_id, referred_id))
            return conn.total_changes > 0


class Payment:
    """Модель платежа."""
    
    @staticmethod
    def create(
        user_id: int, 
        stars: int, 
        invoice_payload: str,
        subscription_days: int,
        promo_code: Optional[str] = None,
        remnawave_user_uuid: Optional[str] = None
    ) -> int:
        """Создает запись о платеже."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payments (user_id, stars, remnawave_user_uuid, invoice_payload, subscription_days, promo_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, stars, remnawave_user_uuid, invoice_payload, subscription_days, promo_code))
            return cursor.lastrowid
    
    @staticmethod
    def get_by_payload(invoice_payload: str) -> Optional[dict]:
        """Получает платеж по invoice payload."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE invoice_payload = ?", (invoice_payload,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def update_status(payment_id: int, status: str, remnawave_uuid: Optional[str] = None):
        """Обновляет статус платежа."""
        with get_db_connection() as conn:
            completed_at = datetime.now().isoformat() if status == "completed" else None
            if remnawave_uuid:
                conn.execute("""
                    UPDATE payments 
                    SET status = ?, completed_at = ?, remnawave_user_uuid = ?
                    WHERE id = ?
                """, (status, completed_at, remnawave_uuid, payment_id))
            else:
                conn.execute("""
                    UPDATE payments 
                    SET status = ?, completed_at = ?
                    WHERE id = ?
                """, (status, completed_at, payment_id))
    
    @staticmethod
    def get(payment_id: int) -> Optional[dict]:
        """Получает платеж по ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

