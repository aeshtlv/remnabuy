"""Клавиатуры для оплаты через YooKassa."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _


def get_yookassa_payment_keyboard(
    payment_id: str,
    confirmation_url: str | None = None
) -> InlineKeyboardMarkup:
    """Создает клавиатуру для оплаты через YooKassa.
    
    Args:
        payment_id: ID платежа в YooKassa
        confirmation_url: URL для перехода к оплате
    
    Returns:
        InlineKeyboardMarkup с кнопками оплаты
    """
    buttons = []
    
    # Кнопка "Перейти к оплате"
    if confirmation_url:
        buttons.append([InlineKeyboardButton(
            text=_("payment.yookassa.go_to_payment"),
            url=confirmation_url
        )])
    
    # Кнопка "Проверить статус"
    buttons.append([InlineKeyboardButton(
        text=_("payment.yookassa.check_status"),
        callback_data=f"yookassa:check_status:{payment_id}"
    )])
    
    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(
        text=_("user_menu.back"),
        callback_data="user:menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

