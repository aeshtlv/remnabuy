from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def config_actions_keyboard(profile_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[nav_row(NavTarget.CONFIGS_MENU)])
