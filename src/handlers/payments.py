"""Обработчики платежей через Telegram Stars."""
from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, PreCheckoutQuery
from aiogram.utils.i18n import gettext as _

from src.database import BotUser, Payment
from src.services.payment_service import process_successful_payment
from src.utils.i18n import get_i18n
from src.utils.logger import logger

router = Router(name="payments")


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    """Обрабатывает pre_checkout_query перед подтверждением платежа."""
    invoice_payload = pre_checkout_query.invoice_payload
    
    try:
        # Проверяем платеж в БД
        payment = Payment.get_by_payload(invoice_payload)
        
        if not payment:
            await pre_checkout_query.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Платеж не найден. Пожалуйста, создайте новый заказ."
            )
            return
        
        if payment["status"] == "completed":
            await pre_checkout_query.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Этот платеж уже был обработан."
            )
            return
        
        # Проверяем сумму
        if payment["stars"] != pre_checkout_query.total_amount:
            await pre_checkout_query.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Сумма платежа не совпадает. Пожалуйста, создайте новый заказ."
            )
            return
        
        # Все проверки пройдены
        await pre_checkout_query.bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=True
        )
    except Exception as e:
        logger.exception("Error in pre_checkout_query")
        await pre_checkout_query.bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Произошла ошибка при обработке платежа. Попробуйте позже."
        )


@router.message(F.content_type == "successful_payment")
async def process_successful_payment_message(message: Message) -> None:
    """Обрабатывает успешный платеж."""
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    invoice_payload = payment_info.invoice_payload
    total_amount = payment_info.total_amount
    
    user = BotUser.get_or_create(user_id, message.from_user.username)
    locale = user.get("language", "ru")
    
    i18n = get_i18n()
    with i18n.use_locale(locale):
        try:
            # Обрабатываем платеж
            result = await process_successful_payment(
                user_id=user_id,
                invoice_payload=invoice_payload,
                total_amount=total_amount
            )
            
            if result.get("success"):
                if result.get("already_completed"):
                    text = _("payment.already_processed")
                    buttons = [[
                        InlineKeyboardButton(
                            text=_("user_menu.subscription"),
                            callback_data="user:subscription"
                        )
                    ]]
                else:
                    subscription_url = result.get("subscription_url", "")
                    expire_date = result.get("expire_date", "")
                    
                    text = _("payment.success").format(
                        expire_date=expire_date[:10] if expire_date else _("payment.unknown")
                    )
                    
                    buttons = []
                    if subscription_url:
                        buttons.append([InlineKeyboardButton(
                            text=_("user.get_config"),
                            url=subscription_url
                        )])
                    buttons.append([InlineKeyboardButton(
                        text=_("payment.view_subscription"),
                        callback_data="user:subscription"
                    )])
                    
                    await message.answer(
                        text,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                        parse_mode="HTML"
                    )
                    return
            else:
                error = result.get("error", _("payment.error_processing"))
                text = _("payment.error").format(error=error)
                
                # Уведомляем пользователя, что нужно обратиться в поддержку
                text += f"\n\n{_('payment.contact_support')}"
                
                buttons = [[
                    InlineKeyboardButton(
                        text=_("actions.back"),
                        callback_data="user:menu"
                    )
                ]]
                
                await message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                    parse_mode="HTML"
                )
                return
        except Exception as e:
            logger.exception("Error processing successful payment")
            await message.answer(
                _("payment.error_processing"),
                parse_mode="HTML"
            )

