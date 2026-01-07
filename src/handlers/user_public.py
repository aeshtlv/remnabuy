"""Обработчики для публичных пользователей (не админов)."""
from datetime import datetime, timedelta
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _

from src.database import BotUser, PromoCode, Referral, Payment
from src.services.api_client import NotFoundError, api_client
from src.utils.i18n import get_i18n
from src.utils.logger import logger

router = Router(name="user_public")


def _get_user_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню пользователя."""
    from src.utils.auth import is_admin
    buttons = [
        [
            InlineKeyboardButton(
                text=_("user_menu.subscription"),
                callback_data="user:subscription"
            )
        ],
        [
            InlineKeyboardButton(
                text=_("user_menu.buy_subscription"),
                callback_data="user:buy"
            )
        ],
        [
            InlineKeyboardButton(
                text=_("user_menu.trial"),
                callback_data="user:trial"
            )
        ],
        [
            InlineKeyboardButton(
                text=_("user_menu.promo_code"),
                callback_data="user:promo"
            )
        ],
        [
            InlineKeyboardButton(
                text=_("user_menu.referral"),
                callback_data="user:referral"
            )
        ],
        [
            InlineKeyboardButton(
                text=_("user_menu.language"),
                callback_data="user:language"
            )
        ]
    ]
    if is_admin(user_id):
        buttons.append([
            InlineKeyboardButton(
                text=_("user_menu.admin_panel"),
                callback_data="admin:panel",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка."""
    buttons = [
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start для всех пользователей."""
    user_id = message.from_user.id
    username = message.from_user.username

    # Получаем или создаем пользователя
    user = BotUser.get_or_create(user_id, username)
    locale = user.get("language", "ru")
    
    # Устанавливаем локализацию
    i18n = get_i18n()
    with i18n.use_locale(locale):
        # Проверяем, есть ли реферальный код
        args = message.text.split()[1:] if message.text and len(message.text.split()) > 1 else []
        
        if args:
            try:
                referrer_id = int(args[0])
                if referrer_id != user_id:
                    BotUser.set_referrer(user_id, referrer_id)
                    Referral.create(referrer_id, user_id)
                    welcome_text = _("user.welcome_with_referral")
            except (ValueError, IndexError):
                welcome_text = _("user.welcome")
        else:
            welcome_text = _("user.welcome")
        
        await message.answer(
            welcome_text,
            reply_markup=_get_user_menu_keyboard(user_id)
        )


@router.callback_query(F.data == "admin:panel")
async def cb_admin_panel(callback: CallbackQuery) -> None:
    """Открывает админ-панель (только для админов)."""
    from src.utils.auth import is_admin
    from src.handlers.navigation import _fetch_main_menu_text
    from src.keyboards.main_menu import main_menu_keyboard

    await callback.answer()
    if not is_admin(callback.from_user.id):
        # Защита на всякий случай (middleware тоже блокирует)
        await callback.answer(_("errors.unauthorized"), show_alert=True)
        return

    menu_text = await _fetch_main_menu_text()
    await callback.message.edit_text(menu_text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "user:menu")
async def cb_user_menu(callback: CallbackQuery) -> None:
    """Показывает главное меню пользователя."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        await callback.message.edit_text(
            _("user_menu.title"),
            reply_markup=_get_user_menu_keyboard(user_id)
        )


