import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)


class StarsPaymentService:
    def __init__(self, bot, db, config):
        self.bot = bot
        self.db = db
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.bot_token = config.BOT_TOKEN

        self.api_url = "https://api.telegram.org/bot"
        self.stars_exchange_rate = 0.01
        self.min_stars_amount = 50

        self.prices_in_stars = {
            "basic_1": 500,
            "premium_1": 1500,
            "nuke_1": 1000,
            "nuke_7": 4500,
            "nuke_30": 8000,
            "nuke_forever": 11000,
        }

    async def initialize(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            await self.initialize()

    def _sign_payload(self, payload_json: str) -> str:
        return hmac.new(self.bot_token.encode(), payload_json.encode(), hashlib.sha256).hexdigest()

    def _build_payload(self, user_id: int, product_id: str, stars_amount: int, invoice_id: str) -> str:
        payload = {
            "invoice_id": invoice_id,
            "user_id": user_id,
            "product_id": product_id,
            "stars": stars_amount,
            "timestamp": int(time.time()),
        }
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        return f"{payload_json}:{self._sign_payload(payload_json)}"

    def _parse_signed_payload(self, signed_payload: str) -> Optional[Dict]:
        if not signed_payload or ":" not in signed_payload:
            return None

        payload_json, signature = signed_payload.rsplit(":", 1)
        expected_signature = self._sign_payload(payload_json)
        if not hmac.compare_digest(signature, expected_signature):
            return None

        try:
            return json.loads(payload_json)
        except json.JSONDecodeError:
            return None

    async def create_invoice_link(self, user_id: int, product_id: str, description: str) -> Optional[str]:
        try:
            await self._ensure_session()

            stars_amount = self.prices_in_stars.get(product_id)
            if not stars_amount:
                logger.error(f"❌ Цена для {product_id} не найдена")
                return None

            product_info = self.config.SUBSCRIPTION_PLANS.get(product_id, {})
            product_name = product_info.get("name", "Подписка")

            invoice_id = f"stars_{user_id}_{int(time.time())}"
            payload = self._build_payload(user_id, product_id, stars_amount, invoice_id)

            prices = [{"label": product_name[:32], "amount": stars_amount * 100}]
            tips = [int(stars_amount * 100 * 0.1), int(stars_amount * 100 * 0.15), int(stars_amount * 100 * 0.2)]

            method_url = f"{self.api_url}{self.bot_token}/createInvoiceLink"
            data = {
                "title": "Оплата подписки",
                "description": description,
                "payload": payload,
                "provider_token": self.config.PAYMENT_PROVIDER_TOKEN,
                "currency": "XTR",
                "prices": json.dumps(prices),
                "max_tip_amount": stars_amount * 200,
                "suggested_tip_amounts": json.dumps(tips),
                "need_name": False,
                "need_phone_number": False,
                "need_email": False,
                "need_shipping_address": False,
                "send_phone_number_to_provider": False,
                "send_email_to_provider": False,
                "is_flexible": False,
            }
            if hasattr(self.config, "PAYMENT_PHOTO_URL") and self.config.PAYMENT_PHOTO_URL:
                data["photo_url"] = self.config.PAYMENT_PHOTO_URL

            async with self.session.post(method_url, data=data) as response:
                result = await response.json()

            if not result.get("ok"):
                logger.error(f"❌ Ошибка создания инвойса: {result}")
                return None

            invoice_link = result["result"]
            self.db.save_invoice(
                user_id=user_id,
                invoice_id=invoice_id,
                product_id=product_id,
                stars_amount=stars_amount,
                usd_amount=stars_amount * self.stars_exchange_rate,
                status="created",
            )
            return invoice_link

        except Exception as e:
            logger.error(f"❌ Ошибка create_invoice_link: {e}", exc_info=True)
            return None

    async def verify_payment(self, invoice_id: str) -> Tuple[bool, Dict]:
        try:
            await self._ensure_session()
            method_url = f"{self.api_url}{self.bot_token}/getPayments"
            async with self.session.post(method_url, data={"invoice_id": invoice_id}) as response:
                result = await response.json()

            if not (result.get("ok") and result.get("result")):
                return False, {}

            payment_info = result["result"][0]
            if payment_info.get("status") != "paid":
                return False, payment_info

            payload_data = self._parse_signed_payload(payment_info.get("payload", ""))
            if payload_data and payload_data.get("invoice_id") != invoice_id:
                return False, {}

            return True, payment_info
        except Exception as e:
            logger.error(f"❌ Ошибка verify_payment: {e}", exc_info=True)
            return False, {}

    async def process_stars_payment_webhook(self, update: Dict) -> Tuple[bool, str]:
        try:
            pre_checkout_query = update.get("pre_checkout_query")
            if not pre_checkout_query:
                return False, "Нет данных о платеже"

            payload_data = self._parse_signed_payload(pre_checkout_query.get("invoice_payload", ""))
            if not payload_data:
                await self._answer_pre_checkout_query(pre_checkout_query["id"], False)
                return False, "Некорректный payload"

            invoice_id = payload_data.get("invoice_id")
            user_id = payload_data.get("user_id")
            total_amount = pre_checkout_query.get("total_amount", 0) / 100

            invoice_info = self.db.get_invoice_by_id(invoice_id)
            if not invoice_info:
                await self._answer_pre_checkout_query(pre_checkout_query["id"], False)
                return False, "Инвойс не найден"

            if total_amount < invoice_info["stars_amount"]:
                await self._answer_pre_checkout_query(pre_checkout_query["id"], False)
                return False, "Недостаточная сумма оплаты"

            self.db.update_invoice_status(invoice_id, "paid")
            usd_amount = invoice_info["stars_amount"] * self.stars_exchange_rate
            self.db.update_user_balance(user_id, usd_amount)

            product_id = invoice_info["product_id"]
            if product_id.startswith(("basic_", "premium_", "nuke_")):
                await self._activate_subscription(user_id, product_id)

            await self._answer_pre_checkout_query(pre_checkout_query["id"], True)
            return True, f"✅ Оплачено {invoice_info['stars_amount']} звезд"

        except Exception as e:
            logger.error(f"❌ Ошибка process_stars_payment_webhook: {e}")
            return False, str(e)

    async def _answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool):
        try:
            await self._ensure_session()
            method_url = f"{self.api_url}{self.bot_token}/answerPreCheckoutQuery"
            data = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
            if not ok:
                data["error_message"] = "Ошибка обработки платежа"
            async with self.session.post(method_url, data=data) as response:
                await response.json()
        except Exception as e:
            logger.error(f"❌ Ошибка answer_pre_checkout_query: {e}")

    async def _activate_subscription(self, user_id: int, product_id: str):
        try:
            plan_info = self.config.SUBSCRIPTION_PLANS.get(product_id, {})
            if not plan_info:
                return

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

            days = plan_info.get("days", 30)
            end_date = datetime.now() + timedelta(days=days)

            self.db.update_user_subscription(
                user_id=user_id,
                subscription_type=sub_type,
                subscription_name=sub_name,
                end_date=end_date.strftime("%Y-%m-%d %H:%M:%S"),
            )

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🎉 <b>Подписка активирована!</b>\n\n"
                        f"Тип: {sub_type}\n"
                        f"Название: {sub_name}\n"
                        f"Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                        "Спасибо за покупку! 🚀"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"❌ Ошибка активации подписки: {e}")

    def get_stars_price(self, product_id: str) -> int:
        return self.prices_in_stars.get(product_id, 0)

    def convert_usd_to_stars(self, usd_amount: float) -> int:
        return int(usd_amount / self.stars_exchange_rate)

    def convert_stars_to_usd(self, stars_amount: int) -> float:
        return stars_amount * self.stars_exchange_rate
