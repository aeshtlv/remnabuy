from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def bulk_hosts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("bulk_hosts.template_enable_all"), callback_data="bulk:hosts:enable_all")],
            [InlineKeyboardButton(text=_("bulk_hosts.template_disable_all"), callback_data="bulk:hosts:disable_all")],
            [InlineKeyboardButton(text=_("bulk_hosts.template_delete_disabled"), callback_data="bulk:hosts:delete_disabled")],
            [InlineKeyboardButton(text=_("bulk_hosts.list"), callback_data="bulk:hosts:list")],
            nav_row(NavTarget.BULK_MENU),
        ]
    )
