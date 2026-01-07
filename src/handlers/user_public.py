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


def _get_months_text(months: int, locale: str) -> str:
    """Возвращает правильное склонение месяцев для русского языка."""
    if locale == "ru":
        if months == 1:
            return "1 месяц"
        elif months in (2, 3, 4):
            return f"{months} месяца"
        else:
            return f"{months} месяцев"
    else:
        # Для английского
        if months == 1:
            return "1 month"
        else:
            return f"{months} months"


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
            
            keyboard_buttons = []
            
            if subscription_url:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=_("user.get_config", locale=locale),
                        url=subscription_url
                    )
                ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=_("actions.back", locale=locale),
                    callback_data="user:menu"
                )
            ])
            
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
            logger.exception(f"Error getting subscription info for user {user_id}, uuid {remnawave_uuid}: {e}")
            error_msg = str(e)
            # Более информативное сообщение об ошибке
            if "404" in error_msg or "not found" in error_msg.lower():
                error_text = _("user.subscription_not_found", locale=locale)
            else:
                error_text = _("errors.generic", locale=locale) + f"\n\nОшибка: {error_msg[:100]}"
            
            await callback.message.edit_text(
                error_text,
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

        # Подготавливаем сквады
        internal_squads = settings.default_internal_squads if settings.default_internal_squads else None
        
        # Логируем, что передаем
        logger.info(
            "Creating trial user for %d: external_squad=%s, internal_squads=%s (type=%s, len=%s)",
            user_id,
            settings.default_external_squad_uuid,
            internal_squads,
            type(internal_squads).__name__,
            len(internal_squads) if internal_squads else 0
        )
        
        created = None
        username_try = base_username
        for attempt in range(3):
            try:
                created = await api_client.create_user(
                    username=username_try,
                    expire_at=expire_at,
                    telegram_id=user_id,
                    description="trial",
                    external_squad_uuid=settings.default_external_squad_uuid,
                    active_internal_squads=internal_squads,
                )
                logger.info("Trial user created successfully: %s", created.get("response", {}).get("uuid", "unknown"))
                break
            except Exception as e:
                logger.warning(f"Trial activation attempt {attempt+1} failed for user {user_id}: {e}")
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

        # На всякий случай дожимаем сквады через update (если create проигнорировал)
        if settings.default_external_squad_uuid or internal_squads:
            try:
                update_payload = {}
                if settings.default_external_squad_uuid:
                    update_payload["externalSquadUuid"] = settings.default_external_squad_uuid
                if internal_squads:
                    update_payload["activeInternalSquads"] = internal_squads
                
                if update_payload:
                    await api_client.update_user(user_uuid, **update_payload)
                    logger.info(
                        "Applied squads on trial user %s: external=%s, internal=%s",
                        user_uuid,
                        settings.default_external_squad_uuid,
                        internal_squads
                    )
            except Exception as squad_exc:
                logger.warning("Failed to apply squads on trial user %s: %s", user_uuid, squad_exc)

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


# Обработчик промокода убран из главного меню - теперь промокод вводится при оплате


@router.callback_query(F.data.startswith("promo_input:"))
async def cb_promo_input(callback: CallbackQuery) -> None:
    """Запрашивает ввод промокода для выбранного периода."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    subscription_months = int(callback.data.split(":")[1])
    
    # Сохраняем состояние ожидания промокода
    from src.handlers.state import PENDING_INPUT
    PENDING_INPUT[user_id] = f"promo_for_buy:{subscription_months}"
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        await callback.message.edit_text(
            _("payment.enter_promo_code_text").format(months_text=_get_months_text(subscription_months, locale)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=_("actions.cancel"),
                    callback_data=f"buy:{subscription_months}"
                )
            ]])
        )


@router.message(F.text.regexp(r'^[A-Za-z0-9]{3,20}$'))
async def handle_promo_code(message: Message) -> None:
    """Обработка введенного промокода в процессе оплаты."""
    from src.handlers.state import PENDING_INPUT
    from src.utils.auth import is_admin
    
    user_id = message.from_user.id
    if is_admin(user_id):
        return
    
    # Проверяем, ожидается ли ввод промокода для оплаты
    if user_id not in PENDING_INPUT:
        return
    
    pending = PENDING_INPUT[user_id]
    if not pending.startswith("promo_for_buy:"):
        return
    
    subscription_months = int(pending.split(":")[1])
    del PENDING_INPUT[user_id]
    
    user = BotUser.get_or_create(user_id, message.from_user.username)
    locale = user.get("language", "ru")
    promo_code = message.text.upper()
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        can_use, error = PromoCode.can_use(promo_code)
        
        if not can_use:
            await message.answer(
                error or _("user.promo_invalid"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back"),
                        callback_data=f"buy:{subscription_months}"
                    )
                ]])
            )
            return
        
        # Промокод валиден - применяем его и создаем invoice
        from src.services.payment_service import create_subscription_invoice
        
        try:
            invoice_link = await create_subscription_invoice(
                bot=message.bot,
                user_id=user_id,
                subscription_months=subscription_months,
                promo_code=promo_code
            )
            
            promo = PromoCode.get(promo_code)
            promo_text = ""
            if promo:
                if promo.get("discount_percent"):
                    promo_text = f"\n\n🎫 {_('user.promo_applied')}: {promo['discount_percent']}% {_('user.promo_discount')}"
                elif promo.get("bonus_days"):
                    promo_text = f"\n\n🎫 {_('user.promo_applied')}: +{promo['bonus_days']} {_('user.promo_bonus_days')}"
            
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
            
            await message.answer(
                _("payment.invoice_created") + promo_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        except Exception as e:
            logger.exception("Error creating invoice with promo code")
            await message.answer(
                _("payment.error_creating_invoice"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_("actions.back"),
                        callback_data=f"buy:{subscription_months}"
                    )
                ]])
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
        # Получаем актуальные цены из настроек
        from src.config import get_settings
        settings = get_settings()
        
        # Клавиатура с вариантами подписки и ценами
        buttons = [
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_1month").format(stars=settings.subscription_stars_1month),
                    callback_data="buy:1"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_3months").format(stars=settings.subscription_stars_3months),
                    callback_data="buy:3"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_6months").format(stars=settings.subscription_stars_6months),
                    callback_data="buy:6"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_12months").format(stars=settings.subscription_stars_12months),
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
    """Обрабатывает покупку подписки - показывает ввод промокода или создает invoice."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    try:
        parts = callback.data.split(":")
        subscription_months = int(parts[1])
        action = parts[2] if len(parts) > 2 else None
        
        # Если action = "skip", пропускаем промокод и сразу создаем invoice
        if action == "skip":
            from src.services.payment_service import create_subscription_invoice
            
            invoice_link = await create_subscription_invoice(
                bot=callback.message.bot,
                user_id=user_id,
                subscription_months=subscription_months,
                promo_code=None
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
                
                await callback.message.edit_text(
                    _("payment.invoice_created"),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
        # Если есть промокод в callback, применяем его
        elif action and action != "skip":
            promo_code = action.upper()
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
                
                promo = PromoCode.get(promo_code)
                promo_text = ""
                if promo:
                    if promo.get("discount_percent"):
                        promo_text = f"\n\n🎫 {_('user.promo_applied')}: {promo['discount_percent']}% {_('user.promo_discount')}"
                    elif promo.get("bonus_days"):
                        promo_text = f"\n\n🎫 {_('user.promo_applied')}: +{promo['bonus_days']} {_('user.promo_bonus_days')}"
                
                await callback.message.edit_text(
                    _("payment.invoice_created") + promo_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
        else:
            # Показываем экран ввода промокода
            i18n = get_i18n()
            with i18n.use_locale(locale):
                from src.config import get_settings
                settings = get_settings()
                
                # Получаем цену для выбранного периода
                prices = {
                    1: settings.subscription_stars_1month,
                    3: settings.subscription_stars_3months,
                    6: settings.subscription_stars_6months,
                    12: settings.subscription_stars_12months,
                }
                stars_price = prices.get(subscription_months, 0)
                
                buttons = [
                    [
                        InlineKeyboardButton(
                            text=_("payment.enter_promo_code"),
                            callback_data=f"promo_input:{subscription_months}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=_("payment.skip_promo_code"),
                            callback_data=f"buy:{subscription_months}:skip"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=_("actions.back"),
                            callback_data="user:buy"
                        )
                    ]
                ]
                
                await callback.message.edit_text(
                    _("payment.promo_code_prompt").format(
                        months_text=_get_months_text(subscription_months, locale),
                        stars=stars_price
                    ),
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

