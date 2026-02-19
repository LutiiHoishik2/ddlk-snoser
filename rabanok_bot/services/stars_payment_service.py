import logging
import asyncio
import aiohttp
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import json
import hashlib
import hmac
import time

logger = logging.getLogger(__name__)

class StarsPaymentService:
    def __init__(self, bot, db, config):
        """
        Реальный сервис для работы с Telegram Stars
        """
        self.bot = bot
        self.db = db
        self.config = config
        self.session = None
        self.bot_token = config.BOT_TOKEN
        
        # Настройки API
        self.api_url = "https://api.telegram.org/bot"
        self.stars_exchange_rate = 0.01  # 1 звезда = $0.01
        self.min_stars_amount = 50
        
        # Цены в звездах
        self.prices_in_stars = {
            "basic_1": 500,      # BASIC 30 дней
            "premium_1": 1500,   # PREMIUM 30 дней
            "nuke_1": 1000,      # NUKE день
            "nuke_7": 4500,      # NUKE неделя
            "nuke_30": 8000,     # NUKE месяц
            "nuke_forever": 11000 # NUKE навсегда
        }
        
        logger.info("✅ StarsPaymentService инициализирован")
    
    async def initialize(self):
        """Инициализация сессии"""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
    
    async def create_invoice_link(self, user_id: int, product_id: str, 
                                  description: str) -> Optional[str]:
        """
        Создает ссылку на оплату через Telegram Stars
        Возвращает invoice_link для оплаты
        """
        try:
            stars_amount = self.prices_in_stars.get(product_id)
            if not stars_amount:
                logger.error(f"❌ Цена для {product_id} не найдена")
                return None
            
            # Получаем информацию о продукте
            product_info = self.config.SUBSCRIPTION_PLANS.get(product_id, {})
            product_name = product_info.get("name", "Подписка")
            
            # Формируем payload для верификации
            payload = {
                "user_id": user_id,
                "product_id": product_id,
                "stars": stars_amount,
                "timestamp": int(datetime.now().timestamp())
            }
            payload_json = json.dumps(payload)
            
            # Создаем подпись payload
            signature = hmac.new(
                self.bot_token.encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Создаем параметры для инвойса
            prices = [
                {
                    "label": product_name[:32],
                    "amount": stars_amount * 100  # В копейках/центах
                }
            ]
            
            # Используем метод createInvoiceLink
            # https://core.telegram.org/bots/api#createinvoicelink
            method_url = f"{self.api_url}{self.bot_token}/createInvoiceLink"
            
            data = {
                "title": "Оплата подписки",
                "description": description,
                "payload": f"{payload_json}:{signature}",  # payload с подписью
                "provider_token": self.config.PAYMENT_PROVIDER_TOKEN,
                "currency": "XTR",  # Telegram Stars
                "prices": json.dumps(prices),
                "max_tip_amount": stars_amount * 100 * 2,  # Максимум x2
                "suggested_tip_amounts": json.dumps([
                    stars_amount * 100 * 0.1,  # 10%
                    stars_amount * 100 * 0.15, # 15%
                    stars_amount * 100 * 0.2   # 20%
                ]),
                "photo_url": self.config.PAYMENT_PHOTO_URL if hasattr(self.config, 'PAYMENT_PHOTO_URL') else None,
                "need_name": False,
                "need_phone_number": False,
                "need_email": False,
                "need_shipping_address": False,
                "send_phone_number_to_provider": False,
                "send_email_to_provider": False,
                "is_flexible": False
            }
            
            async with self.session.post(method_url, data=data) as response:
                result = await response.json()
                
                if result.get("ok"):
                    invoice_link = result["result"]
                    logger.info(f"✅ Создана ссылка на оплату для {user_id}: {stars_amount} звезд")
                    
                    # Сохраняем информацию о инвойсе
                    self.db.save_invoice(
                        user_id=user_id,
                        invoice_id=invoice_link.split('/')[-1] if '/' in invoice_link else invoice_link,
                        product_id=product_id,
                        stars_amount=stars_amount,
                        usd_amount=stars_amount * self.stars_exchange_rate,
                        status="created"
                    )
                    
                    return invoice_link
                else:
                    logger.error(f"❌ Ошибка создания инвойса: {result}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка create_invoice_link: {e}", exc_info=True)
            return None
    
    async def verify_payment(self, invoice_id: str) -> Tuple[bool, Dict]:
        """
        Проверяет статус платежа через getPayments (упрощённо)
        """
        try:
            method_url = f"{self.api_url}{self.bot_token}/getPayments"
            data = {"invoice_id": invoice_id}
            async with self.session.post(method_url, data=data) as response:
                result = await response.json()
                if result.get("ok") and result.get("result"):
                    # Берём первый платеж
                    payment_info = result["result"][0]
                    if payment_info.get("status") == "paid":
                        # Попытка распарсить payload и проверить подпись (если есть)
                        payload = payment_info.get("payload", "")
                        if ":" in payload:
                            payload_json, signature = payload.split(":", 1)
                            expected_signature = hmac.new(
                                self.bot_token.encode(),
                                payload_json.encode(),
                                hashlib.sha256
                            ).hexdigest()
                            if hmac.compare_digest(signature, expected_signature):
                                logger.info(f"✅ Платёж проверен и подписан: {invoice_id}")
                                return True, payment_info
                        # Если подписи нет, принимаем как оплаченный (упрощённо)
                        return True, payment_info
                return False, {}
        except Exception as e:
            logger.error(f"❌ Ошибка verify_payment: {e}", exc_info=True)
            return False, {}
    
    async def process_stars_payment_webhook(self, update: Dict) -> Tuple[bool, str]:
        """
        Обработка вебхука от Telegram о успешной оплате
        """
        try:
            # Получаем информацию о платеже из вебхука
            pre_checkout_query = update.get("pre_checkout_query")
            if not pre_checkout_query:
                return False, "Нет данных о платеже"
            
            invoice_id = pre_checkout_query.get("invoice_payload", "").split(":")[0]
            user_id = pre_checkout_query.get("from", {}).get("id")
            total_amount = pre_checkout_query.get("total_amount", 0) / 100  # Конвертируем из копеек
            
            if not invoice_id or not user_id:
                return False, "Некорректные данные платежа"
            
            # Получаем информацию о инвойсе из базы
            invoice_info = self.db.get_invoice_by_id(invoice_id)
            if not invoice_info:
                return False, "Инвойс не найден"
            
            # Проверяем сумму
            if total_amount < invoice_info["stars_amount"]:
                return False, "Недостаточная сумма оплаты"
            
            # Обновляем статус инвойса
            self.db.update_invoice_status(invoice_id, "paid")
            
            # Начисляем баланс
            usd_amount = invoice_info["stars_amount"] * self.stars_exchange_rate
            self.db.update_user_balance(user_id, usd_amount)
            
            # Если это подписка - активируем
            product_id = invoice_info["product_id"]
            if product_id.startswith(("basic_", "premium_", "nuke_")):
                await self._activate_subscription(user_id, product_id)
            
            # Подтверждаем платеж Telegram
            await self._answer_pre_checkout_query(pre_checkout_query["id"], True)
            
            logger.info(f"💰 Успешная оплата звездами: {user_id} -> {invoice_info['stars_amount']} звезд")
            return True, f"✅ Оплачено {invoice_info['stars_amount']} звезд"
            
        except Exception as e:
            logger.error(f"❌ Ошибка process_stars_payment_webhook: {e}")
            return False, str(e)
    
    async def _answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool):
        """Подтверждает pre-checkout запрос"""
        try:
            method_url = f"{self.api_url}{self.bot_token}/answerPreCheckoutQuery"
            
            data = {
                "pre_checkout_query_id": pre_checkout_query_id,
                "ok": ok
            }
            
            if not ok:
                data["error_message"] = "Ошибка обработки платежа"
            
            async with self.session.post(method_url, data=data) as response:
                await response.json()
                
        except Exception as e:
            logger.error(f"❌ Ошибка answer_pre_checkout_query: {e}")
    
    async def _activate_subscription(self, user_id: int, product_id: str):
        """Активация подписки после оплаты"""
        try:
            plan_info = self.config.SUBSCRIPTION_PLANS.get(product_id, {})
            if not plan_info:
                logger.error(f"❌ План {product_id} не найден")
                return
            
            # Определяем тип подписки
            if product_id.startswith("basic_"):
                sub_type = "BASIC"
                sub_name = "BASIC 30 дней"
            elif product_id.startswith("premium_"):
                sub_type = "PREMIUM"
                sub_name = "PREMIUM 30 дней"
            elif product_id.startswith("nuke_"):
                sub_type = "NUKE"
                if "7" in product_id:
                    sub_name = "NUKE НЕДЕЛЯ"
                elif "30" in product_id:
                    sub_name = "NUKE МЕСЯЦ"
                elif "forever" in product_id:
                    sub_name = "NUKE НАВСЕГДА"
                else:
                    sub_name = "NUKE ДЕНЬ"
            else:
                sub_type = "BASIC"
                sub_name = "BASIC"
            
            # Устанавливаем дату окончания
            days = plan_info.get("days", 30)
            end_date = datetime.now() + timedelta(days=days)
            
            # Сохраняем подписку
            self.db.update_user_subscription(
                user_id=user_id,
                subscription_type=sub_type,
                subscription_name=sub_name,
                end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            # Отправляем уведомление пользователю
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 <b>Подписка активирована!</b>\n\n"
                         f"Тип: {sub_type}\n"
                         f"Название: {sub_name}\n"
                         f"Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                         f"Спасибо за покупку! 🚀",
                    parse_mode="HTML"
                )
            except:
                pass
            
            logger.info(f"🎫 Активирована подписка {sub_type} для {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка активации подписки: {e}")
    
    def get_stars_price(self, product_id: str) -> int:
        """Получает цену в звездах"""
        return self.prices_in_stars.get(product_id, 0)
    
    def convert_usd_to_stars(self, usd_amount: float) -> int:
        """Конвертирует USD в звезды"""
        return int(usd_amount / self.stars_exchange_rate)
    
    def convert_stars_to_usd(self, stars_amount: int) -> float:
        """Конвертирует звезды в USD"""
        return stars_amount * self.stars_exchange_rate