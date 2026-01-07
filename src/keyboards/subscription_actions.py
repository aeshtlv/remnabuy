from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def subscription_keyboard(subscription_url: str | None) -> InlineKeyboardMarkup:
    buttons = [nav_row(NavTarget.MAIN_MENU)]
    if subscription_url:
        buttons.insert(0, [InlineKeyboardButton(text=_("sub.open_url"), url=subscription_url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
