from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def host_edit_keyboard(host_uuid: str, back_to: str = NavTarget.HOSTS_MENU) -> InlineKeyboardMarkup:
    """Клавиатура для редактирования хоста."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("host.edit_remark"), callback_data=f"hef:remark::{host_uuid}"),
                InlineKeyboardButton(text=_("host.edit_address"), callback_data=f"hef:address::{host_uuid}"),
            ],
            [
                InlineKeyboardButton(text=_("host.edit_port"), callback_data=f"hef:port::{host_uuid}"),
                InlineKeyboardButton(text=_("host.edit_tag"), callback_data=f"hef:tag::{host_uuid}"),
            ],
            [
                InlineKeyboardButton(text=_("host.edit_inbound"), callback_data=f"hef:inbound::{host_uuid}"),
            ],
            nav_row(back_to),
        ]
    )

