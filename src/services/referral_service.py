"""Сервис реферальной программы."""
from datetime import datetime, timedelta

from src.config import get_settings
from src.database import BotUser, Referral
from src.services.api_client import api_client
from src.utils.logger import logger


async def grant_referral_bonus(referred_user_id: int) -> bool:
    """
    Начисляет бонусные дни рефереру за активацию реферала.
    
    Args:
        referred_user_id: ID пользователя, который активировал триал/оплатил подписку
    
    Returns:
        True если бонус начислен, False если реферера нет или уже начислено
    """
    settings = get_settings()
    bonus_days = settings.referral_bonus_days
    
    # Получаем информацию о пользователе
    referred_user = BotUser.get_or_create(referred_user_id, None)
    referrer_id = referred_user.get("referrer_id")
    
    if not referrer_id:
        logger.debug("User %s has no referrer", referred_user_id)
        return False
    
    # Проверяем, не начислен ли уже бонус
    # (бонус начисляется только один раз — при первой активации триала/оплате)
    referrals = Referral.get_referrals_count(referrer_id)
    if referrals == 0:
        logger.debug("No referral record found for referrer %s", referrer_id)
        return False
    
    # Получаем UUID реферера в Remnawave
    referrer_user = BotUser.get_or_create(referrer_id, None)
    referrer_uuid = referrer_user.get("remnawave_user_uuid")
    
    if not referrer_uuid:
        logger.warning(
            "Referrer %s has no Remnawave account, cannot grant bonus",
            referrer_id
        )
        return False
    
    try:
        # Получаем текущую подписку реферера
        user_data = await api_client.get_user_by_uuid(referrer_uuid)
        user_info = user_data.get("response", user_data)
        current_expire = user_info.get("expireAt")
        
        if not current_expire:
            logger.warning(
                "Referrer %s has no expireAt, cannot extend subscription",
                referrer_id
            )
            return False
        
        # Продлеваем подписку на bonus_days
        current_dt = datetime.fromisoformat(current_expire.replace("Z", "+00:00"))
        new_expire = current_dt + timedelta(days=bonus_days)
        new_expire_iso = new_expire.replace(microsecond=0).isoformat() + "Z"
        
        # Обновляем expireAt в Remnawave
        await api_client.update_user(referrer_uuid, expireAt=new_expire_iso)
        
        # Записываем в БД
        Referral.grant_bonus(referrer_id, referred_user_id, bonus_days)
        
        logger.info(
            "✅ Referral bonus granted: referrer=%s referred=%s bonus_days=%s new_expire=%s",
            referrer_id,
            referred_user_id,
            bonus_days,
            new_expire_iso
        )
        
        return True
        
    except Exception as e:
        logger.exception(
            "Failed to grant referral bonus for referrer %s: %s",
            referrer_id,
            e
        )
        return False

