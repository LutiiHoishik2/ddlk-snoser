import aiohttp
import json
import logging
from typing import Dict, Optional, Tuple, Any
import asyncio

logger = logging.getLogger(__name__)

class CryptoBotAPI:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api"
        self.headers = {
            "Crypto-Pay-API-Token": token,
            "Content-Type": "application/json"
        }
        logger.info("💰 CryptoBot API инициализирован")
    
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Базовый метод для запросов к API"""
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "headers": self.headers,
                    "timeout": aiohttp.ClientTimeout(total=30)
                }
                
                if data:
                    kwargs["json"] = data
                
                async with session.request(
                    method, 
                    f"{self.base_url}/{endpoint}", 
                    **kwargs
                ) as response:
                    
                    if response.status != 200:
                        logger.error(f"CryptoBot API HTTP error: {response.status}")
                        return None
                    
                    result = await response.json()
                    
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        error_msg = result.get('error', {}).get('name', 'Unknown error')
                        logger.error(f"CryptoBot API error: {error_msg}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("CryptoBot API timeout")
            return None
        except Exception as e:
            logger.error(f"CryptoBot API request error: {e}")
            return None
    
    async def create_invoice(self, amount: float, description: str = "", payload: str = "") -> Optional[Dict]:
        """Создание инвойса в CryptoBot"""
        try:
            # CryptoBot требует сумму в виде строки
            amount_str = str(amount)
            
            data = {
                "asset": "USDT",
                "amount": amount_str,
                "description": description,
                "hidden_message": "Оплата услуг RABANOK REPORTER",
                "paid_btn_name": "openBot",
                "paid_btn_url": "https://t.me/rabanok_bot",
                "payload": payload,
                "allow_comments": False,
                "allow_anonymous": False,
                "expires_in": 3600  # 1 час
            }
            
            result = await self._make_request("POST", "createInvoice", data)
            
            if result:
                logger.info(f"✅ Инвойс создан: {result.get('invoice_id')}")
                return {
                    'invoice_id': str(result.get('invoice_id')),
                    'pay_url': result.get('pay_url'),
                    'amount': amount,
                    'description': description,
                    'status': 'active'
                }
            else:
                logger.error("❌ Не удалось создать инвойс")
                return None
                
        except Exception as e:
            logger.error(f"CryptoBot create_invoice error: {e}")
            return None
    
    async def get_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Получить информацию об инвойсе"""
        try:
            result = await self._make_request("GET", f"getInvoices?invoice_ids={invoice_id}")
            
            if result and result.get('items'):
                invoice = result['items'][0]
                return {
                    'invoice_id': str(invoice.get('invoice_id')),
                    'status': invoice.get('status'),
                    'amount': float(invoice.get('amount', 0)),
                    'paid_at': invoice.get('paid_at'),
                    'description': invoice.get('description', ''),
                    'payload': invoice.get('payload', '')
                }
            return None
            
        except Exception as e:
            logger.error(f"CryptoBot get_invoice error: {e}")
            return None
    
    async def check_invoice(self, invoice_id: str) -> Tuple[bool, Optional[Dict]]:
        """Проверка статуса инвойса"""
        try:
            invoice = await self.get_invoice(invoice_id)
            
            if invoice:
                is_paid = invoice.get('status') == 'paid'
                
                if is_paid:
                    logger.info(f"✅ Инвойс оплачен: {invoice_id}")
                else:
                    logger.debug(f"⏳ Инвойс не оплачен: {invoice_id}")
                    
                return is_paid, invoice
            
            return False, None
            
        except Exception as e:
            logger.error(f"CryptoBot check_invoice error: {e}")
            return False, None

    async def get_exchange_rates(self) -> Optional[Dict]:
        """Получить курсы валют"""
        try:
            result = await self._make_request("GET", "getExchangeRates")
            return result
        except Exception as e:
            logger.error(f"CryptoBot get_exchange_rates error: {e}")
            return None

