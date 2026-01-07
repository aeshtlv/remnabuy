from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def snippet_actions_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("snippet.delete"), callback_data=f"snippet:{name}:delete")],
            nav_row(NavTarget.SNIPPETS_MENU),
        ]
    )
