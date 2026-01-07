from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.keyboards.navigation import NavTarget, nav_row


def template_actions_keyboard(template_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("template.update_json"), callback_data=f"template:{template_uuid}:update_json"
                )
            ],
            [InlineKeyboardButton(text=_("template.delete"), callback_data=f"template:{template_uuid}:delete")],
            nav_row(NavTarget.TEMPLATES_MENU),
        ]
    )