class PaymentService:
    def __init__(self, cryptobot_token: str = None):
        self.cryptobot = CryptoBotAPI(cryptobot_token) if cryptobot_token else None
        logger.info("💰 PaymentService инициализирован")
    
    async def create_invoice(self, user_id: int, amount: float, description: str = "") -> Optional[Dict]:
        """Создание инвойса для пополнения баланса"""
        if not self.cryptobot:
            logger.error("CryptoBot token not configured")
            return None
            
        try:
            if amount <= 0:
                logger.error(f"Invalid amount: {amount}")
                return None
            
            # Используем user_id как payload для идентификации
            payload = str(user_id)
            
            if not description:
                description = f"Пополнение баланса RABANOK на ${amount:.2f}"
            
            invoice_data = await self.cryptobot.create_invoice(amount, description, payload)
            
            if invoice_data:
                logger.info(f"✅ Инвойс создан для пользователя {user_id}: ${amount}")
                return invoice_data
            else:
                logger.error(f"❌ Ошибка создания инвойса для {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"PaymentService create_invoice error: {e}")
            return None
    
    async def create_subscription_payment(self, user_id: int, plan_id: str, amount: float, description: str = "") -> Optional[Dict]:
        """Создание платежа для подписки"""
        if not self.cryptobot:
            logger.error("CryptoBot token not configured")
            return None
            
        try:
            if not description:
                description = f"Подписка RABANOK - {plan_id}"
            
            payload = f"subscription:{user_id}:{plan_id}"
            
            invoice_data = await self.cryptobot.create_invoice(amount, description, payload)
            
            if invoice_data:
                logger.info(f"✅ Платеж за подписку создан для {user_id}: {plan_id} - ${amount}")
                return invoice_data
            else:
                logger.error(f"❌ Ошибка создания платежа за подписку для {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"PaymentService subscription error: {e}")
            return None
    
    async def create_single_report_payment(self, user_id: int, report_type: str, amount: float, description: str = "") -> Optional[Dict]:
        """Создание платежа для отдельных жалоб"""
        if not self.cryptobot:
            logger.error("CryptoBot token not configured")
            return None
            
        try:
            type_names = {
                "session": "жалоба (сессии)",
                "email": "жалоба (почта)", 
                "combo": "жалоба (комбо)",
                "dsa": "DSA жалоба",
                "nuke": "снос сессий"
            }
            
            if not description:
                description = f"Покупка {type_names.get(report_type, 'услуги')} - ${amount}"
            
            payload = f"report:{user_id}:{report_type}"
            
            invoice_data = await self.cryptobot.create_invoice(amount, description, payload)
            
            if invoice_data:
                logger.info(f"✅ Платеж за жалобу создан для {user_id}: {report_type} - ${amount}")
                return invoice_data
            else:
                logger.error(f"❌ Ошибка создания платежа за жалобу для {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"PaymentService single report error: {e}")
            return None
    
    async def check_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Проверить статус инвойса"""
        if not self.cryptobot:
            logger.error("CryptoBot token not configured")
            return None
            
        try:
            invoice = await self.cryptobot.get_invoice(invoice_id)
            return invoice
        except Exception as e:
            logger.error(f"PaymentService check_invoice error: {e}")
            return None
    
    async def check_payment_status(self, invoice_id: str) -> Tuple[bool, Optional[Dict]]:
        """Проверка статуса платежа"""
        if not self.cryptobot:
            return False, None
            
        return await self.cryptobot.check_invoice(invoice_id)
    
    async def create_custom_payment(self, user_id: int, amount: float, description: str, payment_type: str = "custom") -> Optional[Dict]:
        """Создание кастомного платежа"""
        if not self.cryptobot:
            logger.error("CryptoBot token not configured")
            return None
            
        try:
            payload = f"{payment_type}:{user_id}"
            
            invoice_data = await self.cryptobot.create_invoice(amount, description, payload)
            
            if invoice_data:
                logger.info(f"✅ Кастомный платеж создан для {user_id}: ${amount} - {description}")
                return invoice_data
            return None
            
        except Exception as e:
            logger.error(f"PaymentService custom payment error: {e}")
            return None
    
    async def validate_configuration(self) -> bool:
        """Проверить корректность конфигурации CryptoBot"""
        if not self.cryptobot:
            logger.error("CryptoBot не настроен")
            return False
            
        try:
            rates = await self.cryptobot.get_exchange_rates()
            if rates:
                logger.info("✅ CryptoBot configuration is valid")
                return True
            else:
                logger.error("❌ CryptoBot configuration test failed")
                return False
        except Exception as e:
            logger.error(f"CryptoBot configuration validation error: {e}")
            return False

    async def process_payment_webhook(self, webhook_data: Dict) -> Tuple[bool, Dict]:
        """Обработка вебхука от CryptoBot"""
        try:
            invoice_id = webhook_data.get('payload', {}).get('invoice_id')
            status = webhook_data.get('status')
            
            if status == 'paid' and invoice_id:
                invoice = await self.check_invoice(invoice_id)
                if invoice and invoice.get('status') == 'paid':
                    # Извлекаем данные из payload
                    payload = invoice.get('payload', '')
                    amount = invoice.get('amount', 0)
                    
                    # Парсим payload для определения типа платежа
                    if ':' in payload:
                        parts = payload.split(':')
                        if len(parts) >= 2:
                            payment_type = parts[0]
                            user_id = int(parts[1])
                            
                            return True, {
                                'user_id': user_id,
                                'amount': amount,
                                'invoice_id': invoice_id,
                                'payment_type': payment_type,
                                'payload': payload
                            }
                    
            return False, {}
            
        except Exception as e:
            logger.error(f"Payment webhook processing error: {e}")
            return False, {}

# Глобальный экземпляр для использования
_payment_service_instance = None

def get_payment_service(token: str = None) -> PaymentService:
    """Получить экземпляр PaymentService (синглтон)"""
    global _payment_service_instance
    if _payment_service_instance is None and token:
        _payment_service_instance = PaymentService(token)
    return _payment_service_instance

async def initialize_payment_service(token: str) -> bool:
    """Инициализировать платежную систему"""
    global _payment_service_instance
    try:
        _payment_service_instance = PaymentService(token)
        is_valid = await _payment_service_instance.validate_configuration()
        
        if is_valid:
            logger.info("✅ Платежная система инициализирована успешно")
        else:
            logger.error("❌ Ошибка инициализации платежной системы")
            
        return is_valid
    except Exception as e:
        logger.error(f"Payment service initialization error: {e}")
        return False
