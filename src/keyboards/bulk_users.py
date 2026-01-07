from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def bulk_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("bulk.template_delete_disabled"), callback_data="bulk:users:delete:DISABLED")],
            [InlineKeyboardButton(text=_("bulk.template_delete_expired"), callback_data="bulk:users:delete:EXPIRED")],
            [InlineKeyboardButton(text=_("bulk.template_extend_active"), callback_data="bulk:users:extend_active")],
            [InlineKeyboardButton(text=_("bulk.reset_all_traffic"), callback_data="bulk:users:reset")],
            [
                InlineKeyboardButton(text=_("bulk.extend_all_7"), callback_data="bulk:users:extend_all:7"),
                InlineKeyboardButton(text=_("bulk.extend_all_30"), callback_data="bulk:users:extend_all:30"),
            ],
            nav_row(NavTarget.BULK_MENU),
        ]
    )