@router.callback_query(F.data == "user:language")
async def cb_language(callback: CallbackQuery) -> None:
    """Обработчик выбора языка."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        await callback.message.edit_text(
            _("user.choose_language"),
            reply_markup=_get_language_keyboard()
        )


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(callback: CallbackQuery) -> None:
    """Устанавливает язык пользователя."""
    await callback.answer()
    language = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    BotUser.update_language(user_id, language)
    
    i18n = get_i18n()
    with i18n.use_locale(language):
        await callback.message.edit_text(
            _("user.language_changed"),
            reply_markup=_get_user_menu_keyboard(user_id)
        )


@router.callback_query(F.data == "user:subscription")
async def cb_subscription(callback: CallbackQuery) -> None:
    """Показывает информацию о подписке пользователя."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        remnawave_uuid = user.get("remnawave_user_uuid")
        
        if not remnawave_uuid:
            await callback.message.edit_text(
                _("user.no_subscription"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back", locale=locale),
                        callback_data="user:menu"
                    )
                ]])
            )
            return
        
        try:
            # Получаем информацию о пользователе из Remnawave
            user_data = await api_client.get_user_by_uuid(remnawave_uuid)
            info = user_data.get("response", user_data)
            
            # Получаем подписку
            short_uuid = info.get("shortUuid")
            if short_uuid:
                sub_info = await api_client.get_subscription_info(short_uuid)
                sub_data = sub_info.get("response", sub_info)
                subscription_url = sub_data.get("subscriptionUrl", "")
            else:
                subscription_url = ""
            
            # Формируем текст
            status = info.get("status", "UNKNOWN")
            expire_at = info.get("expireAt")
            traffic_used = info.get("trafficUsed", 0)
            traffic_limit = info.get("trafficLimit", 0)
            
            status_text = {
                "ACTIVE": _("user.status_active", locale=locale),
                "DISABLED": _("user.status_disabled", locale=locale),
                "LIMITED": _("user.status_limited", locale=locale),
                "EXPIRED": _("user.status_expired", locale=locale),
            }.get(status, status)
            
            expire_text = ""
            if expire_at:
                try:
                    expire_dt = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
                    expire_text = expire_dt.strftime("%d.%m.%Y %H:%M")
                except:
                    expire_text = expire_at
            
            from src.utils.formatters import format_bytes
            traffic_text = f"{format_bytes(traffic_used)} / {format_bytes(traffic_limit)}"
            
            text = _("user.subscription_info", locale=locale).format(
                status=status_text,
                expire=expire_text or _("user.no_expire", locale=locale),
                traffic=traffic_text,
                url=subscription_url or _("user.no_url", locale=locale)
            )
            
            keyboard_buttons = [[
                InlineKeyboardButton(
                    text=_("actions.back", locale=locale),
                    callback_data="user:menu"
                )
            ]]
            
            if subscription_url:
                keyboard_buttons.insert(0, [[
                    InlineKeyboardButton(
                        text=_("user.get_config", locale=locale),
                        url=subscription_url
                    )
                ]])
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
                parse_mode="HTML"
            )
        except NotFoundError:
            await callback.message.edit_text(
                _("user.subscription_not_found", locale=locale),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back", locale=locale),
                        callback_data="user:menu"
                    )
                ]])
            )
        except Exception as e:
            logger.exception("Error getting subscription info")
            await callback.message.edit_text(
                _("errors.generic", locale=locale),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back", locale=locale),
                        callback_data="user:menu"
                    )
                ]])
            )


