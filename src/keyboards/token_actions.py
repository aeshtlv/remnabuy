from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def token_actions_keyboard(token_uuid: str, back_to: str = NavTarget.TOKENS_MENU) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("token.delete"), callback_data=f"token:{token_uuid}:delete")],
            nav_row(back_to),
        ]
    )
