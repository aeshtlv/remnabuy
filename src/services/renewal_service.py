"""Сервис для автопродления и напоминаний о истекающих подписках."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.config import get_settings
from src.database import BotUser
from src.services.api_client import NotFoundError, api_client
from src.services.payment_service import create_subscription_invoice
from src.utils.i18n import get_i18n
from src.utils.logger import logger


async def check_expiring_subscriptions(bot: Bot) -> None:
    """
    Проверяет пользователей с истекающими подписками и отправляет напоминания.
    
    Логика:
    - За 3-5 дней до окончания: напоминание с кнопкой "Продлить доступ"
    - За 1 день: повторное напоминание
    - После окончания: сообщение о приостановке доступа с кнопкой "Возобновить доступ"
    """
    try:
        # Получаем всех пользователей с включенным автопродлением
        users_with_auto_renewal = BotUser.get_users_with_auto_renewal()
        
        if not users_with_auto_renewal:
            logger.debug("No users with auto renewal enabled")
            return
        
        logger.info("Checking %d users with auto renewal for expiring subscriptions", len(users_with_auto_renewal))
        
        now = datetime.now()
        for user_data in users_with_auto_renewal:
            user_id = user_data.get("telegram_id")
            remnawave_uuid = user_data.get("remnawave_user_uuid")
            last_notification = user_data.get("last_renewal_notification")
            
            if not remnawave_uuid:
                continue
            
            try:
                # Получаем информацию о подписке пользователя из Remnawave
                user_info_response = await api_client.get_user_by_uuid(remnawave_uuid)
                user_info = user_info_response.get("response", user_info_response)
                expire_at_str = user_info.get("expireAt")
                status = user_info.get("status", "UNKNOWN")
                
                if not expire_at_str:
                    continue
                
                # Парсим дату истечения
                try:
                    expire_at = datetime.fromisoformat(expire_at_str.replace("Z", "+00:00"))
                    # Приводим к UTC и убираем timezone для сравнения с naive datetime
                    if expire_at.tzinfo:
                        expire_at = expire_at.replace(tzinfo=None)
                except (ValueError, AttributeError) as e:
                    logger.warning("Failed to parse expire_at for user %s: %s", user_id, e)
                    continue
                
                # Вычисляем дни до окончания
                days_until_expiry = (expire_at - now).days
                
                # Проверяем последнее напоминание
                last_notif_dt = None
                if last_notification:
                    try:
                        last_notif_dt = datetime.fromisoformat(last_notification)
                    except (ValueError, TypeError):
                        pass
                
                # Определяем, нужно ли отправлять напоминание
                should_send_reminder = False
                reminder_type = None
                
                if status == "EXPIRED" or expire_at < now:
                    # Подписка уже истекла - отправляем уведомление о приостановке
                    if not last_notif_dt or (now - last_notif_dt).days >= 1:
                        should_send_reminder = True
                        reminder_type = "expired"
                elif 1 <= days_until_expiry <= 5:
                    # За 1-5 дней до окончания
                    if not last_notif_dt:
                        # Первое напоминание
                        should_send_reminder = True
                        reminder_type = "expiring_soon"
                    elif days_until_expiry == 1 and (now - last_notif_dt).days >= 1:
                        # Повторное напоминание за 1 день
                        should_send_reminder = True
                        reminder_type = "expiring_tomorrow"
                
                if should_send_reminder:
                    await send_renewal_reminder(
                        bot=bot,
                        user_id=user_id,
                        days_until_expiry=days_until_expiry,
                        reminder_type=reminder_type,
                        expire_at=expire_at
                    )
                    # Обновляем время последнего напоминания
                    BotUser.update_last_renewal_notification(user_id)
            
            except NotFoundError:
                logger.debug("User %s not found in Remnawave (uuid: %s)", user_id, remnawave_uuid)
                continue
            except Exception as e:
                logger.exception("Error checking subscription for user %s: %s", user_id, e)
                continue
    
    except Exception as e:
        logger.exception("Error in check_expiring_subscriptions: %s", e)


async def send_renewal_reminder(
    bot: Bot,
    user_id: int,
    days_until_expiry: int,
    reminder_type: str,
    expire_at: datetime
) -> None:
    """
    Отправляет напоминание об истекающей подписке.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя Telegram
        days_until_expiry: Количество дней до окончания (отрицательное, если уже истекла)
        reminder_type: Тип напоминания ("expiring_soon", "expiring_tomorrow", "expired")
        expire_at: Дата истечения подписки
    """
    try:
        user = BotUser.get_or_create(user_id, None)
        locale = user.get("language", "ru")
        
        i18n = get_i18n()
        with i18n.use_locale(locale):
            if reminder_type == "expired":
                # Подписка истекла
                text = _("renewal.access_suspended")
                buttons = [
                    [
                        InlineKeyboardButton(
                            text=_("renewal.resume_access_button"),
                            callback_data="user:resume"
                        )
                    ]
                ]
            elif reminder_type == "expiring_tomorrow":
                # Завтра истекает
                text = _("renewal.expiring_tomorrow")
                buttons = [
                    [
                        InlineKeyboardButton(
                            text=_("renewal.renew_button"),
                            callback_data="user:renew"
                        )
                    ]
                ]
            else:
                # За 3-5 дней до окончания
                text = _("renewal.expiring_soon").format(days=days_until_expiry)
                buttons = [
                    [
                        InlineKeyboardButton(
                            text=_("renewal.renew_button"),
                            callback_data="user:renew"
                        )
                    ]
                ]
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                    parse_mode="HTML"
                )
                logger.info(
                    "Sent renewal reminder to user %s: type=%s days_until_expiry=%s",
                    user_id, reminder_type, days_until_expiry
                )
            except Exception as e:
                logger.warning("Failed to send renewal reminder to user %s: %s", user_id, e)
    
    except Exception as e:
        logger.exception("Error in send_renewal_reminder for user %s: %s", user_id, e)


async def start_renewal_checker(bot: Bot, interval_hours: int = 6) -> None:
    """
    Запускает фоновую задачу для периодической проверки истекающих подписок.
    
    Args:
        bot: Экземпляр бота
        interval_hours: Интервал проверки в часах (по умолчанию 6 часов)
    """
    logger.info("Starting renewal checker (interval: %d hours)", interval_hours)
    
    while True:
        try:
            await check_expiring_subscriptions(bot)
        except Exception as e:
            logger.exception("Error in renewal checker loop: %s", e)
        
        # Ждем перед следующей проверкой
        await asyncio.sleep(interval_hours * 3600)