@router.callback_query(F.data == "user:trial")
async def cb_trial(callback: CallbackQuery) -> None:
    """Обработчик пробной подписки."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        if user.get("trial_used"):
            await callback.message.edit_text(
                _("user.trial_already_used"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back"),
                        callback_data="user:menu"
                    )
                ]])
            )
            return
        
        # Пользователь сам активирует триал кнопкой
        await callback.message.edit_text(
            _("user.trial_info"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=_("user.activate_trial"),
                    callback_data="user:trial:activate"
                )
            ], [
                InlineKeyboardButton(
                    text=_("actions.back"),
                    callback_data="user:menu"
                )
            ]])
        )


@router.callback_query(F.data == "user:trial:activate")
async def cb_trial_activate(callback: CallbackQuery) -> None:
    """Активация пробной подписки (создаёт пользователя в Remnawave)."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        if user.get("trial_used") or user.get("remnawave_user_uuid"):
            await callback.message.edit_text(
                _("user.trial_already_used"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=_("actions.back"), callback_data="user:menu")
                ]]),
            )
            return

        from src.config import get_settings
        settings = get_settings()
        trial_days = max(1, int(settings.trial_days))

        # Генерим безопасный username для Remnawave
        base_username = (callback.from_user.username or "").lstrip("@")
        if not base_username:
            base_username = f"tg{user_id}"

        expire_at = (datetime.utcnow() + timedelta(days=trial_days)).replace(microsecond=0).isoformat() + "Z"

        created = None
        username_try = base_username
        for attempt in range(3):
            try:
                created = await api_client.create_user(
                    username=username_try,
                    expire_at=expire_at,
                    telegram_id=user_id,
                    description="trial",
                )
                break
            except Exception:
                # возможно конфликт username — добавим суффикс
                username_try = f"{base_username}_{attempt+1}"
                continue

        if not created:
            await callback.message.edit_text(
                _("user.trial_activation_failed"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=_("actions.back"), callback_data="user:menu")
                ]]),
            )
            return

        info = created.get("response", created)
        user_uuid = info.get("uuid")
        if user_uuid:
            BotUser.set_remnawave_uuid(user_id, user_uuid)
        BotUser.set_trial_used(user_id)

        # Получаем ссылку на подписку
        subscription_url = ""
        short_uuid = info.get("shortUuid")
        if short_uuid:
            try:
                sub_info = await api_client.get_subscription_info(short_uuid)
                sub_data = sub_info.get("response", sub_info)
                subscription_url = sub_data.get("subscriptionUrl", "") or ""
            except Exception:
                subscription_url = ""

        buttons: list[list[InlineKeyboardButton]] = []
        if subscription_url:
            buttons.append([InlineKeyboardButton(text=_("user.get_config"), url=subscription_url)])
        buttons.append([InlineKeyboardButton(text=_("actions.back"), callback_data="user:menu")])

        await callback.message.edit_text(
            _("user.trial_activated").format(days=trial_days),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


@router.callback_query(F.data == "user:promo")
async def cb_promo(callback: CallbackQuery) -> None:
    """Обработчик промокода."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        await callback.message.edit_text(
            _("user.enter_promo_code", locale=locale),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=_("actions.back", locale=locale),
                    callback_data="user:menu"
                )
            ]])
        )


@router.message(F.text.regexp(r'^[A-Za-z0-9]{3,20}$'))
async def handle_promo_code(message: Message) -> None:
    """Обработка введенного промокода."""
    from src.handlers.state import PENDING_INPUT
    from src.utils.auth import is_admin
    
    # Пропускаем, если это админ или есть ожидаемый ввод
    user_id = message.from_user.id
    if is_admin(user_id) or user_id in PENDING_INPUT:
        return
    
    user = BotUser.get_or_create(user_id, message.from_user.username)
    locale = user.get("language", "ru")
    
    promo_code = message.text.upper()
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        can_use, error = PromoCode.can_use(promo_code)
        
        if not can_use:
            await message.answer(
                error or _("user.promo_invalid", locale=locale),
                reply_markup=_get_user_menu_keyboard(locale)
            )
            return
        
        # Проверяем промокод (не используем, просто показываем информацию)
        promo = PromoCode.get(promo_code)
        result_text = _("user.promo_valid", locale=locale)
        
        if promo.get("discount_percent"):
            result_text += f"\n💯 {_('user.promo_discount', locale=locale)}: {promo['discount_percent']}%"
        if promo.get("bonus_days"):
            result_text += f"\n🎁 {_('user.promo_bonus_days', locale=locale)}: {promo['bonus_days']}"
        
        # Предлагаем использовать промокод при покупке
        buttons = [
            [
                InlineKeyboardButton(
                    text=_("payment.buy_with_promo", locale=locale),
                    callback_data=f"promo_apply:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("actions.back", locale=locale),
                    callback_data="user:menu"
                )
            ]
        ]
        
        await message.answer(
            result_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@router.callback_query(F.data.startswith("promo_apply:"))
async def cb_apply_promo(callback: CallbackQuery) -> None:
    """Применяет промокод и показывает меню покупки."""
    await callback.answer()
    promo_code = callback.data.split(":")[1]
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        # Показываем меню покупки с примененным промокодом
        buttons = [
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_1month", locale=locale),
                    callback_data=f"buy:1:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_3months", locale=locale),
                    callback_data=f"buy:3:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_6months", locale=locale),
                    callback_data=f"buy:6:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_12months", locale=locale),
                    callback_data=f"buy:12:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("actions.back", locale=locale),
                    callback_data="user:buy"
                )
            ]
        ]
        
        promo = PromoCode.get(promo_code)
        promo_text = ""
        if promo:
            if promo.get("discount_percent"):
                promo_text = f"\n\n🎫 {_('user.promo_applied', locale=locale)}: {promo['discount_percent']}% {_('user.promo_discount', locale=locale)}"
            elif promo.get("bonus_days"):
                promo_text = f"\n\n🎫 {_('user.promo_applied', locale=locale)}: +{promo['bonus_days']} {_('user.promo_bonus_days', locale=locale)}"
        
        await callback.message.edit_text(
            _("payment.choose_subscription", locale=locale) + promo_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@router.callback_query(F.data == "user:referral")
async def cb_referral(callback: CallbackQuery) -> None:
    """Показывает реферальную информацию."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        referrals_count = Referral.get_referrals_count(user_id)
        bonus_days = Referral.get_bonus_days(user_id)
        
        # Создаем реферальную ссылку
        try:
            bot_username = (await callback.message.bot.get_me()).username or "your_bot"
        except:
            bot_username = "your_bot"
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        text = _("user.referral_info", locale=locale).format(
            link=referral_link,
            count=referrals_count,
            bonus_days=bonus_days
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=_("actions.back", locale=locale),
                    callback_data="user:menu"
                )
            ]])
        )


