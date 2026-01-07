"""Сервис для работы с платежами через Telegram Stars."""
import json
import uuid
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import LabeledPrice

from src.config import get_settings
from src.database import Payment
from src.utils.logger import logger


async def create_subscription_invoice(
    bot: Bot,
    user_id: int,
    subscription_months: int,
    promo_code: str | None = None
) -> str:
    """Создает ссылку на оплату подписки через Telegram Stars.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя Telegram
        subscription_months: Количество месяцев подписки (1, 3, 6, 12)
        promo_code: Промокод для скидки (опционально)
    
    Returns:
        Ссылка на оплату
    """
    settings = get_settings()
    
    # Получаем цену в Stars
    stars_prices = {
        1: settings.subscription_stars_1month,
        3: settings.subscription_stars_3months,
        6: settings.subscription_stars_6months,
        12: settings.subscription_stars_12months,
    }
    
    if subscription_months not in stars_prices:
        raise ValueError(f"Invalid subscription months: {subscription_months}")
    
    base_stars = stars_prices[subscription_months]
    
    # Применяем промокод (если есть)
    discount_percent = 0
    if promo_code:
        from src.database import PromoCode
        promo = PromoCode.get(promo_code)
        if promo:
            discount_percent = promo.get("discount_percent", 0) or 0
    
    stars = int(base_stars * (1 - discount_percent / 100))
    subscription_days = subscription_months * 30
    
    # Создаем payload для invoice
    invoice_payload = json.dumps({
        "user_id": user_id,
        "subscription_months": subscription_months,
        "subscription_days": subscription_days,
        "stars": stars,
        "promo_code": promo_code,
        "timestamp": datetime.now().isoformat()
    })
    
    # Создаем запись о платеже
    payment_id = Payment.create(
        user_id=user_id,
        stars=stars,
        invoice_payload=invoice_payload,
        subscription_days=subscription_days,
        promo_code=promo_code
    )
    
    # Описание подписки
    locale_map = {
        1: ("1 месяц", "1 month"),
        3: ("3 месяца", "3 months"),
        6: ("6 месяцев", "6 months"),
        12: ("12 месяцев", "12 months"),
    }
    
    description_ru, description_en = locale_map[subscription_months]
    description = f"Подписка Remnawave {description_ru} | Remnawave subscription {description_en}"
    
    # Создаем invoice link
    try:
        invoice_link = await bot.create_invoice_link(
            title=f"Remnawave {description_ru}",
            description=description,
            payload=invoice_payload,
            provider_token="",  # Для Stars не требуется
            currency="XTR",  # Telegram Stars currency
            prices=[LabeledPrice(label=description, amount=stars)],
        )
        
        logger.info(f"Invoice created for user {user_id}: {payment_id}, {stars} stars")
        return invoice_link.invoice_link
    except Exception as e:
        logger.error(f"Failed to create invoice for user {user_id}: {e}")
        # Обновляем статус платежа на failed
        Payment.update_status(payment_id, "failed")
        raise


async def process_successful_payment(
    user_id: int,
    invoice_payload: str,
    total_amount: int
) -> dict:
    """Обрабатывает успешный платеж и создает пользователя в Remnawave.
    
    Args:
        user_id: ID пользователя Telegram
        invoice_payload: Payload из invoice
        total_amount: Общая сумма в Stars
    
    Returns:
        Словарь с результатом (success, user_uuid, subscription_url, error)
    """
    try:
        # Парсим payload
        payload_data = json.loads(invoice_payload)
        subscription_days = payload_data.get("subscription_days", 30)
        promo_code = payload_data.get("promo_code")
        
        # Находим платеж в БД
        payment = Payment.get_by_payload(invoice_payload)
        if not payment:
            logger.error(f"Payment not found for payload: {invoice_payload}")
            return {"success": False, "error": "Payment not found"}
        
        if payment["status"] == "completed":
            logger.warning(f"Payment {payment['id']} already completed")
            return {
                "success": True,
                "user_uuid": payment["remnawave_user_uuid"],
                "already_completed": True
            }
        
        # Проверяем сумму
        if payment["stars"] != total_amount:
            logger.error(f"Amount mismatch: expected {payment['stars']}, got {total_amount}")
            Payment.update_status(payment["id"], "failed")
            return {"success": False, "error": "Amount mismatch"}
        
        # Получаем информацию о пользователе
        from src.database import BotUser
        bot_user = BotUser.get_or_create(user_id, None)
        username = bot_user.get("username") or f"user_{user_id}"
        
        # Вычисляем дату истечения
        expire_date = (datetime.now() + timedelta(days=subscription_days)).replace(microsecond=0).isoformat() + "Z"
        
        # Создаем пользователя в Remnawave
        from src.services.api_client import api_client
        
        # Проверяем, есть ли уже пользователь
        remnawave_uuid = bot_user.get("remnawave_user_uuid")
        
        if remnawave_uuid:
            # Обновляем существующего пользователя
            try:
                user_data = await api_client.get_user_by_uuid(remnawave_uuid)
                current_expire = user_data.get("response", {}).get("expireAt")
                
                if current_expire:
                    # Продлеваем подписку от текущей даты
                    current_dt = datetime.fromisoformat(current_expire.replace("Z", "+00:00"))
                    if current_dt > datetime.now(current_dt.tzinfo):
                        expire_date = (current_dt + timedelta(days=subscription_days)).replace(microsecond=0).isoformat() + "Z"
                
                await api_client.update_user(remnawave_uuid, expireAt=expire_date)
                user_uuid = remnawave_uuid
            except Exception as e:
                logger.error(f"Failed to update user {remnawave_uuid}: {e}")
                # Создаем нового пользователя
                user_data = await api_client.create_user(
                    username=username,
                    expire_at=expire_date,
                    telegram_id=user_id
                )
                user_info = user_data.get("response", user_data)
                user_uuid = user_info.get("uuid")
                BotUser.set_remnawave_uuid(user_id, user_uuid)
        else:
            # Создаем нового пользователя
            user_data = await api_client.create_user(
                username=username,
                expire_at=expire_date,
                telegram_id=user_id
            )
            user_info = user_data.get("response", user_data)
            user_uuid = user_info.get("uuid")
            BotUser.set_remnawave_uuid(user_id, user_uuid)
        
        # Получаем ссылку на подписку
        user_full = await api_client.get_user_by_uuid(user_uuid)
        user_full_info = user_full.get("response", user_full)
        short_uuid = user_full_info.get("shortUuid")
        
        subscription_url = ""
        if short_uuid:
            try:
                sub_info = await api_client.get_subscription_info(short_uuid)
                sub_data = sub_info.get("response", sub_info)
                subscription_url = sub_data.get("subscriptionUrl", "")
            except:
                pass
        
        # Обновляем статус платежа
        Payment.update_status(payment["id"], "completed", user_uuid)
        
        # Применяем промокод (если есть)
        if promo_code:
            from src.database import PromoCode
            PromoCode.use(promo_code, user_id)
        
        logger.info(f"Payment processed successfully for user {user_id}: user_uuid={user_uuid}")
        
        return {
            "success": True,
            "user_uuid": user_uuid,
            "subscription_url": subscription_url,
            "expire_date": expire_date
        }
    except Exception as e:
        logger.exception(f"Failed to process payment for user {user_id}: {e}")
        payment = Payment.get_by_payload(invoice_payload)
        if payment:
            Payment.update_status(payment["id"], "failed")
        return {"success": False, "error": str(e)}

