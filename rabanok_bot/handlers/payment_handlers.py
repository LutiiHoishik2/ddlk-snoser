from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from core.database import Database
from core.config import Config
from utils.keyboards import Keyboards
from services.payment_service import PaymentService
import asyncio
import logging

router = Router()
logger = logging.getLogger(__name__)

class PaymentHandlers:
    def __init__(self, bot, db: Database, config: Config):
        self.bot = bot
        self.db = db
        self.config = config
        self.payment_service = PaymentService(config.CRYPTOBOT_TOKEN)
        self.active_payments = {}  # {user_id: payment_data}
    
    async def process_payment_callback(self, callback: CallbackQuery, state: FSMContext):
        data = callback.data
        user_id = callback.from_user.id
        
        try:
            if data.startswith("buy_basic_") or data.startswith("buy_premium_") or data.startswith("buy_nuke_"):
                await self.process_subscription_purchase(callback, data)
            elif data.startswith("buy_single_"):
                await self.process_single_report_purchase(callback, data)
            elif data.startswith("check_payment_"):
                await self.check_payment_status(callback)
            
        except Exception as e:
            logger.error(f"Payment callback error: {e}")
            await callback.message.edit_text(f"❌ Ошибка оплаты: {str(e)}", 
                                           reply_markup=Keyboards.back_to_main())
        
        await callback.answer()
    
    async def process_subscription_purchase(self, callback: CallbackQuery, plan: str):
        user_id = callback.from_user.id
        
        if plan not in self.config.SUBSCRIPTION_PLANS:
            await callback.message.edit_text("❌ Неверный план подписки", 
                                           reply_markup=Keyboards.back_to_main())
            return
        
        plan_data = self.config.SUBSCRIPTION_PLANS[plan]
        amount = plan_data["price"]
        
        await callback.message.edit_text("🔄 <b>Создание счета...</b>", parse_mode="HTML")
        
        # Создаем платеж
        payment_data = await self.payment_service.create_subscription_payment(user_id, plan, amount)
        
        if not payment_data:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания счета</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        # Сохраняем активный платеж
        self.active_payments[user_id] = {
            "type": "subscription",
            "plan": plan,
            "invoice_id": payment_data["invoice_id"],
            "amount": amount,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        payment_text = f"""
💰 <b>ОПЛАТА ПОДПИСКИ</b>

📋 <b>План:</b> {plan_data['name']}
💵 <b>Сумма:</b> ${amount}
⏰ <b>Счет действителен:</b> 1 час

🔗 <b>Ссылка для оплаты:</b>
<code>{payment_data['pay_url']}</code>

📝 <b>Инструкция:</b>
1. Нажмите на ссылку выше
2. Оплатите счет в USDT
3. Вернитесь в бот
4. Нажмите "Проверить оплату"

🎁 <b>После оплаты подписка активируется автоматически!</b>
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти к оплате", url=payment_data['pay_url'])],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_payment_{payment_data['invoice_id']}")],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="buy_subscription")]
        ])
        
        await callback.message.edit_text(payment_text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
    
    async def process_single_report_purchase(self, callback: CallbackQuery, report_type: str):
        user_id = callback.from_user.id
        
        report_type_clean = report_type.replace("buy_single_", "")
        
        if report_type_clean not in self.config.PAY_PER_USE:
            await callback.message.edit_text("❌ Неверный тип жалобы", 
                                           reply_markup=Keyboards.back_to_main())
            return
        
        amount = self.config.PAY_PER_USE[report_type_clean]
        
        await callback.message.edit_text("🔄 <b>Создание счета...</b>", parse_mode="HTML")
        
        # Создаем платеж
        payment_data = await self.payment_service.create_single_report_payment(user_id, report_type_clean, amount)
        
        if not payment_data:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания счета</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        # Сохраняем активный платеж
        self.active_payments[user_id] = {
            "type": "single_report",
            "report_type": report_type_clean,
            "invoice_id": payment_data["invoice_id"],
            "amount": amount,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        type_names = {
            "session": "1 жалоба (сессии)",
            "email": "1 жалоба (почта)",
            "combo": "1 жалоба (комбо)",
            "dsa": "1 DSA жалоба",
            "nuke": "1 снос сессий"
        }
        
        payment_text = f"""
💰 <b>ПОКУПКА ЖАЛОБЫ</b>

📋 <b>Тип:</b> {type_names.get(report_type_clean, 'услуга')}
💵 <b>Сумма:</b> ${amount}
⏰ <b>Счет действителен:</b> 1 час

🔗 <b>Ссылка для оплаты:</b>
<code>{payment_data['pay_url']}</code>

🎁 <b>После оплаты жалоба добавится в баланс!</b>
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти к оплате", url=payment_data['pay_url'])],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_payment_{payment_data['invoice_id']}")],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="buy_single_reports")]
        ])
        
        await callback.message.edit_text(payment_text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
    
    async def check_payment_status(self, callback: CallbackQuery):
        user_id = callback.from_user.id
        invoice_id = callback.data.replace("check_payment_", "")
        
        await callback.message.edit_text("🔄 <b>Проверка статуса оплаты...</b>", parse_mode="HTML")
        
        try:
            is_paid, invoice = await self.payment_service.check_payment_status(invoice_id)
            
            if is_paid and invoice:
                amount = float(invoice.get("amount", 0))
                
                # Пополняем баланс пользователя
                self.db.update_user_balance(user_id, amount)
                
                # Получаем обновленные данные пользователя
                user = self.db.get_user(user_id)
                new_balance = user[2] if user else amount
                
                success_text = f"""
🎉 <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>

✅ <b>Баланс пополнен</b>
💵 <b>Сумма:</b> ${amount:.2f}
💰 <b>Новый баланс:</b> ${new_balance:.2f}

🚀 <b>Теперь вы можете приобрести подписку или отдельные жалобы!</b>
                """
                
                await callback.message.edit_text(
                    success_text, 
                    parse_mode="HTML",
                    reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
                )
                
                # Удаляем из активных платежей
                if user_id in self.active_payments:
                    del self.active_payments[user_id]
                    
            else:
                payment_text = f"""
⏳ <b>ОЖИДАНИЕ ОПЛАТЫ</b>

❌ <b>Оплата еще не поступила</b>

💡 Если вы оплатили, подождите 2-3 минуты
🔄 Проверьте снова через некоторое время
                """
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_payment_{invoice_id}")],
                    [InlineKeyboardButton(text="💰 Баланс", callback_data="balance_menu")],
                    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
                ])
                
                await callback.message.edit_text(payment_text, parse_mode="HTML", reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"Payment check error: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при проверке оплаты",
                reply_markup=Keyboards.back_to_main()
            )

# Создаем экземпляр обработчика
payment_handlers = None

def setup_payment_handlers(bot, db, config):
    """Инициализация платежных обработчиков"""
    global payment_handlers
    payment_handlers = PaymentHandlers(bot, db, config)
    return payment_handlers

# Регистрируем обработчики
@router.callback_query(F.data.startswith("buy_basic_"))
@router.callback_query(F.data.startswith("buy_premium_")) 
@router.callback_query(F.data.startswith("buy_nuke_"))
async def subscription_purchase_callback(callback: CallbackQuery, state: FSMContext):
    if payment_handlers:
        await payment_handlers.process_subscription_purchase(callback, callback.data)

@router.callback_query(F.data.startswith("buy_single_"))
async def single_report_purchase_callback(callback: CallbackQuery, state: FSMContext):
    if payment_handlers:
        await payment_handlers.process_single_report_purchase(callback, callback.data)

@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_callback(callback: CallbackQuery, state: FSMContext):
    if payment_handlers:
        await payment_handlers.check_payment_status(callback)