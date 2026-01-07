from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def bulk_nodes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("bulk_nodes.profile"), callback_data="bulk:nodes:profile")],
            nav_row(NavTarget.BULK_MENU),
        ]
    )