@router.callback_query(F.data == "user:buy")
async def cb_buy(callback: CallbackQuery) -> None:
    """Обработчик покупки подписки."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        # Клавиатура с вариантами подписки
        buttons = [
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_1month"),
                    callback_data="buy:1"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_3months"),
                    callback_data="buy:3"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_6months"),
                    callback_data="buy:6"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_12months"),
                    callback_data="buy:12"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("actions.back"),
                    callback_data="user:menu"
                )
            ]
        ]
        
        await callback.message.edit_text(
            _("payment.choose_subscription"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_subscription(callback: CallbackQuery) -> None:
    """Создает invoice для покупки подписки."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    try:
        parts = callback.data.split(":")
        subscription_months = int(parts[1])
        promo_code = parts[2] if len(parts) > 2 else None
        
        from src.services.payment_service import create_subscription_invoice
        
        invoice_link = await create_subscription_invoice(
            bot=callback.message.bot,
            user_id=user_id,
            subscription_months=subscription_months,
            promo_code=promo_code
        )
        
        i18n = get_i18n()
        with i18n.use_locale(locale):
            buttons = [
                [
                    InlineKeyboardButton(
                        text=_("payment.pay_button"),
                        url=invoice_link
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("actions.back"),
                        callback_data="user:buy"
                    )
                ]
            ]
            
            text = _("payment.invoice_created")
            if promo_code:
                text += f"\n\n🎫 {_('user.promo_applied')}"
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except ValueError as e:
        logger.exception("Invalid subscription months")
        i18n = get_i18n()
        with i18n.use_locale(locale):
            await callback.message.edit_text(
                _("payment.error_creating_invoice", locale=locale),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back", locale=locale),
                        callback_data="user:buy"
                    )
                ]])
            )
    except Exception as e:
        logger.exception("Failed to create invoice")
        i18n = get_i18n()
        with i18n.use_locale(locale):
            await callback.message.edit_text(
                _("payment.error_creating_invoice"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back"),
                        callback_data="user:buy"
                    )
                ]])
            )

