from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.utils.i18n import gettext as _

from src.config import get_settings
from src.utils.i18n import get_i18n
from src.utils.logger import logger


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором.
    
    Если список администраторов пустой, возвращает False (никто не является администратором).
    Если список не пустой, проверяет наличие user_id в списке.
    """
    settings = get_settings()
    allowed_admins = settings.allowed_admins
    # Если список администраторов пустой, никто не является администратором
    if not allowed_admins:
        return False
    # Проверяем, есть ли пользователь в списке администраторов
    return user_id in allowed_admins


class AdminMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора.
    
    Блокирует только админские команды и callback-запросы от не-администраторов.
    Пользовательские команды (например, /start) пропускаются для всех.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Проверяет права администратора перед обработкой события."""
        user_id = None
        
        # Извлекаем user_id из события
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
        
        # Если user_id не найден, пропускаем событие (может быть системное)
        if user_id is None:
            return await handler(event, data)
        
        # Определяем, является ли это админской командой/колбэком
        is_admin_command = False
        
        if isinstance(event, Message):
            if event.text and event.text.startswith("/"):
                # Команды админов (кроме пользовательских)
                admin_commands = [
                    "/user", "/node", "/host", "/stats", "/health", "/bandwidth",
                    "/user_create", "/sub", "/tokens", "/templates", "/snippets",
                    "/configs", "/billing", "/providers"
                ]
                is_admin_command = any(event.text.startswith(cmd) for cmd in admin_commands)
        
        if isinstance(event, CallbackQuery):
            if event.data:
                # Колбэки админов начинаются с определенных префиксов
                # НЕ включаем user: и buy: - это пользовательские колбэки!
                admin_prefixes = [
                    "admin:",
                    "menu:", "node:", "host:", "token:", "template:",
                    "snippet:", "config:", "billing:", "provider:", "bulk:",
                    "system:", "nav:", "subs:", "input:", "user_edit", "user_create",
                    "user_search", "node_", "host_", "uef:", "nef:", "hef:", "stats:"
                ]
                is_admin_command = any(event.data.startswith(prefix) for prefix in admin_prefixes)
        
        # Если это админская команда и пользователь не админ, блокируем
        if is_admin_command and not is_admin(user_id):
            settings = get_settings()
            logger.warning(
                "🚫 Unauthorized admin access attempt user_id=%s event_type=%s",
                user_id,
                type(event).__name__,
            )
            # Для CallbackQuery отправляем ответ с ошибкой
            if isinstance(event, CallbackQuery):
                try:
                    # Используем локализацию для сообщения об ошибке
                    i18n = get_i18n()
                    with i18n.use_locale(i18n.default_locale):
                        error_text = _("errors.unauthorized")
                    await event.answer(error_text, show_alert=True)
                except Exception:
                    try:
                        await event.answer("⛔️ Доступ запрещен. Вы не являетесь администратором.", show_alert=True)
                    except Exception:
                        pass
            # Для Message отправляем сообщение об ошибке
            elif isinstance(event, Message):
                try:
                    i18n = get_i18n()
                    with i18n.use_locale(i18n.default_locale):
                        error_text = _("errors.unauthorized")
                    await event.answer(error_text)
                except Exception:
                    try:
                        await event.answer("⛔️ Доступ запрещен. Вы не являетесь администратором.")
                    except Exception:
                        pass
            # Не вызываем handler, чтобы заблокировать обработку
            return
        
        # Пропускаем событие дальше (либо это пользовательская команда, либо пользователь - админ)
        return await handler(event, data)
