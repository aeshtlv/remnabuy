"""Сервис для работы с платежами через YooKassa."""
import io
from typing import Optional

import qrcode
from yookassa import Configuration, Payment

from src.config import get_settings
from src.utils.logger import logger


def init_yookassa():
    """Инициализирует YooKassa с настройками из конфига."""
    settings = get_settings()
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        logger.warning("YooKassa credentials not configured")
        return False
    
    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key
    return True


async def create_payment(
    amount: float,
    description: str,
    user_id: int,
    subscription_months: int,
    return_url: Optional[str] = None,
    metadata: Optional[dict] = None
) -> dict:
    """Создает платеж в YooKassa.
    
    Args:
        amount: Сумма платежа в рублях
        description: Описание платежа
        user_id: ID пользователя Telegram
        subscription_months: Количество месяцев подписки
        return_url: URL для возврата после оплаты (опционально)
        metadata: Дополнительные метаданные (опционально)
    
    Returns:
        Словарь с данными платежа (id, confirmation_url, qr_code)
    """
    if not init_yookassa():
        raise ValueError("YooKassa not configured")
    
    settings = get_settings()
    
    # Формируем метаданные
    payment_metadata = {
        "user_id": str(user_id),
        "subscription_months": str(subscription_months),
        **(metadata or {})
    }
    
    # Создаем платеж
    payment_data = {
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "qr",
            "return_url": return_url or settings.yookassa_webhook_url or "https://t.me/your_bot"
        },
        "capture": True,
        "description": description,
        "metadata": payment_metadata
    }
    
    try:
        payment = Payment.create(payment_data)
        payment_id = payment.id
        confirmation = payment.confirmation
        
        # Получаем confirmation_url
        confirmation_url = None
        if confirmation:
            if hasattr(confirmation, 'confirmation_url'):
                confirmation_url = confirmation.confirmation_url
            elif hasattr(confirmation, 'confirmation_data') and hasattr(confirmation.confirmation_data, 'qr_data'):
                # Если есть QR-данные напрямую
                qr_data = confirmation.confirmation_data.qr_data
                confirmation_url = qr_data if qr_data else None
        
        # Генерируем QR-код из URL, если есть
        qr_code_data = None
        if confirmation_url:
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(confirmation_url)
                qr.make(fit=True)
                
                # Создаем изображение QR-кода
                img = qr.make_image(fill_color="black", back_color="white")
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                qr_code_data = img_buffer.getvalue()
            except Exception as e:
                logger.warning(f"Failed to generate QR code: {e}")
        
        logger.info(f"YooKassa payment created: {payment_id} for user {user_id}, amount {amount} RUB")
        
        return {
            "id": payment_id,
            "status": payment.status,
            "confirmation_url": confirmation_url,
            "qr_code": qr_code_data,
            "amount": amount,
            "description": description
        }
    except Exception as e:
        logger.exception(f"Failed to create YooKassa payment: {e}")
        raise


async def get_payment_status(payment_id: str) -> dict:
    """Получает статус платежа в YooKassa.
    
    Args:
        payment_id: ID платежа в YooKassa
    
    Returns:
        Словарь с данными платежа
    """
    if not init_yookassa():
        raise ValueError("YooKassa not configured")
    
    try:
        payment = Payment.find_one(payment_id)
        return {
            "id": payment.id,
            "status": payment.status,
            "amount": float(payment.amount.value),
            "paid": payment.paid,
            "cancelled": payment.cancelled,
            "metadata": payment.metadata
        }
    except Exception as e:
        logger.exception(f"Failed to get YooKassa payment status: {e}")
        raise

