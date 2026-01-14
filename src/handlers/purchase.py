"""Простой процесс покупки подписки через YooKassa."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _
from aiogram.types import BufferedInputFile

from src.database import BotUser, PromoCode
from src.handlers.common import _edit_text_safe
from src.services.payment_service import create_yookassa_payment
from src.keyboards.yookassa_payment import get_yookassa_payment_keyboard
from src.utils.i18n import get_i18n
from src.utils.logger import logger
from src.handlers.state import PENDING_INPUT

router = Router(name="purchase")


@router.callback_query(F.data == "user:buy")
async def cb_buy(callback: CallbackQuery) -> None:
    """Показывает выбор тарифа подписки."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        from src.config import get_settings
        settings = get_settings()
        
        # Получаем цены в рублях
        rub_prices = {
            1: settings.subscription_rub_1month,
            3: settings.subscription_rub_3months,
            6: settings.subscription_rub_6months,
            12: settings.subscription_rub_12months,
        }
        
        # Убираем цены из кнопок - только название тарифа
        buttons = [
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_1month").split(" (")[0],
                    callback_data="purchase:1"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_3months").split(" (")[0],
                    callback_data="purchase:3"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_6months").split(" (")[0],
                    callback_data="purchase:6"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.subscription_12months").split(" (")[0],
                    callback_data="purchase:12"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("user_menu.back"),
                    callback_data="user:connect"
                )
            ]
        ]
        
        await _edit_text_safe(
            callback.message,
            _("payment.choose_subscription"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@router.callback_query(F.data.startswith("purchase:"))
async def cb_purchase_subscription(callback: CallbackQuery) -> None:
    """Обрабатывает выбор тарифа - показывает выбор способа оплаты."""
    await callback.answer()
    user_id = callback.from_user.id
    user = BotUser.get_or_create(user_id, callback.from_user.username)
    locale = user.get("language", "ru")
    
    try:
        parts = callback.data.split(":")
        subscription_months = int(parts[1])
        action = parts[2] if len(parts) > 2 else None
        
        i18n = get_i18n()
        with i18n.use_locale(locale):
            from src.config import get_settings
            settings = get_settings()
            
            rub_prices = {
                1: settings.subscription_rub_1month,
                3: settings.subscription_rub_3months,
                6: settings.subscription_rub_6months,
                12: settings.subscription_rub_12months,
            }
            price = rub_prices.get(subscription_months, 0)
            
            # Если выбран способ оплаты, создаем платеж
            if action in ("stars", "sbp", "card"):
                payment_method = action
                promo_code = parts[3] if len(parts) > 3 and parts[3] else None
                
                # Обработка Stars
                if payment_method == "stars":
                    from src.services.payment_service import create_subscription_invoice
                    
                    try:
                        invoice_link = await create_subscription_invoice(
                            bot=callback.message.bot,
                            user_id=user_id,
                            subscription_months=subscription_months,
                            promo_code=promo_code
                        )
                        
                        # Формируем текст с промокодом
                        promo_text = ""
                        if promo_code:
                            promo = PromoCode.get(promo_code)
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
                                    text=_("user_menu.back"),
                                    callback_data="user:buy"
                                )
                            ]
                        ]
                        
                        await _edit_text_safe(
                            callback.message,
                            _("payment.invoice_created") + promo_text,
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                        )
                    except Exception as e:
                        logger.exception(f"Error creating Stars invoice: {e}")
                        await _edit_text_safe(
                            callback.message,
                            _("payment.error_creating_invoice"),
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(
                                    text=_("user_menu.back"),
                                    callback_data="user:buy"
                                )
                            ]])
                        )
                    return
                
                # Обработка YooKassa (sbp, card)
                if action in ("sbp", "card"):
                
                try:
                    payment_data = await create_yookassa_payment(
                        bot=callback.message.bot,
                        user_id=user_id,
                        subscription_months=subscription_months,
                        promo_code=promo_code,
                        payment_method=payment_method
                    )
                    
                    payment_id = payment_data["payment_id"]
                    confirmation_url = payment_data.get("confirmation_url")
                    amount = payment_data.get("amount", 0)
                    qr_code = payment_data.get("qr_code")
                    
                    # Отправляем QR-код для СБП
                    if qr_code and payment_method == "sbp":
                        await callback.message.answer_photo(
                            BufferedInputFile(qr_code, filename="qr_code.png"),
                            caption=_("payment.yookassa.qr_code_sent")
                        )
                    
                    # Формируем текст с промокодом
                    promo_text = ""
                    if promo_code:
                        promo = PromoCode.get(promo_code)
                        if promo:
                            if promo.get("discount_percent"):
                                promo_text = f"\n\n🎫 {_('user.promo_applied')}: {promo['discount_percent']}% {_('user.promo_discount')}"
                            elif promo.get("bonus_days"):
                                promo_text = f"\n\n🎫 {_('user.promo_applied')}: +{promo['bonus_days']} {_('user.promo_bonus_days')}"
                    
                    text = _("payment.yookassa.payment_created").format(
                        amount=f"{amount:.0f}",
                        payment_id=payment_id[:16] + "..."
                    ) + promo_text
                    
                    keyboard = get_yookassa_payment_keyboard(
                        payment_id=payment_id,
                        confirmation_url=confirmation_url
                    )
                    
                    await _edit_text_safe(
                        callback.message,
                        text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except ValueError as e:
                    error_text = _("payment.error_creating_invoice")
                    if "not configured" in str(e).lower():
                        error_text += "\n\n⚠️ YooKassa не настроен. Проверьте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env"
                    await _edit_text_safe(
                        callback.message,
                        error_text,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text=_("user_menu.back"),
                                callback_data="user:buy"
                            )
                        ]])
                    )
                except Exception as e:
                    logger.exception(f"Error creating YooKassa payment: {e}")
                    await _edit_text_safe(
                        callback.message,
                        _("payment.error_creating_invoice"),
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text=_("user_menu.back"),
                                callback_data="user:buy"
                            )
                        ]])
                    )
                return
            
            # Если запрос промокода
            if action == "promo":
                PENDING_INPUT[user_id] = f"promo_for_purchase:{subscription_months}:all"
                
                locale_map = {
                    1: _("payment.subscription_1month").split(" (")[0],
                    3: _("payment.subscription_3months").split(" (")[0],
                    6: _("payment.subscription_6months").split(" (")[0],
                    12: _("payment.subscription_12months").split(" (")[0],
                }
                months_text = locale_map.get(subscription_months, f"{subscription_months} месяцев")
                
                await _edit_text_safe(
                    callback.message,
                    _("payment.enter_promo_code_text").format(months_text=months_text),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text=_("actions.cancel"),
                            callback_data=f"purchase:{subscription_months}"
                        )
                    ]])
                )
                return
            
            # Получаем цены в Stars
            stars_prices = {
                1: settings.subscription_stars_1month,
                3: settings.subscription_stars_3months,
                6: settings.subscription_stars_6months,
                12: settings.subscription_stars_12months,
            }
            stars_price = stars_prices.get(subscription_months, 0)
            
            # Показываем выбор способа оплаты
            buttons = [
                [
                    InlineKeyboardButton(
                        text=_("payment.payment_method_stars") + f" ({stars_price} ⭐)",
                        callback_data=f"purchase:{subscription_months}:stars"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("payment.payment_method_sbp") + f" ({price:.0f} ₽)",
                        callback_data=f"purchase:{subscription_months}:sbp"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("payment.payment_method_card") + f" ({price:.0f} ₽)",
                        callback_data=f"purchase:{subscription_months}:card"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("payment.enter_promo_code"),
                        callback_data=f"purchase:{subscription_months}:promo"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("user_menu.back"),
                        callback_data="user:buy"
                    )
                ]
            ]
            
            locale_map = {
                1: _("payment.subscription_1month").split(" (")[0],
                3: _("payment.subscription_3months").split(" (")[0],
                6: _("payment.subscription_6months").split(" (")[0],
                12: _("payment.subscription_12months").split(" (")[0],
            }
            months_text = locale_map.get(subscription_months, f"{subscription_months} месяцев")
            
            await _edit_text_safe(
                callback.message,
                _("payment.promo_code_prompt").format(
                    months_text=months_text,
                    stars=f"{price:.0f} ₽"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except Exception as e:
        logger.exception(f"Error in purchase handler: {e}")
        await callback.answer(_("payment.error_creating_invoice"), show_alert=True)


@router.message(F.text.regexp(r'^[A-Za-z0-9]{3,20}$'))
async def handle_promo_code_input(message: Message) -> None:
    """Обрабатывает введенный промокод."""
    from src.utils.auth import is_admin
    
    user_id = message.from_user.id
    if is_admin(user_id):
        return
    
    if user_id not in PENDING_INPUT:
        return
    
    pending = PENDING_INPUT[user_id]
    if not pending.startswith("promo_for_purchase:"):
        return
    
    parts = pending.split(":")
    subscription_months = int(parts[1])
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
                        text=_("user_menu.back"),
                        callback_data=f"purchase:{subscription_months}"
                    )
                ]])
            )
            return
        
        # Промокод валиден - показываем выбор способа оплаты с промокодом
        from src.config import get_settings
        settings = get_settings()
        
        # Получаем цены
        stars_prices = {
            1: settings.subscription_stars_1month,
            3: settings.subscription_stars_3months,
            6: settings.subscription_stars_6months,
            12: settings.subscription_stars_12months,
        }
        rub_prices = {
            1: settings.subscription_rub_1month,
            3: settings.subscription_rub_3months,
            6: settings.subscription_rub_6months,
            12: settings.subscription_rub_12months,
        }
        base_stars = stars_prices.get(subscription_months, 0)
        base_rub = rub_prices.get(subscription_months, 0)
        
        # Применяем скидку
        promo = PromoCode.get(promo_code)
        discount_percent = promo.get("discount_percent", 0) if promo else 0
        final_stars = int(base_stars * (1 - discount_percent / 100))
        final_rub = base_rub * (1 - discount_percent / 100)
        
        promo_text = ""
        if promo:
            if promo.get("discount_percent"):
                promo_text = f"\n\n🎫 {_('user.promo_applied')}: {promo['discount_percent']}% {_('user.promo_discount')}"
            elif promo.get("bonus_days"):
                promo_text = f"\n\n🎫 {_('user.promo_applied')}: +{promo['bonus_days']} {_('user.promo_bonus_days')}"
        
        buttons = [
            [
                InlineKeyboardButton(
                    text=_("payment.payment_method_stars") + f" ({final_stars} ⭐)",
                    callback_data=f"purchase:{subscription_months}:stars:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.payment_method_sbp") + f" ({final_rub:.0f} ₽)",
                    callback_data=f"purchase:{subscription_months}:sbp:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("payment.payment_method_card") + f" ({final_rub:.0f} ₽)",
                    callback_data=f"purchase:{subscription_months}:card:{promo_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("user_menu.back"),
                    callback_data=f"purchase:{subscription_months}"
                )
            ]
        ]
        
        locale_map = {
            1: _("payment.subscription_1month").split(" (")[0],
            3: _("payment.subscription_3months").split(" (")[0],
            6: _("payment.subscription_6months").split(" (")[0],
            12: _("payment.subscription_12months").split(" (")[0],
        }
        months_text = locale_map.get(subscription_months, f"{subscription_months} месяцев")
        
        await message.answer(
            _("payment.promo_code_prompt").format(
                months_text=months_text,
                stars=f"{final_stars} ⭐ / {final_rub:.0f} ₽"
            ) + promo_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

