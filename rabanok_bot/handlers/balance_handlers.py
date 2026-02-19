from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from services.balance_service import BalanceService
from services.payment_service import PaymentService
from utils.keyboards import Keyboards
from utils.states import UserStates
from core.database import Database
from core.config import Config
import logging
import sqlite3

router = Router()
logger = logging.getLogger(__name__)

class BalanceHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.balance_service = BalanceService(db)
        self.payment_service = PaymentService(Config.CRYPTOBOT_TOKEN)
        self.keyboards = Keyboards()
        
        # Регистрируем все хендлеры
        self._register_handlers()

    def _register_handlers(self):
        """Регистрация всех хендлеров"""
        # Callback хендлеры
        router.callback_query.register(self.show_balance_menu, F.data == "balance_menu")
        router.callback_query.register(self.start_deposit, F.data == "deposit_balance")
        router.callback_query.register(self.withdraw_referral_balance, F.data == "withdraw_referral")
        router.callback_query.register(self.show_transaction_history, F.data == "transaction_history")
        router.callback_query.register(self.show_balance_shop, F.data == "balance_shop")
        router.callback_query.register(self.check_payment_status, F.data.startswith("check_payment_"))
        
        # Message хендлеры
        router.message.register(self.process_deposit_amount, UserStates.waiting_deposit_amount)

    def _get_user_balance_data(self, user_id: int) -> tuple:
        """Получить данные о балансе пользователя из базы"""
        user = self.db.get_user(user_id)
        if user:
            return float(user[2]), float(user[3]), int(user[4])  # balance, referral_balance, referrals
        return 0.0, 0.0, 0

    async def show_balance_menu(self, callback: CallbackQuery):
        """Показать меню баланса с реальными данными из базы"""
        user_id = callback.from_user.id
        
        # Получаем реальные данные из базы
        balance, ref_balance, referrals_count = self._get_user_balance_data(user_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit_balance")],
            [InlineKeyboardButton(text="💸 Вывести реферальные", callback_data="withdraw_referral")],
            [InlineKeyboardButton(text="📊 История операций", callback_data="transaction_history")],
            [InlineKeyboardButton(text="🛒 Магазин", callback_data="balance_shop")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
        ])
        
        balance_text = f"""
💰 <b>ВАШ БАЛАНС</b>

💵 <b>Основной:</b> ${balance:.2f}
🎁 <b>Реферальный:</b> ${ref_balance:.2f}
👥 <b>Рефералов:</b> {referrals_count}

💡 <b>Реферальный баланс можно вывести с комиссией 10%</b>
        """
        
        await callback.message.edit_text(
            balance_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def start_deposit(self, callback: CallbackQuery, state: FSMContext):
        """Начать пополнение баланса"""
        await state.set_state(UserStates.waiting_deposit_amount)
        min_deposit = Config.BALANCE_CONFIG["min_deposit"]
        
        await callback.message.edit_text(
            f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
            f"Введите сумму в USD для пополнения:\n"
            f"<b>Минимальная сумма:</b> ${min_deposit}\n\n"
            f"<i>Пример: 5.50</i>",
            parse_mode="HTML",
            reply_markup=self.keyboards.back_to_balance()
        )

    async def process_deposit_amount(self, message: Message, state: FSMContext):
        """Обработать сумму пополнения и создать реальный платеж"""
        try:
            amount = float(message.text)
            min_deposit = Config.BALANCE_CONFIG['min_deposit']
            
            if amount < min_deposit:
                await message.answer(
                    f"❌ <b>Сумма меньше минимальной!</b>\n\n"
                    f"Минимальное пополнение: <b>${min_deposit}</b>\n"
                    f"Вы ввели: <b>${amount:.2f}</b>",
                    parse_mode="HTML",
                    reply_markup=self.keyboards.back_to_balance()
                )
                return

            # Создаем реальный инвойс в CryptoBot
            logger.info(f"Creating invoice for user {message.from_user.id} amount ${amount}")
            
            invoice = await self.payment_service.create_invoice(
                user_id=message.from_user.id,
                amount=amount,
                description=f"Пополнение баланса RABANOK на ${amount:.2f}"
            )
            
            if invoice and 'invoice_id' in invoice and 'pay_url' in invoice:
                # Сохраняем платеж в базу
                self.db.add_payment(message.from_user.id, amount, "balance", invoice['invoice_id'])
                
                await message.answer(
                    f"💳 <b>СЧЕТ НА ОПЛАТУ</b>\n\n"
                    f"💵 <b>Сумма:</b> ${amount:.2f}\n"
                    f"📊 <b>Статус:</b> Ожидание оплаты\n"
                    f"🆔 <b>ID счета:</b> <code>{invoice['invoice_id']}</code>\n\n"
                    f"⚡ После оплаты нажмите \"Проверить оплату\"",
                    parse_mode="HTML",
                    reply_markup=self.keyboards.payment_keyboard(invoice['invoice_id'], invoice['pay_url']),
                    disable_web_page_preview=True
                )
                logger.info(f"Invoice created successfully: {invoice['invoice_id']}")
            else:
                logger.error(f"Failed to create invoice for user {message.from_user.id}")
                await message.answer(
                    "❌ <b>Ошибка создания счета</b>\n\n"
                    "Попробуйте позже или обратитесь в поддержку",
                    parse_mode="HTML",
                    reply_markup=self.keyboards.back_to_balance()
                )
            
            await state.clear()
            
        except ValueError:
            await message.answer(
                "❌ <b>Неверный формат суммы!</b>\n\n"
                "Введите число, например: <code>5.50</code>",
                parse_mode="HTML",
                reply_markup=self.keyboards.back_to_balance()
            )
        except Exception as e:
            logger.error(f"Error in process_deposit_amount: {e}")
            await message.answer(
                "❌ <b>Произошла ошибка</b>\n\n"
                "Попробуйте позже",
                parse_mode="HTML",
                reply_markup=self.keyboards.back_to_balance()
            )

    async def withdraw_referral_balance(self, callback: CallbackQuery):
        """Реальный вывод реферального баланса с комиссией 10%"""
        user_id = callback.from_user.id
        
        # Используем метод из balance_service
        success, amount_transferred, commission = self.balance_service.transfer_referral_to_main(user_id)
        
        if not success:
            await callback.message.edit_text(
                "❌ <b>Нет средств для вывода</b>\n\n"
                "На вашем реферальном балансе нет средств",
                parse_mode="HTML",
                reply_markup=self.keyboards.back_to_balance()
            )
            return

        # Получаем обновленный баланс
        balance, _, _ = self._get_user_balance_data(user_id)
        
        await callback.message.edit_text(
            f"✅ <b>РЕФЕРАЛЬНЫЙ БАЛАНС ВЫВЕДЕН</b>\n\n"
            f"💵 <b>Сумма вывода:</b> ${amount_transferred + commission:.2f}\n"
            f"📊 <b>Комиссия (10%):</b> ${commission:.2f}\n"
            f"💰 <b>Зачислено:</b> ${amount_transferred:.2f}\n\n"
            f"💎 <b>Новый основной баланс:</b> ${balance:.2f}",
            parse_mode="HTML",
            reply_markup=self.keyboards.back_to_balance()
        )

    async def show_transaction_history(self, callback: CallbackQuery):
        """Показать реальную историю транзакций из базы"""
        user_id = callback.from_user.id
        
        transactions = self.db.get_transactions(user_id, 10)
        
        if not transactions:
            await callback.message.edit_text(
                "📊 <b>ИСТОРИЯ ОПЕРАЦИЙ</b>\n\n"
                "Транзакций пока нет",
                parse_mode="HTML",
                reply_markup=self.keyboards.back_to_balance()
            )
            return
        
        text = "📊 <b>ПОСЛЕДНИЕ ОПЕРАЦИИ:</b>\n\n"
        for trans in transactions:
            trans_type, amount, description, created_at = trans
            
            type_emoji = "📥" if trans_type in ["deposit", "referral_bonus"] else "📤"
            amount_color = "🟢" if amount > 0 else "🔴"
            amount_text = f"+${amount:.2f}" if amount > 0 else f"${amount:.2f}"
            
            text += f"{type_emoji} {amount_color} <b>{amount_text}</b>\n"
            text += f"   📝 {description}\n"
            text += f"   ⏰ {created_at[:16]}\n\n"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=self.keyboards.back_to_balance()
        )

    async def show_balance_shop(self, callback: CallbackQuery):
        """Показать магазин за баланс с реальными ценами"""
        user_id = callback.from_user.id
        balance, _, _ = self._get_user_balance_data(user_id)
        
        # Используем реальные цены из конфига
        report_prices = Config.BALANCE_PRICES["reports"]
        subscription_prices = Config.BALANCE_PRICES["subscriptions"]
        
        text = (
            f"🛒 <b>МАГАЗИН ЗА БАЛАНС</b>\n\n"
            f"💰 <b>Ваш баланс:</b> ${balance:.2f}\n\n"
            f"<b>📦 Пакеты жалоб:</b>\n"
            f"• 1 жалоба - ${report_prices['single']:.2f}\n"
            f"• 10 жалоб - ${report_prices['pack_10']:.2f}\n"
            f"• 50 жалоб - ${report_prices['pack_50']:.2f}\n"
            f"• 100 жалоб - ${report_prices['pack_100']:.2f}\n\n"
            f"<b>🎫 Подписки:</b>\n"
            f"• BASIC 1 день - ${subscription_prices['basic_1day']:.2f}\n"
            f"• PREMIUM 1 день - ${subscription_prices['premium_1day']:.2f}\n"
            f"• NUKE 1 день - ${subscription_prices['nuke_1day']:.2f}\n\n"
            f"💡 <b>Все покупки списываются с вашего баланса</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Пакеты жалоб", callback_data="buy_single_reports")],
            [InlineKeyboardButton(text="🎫 Подписки", callback_data="buy_subscription")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit_balance")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="balance_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    async def check_payment_status(self, callback: CallbackQuery):
        """Проверить статус платежа и зачислить средства"""
        invoice_id = callback.data.replace("check_payment_", "")
        user_id = callback.from_user.id
        
        await callback.message.edit_text("🔄 <b>Проверка оплаты...</b>", parse_mode="HTML")
        
        try:
            invoice = await self.payment_service.check_invoice(invoice_id)
            
            if invoice and invoice.get('status') == 'paid':
                amount = float(invoice.get('amount', 0))
                
                # Зачисляем средства на баланс через balance_service
                if self.balance_service.add_balance(user_id, amount, "Пополнение через CryptoBot"):
                    self.db.update_payment_status(invoice_id, 'completed')
                    
                    new_balance = self.balance_service.get_balance(user_id)
                    
                    success_text = f"""
✅ <b>ПЛАТЕЖ ПОДТВЕРЖДЕН!</b>

💵 <b>Зачислено:</b> ${amount:.2f}
💰 <b>Текущий баланс:</b> ${new_balance:.2f}

🎉 Теперь вы можете покупать подписки и пакеты жалоб!
                    """
                    
                    await callback.message.edit_text(
                        success_text,
                        parse_mode="HTML",
                        reply_markup=self.keyboards.balance_menu()
                    )
                    logger.info(f"Payment confirmed for user {user_id}: ${amount}")
                else:
                    await callback.message.edit_text(
                        "❌ <b>Ошибка зачисления средств</b>\n\n"
                        "Обратитесь в поддержку",
                        parse_mode="HTML",
                        reply_markup=self.keyboards.back_to_balance()
                    )
            
            else:
                payment_text = """
❌ <b>ОПЛАТА НЕ НАЙДЕНА</b>

⚡ Если вы уже оплатили, подождите 2-3 минуты
🔄 Или проверьте снова через некоторое время
                """
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_payment_{invoice_id}")],
                    [InlineKeyboardButton(text="💰 Баланс", callback_data="balance_menu")]
                ])
                
                await callback.message.edit_text(
                    payment_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
        
        except Exception as e:
            logger.error(f"Payment check error: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при проверке оплаты",
                reply_markup=self.keyboards.back_to_balance()
            )

# Создаем экземпляр для импорта (будет инициализирован позже)
balance_handlers = None

def setup_balance_handlers(db: Database):
    """Инициализация баланс хендлеров"""
    global balance_handlers
    balance_handlers = BalanceHandlers(db)
    return router