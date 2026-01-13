"""HTTP сервер для обработки webhook'ов от YooKassa."""
import asyncio
import hmac
import hashlib
import json
from typing import Optional

from aiohttp import web
from yookassa import Configuration

from src.config import get_settings
from src.services.payment_service import process_yookassa_payment
from src.utils.logger import logger


class YooKassaWebhookServer:
    """HTTP сервер для обработки webhook'ов от YooKassa."""
    
    def __init__(self, bot, port: int = 8080):
        self.bot = bot
        self.port = port
        self.app = web.Application()
        self.app.router.add_post('/webhook/yookassa', self.handle_webhook)
        self.app.router.add_get('/health', self.health_check)
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Проверка здоровья сервера."""
        return web.json_response({"status": "ok"})
    
    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Проверяет подпись webhook от YooKassa.
        
        YooKassa отправляет подпись в заголовке X-YooMoney-Signature.
        Подпись вычисляется как HMAC-SHA256 от тела запроса с использованием secret_key.
        """
        settings = get_settings()
        if not settings.yookassa_secret_key:
            logger.warning("YooKassa secret key not configured, skipping signature verification")
            return True
        
        try:
            # Вычисляем ожидаемую подпись
            expected_signature = hmac.new(
                settings.yookassa_secret_key.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Сравниваем подписи
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.exception(f"Error verifying signature: {e}")
            return False
    
    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Обрабатывает webhook от YooKassa."""
        try:
            # Получаем тело запроса
            body = await request.read()
            
            # Получаем подпись из заголовка
            signature = request.headers.get('X-YooMoney-Signature', '')
            
            # Проверяем подпись (если настроена)
            if signature:
                if not self._verify_signature(body, signature):
                    logger.warning("Invalid webhook signature from YooKassa")
                    return web.Response(status=401, text="Invalid signature")
            
            # Парсим JSON
            try:
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in webhook: {e}")
                return web.Response(status=400, text="Invalid JSON")
            
            # Проверяем тип события
            event_type = data.get('event')
            if event_type != 'payment.succeeded':
                logger.info(f"Webhook event type '{event_type}' ignored (only 'payment.succeeded' is processed)")
                return web.json_response({"status": "ok"})
            
            # Получаем данные платежа
            payment_object = data.get('object', {})
            payment_id = payment_object.get('id')
            
            if not payment_id:
                logger.error("Payment ID not found in webhook data")
                return web.Response(status=400, text="Payment ID not found")
            
            logger.info(f"Received webhook for payment {payment_id}, event: {event_type}")
            
            # Обрабатываем платеж
            try:
                result = await process_yookassa_payment(
                    yookassa_payment_id=payment_id,
                    bot=self.bot
                )
                
                if result.get("success"):
                    logger.info(f"Payment {payment_id} processed successfully via webhook")
                    
                    # Отправляем уведомление пользователю (если нужно)
                    # Это уже делается в process_yookassa_payment через notification_service
                else:
                    error = result.get("error", "Unknown error")
                    logger.error(f"Failed to process payment {payment_id}: {error}")
                
                return web.json_response({"status": "ok"})
            except Exception as e:
                logger.exception(f"Error processing payment {payment_id}: {e}")
                # Все равно возвращаем 200, чтобы YooKassa не повторял запрос
                return web.json_response({"status": "error", "message": str(e)})
        
        except Exception as e:
            logger.exception("Error handling webhook")
            return web.Response(status=500, text=f"Internal server error: {str(e)}")
    
    async def start(self):
        """Запускает HTTP сервер."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()
        logger.info(f"🌐 YooKassa webhook server started on port {self.port}")
        logger.info(f"📡 Webhook URL: https://shftvpn.click/webhook/yookassa")
    
    async def stop(self):
        """Останавливает HTTP сервер."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("🌐 YooKassa webhook server stopped")

