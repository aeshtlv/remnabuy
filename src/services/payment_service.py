"""Сервис для работы с платежами через Telegram Stars."""
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
    logger.info(
        "Stars price table: 1m=%s,3m=%s,6m=%s,12m=%s (requested %s months)",
        stars_prices[1], stars_prices[3], stars_prices[6], stars_prices[12], subscription_months
    )
    
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
    # Telegram не принимает нулевую сумму
    stars = max(1, stars)
    subscription_days = subscription_months * 30
    
    # Создаем короткий payload для invoice (Telegram ограничивает длину)
    # Используем только необходимые данные
    invoice_payload = f"{user_id}:{subscription_months}:{stars}:{promo_code or ''}"
    
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
    # LabeledPrice.label имеет строгий лимит длины у Telegram — держим коротким
    price_label = f"Remnawave {subscription_months}m"
    
    # Создаем invoice link
    try:
        invoice_link = await bot.create_invoice_link(
            title=f"Remnawave {description_ru}",
            description=description,
            payload=invoice_payload,
            provider_token=None,  # Для Stars не требуется
            currency="XTR",  # Telegram Stars currency
            prices=[LabeledPrice(label=price_label, amount=stars)],
        )
        
        logger.info(f"Invoice created for user {user_id}: {payment_id}, {stars} stars")
        # create_invoice_link возвращает строку URL
        return str(invoice_link)
    except Exception as e:
        logger.exception(
            "Failed to create invoice for user %s: %s (payload=%r stars=%s months=%s promo=%r)",
            user_id,
            type(e).__name__,
            invoice_payload,
            stars,
            subscription_months,
            promo_code,
        )
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
        # Парсим короткий payload формата: user_id:months:stars:promo
        parts = invoice_payload.split(":")
        if len(parts) < 3:
            logger.error(f"Invalid payload format: {invoice_payload}")
            return {"success": False, "error": "Invalid payload format"}
        
        payload_user_id = int(parts[0])
        subscription_months = int(parts[1])
        payload_stars = int(parts[2])
        promo_code = parts[3] if len(parts) > 3 and parts[3] else None
        
        subscription_days = subscription_months * 30
        
        # Проверяем user_id
        if payload_user_id != user_id:
            logger.error(f"User ID mismatch: payload={payload_user_id}, actual={user_id}")
            return {"success": False, "error": "User ID mismatch"}
        
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
        
        # Проверяем сумму (допускаем небольшую погрешность)
        if abs(payment["stars"] - total_amount) > 1:
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
        settings = get_settings()
        
        # Проверяем, есть ли уже пользователь
        remnawave_uuid = bot_user.get("remnawave_user_uuid")
        
        if remnawave_uuid:
            # Обновляем существующего пользователя
            try:
                user_data = await api_client.get_user_by_uuid(remnawave_uuid)
                current_expire = user_data.get("response", {}).get("expireAt")
                # Убедимся, что нужные сквады применены
                try:
                    desired_external = settings.default_external_squad_uuid
                    desired_internal = settings.default_internal_squads or None
                    if desired_external or desired_internal:
                        await api_client.update_user(
                            remnawave_uuid,
                            externalSquadUuid=desired_external,
                            activeInternalSquads=desired_internal,
                        )
                        logger.info(
                            "Applied squads to existing user %s: external=%s internal=%s",
                            remnawave_uuid, desired_external, desired_internal
                        )
                except Exception as squad_exc:
                    logger.warning("Failed to apply squads to existing user %s: %s", remnawave_uuid, squad_exc)
                
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
                # Подготавливаем сквады
                internal_squads = settings.default_internal_squads if settings.default_internal_squads else None
                
                # Логируем, что передаем при создании пользователя
                logger.info(
                    "Creating payment user for %d: external_squad=%s, internal_squads=%s (type=%s, len=%s)",
                    user_id,
                    settings.default_external_squad_uuid,
                    internal_squads,
                    type(internal_squads).__name__ if internal_squads else "None",
                    len(internal_squads) if internal_squads else 0
                )
                
                user_data = await api_client.create_user(
                    username=username,
                    expire_at=expire_date,
                    telegram_id=user_id,
                    external_squad_uuid=settings.default_external_squad_uuid,
                    active_internal_squads=internal_squads,
                )
                user_info = user_data.get("response", user_data)
                user_uuid = user_info.get("uuid")
                BotUser.set_remnawave_uuid(user_id, user_uuid)
        else:
            # Создаем нового пользователя
            # Подготавливаем сквады
            internal_squads = settings.default_internal_squads if settings.default_internal_squads else None
            
            user_data = await api_client.create_user(
                username=username,
                expire_at=expire_date,
                telegram_id=user_id,
                external_squad_uuid=settings.default_external_squad_uuid,
                active_internal_squads=internal_squads,
            )
            user_info = user_data.get("response", user_data)
            user_uuid = user_info.get("uuid")
            BotUser.set_remnawave_uuid(user_id, user_uuid)
            # На всякий случай повторно применим сквады через update (если create их проигнорировал)
            if settings.default_external_squad_uuid or internal_squads:
                try:
                    update_payload = {}
                    if settings.default_external_squad_uuid:
                        update_payload["externalSquadUuid"] = settings.default_external_squad_uuid
                    if internal_squads:
                        update_payload["activeInternalSquads"] = internal_squads
                    
                    if update_payload:
                        await api_client.update_user(user_uuid, **update_payload)
                        logger.info(
                            "Applied squads on payment user %s: external=%s, internal=%s (type=%s, len=%s)",
                            user_uuid,
                            settings.default_external_squad_uuid,
                            internal_squads,
                            type(internal_squads).__name__ if internal_squads else "None",
                            len(internal_squads) if internal_squads else 0
                        )
                except Exception as squad_exc:
                    logger.warning("Failed to apply squads on payment user %s: %s", user_uuid, squad_exc)
        
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
        
        # Начисляем бонус рефереру (если есть)
        from src.services.referral_service import grant_referral_bonus
        try:
            await grant_referral_bonus(user_id)
        except Exception as ref_exc:
            logger.warning("Failed to grant referral bonus on payment: %s", ref_exc)
        
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

