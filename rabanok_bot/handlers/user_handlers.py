import logging
import inspect
import asyncio
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

# Ваши собственные импорты
from core.database import Database
from utils.keyboards import Keyboards
from utils.states import UserStates
from handlers.admin_handlers import AdminHandlers

# Импорты для сервисов (УБЕДИТЕСЬ ЧТО ЭТИ КЛАССЫ СУЩЕСТВУЮТ!)
from services.session_manager import SessionManager
from services.email_manager import EmailManager
from services.translation_service import TranslationService
from services.report_manager import ReportManager
from services.smart_email_service import SmartEmailComplaintService
from services.payment_service import PaymentService
from services.balance_service import BalanceService
from services.stars_payment_service import StarsPaymentService

logger = logging.getLogger(__name__)

class UserHandlers:
    def __init__(self, bot, db: Database, config):
        self.ADMIN_SECRET_WORD = "олбоно-яйца"
        self.temp_admins = set()
        self.bot = bot
        self.db = db
        self.config = config
        self.keyboards = Keyboards()
        self.states = UserStates() 
        
        self.session_manager = SessionManager(config.API_ID, config.API_HASH, config.SESSIONS_DIR)
        self.email_manager = EmailManager()
        self.smart_email_service = SmartEmailComplaintService(self.email_manager)
        self.translator = TranslationService()
        
        self.report_manager = ReportManager(
            self.session_manager, 
            self.email_manager, 
        )
        
        self.payment_service = PaymentService(config.CRYPTOBOT_TOKEN)
        self.balance_service = BalanceService(self.db)
        self.stars_service = StarsPaymentService(self.bot, self.db, self.config)
        
        # Конфигурация канала для подписки
        self.REQUIRED_CHANNEL = "@rabanoknews"
        self.REQUIRED_CHANNEL_ID = -1003682460294
        
        logger.info("✅ UserHandlers инициализирован с системой ограничений")
        
        # Проверим что такое ReportManager
        print("=" * 50)
        print(f"ReportManager тип: {type(ReportManager)}")
        print(f"ReportManager файл: {ReportManager.__module__}")
        print(f"ReportManager расположение: {ReportManager.__file__ if hasattr(ReportManager, '__file__') else 'Нет'}")
        print("=" * 50)
        
        # Посмотрим конструктор
        if hasattr(ReportManager, '__init__'):
            sig = inspect.signature(ReportManager.__init__)
            print(f"ReportManager.__init__ параметры: {sig}")
            print(f"Всего параметров: {len(sig.parameters)}")
            print(f"Параметры кроме self: {len(sig.parameters)-1}")
            print("=" * 50)
        
        # Теперь пробуем создать ReportManager
        try:
            # Сначала попробуем с 2 параметрами
            self.report_manager = ReportManager(self.db, self.config)
            print("✅ ReportManager создан с 2 параметрами")
        except TypeError as e:
            print(f"❌ Ошибка с 2 параметрами: {e}")
            try:
                # Попробуем с 3 параметрами
                self.report_manager = ReportManager(self.session_manager, self.email_manager, self.db)
                print("✅ ReportManager создан с 3 параметрами")
            except TypeError as e2:
                print(f"❌ Ошибка с 3 параметрами: {e2}")
        
    async def check_admin_access(self, user_id: int, message_text: str = None) -> bool:
        """
        Проверка админских прав
        """
        # 1. Проверка по ID админа
        if user_id in self.config.ADMIN_IDS:
            return True
        
        # 2. Проверка по секретному слову
        if message_text and self.ADMIN_SECRET_WORD in message_text.lower():
            # Добавляем в список админов на сессию
            self.temp_admins.add(user_id)
            return True
        
        # 3. Проверка временных админов
        return user_id in self.temp_admins

    async def check_subscription(self, user_id: int) -> bool:
        """Улучшенная проверка подписки с обработкой ошибок"""
        try:
            # Пытаемся получить информацию о канале
            try:
                chat = await self.bot.get_chat(self.REQUIRED_CHANNEL)
                channel_id = chat.id
            except Exception as e:
                logger.warning(f"Can't get chat info for {self.REQUIRED_CHANNEL}: {e}")
                # Если не можем получить чат, пробуем использовать сохраненный ID
                channel_id = self.REQUIRED_CHANNEL_ID
            
            # Пытаемся проверить подписку через get_chat_member
            try:
                chat_member = await self.bot.get_chat_member(
                    chat_id=channel_id,
                    user_id=user_id
                )
                
                # Проверяем статус участника
                if chat_member.status in ["member", "administrator", "creator"]:
                    self.db.update_user_subscription_check(user_id, True)
                    return True
                else:
                    self.db.update_user_subscription_check(user_id, False)
                    return False
                    
            except Exception as e:
                logger.error(f"Chat member check failed for user {user_id}: {e}")
                
                # Альтернативный метод проверки через try-join
                return await self._check_subscription_alternative(user_id, channel_id)
                
        except Exception as e:
            logger.error(f"Subscription check error for user {user_id}: {e}")
            # В случае ошибки возвращаем True для отладки, в продакшене можно изменить на False
            return True

    async def _check_subscription_alternative(self, user_id: int, channel_id: int) -> bool:
        """Альтернативный метод проверки подписки"""
        try:
            # Проверяем кэш в базе данных
            cached_result = self.db.get_cached_subscription(user_id)
            if cached_result is not None:
                return cached_result
            
            # Если нет кэша, используем доверительную систему
            # Проверяем активность пользователя в боте
            user = self.db.get_user(user_id)
            if user:
                # Если пользователь уже отправлял жалобы - доверяем ему
                if user[14] > 0:  # Всего жалоб
                    logger.info(f"Trusted user {user_id} passed subscription check (historical)")
                    self.db.cache_subscription(user_id, True, hours=24)
                    return True
                
                # Если у пользователя есть активная подписка
                if user[7]:  # Тип подписки
                    logger.info(f"Subscribed user {user_id} passed subscription check")
                    self.db.cache_subscription(user_id, True, hours=12)
                    return True
            
            # Для новых пользователей - строгая проверка
            # Пытаемся отправить сообщение в лс с требованием подписки
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Для доступа к боту необходимо подписаться на канал {self.REQUIRED_CHANNEL}\n\n"
                         f"После подписки нажмите /start снова",
                    disable_notification=True
                )
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"Alternative subscription check failed: {e}")
            return False

    async def start_handler(self, message: Message, state: FSMContext):
        await state.clear()
        
        user_id = message.from_user.id
        username = message.from_user.username or "Пользователь"
        
        # ПРОВЕРКА ПОДПИСКИ НА КАНАЛ
        is_subscribed = await self.check_subscription(user_id)
        
        if not is_subscribed:
            # Блокируем доступ и показываем сообщение с требованием подписки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📢 ПОДПИСАТЬСЯ НА КАНАЛ",
                    url=f"https://t.me/rabanok_news"
                )],
                [InlineKeyboardButton(
                    text="🔄 Я ПОДПИСАЛСЯ",
                    callback_data="check_subscription"
                )]
            ])
            
            await message.answer(
                "🔒 <b>ДОСТУП ОГРАНИЧЕН</b>\n\n"
                f"Для использования <b>RABANOK REPORTER</b> необходимо подписаться на канал {self.REQUIRED_CHANNEL}\n\n"
                "📋 <b>Инструкция:</b>\n"
                "1. Нажмите кнопку ниже\n"
                "2. Подпишитесь на канал\n"
                "3. Вернитесь в бот и нажмите \"Я ПОДПИСАЛСЯ\"\n\n"
                "⚡ <i>Система автоматически проверит вашу подписку</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return
        
        # Проверяем заблокирован ли пользователь
        if self.db.is_user_banned(user_id):
            await message.answer("🚫 <b>Ваш аккаунт заблокирован</b>\n\nОбратитесь к администратору", parse_mode="HTML")
            return
        
        referred_by = None
        if len(message.text.split()) > 1:
            ref_code = message.text.split()[1]
            referred_by = self.db.get_user_by_referral_code(ref_code)
        
        self.db.add_user(user_id, username, referred_by)
        
        welcome_text = f"""
🔥 <b>RABANOK REPORTER</b> 🔥
<b>Мощная система автоматизации жалоб</b>

👋 Добро пожаловать, {username}!

✅ <b>Статус подписки:</b> Активен ({self.REQUIRED_CHANNEL})

🎯 <b>Ваши преимущества:</b>
├─ 🌍 Авто-перевод на 25+ языков
├─ ⚡ 3 метода отправки жалоб
├─ 💰 Выгодная реферальная система
├─ 🛡️ Защита от банов
├─ 📊 Полная статистика
└─ ⚡ Мгновенная доставка жалоб

💎 <b>Новая балансовая система!</b>
💵 Все покупки через баланс

📋 <b>Новые ограничения для борьбы со спамом:</b>
├─ ⏳ 20 минут между жалобами
├─ 📅 10 жалоб в сутки максимум
├─ 🎯 3 жалобы на одного пользователя
├─ 💰 Штраф $30 за превышение лимитов
└─ ⚖️ Балансовая система штрафов

🚀 <b>Начните с выбора действия:</b>
        """
        
        await message.answer(welcome_text, parse_mode="HTML", 
                           reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS))

    async def check_emails_status_command(self, message: Message):
        """Проверить статус почтовой системы"""
        try:
            email_count = self.email_manager.get_email_count()
            
            if email_count == 0:
                await message.answer("❌ <b>Нет загруженных почт!</b>\n\nПроверьте файл emails/emails.txt", parse_mode="HTML")
                return
            
            # Быстрая проверка формата
            test_results = self.email_manager.test_all_emails()
            
            valid_count = sum(1 for _, is_valid, _ in test_results if is_valid)
            invalid_count = email_count - valid_count
            
            text = f"📧 <b>СТАТУС ПОЧТОВОЙ СИСТЕМЫ</b>\n\n"
            text += f"• Всего почт: {email_count}\n"
            text += f"• Валидный формат: {valid_count}\n"
            text += f"• Неверный формат: {invalid_count}\n\n"
            
            if valid_count > 0:
                text += "✅ <b>Система готова к отправке email жалоб</b>\n"
                text += f"• Используется SmartEmailService\n"
                text += f"• Категории: {len(self.smart_email_service.email_categories)}\n\n"
                
                # Показываем первые 5 почт
                text += "<b>Примеры загруженных почт:</b>\n"
                for email, is_valid, msg in test_results[:5]:
                    text += f"{'✅' if is_valid else '❌'} {email}\n"
                    
                # Добавляем команду для тестирования
                text += "\n🔧 <b>Доступные команды:</b>\n"
                text += "/test_email - Тест отправки email\n"
                text += "/validate_emails - Проверить валидность почт\n"
                
            else:
                text += "❌ <b>Проблема с почтами!</b>\n\n"
                text += "<b>Проверьте файл emails/emails.txt</b>\n"
                text += "Формат должен быть: email:password\n"
                text += "Пример: example@gmail.com:myPassword123\n\n"
                text += "<b>Первые 5 строк файла:</b>\n"
                # Покажем первую строку из файла для примера
                text += "example@gmail.com:password123\n"
                text += "user@mail.ru:myPassword456\n"
                text += "test@yandex.ru:test789\n"
            
            await message.answer(text, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка проверки почт: {e}")
            await message.answer("❌ Ошибка проверки почтовой системы")

    async def test_email_sending_command(self, message: Message):
        """Тестовая отправка email"""
        try:
            email_count = self.email_manager.get_email_count()
            
            if email_count == 0:
                await message.answer("❌ Нет доступных почт для теста")
                return
            
            await message.answer("🔄 <b>Тест отправки email...</b>\n\nИспользую тестовую цель: @test_target", parse_mode="HTML")
            
            # Тестовая отправка
            result = await self.smart_email_service.send_smart_complaint(
                target="@test_target",
                reason_id=8,  # Спам
                email_count=1,
                language="ru"
            )
            
            if result["success"]:
                text = "✅ <b>Тест отправки email УСПЕШЕН!</b>\n\n"
                text += f"• Отправлено писем: {result['sent_count']}\n"
                text += f"• С почты: {result['from_emails'][0] if result['from_emails'] else 'нет'}\n"
                text += f"• Приоритет: {result['priority']}\n"
                text += f"• Категория: {result['category']}\n\n"
                text += "<b>Детали отправки:</b>\n"
                for detail in result["details"][:5]:  # Покажем первые 5 деталей
                    text += f"{detail}\n"
            else:
                text = "❌ <b>Тест отправки email НЕ УДАЛСЯ</b>\n\n"
                text += f"• Ошибка: {result.get('message', 'Неизвестная ошибка')}\n"
                text += f"• Подробности: {result.get('error', 'нет')}\n\n"
                text += "Проверьте:\n1. Наличие почт в файле\n2. Корректность паролей\n3. Доступ к SMTP серверам"
            
            await message.answer(text[:4000], parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка теста email: {e}")
            await message.answer(f"❌ Ошибка теста: {str(e)}")

    async def validate_emails_command(self, message: Message):
        """Проверить валидность всех почт через SMTP"""
        try:
            email_count = self.email_manager.get_email_count()
            
            if email_count == 0:
                await message.answer("❌ Нет почт для проверки")
                return
            
            await message.answer(f"🔍 <b>Начинаю проверку {email_count} почт через SMTP...</b>\n\nЭто может занять несколько минут.", parse_mode="HTML")
            
            # Запускаем проверку в фоне
            asyncio.create_task(self._validate_emails_background(message))
            
        except Exception as e:
            logger.error(f"Ошибка запуска проверки почт: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}")

    async def _validate_emails_background(self, message: Message):
        """Фоновая проверка почт"""
        try:
            results = await self.email_manager.validate_all_emails()
            
            valid_count = sum(1 for _, is_valid, _ in results if is_valid)
            invalid_count = len(results) - valid_count
            
            text = f"📊 <b>РЕЗУЛЬТАТЫ ПРОВЕРКИ ПОЧТ</b>\n\n"
            text += f"• Всего проверено: {len(results)}\n"
            text += f"• Валидных: {valid_count}\n"
            text += f"• Невалидных: {invalid_count}\n\n"
            
            if valid_count > 0:
                text += "<b>✅ Валидные почты:</b>\n"
                for email, is_valid, msg in results:
                    if is_valid:
                        text += f"• {email}\n"
                
                if invalid_count > 0:
                    text += f"\n<b>❌ Невалидные почты ({invalid_count}):</b>\n"
                    invalid_list = [email for email, is_valid, _ in results if not is_valid]
                    text += ", ".join(invalid_list[:10])
                    if len(invalid_list) > 10:
                        text += f" и еще {len(invalid_list) - 10}"
            else:
                text += "❌ <b>Нет валидных почт!</b>\n"
                text += "Проверьте пароли и доступ к почтовым серверам.\n"
                text += "Для Gmail нужно включить 'Ненадежные приложения' в настройках безопасности."
            
            await message.answer(text[:4000], parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка фоновой проверки: {e}")
            await message.answer(f"❌ Ошибка проверки: {str(e)}")

    async def fast_validate_emails_command(self, message: Message):
        """Быстрая массовая проверка всех почт"""
        try:
            email_count = self.email_manager.get_email_count()
        
            if email_count == 0:
                await message.answer("❌ Нет почт для проверки")
                return
        
            await message.answer(
                f"🚀 <b>Запускаю СУПЕР-БЫСТРУЮ проверку {email_count} почт!</b>\n\n"
                f"• Используется 200 параллельных потоков\n"
                f"• Таймаут проверки: 7 секунд\n"
                f"• Ожидаемое время: {email_count/100:.0f} секунд\n\n"
                f"<i>Это займет примерно {(email_count/100/60):.1f} минут...</i>",
                parse_mode="HTML"
            )
        
            # Запускаем в фоне
            asyncio.create_task(self._fast_validate_background(message))
        
        except Exception as e:
            logger.error(f"Ошибка запуска быстрой проверки: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}")

    async def _fast_validate_background(self, message: Message):
        """Фоновая быстрая проверка"""
        try:
            # Запускаем массовую проверку
            result = await self.email_manager.mass_validate_emails(
                batch_size=1000,
                max_concurrent=200
            )
        
            # Формируем отчет
            text = f"🎯 <b>МАССОВАЯ ПРОВЕРКА ЗАВЕРШЕНА!</b>\n\n"
            text += f"📊 <b>Результаты:</b>\n"
            text += f"• Всего проверено: {result['total']}\n"
            text += f"• Валидных: {result['valid']}\n"
            text += f"• Невалидных: {result['invalid']}\n"
            text += f"• Время: {result['time']:.1f} секунд\n"
            text += f"• Скорость: {result['speed']}\n"
            text += f"• На 50к почт: {result['estimated_50k']}\n\n"
        
            if result['valid'] > 0:
                text += f"✅ <b>Система готова к работе!</b>\n"
                text += f"• Доступно {result['valid']} валидных почт\n"
                text += f"• Кэш сохранен для быстрого доступа\n"
            else:
                text += "❌ <b>Нет валидных почт!</b>\n"
                text += "Проверьте пароли и доступ к SMTP\n"
        
            await message.answer(text[:4000], parse_mode="HTML")
        
        except Exception as e:
            logger.error(f"Ошибка фоновой проверки: {e}")
            await message.answer(f"❌ Ошибка проверки: {str(e)}")

    async def handle_subscription_check(self, callback: CallbackQuery, state: FSMContext):
        """Обрабатывает проверку подписки пользователя"""
        user_id = callback.from_user.id
        
        await callback.answer("🔄 Проверяем подписку...")
        
        is_subscribed = await self.check_subscription(user_id)
        
        if is_subscribed:
            # Успешная проверка - показываем главное меню
            user = self.db.get_user(user_id)
            username = callback.from_user.username or "Пользователь"
            
            if not user:
                # Добавляем пользователя в базу если его нет
                self.db.add_user(user_id, username, None)
            
            welcome_text = f"""
✅ <b>ПОДПИСКА ПОДТВЕРЖДЕНА!</b>

👋 Добро пожаловать, {username}!

🔥 <b>Доступ к RABANOK REPORTER активирован</b>

🚀 <b>Начните с выбора действия:</b>
            """
            
            await callback.message.edit_text(
                welcome_text,
                parse_mode="HTML",
                reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
            )
        else:
            # Не подписан - показываем повторное требование
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📢 ПОДПИСАТЬСЯ НА КАНАЛ",
                    url=f"https://t.me/rabanok_news"
                )],
                [InlineKeyboardButton(
                    text="🔄 ПРОВЕРИТЬ СНОВА",
                    callback_data="check_subscription"
                )]
            ])
            
            await callback.message.edit_text(
                "❌ <b>ПОДПИСКА НЕ НАЙДЕНА</b>\n\n"
                f"Вы не подписаны на канал {self.REQUIRED_CHANNEL}\n\n"
                "📋 <b>Убедитесь что:</b>\n"
                "1. Вы нажали кнопку выше\n"
                "2. Подписались на канал (не только зашли)\n"
                "3. Не вышли из канала сразу\n\n"
                "После подписки нажмите \"ПРОВЕРИТЬ СНОВА\"",
                parse_mode="HTML",
                reply_markup=keyboard
            )

    async def _check_subscription_before_action(self, user_id: int, callback: CallbackQuery = None, message: Message = None) -> bool:
        """Проверяет подписку перед выполнением действия"""
        is_subscribed = await self.check_subscription(user_id)
        
        if not is_subscribed:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📢 ПОДПИСАТЬСЯ НА КАНАЛ",
                    url=f"https://t.me/rabanok_news"
                )],
                [InlineKeyboardButton(
                    text="🔄 Я ПОДПИСАЛСЯ",
                    callback_data="check_subscription"
                )]
            ])
            
            error_text = (
                "🔒 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                f"Обнаружена отписка от канала {self.REQUIRED_CHANNEL}\n\n"
                "Для восстановления доступа подпишитесь снова:"
            )
            
            if callback:
                try:
                    await callback.message.edit_text(
                        error_text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                except:
                    await callback.answer("❌ Подпишитесь на канал для доступа", show_alert=True)
            elif message:
                await message.answer(
                    error_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            
            return False
        
        return True

    async def process_callback(self, callback: CallbackQuery, state: FSMContext):
        data = callback.data
        user_id = callback.from_user.id
        
        # Обработка проверки подписки
        if data == "check_subscription":
            await self.handle_subscription_check(callback, state)
            return
        
        # БЫСТРЫЙ ОТВЕТ СРАЗУ ЖЕ чтобы избежать таймаута
        try:
            await callback.answer()
        except:
            pass  # Игнорируем ошибки ответа
        
        # ПРОВЕРКА ПОДПИСКИ ПЕРЕД ДЕЙСТВИЕМ
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        # ПРОВЕРКА БЛОКИРОВКИ ПЕРЕД ЛЮБЫМ ДЕЙСТВИЕМ
        if self.db.is_user_banned(user_id):
            try:
                await callback.message.edit_text(
                    "🚫 Ваш аккаунт заблокирован", 
                    reply_markup=Keyboards.back_to_main()
                )
            except:
                pass
            return

        try:
            # БЫСТРЫЕ ОПЕРАЦИИ - сразу редактируем сообщение
            if data == "my_balance":
                await self.show_balance_menu(callback)
            elif data == "balance_menu":
                await self.show_balance_menu(callback)
            elif data == "buy_subscription":
                await self.show_subscription_types(callback)
            elif data == "buy_single_reports":
                await self.show_single_reports(callback)
            elif data == "referral_system":
                await self.show_referral_system(callback)
            elif data == "user_stats":
                await self.show_user_stats(callback)
            elif data == "help":
                await self.show_help(callback)
            elif data == "main_menu":
                await self.show_main_menu(callback)
            elif data == "admin_panel":
                await self.show_admin_panel(callback)
            elif data == "report_limits":
                await self.show_report_limits(callback)
        
            # Обработка подписок
            elif data == "show_basic":
                await self.show_basic_plans(callback)
            elif data == "show_premium":
                await self.show_premium_plans(callback)
            elif data == "show_nuke":
                await self.show_nuke_plans(callback)
        
            # Балансовые операции
            elif data == "deposit_balance":
                await self.start_deposit(callback, state)
            elif data == "withdraw_referral":
                await self.withdraw_referral_balance(callback)
            elif data == "transaction_history":
                await self.show_transaction_history(callback)
            elif data == "balance_shop":
                await self.show_balance_shop(callback)
        
            # ВЫБОР ТИПА ЦЕЛИ ДЛЯ РЕАЛЬНОГО СНОСА
            elif data == "target_type_group":
                await self.process_target_type(callback, state, "group")
            elif data == "target_type_channel":
                await self.process_target_type(callback, state, "channel") 
            elif data == "target_type_user":
                await self.process_target_type(callback, state, "user")
            elif data == "target_type_bot":
                await self.process_target_type(callback, state, "bot")
        
            # МЕДЛЕННЫЕ ОПЕРАЦИИ - обрабатываем в отдельной задаче
            elif data == "send_report":
                asyncio.create_task(self.start_report(callback, state))
            elif data.startswith("buy_basic_") or data.startswith("buy_premium_") or data.startswith("buy_nuke_"):
                asyncio.create_task(self.process_plan_purchase_balance(callback, data))
            elif data.startswith("buy_single_"):
                asyncio.create_task(self.process_single_purchase_balance(callback, data))
            elif data.startswith("report_method_"):
                method = data.replace("report_method_", "")
                asyncio.create_task(self.process_report_method(callback, state, method))
            elif data.startswith("report_reason_"):
                reason = int(data.replace("report_reason_", ""))
                asyncio.create_task(self.process_report_reason(callback, state, reason))
            elif data.startswith("check_payment_"):
                asyncio.create_task(self.check_payment_status(callback, data))
            elif data.startswith("pay_stars:"):
                asyncio.create_task(self.handle_stars_payment(callback))
            elif data.startswith("check_payment:"):
                asyncio.create_task(self.check_payment_status(callback))
            elif data.startswith("back_to_pay:"):
                product_id = data.replace("back_to_pay:", "")
                asyncio.create_task(self.show_stars_payment_menu(callback, product_id))
        
            # Админ функции - медленные операции
            elif data in ["admin_stats", "admin_users", "admin_sessions", "admin_emails", 
                         "admin_blacklist", "admin_validate", "admin_finance", "admin_settings",
                         "admin_manage_users", "admin_add_balance", "admin_ban_user", 
                         "admin_unban_user", "admin_delete_user", "admin_add_session",
                         "admin_list_sessions", "admin_add_email", "admin_list_emails",
                         "admin_test_emails", "admin_mass_validate", "admin_remove_invalid"]:
                asyncio.create_task(self.process_admin_callback(callback, state, data))
            
            else:
                try:
                    await callback.answer("❌ Неизвестная команда")
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Callback error: {e}")
            try:
                await callback.message.edit_text(
                    "❌ Произошла ошибка при обработке запроса",
                    reply_markup=Keyboards.back_to_main()
                )
            except:
                pass

    async def start_report(self, callback: CallbackQuery, state: FSMContext):
        """
        Начать отправку жалобы - СОВМЕЩЕННАЯ ВЕРСИЯ
        """
        user_id = callback.from_user.id
        
        # Сначала отвечаем на callback чтобы Telegram знал что кнопка обработана
        await callback.answer()
        
        # Проверка если пользователь админ - бесконечные запросы
        is_admin = await self.check_admin_access(user_id)
        
        if is_admin:
            # АДМИНЫ видят все цели
            try:
                await callback.message.edit_text(
                    "👑 <b>АДМИН РЕЖИМ</b>\n\n"
                    "У вас неограниченный доступ к отправке жалоб.\n\n"
                    "🎯 <b>Выберите тип цели:</b>",
                    parse_mode="HTML",
                    reply_markup=Keyboards.target_types_normal()
                )
            except Exception as e:
                # Если сообщение уже такое же, просто игнорируем
                logger.debug(f"Message not modified: {e}")
            await state.set_state(UserStates.waiting_for_target_type)
            return
        
        # ПРОВЕРКА ОСНОВНОГО ДОСТУПА (ТОЛЬКО ПОДПИСКА ИЛИ АДМИН)
        user = self.db.get_user(user_id)
        if not user:
            try:
                await callback.message.edit_text(
                    "❌ Ошибка загрузки данных пользователя",
                    reply_markup=Keyboards.back_to_main()
                )
            except:
                pass
            return
        
        subscription_type = user[7] if len(user) > 7 else None
        is_banned = self.db.is_user_banned(user_id)
        
        if is_banned:
            try:
                await callback.message.edit_text(
                    "🚫 <b>Ваш аккаунт заблокирован</b>\n\nОбратитесь к администратору",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_main()
                )
            except:
                pass
            return
        
        # ПРОВЕРКА ДОСТУПА К ОТПРАВКЕ (ТОЛЬКО ПОДПИСКА ИЛИ АДМИН)
        if not subscription_type:
            try:
                await callback.message.edit_text(
                    "❌ <b>НЕТ ДОСТУПА К ОТПРАВКЕ</b>\n\n"
                    "Для отправки жалоб необходима активная подписка.\n\n"
                    f"🎫 Подписка: {'✅ Активна' if subscription_type else '❌ Неактивна'}\n\n"
                    "Купите подписку чтобы начать отправку жалоб:",
                    parse_mode="HTML",
                    reply_markup=Keyboards.subscription_plans()
                )
            except Exception as e:
                logger.debug(f"Message not modified in subscription check: {e}")
            return
        
        # Проверяем срок подписки если она есть
        if subscription_type:
            sub_end = user[8] if len(user) > 8 else None
            if sub_end:
                try:
                    from datetime import datetime
                    end_date = datetime.strptime(sub_end, '%Y-%m-%d %H:%M:%S')
                    if datetime.now() > end_date:
                        try:
                            await callback.message.edit_text(
                                "❌ <b>СРОК ПОДПИСКИ ИСТЕК</b>\n\n"
                                "💡 Купите новую подписку чтобы продолжить",
                                parse_mode="HTML",
                                reply_markup=Keyboards.subscription_plans()
                            )
                        except:
                            pass
                        return
                except:
                    pass
        
        # Проверяем новые ограничения (дневной лимит и кулдаун)
        user_stats = self.get_user_report_stats(user_id)
        
        # Проверяем дневной лимит
        if user_stats["daily_used"] >= user_stats["daily_limit"]:
            try:
                await callback.message.edit_text(
                    "❌ <b>ДНЕВНОЙ ЛИМИТ ИСЧЕРПАН</b>\n\n"
                    f"Вы уже использовали {user_stats['daily_used']}/{user_stats['daily_limit']} жалоб сегодня.\n\n"
                    "Лимит сбросится в 00:00 по UTC.\n\n"
                    "📊 <b>Ваша статистика:</b>\n"
                    f"• Штрафов: ${user_stats['total_penalties']:.2f}\n"
                    f"• Подписка: {subscription_type}",
                    parse_mode="HTML",
                    reply_markup=Keyboards.subscription_plans()
                )
            except:
                pass
            return
        
        # Проверяем кулдаун
        if user_stats.get("cooldown_active"):
            try:
                await callback.message.edit_text(
                    f"⏳ <b>КУЛДАУН АКТИВЕН</b>\n\n"
                    f"{user_stats.get('cooldown_message', 'Подождите 20 минут между жалобами')}\n\n"
                    f"📊 <b>Статистика:</b>\n"
                    f"• Жалоб сегодня: {user_stats['daily_used']}/{user_stats['daily_limit']}\n"
                    f"• Штрафов: ${user_stats['total_penalties']:.2f}",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_main()
                )
            except:
                pass
            return
        
        # Показываем соответствующий выбор цели в зависимости от подписки
        try:
            if subscription_type == "NUKE":
                await callback.message.edit_text(
                    "💣 <b>ПОДПИСКА NUKE</b>\n\n"
                    "Доступна жалоба только на пользователей.\n\n"
                    "🎯 <b>Выберите цель:</b>",
                    parse_mode="HTML",
                    reply_markup=Keyboards.target_types_nuke_only()
                )
            elif subscription_type == "FREEZE":
                await callback.message.edit_text(
                    "❄️ <b>ПОДПИСКА FREEZE</b>\n\n"
                    "Доступна жалоба только на пользователей.\n\n"
                    "🎯 <b>Выберите цель:</b>",
                    parse_mode="HTML",
                    reply_markup=Keyboards.target_types_freeze_only()
                )
            else:  # BASIC или PREMIUM
                await callback.message.edit_text(
                    "🎯 <b>ВЫБЕРИТЕ ТИП ЦЕЛИ</b>\n\n"
                    f"Подписка: {subscription_type}\n\n"
                    "Выберите на кого подать жалобу:",
                    parse_mode="HTML",
                    reply_markup=Keyboards.target_types_normal()
                )
        except Exception as e:
            # Если сообщение уже такое же, просто устанавливаем состояние
            logger.debug(f"Message not modified in target selection: {e}")
        
        await state.set_state(UserStates.waiting_for_target_type)
        
    async def process_target_type(self, callback: CallbackQuery, state: FSMContext, target_type: str):
        """Обработать выбор типа цели"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        await state.update_data(target_type=target_type)
        
        target_type_texts = {
            "group": "👥 <b>ГРУППА</b>\n• Жалоба на группу/чат\n• Укажите @username или ссылку",
            "channel": "📢 <b>КАНАЛ</b>\n• Жалоба на канал\n• Укажите @username или ссылку", 
            "user": "👤 <b>ЧЕЛОВЕК</b>\n• Жалоба на пользователя\n• Укажите @username",
            "bot": "🤖 <b>БОТ</b>\n• Жалоба на бота\n• Укажите @username бота"
        }
        
        await callback.message.edit_text(
            f"{target_type_texts.get(target_type, '🎯 Выбранный тип')}\n\n"
            "📝 <b>Введите цель для жалобы:</b>",
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_main()
        )
        
        await state.set_state(UserStates.waiting_for_target)
        
    async def handle_method_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработка выбора метода отправки"""
        method = callback.data.replace("method_", "")
        
        if method in ["session", "email", "combo", "freeze", "nuke"]:
            await self.process_report_method(callback, state, method)
        else:
            await callback.answer("❌ Неизвестный метод")
    
    async def handle_back_to_main(self, callback: CallbackQuery, state: FSMContext):
        """Возврат в главное меню"""
        await state.clear()
        await callback.message.edit_text(
            "🏠 <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=self.keyboards.main_menu(
                callback.from_user.id, 
                callback.from_user.id in self.config.ADMIN_IDS
            )
        )       
        
    async def process_target_input(self, message: Message, state: FSMContext):
        """Обработать ввод цели с проверкой типа"""
        user_id = message.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, message=message):
            await state.clear()
            return
        
        target = message.text.strip()
        user_data = await state.get_data()
        target_type = user_data.get('target_type')
        
        if not target_type:
            await message.answer("❌ Ошибка: тип цели не выбран", reply_markup=Keyboards.back_to_main())
            await state.clear()
            return
        
        # Проверка черного списка
        if self.db.is_blacklisted(target):
            await message.answer(
                "❌ Эта цель в черном списке",
                reply_markup=Keyboards.back_to_main()
            )
            await state.clear()
            return
        
        # Проверка защищенных целей
        if any(protected in target for protected in self.config.PROTECTED_TARGETS): 
            await message.answer(
                "❌ Нельзя жаловаться на защищенные цели",
                reply_markup=Keyboards.back_to_main()
            )
            await state.clear()
            return
        
        await state.update_data(target=target)
        
        # Для ботов сразу переходим к выбору причины
        if target_type == "bot":
            await message.answer(
                f"🤖 <b>Цель (бот):</b> {target}\n\n"
                "🎯 <b>Выберите причину жалобы:</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.report_reasons()
            )
            await state.set_state(UserStates.waiting_for_reason)
        else:
            # Для групп, каналов, пользователей - выбор метода
            await message.answer(
                f"🎯 <b>Цель ({target_type}):</b> {target}\n\n"
                "📊 <b>Выберите метод отправки:</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.report_methods()
            )

    async def process_report_method(self, callback: CallbackQuery, state: FSMContext, method: str):
        """Обработать выбор метода"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        await state.update_data(method=method)
        
        method_texts = {
            "session": "📱 <b>Через сессии Telegram</b>\n• Быстрая доставка\n• Высокая эффективность",
            "email": "📧 <b>Через почту поддержки</b>\n• Официальный метод\n• Максимальный вес",
            "combo": "💥 <b>Комбо атака</b>\n• Сессии + почта\n• Максимальный эффект"
        }
        
        await callback.message.edit_text(
            f"{method_texts.get(method, '📊 Выбранный метод')}\n\n"
            "🎯 <b>Выберите причину жалобы:</b>",
            parse_mode="HTML",
            reply_markup=Keyboards.report_reasons()
        )
        await state.set_state(UserStates.waiting_for_reason)
        
    async def process_report_with_limits(
        self,
        user_id: int,
        target: str,
        method: str,
        reason: int,
        target_type: str
    ) -> Dict[str, Any]:
        """
        Обработка жалобы - ТОЛЬКО ПОДПИСКА или АДМИН
        """
        try:
            logger.info(f"📊 Проверка доступа для user={user_id}, метод={method}")
            
            # 1. Получаем информацию о пользователе
            user = self.db.get_user(user_id)
            if not user:
                return {
                    "success": False,
                    "message": "❌ Пользователь не найден",
                    "penalty_applied": False
                }
            
            # 2. Определяем тип подписки
            subscription_type = user[7] if len(user) > 7 else None
            
            # 3. Проверяем срок подписки если она есть
            subscription_active = False
            if subscription_type:
                sub_end = user[8] if len(user) > 8 else None
                if sub_end:
                    try:
                        end_date = datetime.strptime(sub_end, '%Y-%m-%d %H:%M:%S')
                        subscription_active = datetime.now() <= end_date
                    except:
                        subscription_active = False
            
            # 4. Проверяем админ права
            is_admin = user_id in self.admin_ids
            
            # 5. ПРОВЕРКА ДОСТУПА: ТОЛЬКО подписка ИЛИ админ
            if not is_admin and not subscription_active:
                return {
                    "success": False,
                    "message": "❌ <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
                              "Для отправки жалоб необходимо:\n"
                              "• Активная подписка (BASIC/PREMIUM/NUKE)\n\n"
                              "💰 Баланс НЕ дает доступ к отправке!\n"
                              "🎫 Купите подписку для начала работы",
                    "penalty_applied": False,
                    "requires_subscription": True
                }
            
            # 6. Устанавливаем лимиты в зависимости от статуса
            if is_admin:
                # 👑 АДМИН: безлимитный доступ ко всем методам
                daily_limit = 9999
                cooldown_minutes = 1
                subscription_info = "👑 АДМИН"
                allowed_methods = ["session", "email", "combo", "nuke", "freeze"]
                nuke_limit = 9999  # Админам безлимитно
                
            elif subscription_type == "NUKE":
                # 💣 NUKE: ТОЛЬКО метод nuke
                
                # Получаем название подписки
                sub_name = self.db.get_subscription_name(user_id) if hasattr(self.db, 'get_subscription_name') else ""
                
                # Определяем лимит NUKE сносов
                if "навсегда" in sub_name.lower() or "forever" in sub_name.lower():
                    nuke_limit = 110
                    sub_period = "НАВСЕГДА"
                elif "месяц" in sub_name.lower() or "month" in sub_name.lower():
                    nuke_limit = 80
                    sub_period = "МЕСЯЦ"
                elif "неделя" in sub_name.lower() or "week" in sub_name.lower():
                    nuke_limit = 45
                    sub_period = "НЕДЕЛЯ"
                elif "день" in sub_name.lower() or "day" in sub_name.lower():
                    nuke_limit = 10
                    sub_period = "ДЕНЬ"
                else:
                    # По умолчанию для NUKE подписки
                    nuke_limit = 10
                    sub_period = "ДЕНЬ"
                
                # Лимиты для NUKE подписки
                daily_limit = nuke_limit  # Дневной лимит равен общему лимиту сносов
                cooldown_minutes = 5  # Быстрый кулдаун
                subscription_info = f"💣 NUKE ({sub_period})"
                allowed_methods = ["nuke"]  # ТОЛЬКО NUKE!
                
                # Получаем текущий счетчик NUKE сносов
                nuke_count = user[16] if len(user) > 16 else 0
                
                # Для подписок навсегда/месяц/неделю проверяем общий лимит
                if nuke_count >= nuke_limit:
                    days_left = "∞" if "навсегда" in sub_period.lower() else "0"
                    return {
                        "success": False,
                        "message": f"❌ <b>ЛИМИТ NUKE ИСЧЕРПАН</b>\n\n"
                                  f"Подписка: {subscription_info}\n"
                                  f"💣 Использовано NUKE: {nuke_count}/{nuke_limit}\n\n"
                                  f"📅 Срок: {sub_period}\n"
                                  f"⏳ Осталось дней: {days_left}\n\n"
                                  f"🔄 Продлите подписку для продолжения!",
                        "penalty_applied": False,
                        "nuke_limit_exceeded": True
                    }
                
                # Для дневной подписки - отдельная проверка ежедневного лимита
                if "день" in sub_period.lower():
                    daily_nuke_used = self.db.get_daily_nuke_count(user_id) if hasattr(self.db, 'get_daily_nuke_count') else 0
                    if daily_nuke_used >= nuke_limit:
                        return {
                            "success": False,
                            "message": f"❌ <b>ДНЕВНОЙ ЛИМИТ NUKE ИСЧЕРПАН</b>\n\n"
                                      f"Подписка: {subscription_info}\n"
                                      f"💣 Использовано сегодня: {daily_nuke_used}/{nuke_limit}\n\n"
                                      f"Лимит сбросится в 00:00 UTC",
                            "penalty_applied": False,
                            "daily_nuke_limit_exceeded": True
                        }
                
            elif subscription_type == "PREMIUM":
                # ⭐ PREMIUM: 20 запросов в день, 15 мин кулдаун
                daily_limit = 20
                cooldown_minutes = 15
                subscription_info = "⭐ PREMIUM"
                allowed_methods = ["session", "email", "combo", "freeze"]
                
            elif subscription_type == "BASIC":
                # 🎫 BASIC: 10 запросов в день, 20 мин кулдаун
                daily_limit = 10
                cooldown_minutes = 20
                subscription_info = "🎫 BASIC"
                allowed_methods = ["session", "email", "combo"]
                
            else:
                # Не должно сюда попадать
                return {
                    "success": False,
                    "message": "❌ Неизвестный тип подписки",
                    "penalty_applied": False
                }
            
            # 7. Проверяем доступность метода для подписки
            if method not in allowed_methods:
                if subscription_type == "NUKE":
                    error_msg = f"❌ <b>ПОДПИСКА NUKE - ТОЛЬКО СНОС СЕССИЙ</b>\n\n" \
                               f"Ваша подписка: {subscription_info}\n" \
                               f"💣 Лимит сносов: {nuke_limit}\n" \
                               f"🎯 Доступные методы: ТОЛЬКО 💣 NUKE\n\n" \
                               f"⚠️ Для других методов нужна подписка BASIC/PREMIUM"
                else:
                    error_msg = f"❌ <b>МЕТОД НЕ ДОСТУПЕН</b>\n\n" \
                               f"Подписка: {subscription_info}\n" \
                               f"Метод: {method.upper()}\n\n" \
                               f"📋 Доступные методы:\n" \
                               f"{', '.join([m.upper() for m in allowed_methods])}"
                
                return {
                    "success": False,
                    "message": error_msg,
                    "penalty_applied": False
                }
            
            # 8. Для NUKE подписки дополнительные проверки
            if subscription_type == "NUKE" and method == "nuke":
                # Получаем текущий счетчик NUKE
                nuke_count = user[16] if len(user) > 16 else 0
                
                # Проверяем лимит
                if nuke_count >= nuke_limit:
                    return {
                        "success": False,
                        "message": f"❌ <b>ЛИМИТ NUKE ДОСТИГНУТ</b>\n\n"
                                  f"Подписка: {subscription_info}\n"
                                  f"💣 Использовано: {nuke_count}/{nuke_limit}\n\n"
                                  f"🔄 Продлите подписку для продолжения!",
                        "penalty_applied": False
                    }
            
            # 9. Получаем статистику использования за сегодня
            daily_used = self.db.get_daily_reports_count(user_id) if hasattr(self.db, 'get_daily_reports_count') else 0
            
            # 10. Проверяем дневной лимит
            if subscription_type != "NUKE" and daily_used >= daily_limit and not is_admin:
                return {
                    "success": False,
                    "message": f"❌ <b>ДНЕВНОЙ ЛИМИТ ИСЧЕРПАН</b>\n\n"
                              f"Подписка: {subscription_info}\n"
                              f"📊 Использовано: {daily_used}/{daily_limit}\n\n"
                              f"Лимит сбросится в 00:00 по UTC\n"
                              f"⏰ Кулдаун: {cooldown_minutes} мин между жалобами",
                    "daily_limit_exceeded": True,
                    "penalty_applied": False
                }
            
            # 11. Проверяем кулдаун (кроме админов)
            last_report_time = self.db.get_last_report_time(user_id) if hasattr(self.db, 'get_last_report_time') else None
            if last_report_time and not is_admin:
                time_diff = (datetime.now() - last_report_time).total_seconds() / 60
                
                if time_diff < cooldown_minutes:
                    minutes_left = cooldown_minutes - int(time_diff)
                    return {
                        "success": False,
                        "message": f"⏳ <b>КУЛДАУН АКТИВЕН</b>\n\n"
                                  f"Подписка: {subscription_info}\n"
                                  f"⏰ До следующей жалобы: {minutes_left} мин\n"
                                  f"📊 Использовано сегодня: {daily_used}/{daily_limit}",
                        "cooldown_active": True,
                        "penalty_applied": False
                    }
            
            # 12. Проверяем лимит на цель (макс 3 жалобы на одного пользователя)
            reports_to_target = self.db.get_reports_to_target(user_id, target) if hasattr(self.db, 'get_reports_to_target') else 0
            
            if reports_to_target >= self.max_reports_per_target and not is_admin:
                # Применяем штраф за превышение лимита на цель
                penalty_amount = self.penalty_amount
                
                # Получаем баланс
                balance = user[2] if len(user) > 2 else 0.0
                
                if balance >= penalty_amount:
                    # Списание со счета
                    self.db.update_user_balance(user_id, -penalty_amount)
                    penalty_applied = True
                    penalty_text = f"\n⚠️ <b>Списано ${penalty_amount:.2f}</b> за превышение лимита"
                else:
                    penalty_applied = False
                    penalty_text = f"\n⚠️ <b>Недостаточно средств для штрафа</b>"
                
                return {
                    "success": False,
                    "message": f"❌ <b>ЛИМИТ НА ЦЕЛЬ ИСЧЕРПАН</b>\n\n"
                              f"Подписка: {subscription_info}\n"
                              f"🎯 Цель: {target}\n"
                              f"📊 Отправлено жалоб: {reports_to_target}/{self.max_reports_per_target}\n"
                              f"{penalty_text}\n\n"
                              f"💡 Подождите 24 часа или выберите другую цель",
                    "penalty_applied": penalty_applied,
                    "penalty_amount": penalty_amount if penalty_applied else 0.0
                }
            
            # 13. ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - запускаем отправку
            
            # Обновляем статистику
            if hasattr(self.db, 'increment_daily_reports'):
                self.db.increment_daily_reports(user_id)
            
            if not is_admin and hasattr(self.db, 'set_user_cooldown'):
                self.db.set_user_cooldown(user_id, minutes=cooldown_minutes)
            
            if hasattr(self.db, 'add_report_to_target'):
                self.db.add_report_to_target(user_id, target)
            
            # 14. Запускаем соответствующий метод отправки
            result_message = ""
            success = False
            
            if method == "nuke":
                # NUKE снос сессий
                success, result_message = await self.execute_nuke_report(target, reason, user_id)
                if success and hasattr(self.db, 'increment_nuke_count'):
                    self.db.increment_nuke_count(user_id)
                    current_nuke = (user[16] if len(user) > 16 else 0) + 1
                    logger.info(f"💣 NUKE снос #{current_nuke}/{nuke_limit} выполнен для {target}")
                    
            elif method == "session":
                violation_links = self.get_violation_links(user_id, target)
                success, result_message = await self.execute_session_report_with_links(
                    user_id, target, reason, target_type, violation_links
                )
                if success and hasattr(self.db, 'increment_session_count'):
                    self.db.increment_session_count(user_id)
                    
            elif method == "email":
                success, result_message = await self.execute_email_report(target, reason, target_type, user_id)
                if success and hasattr(self.db, 'increment_email_count'):
                    self.db.increment_email_count(user_id)
                    
            elif method == "combo":
                violation_links = self.get_violation_links(user_id, target)
                success, result_message = await self.execute_combo_report(
                    user_id, target, reason, target_type, violation_links
                )
                if success:
                    if hasattr(self.db, 'increment_session_count'):
                        self.db.increment_session_count(user_id)
                    if hasattr(self.db, 'increment_email_count'):
                        self.db.increment_email_count(user_id)
                        
            elif method == "freeze":
                success, result_message = await self.execute_freeze_report(target, reason, user_id)
                if success and hasattr(self.db, 'increment_freeze_count'):
                    self.db.increment_freeze_count(user_id)
            
            else:
                success, result_message = False, f"❌ Метод {method} не поддерживается"
            
            # 15. Формируем финальный результат
            if success:
                # Получаем обновленную статистику
                updated_daily_used = daily_used + 1
                
                # Для NUKE получаем обновленный счетчик
                if method == "nuke" and subscription_type == "NUKE":
                    updated_nuke_count = (user[16] if len(user) > 16 else 0) + 1
                    nuke_progress = f"💣 Прогресс: {updated_nuke_count}/{nuke_limit}"
                else:
                    nuke_progress = ""
                
                # Формируем сообщение в зависимости от метода
                if method == "nuke":
                    method_icon = "💣"
                    method_name = "NUKE (снос сессий)"
                elif method == "session":
                    method_icon = "📱"
                    method_name = "Сессии"
                elif method == "email":
                    method_icon = "📧"
                    method_name = "Почты"
                elif method == "combo":
                    method_icon = "💥"
                    method_name = "Комбо"
                elif method == "freeze":
                    method_icon = "❄️"
                    method_name = "Фриз"
                else:
                    method_icon = "⚡"
                    method_name = method.upper()
                
                result_text = f"✅ <b>ЖАЛОБА УСПЕШНО ОТПРАВЛЕНА</b>\n\n" \
                             f"{method_icon} Метод: {method_name}\n" \
                             f"🎯 Цель: {target}\n" \
                             f"📋 Тип: {target_type}\n\n" \
                             f"{result_message}\n\n" \
                             f"📊 <b>Статистика:</b>\n" \
                             f"• Подписка: {subscription_info}\n" \
                             f"• Использовано сегодня: {updated_daily_used}/{daily_limit}"
                
                if subscription_type == "NUKE" and method == "nuke":
                    result_text += f"\n• {nuke_progress}"
                
                if not is_admin:
                    result_text += f"\n• Следующая жалоба через: {cooldown_minutes} мин"
                
                result = {
                    "success": True,
                    "message": result_text,
                    "penalty_applied": False,
                    "penalty_amount": 0.0,
                    "method_used": method,
                    "subscription_type": subscription_type
                }
            else:
                result = {
                    "success": False,
                    "message": f"❌ <b>ОШИБКА ОТПРАВКИ</b>\n\n"
                              f"Метод: {method.upper()}\n"
                              f"Цель: {target}\n\n"
                              f"{result_message}",
                    "penalty_applied": False
                }
            
            logger.info(f"📊 Завершение обработки: success={result['success']}, method={method}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в process_report_with_limits: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"❌ <b>СИСТЕМНАЯ ОШИБКА</b>\n\n{str(e)[:200]}",
                "penalty_applied": False
            }
            
    async def show_stars_payment_menu(self, callback: CallbackQuery, product_id: str):
        """
        Показывает меню оплаты звездами для выбранного продукта
        """
        user_id = callback.from_user.id
        
        # Получаем цену в звездах
        stars_price = self.stars_service.get_stars_price(product_id)
        usd_price = self.stars_service.convert_stars_to_usd(stars_price)
        
        # Получаем информацию о продукте
        product_info = self.config.SUBSCRIPTION_PLANS.get(product_id, {})
        product_name = product_info.get("name", "Продукт")
        
        # Создаем клавиатуру
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⭐ Оплатить {stars_price} звезд",
                    callback_data=f"pay_stars:{product_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Оплатить криптовалютой",
                    callback_data=f"pay_crypto:{product_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Оплатить с баланса",
                    callback_data=f"pay_balance:{product_id}"
                )
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subscriptions")]
        ])
        
        await callback.message.edit_text(
            f"⭐ <b>ОПЛАТА ПОДПИСКИ</b>\n\n"
            f"📦 Продукт: {product_name}\n"
            f"💎 Стоимость: {stars_price} звезд (${usd_price:.2f})\n"
            f"📅 Срок: {product_info.get('days', 30)} дней\n\n"
            f"<b>Выберите способ оплаты:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    async def handle_stars_payment(self, callback: CallbackQuery):
        """Обработка выбора оплаты звездами"""
        user_id = callback.from_user.id
        product_id = callback.data.replace("pay_stars:", "")
        
        # Получаем цену и информацию
        stars_price = self.stars_service.get_stars_price(product_id)
        product_info = self.config.SUBSCRIPTION_PLANS.get(product_id, {})
        
        # Создаем описание
        description = f"Оплата подписки {product_info.get('name', '')}"
        
        # Создаем ссылку на оплату
        invoice_link = await self.stars_service.create_invoice_link(
            user_id=user_id,
            product_id=product_id,
            description=description
        )
        
        if invoice_link:
            # Показываем инструкцию
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ Перейти к оплате", url=invoice_link)],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment:{product_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_pay:{product_id}")]
            ])
            
            await callback.message.edit_text(
                f"⭐ <b>ОПЛАТА ЗВЕЗДАМИ</b>\n\n"
                f"📦 Продукт: {product_info.get('name', '')}\n"
                f"💎 Сумма: {stars_price} звезд\n\n"
                f"📋 <b>Инструкция:</b>\n"
                f"1. Нажмите кнопку 'Перейти к оплате'\n"
                f"2. Оплатите счет в Telegram\n"
                f"3. Нажмите 'Проверить оплату'\n\n"
                f"💡 <i>Оплата обрабатывается автоматически в течение 1-2 минут</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                "❌ <b>ОШИБКА СОЗДАНИЯ СЧЕТА</b>\n\n"
                "Не удалось создать счет для оплаты.\n"
                "Попробуйте позже или выберите другой способ оплаты.",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_subscriptions()
            )

    async def check_payment_status(self, callback: CallbackQuery):
        """Проверка статуса оплаты"""
        user_id = callback.from_user.id
        product_id = callback.data.replace("check_payment:", "")
        
        # Получаем последний релевантный инвойс пользователя
        invoices = self.db.get_user_invoices(user_id, limit=20)

        if not invoices:
            await callback.answer("❌ Нет активных платежей", show_alert=True)
            return

        invoice_row = None
        for row in invoices:
            # row: id, user_id, invoice_id, product_id, stars_amount, usd_amount, status, ...
            if row[3] == product_id and row[6] != "paid":
                invoice_row = row
                break

        if invoice_row is None:
            for row in invoices:
                if row[3] == product_id:
                    invoice_row = row
                    break

        if invoice_row is None:
            await callback.answer("❌ Не найден счет для этого продукта", show_alert=True)
            return

        invoice_id = invoice_row[2]
        
        # Проверяем статус платежа
        is_paid, payment_data = await self.stars_service.verify_payment(invoice_id)
        
        if is_paid:
            await callback.message.edit_text(
                "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
                "Ваша подписка активирована.\n"
                "Можете начинать пользоваться ботом! 🚀",
                parse_mode="HTML",
                reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
            )
        else:
            await callback.answer("⏳ Платеж еще не прошел. Попробуйте через минуту.", show_alert=True)
            
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ =====
    
    def check_user_access(self, user_id: int, method: str) -> Dict[str, Any]:
        """Проверка доступа пользователя к отправке жалоб"""
        try:
            user = self.db.get_user(user_id)
            if not user:
                return {
                    "can_report": False,
                    "message": "❌ Пользователь не найден",
                    "requires_subscription": False
                }
            
            # Проверка подписки
            subscription_type = user[7] if len(user) > 7 else None
            subscription_active = False
            
            if subscription_type:
                sub_end = user[8] if len(user) > 8 else None
                if sub_end:
                    try:
                        end_date = datetime.strptime(sub_end, '%Y-%m-%d %H:%M:%S')
                        subscription_active = datetime.now() <= end_date
                    except:
                        subscription_active = False
            
            # Проверка админ прав
            is_admin = user_id in self.admin_ids
            
            # Определение доступных методов
            if is_admin:
                allowed_methods = ["session", "email", "combo", "nuke", "freeze"]
            elif subscription_type == "NUKE":
                allowed_methods = ["nuke"]
            elif subscription_type == "PREMIUM":
                allowed_methods = ["session", "email", "combo", "freeze"]
            elif subscription_type == "BASIC":
                allowed_methods = ["session", "email", "combo"]
            else:
                allowed_methods = []
            
            # Проверка доступа к конкретному методу
            if not is_admin and not subscription_active:
                return {
                    "can_report": False,
                    "message": "❌ Требуется активная подписка",
                    "requires_subscription": True,
                    "allowed_methods": allowed_methods
                }
            
            if method not in allowed_methods:
                return {
                    "can_report": False,
                    "message": f"❌ Метод {method} не доступен для вашей подписки",
                    "requires_subscription": False,
                    "allowed_methods": allowed_methods
                }
            
            # Проверка дневного лимита
            daily_used = self.db.get_daily_reports_count(user_id) if hasattr(self.db, 'get_daily_reports_count') else 0
            
            if subscription_type == "PREMIUM":
                daily_limit = 20
            elif subscription_type == "BASIC":
                daily_limit = 10
            elif subscription_type == "NUKE":
                daily_limit = 9999  # NUKE имеет отдельные лимиты
            else:
                daily_limit = 0
            
            if daily_used >= daily_limit and not is_admin:
                return {
                    "can_report": False,
                    "message": f"❌ Достигнут дневной лимит ({daily_used}/{daily_limit})",
                    "requires_subscription": False,
                    "daily_limit_exceeded": True
                }
            
            # Проверка кулдауна
            last_report_time = self.db.get_last_report_time(user_id) if hasattr(self.db, 'get_last_report_time') else None
            if last_report_time and not is_admin:
                time_diff = (datetime.now() - last_report_time).total_seconds() / 60
                
                if subscription_type == "PREMIUM":
                    cooldown = 15
                elif subscription_type == "BASIC":
                    cooldown = 20
                elif subscription_type == "NUKE":
                    cooldown = 5
                else:
                    cooldown = self.default_cooldown
                
                if time_diff < cooldown:
                    minutes_left = cooldown - int(time_diff)
                    return {
                        "can_report": False,
                        "message": f"⏳ Кулдаун: {minutes_left} мин до следующей жалобы",
                        "requires_subscription": False,
                        "cooldown_active": True
                    }
            
            return {
                "can_report": True,
                "message": "✅ Доступ разрешен",
                "requires_subscription": False,
                "subscription_type": subscription_type,
                "subscription_active": subscription_active,
                "is_admin": is_admin,
                "daily_used": daily_used,
                "daily_limit": daily_limit
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа пользователя {user_id}: {e}")
            return {
                "can_report": False,
                "message": "❌ Ошибка проверки доступа",
                "requires_subscription": False
            }
    
    def get_user_report_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики жалоб пользователя"""
        try:
            daily_used = self.db.get_daily_reports_count(user_id) if hasattr(self.db, 'get_daily_reports_count') else 0
            daily_limit = 10  # По умолчанию
            
            user = self.db.get_user(user_id)
            if user:
                subscription_type = user[7] if len(user) > 7 else None
                if subscription_type == "PREMIUM":
                    daily_limit = 20
                elif subscription_type == "NUKE":
                    daily_limit = 9999
            
            # Получаем количество жалоб на цели
            # Это нужно реализовать в зависимости от вашей структуры базы данных
            
            return {
                "daily_used": daily_used,
                "daily_limit": daily_limit,
                "total_penalties": 0.0,  # Реализуйте получение из базы
                "balance": user[2] if user and len(user) > 2 else 0.0,
                "has_subscription": subscription_type is not None,
                "cooldown_active": False,  # Реализуйте проверку кулдауна
                "cooldown_message": "",
                "target_stats": [],  # Реализуйте получение статистики по целям
                "has_double_complaints": False,
                "total_targets": 0
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {
                "daily_used": 0,
                "daily_limit": 10,
                "total_penalties": 0.0,
                "balance": 0.0,
                "has_subscription": False,
                "cooldown_active": False,
                "cooldown_message": "",
                "target_stats": [],
                "has_double_complaints": False,
                "total_targets": 0
            }
            
    # ===== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ =====
    
    def get_subscription_limits(self, subscription_type: str) -> Dict[str, Any]:
        """Получение лимитов для типа подписки"""
        limits = {
            "BASIC": {
                "daily_limit": 10,
                "cooldown": 20,
                "methods": ["session", "email", "combo"],
                "price": 10.0,
                "description": "🎫 Базовая подписка"
            },
            "PREMIUM": {
                "daily_limit": 20,
                "cooldown": 15,
                "methods": ["session", "email", "combo", "freeze"],
                "price": 25.0,
                "description": "⭐ Премиум подписка"
            },
            "NUKE": {
                "daily_limit": "custom",
                "cooldown": 5,
                "methods": ["nuke"],
                "price": "custom",
                "description": "💣 NUKE подписка"
            }
        }
        return limits.get(subscription_type, {})
    
    def init_report_manager(self):
        """Инициализация менеджера отчетов"""
        # Создаем менеджер отчетов если он нужен
        try:
            from core.report_manager import ReportManager
            self.report_manager = ReportManager(
                session_manager=self.session_manager,
                email_manager=self.email_manager,
                translator=self.translator,
                db=self.db
            )
            logger.info("✅ Менеджер отчетов инициализирован")
        except ImportError:
            logger.warning("⚠️ Модуль ReportManager не найден")
            self.report_manager = None
    
    def __del__(self):
        """Деструктор для очистки ресурсов"""
        try:
            # Закрываем соединения и освобождаем ресурсы
            if hasattr(self, 'violation_storage'):
                self.violation_storage.clear()
            logger.debug("✅ Ресурсы UserHandlers очищены")
        except:
            pass            

    async def process_reason_input(self, message: Message, state: FSMContext):
        """Обработка выбора причины жалобы"""
        user_id = message.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, message=message):
            await state.clear()
            return
        
        try:
            data = await state.get_data()
            target = data.get('target')
            target_type = data.get('target_type')
            method = data.get('method', 'session')
            
            # Проверяем доступность с новыми ограничениями
            user_stats = await self.report_manager.get_user_report_stats(user_id)
            
            # Проверяем дневной лимит
            if user_stats["daily_used"] >= user_stats["daily_limit"]:
                await message.answer(
                    "❌ <b>ДНЕВНОЙ ЛИМИТ ИСЧЕРПАН</b>\n\n"
                    f"Вы уже использовали {user_stats['daily_used']}/{user_stats['daily_limit']} жалоб сегодня.",
                    reply_markup=self.keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
                )
                await state.clear()
                return
            
            # Проверяем кулдаун
            if user_stats.get("cooldown_active"):
                await message.answer(
                    f"⏳ <b>КУЛДАУН АКТИВЕН</b>\n\n"
                    f"{user_stats.get('cooldown_message', 'Подождите 20 минут между жалобами')}",
                    reply_markup=self.keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
                )
                await state.clear()
                return
            
            # Получаем причину из текста сообщения
            reason_text = message.text.strip()
            
            # Используем новый метод с ограничениями
            report_result = await self.process_report_with_limits(
                user_id=user_id,
                target=target,
                method=method,
                reason=8,  # По умолчанию спам
                target_type=target_type
            )
            
            if report_result["success"]:
                success_message = f"✅ {report_result['message']}"
                if report_result.get("penalty_applied"):
                    success_message += f"\n⚠️ Списано ${report_result.get('penalty_amount', 30):.2f} за превышение лимита"
                
                # Добавляем статистику
                user_stats = await self.report_manager.get_user_report_stats(user_id)
                success_message += f"\n\n📊 <b>Статистика:</b>"
                success_message += f"\n• Жалоб сегодня: {user_stats['daily_used']}/{user_stats['daily_limit']}"
                success_message += f"\n• Баланс: ${user_stats['balance']:.2f}"
                
                await message.answer(
                    success_message,
                    parse_mode="HTML",
                    reply_markup=self.keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
                )
            else:
                await message.answer(
                    f"❌ {report_result['message']}",
                    parse_mode="HTML",
                    reply_markup=self.keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
                )
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки причины: {e}")
            await message.answer(
                "❌ Произошла ошибка. Попробуйте снова.",
                reply_markup=self.keyboards.main_menu(message.from_user.id, message.from_user.id in self.config.ADMIN_IDS)
            )
            await state.clear()

    async def process_report_reason(self, callback: CallbackQuery, state: FSMContext, reason: int):
        """Обработать выбор причины и запустить РЕАЛЬНЫЙ СНОС С ОГРАНИЧЕНИЯМИ"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            await state.clear()
            return
        
        user_data = await state.get_data()
        target = user_data.get('target')
        target_type = user_data.get('target_type')
        method = user_data.get('method', 'session')
        
        if not target:
            await callback.message.edit_text(
                "❌ Ошибка данных",
                reply_markup=Keyboards.back_to_main()
            )
            await state.clear()
            return
        
        # ===== НОВАЯ ЛОГИКА: ПРОВЕРКА ОГРАНИЧЕНИЙ =====
        try:
            # Показываем начальное сообщение с проверкой ограничений
            await callback.message.edit_text(
                f"🔍 <b>ПРОВЕРКА ОГРАНИЧЕНИЙ...</b>\n\n"
                f"🎯 <b>Цель:</b> {target}\n"
                f"📝 <b>Тип:</b> {target_type}\n"
                f"⚡ <b>Метод:</b> {method.upper()}\n"
                f"📄 <b>Причина:</b> {self.config.COMPLAINT_REASONS.get(reason, 'Не указана')}\n\n"
                f"<i>Проверяю доступные лимиты...</i>",
                parse_mode="HTML"
            )
            
            # Используем новый метод проверки ограничений
            report_result = await self.process_report_with_limits(
                user_id=user_id,
                target=target,
                method=method,
                reason=reason,
                target_type=target_type
            )
            
            if not report_result["success"]:
                # Получаем детальную статистику для сообщения
                limit_stats = await self.report_manager.get_user_report_stats(user_id)
                
                error_text = f"❌ <b>НЕВОЗМОЖНО ОТПРАВИТЬ ЖАЛОБУ</b>\n\n"
                error_text += report_result["message"]
                
                # Добавляем статистику, если есть дневной лимит
                if report_result.get("daily_limit_exceeded"):
                    error_text += f"\n\n📊 <b>Ваша статистика:</b>"
                    error_text += f"\n• Использовано жалоб сегодня: {limit_stats['daily_used']}/{limit_stats['daily_limit']}"
                    error_text += f"\n• Баланс: ${limit_stats['balance']:.2f}"
                    error_text += f"\n• Штрафов за спам: ${limit_stats['total_penalties']:.2f}"
                
                # Добавляем время до сброса, если кулдаун активен
                if limit_stats.get("cooldown_active"):
                    error_text += f"\n⏳ {limit_stats.get('cooldown_message', 'Кулдаун активен')}"
                
                # Добавляем кнопки в зависимости от причины отказа
                if "балансе" in report_result["message"].lower() or "средств" in report_result["message"].lower():
                    keyboard = Keyboards.balance_menu()
                else:
                    keyboard = Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
                
                await callback.message.edit_text(
                    error_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                await state.clear()
                return
            
            # ===== ЖАЛОБА РАЗРЕШЕНА, ЗАПУСКАЕМ ОТПРАВКУ =====
            penalty_text = ""
            if report_result.get("penalty_applied"):
                penalty_amount = report_result.get("penalty_amount", 30.0)
                penalty_text = f"\n⚠️ <b>Внимание:</b> Списано ${penalty_amount:.2f} за превышение лимита жалоб на этого пользователя\n\n"
            
            await callback.message.edit_text(
                f"✅ <b>ЛИМИТЫ ПРОВЕРЕНЫ!</b>{penalty_text}"
                f"🚀 <b>ЗАПУСК РЕАЛЬНОГО СНОСА...</b>\n\n"
                f"🎯 <b>Цель:</b> {target}\n"
                f"📝 <b>Тип:</b> {target_type}\n"
                f"⚡ <b>Метод:</b> {method.upper()}\n"
                f"📄 <b>Причина:</b> {self.config.COMPLAINT_REASONS.get(reason, 'Не указана')}\n\n"
                f"⏳ <i>Начинаем массовую отправку жалоб...</i>",
                parse_mode="HTML"
            )
            
            # Получаем результат отправки
            final_message = report_result["message"]
            
            # Добавляем статистику в сообщение
            limit_stats = await self.report_manager.get_user_report_stats(user_id)
            stats_text = f"\n\n📊 <b>Ваша статистика после отправки:</b>"
            stats_text += f"\n• Использовано жалоб сегодня: {limit_stats['daily_used']}/{limit_stats['daily_limit']}"
            stats_text += f"\n• Баланс: ${limit_stats['balance']:.2f}"
            
            if limit_stats.get("cooldown_active"):
                stats_text += f"\n⏳ {limit_stats.get('cooldown_message', 'Следующая жалоба через 20 минут')}"
            
            final_message += stats_text
            
            await callback.message.edit_text(
                final_message,
                parse_mode="HTML",
                reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки жалобы с ограничениями: {e}")
            await callback.message.edit_text(
                "❌ <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
                "Произошла ошибка при обработке жалобы. Попробуйте позже.",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
        
        await state.clear()

    async def send_session_reports(self, target: str, reason: int, user_id: int) -> bool:
        """Реальная отправка жалоб через сессии"""
        try:
            # Получаем все валидные сессии
            session_files = self.session_manager.get_session_files()
            valid_sessions = []
            
            # Быстрая проверка сессий
            for session_file in session_files[:10]:  # Ограничиваем 10 сессиями
                is_valid, info = await self.session_manager.validate_session(session_file)
                if is_valid:
                    valid_sessions.append(session_file)
            
            if not valid_sessions:
                logger.error("No valid sessions available")
                return False
            
            # Отправляем жалобы через валидные сессии
            success_count = 0
            for session_file in valid_sessions:
                try:
                    success, result = await self.session_manager.send_report(session_file, target, reason)
                    if success:
                        success_count += 1
                    await asyncio.sleep(2)  # Задержка между запросами
                except Exception as e:
                    logger.error(f"Error sending report via {session_file}: {e}")
            
            logger.info(f"Session reports: {success_count}/{len(valid_sessions)} successful")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error in send_session_reports: {e}")
            return False

    async def send_email_reports(self, target: str, reason: int, target_type: str, user_id: int) -> bool:
        """Реальная отправка жалоб через email"""
        try:
            logger.info(f"📧 Запуск умной email отправки для цели: {target}, причина: {reason}")
            
            # Используем умный сервис
            result = await self.smart_email_service.send_smart_complaint(
                target=target,
                reason_id=reason,
                email_count=25,  # Используем 3 разные почты
                language="ru"    # Язык отправки
            )
            
            if result["success"]:
                logger.info(f"✅ Умная email отправка успешна: {result['message']}")
                logger.info(f"📊 Детали: {result['sent_count']} отправлено, приоритет: {result['priority']}")
                return True
            else:
                logger.error(f"❌ Умная email отправка не удалась: {result['message']}")
                # Пробуем старый метод как запасной вариант
                return await self._fallback_email_sending(target, reason)
                
        except Exception as e:
            logger.error(f"❌ Ошибка в send_email_reports: {e}")
            return False

    async def _fallback_email_sending(self, target: str, reason: int) -> bool:
        """Запасной метод отправки email (старый код)"""
        try:
            # Получаем почты из менеджера
            emails = self.email_manager.get_emails(2)  # Берем 2 почты
            if not emails:
                logger.error("❌ Нет доступных почт для запасного метода")
                return False
            
            success_count = 0
            for email_data in emails:
                success, message = await self.email_manager.send_complaint(
                    email_data['email'],
                    email_data['password'],
                    target,
                    reason
                )
                if success:
                    success_count += 1
                await asyncio.sleep(2)
            
            return success_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка запасного метода отправки: {e}")
            return False

    async def send_combo_reports(self, target: str, reason: int, target_type: str, user_id: int) -> bool:
        """Комбо атака: сессии + email"""
        try:
            session_success = await self.send_session_reports(target, reason, user_id)
            email_success = await self.send_email_reports(target, reason, target_type, user_id)
            
            return session_success or email_success  # Хотя бы один метод сработал
        except Exception as e:
            logger.error(f"Error in send_combo_reports: {e}")
            return False
            
    async def process_report_method(self, callback: CallbackQuery, state: FSMContext, method: str):
        """
        Обработать выбор метода с проверкой лимитов
        """
        user_id = callback.from_user.id
        
        # Проверка админ доступа
        is_admin = await self.check_admin_access(user_id)
        
        if is_admin:
            await state.update_data(method=method)
            await callback.message.edit_text(
                "👑 <b>АДМИН РЕЖИМ</b>\n\n"
                f"Метод: {method.upper()}\n\n"
                "Выберите тип цели:",
                parse_mode="HTML",
                reply_markup=Keyboards.target_types()
            )
            await state.set_state(UserStates.waiting_for_target_type)
            return
        
        user = self.db.get_user(user_id)
        
        if not user:
            await callback.answer("❌ Ошибка данных")
            return
        
        subscription_type = user[7] if len(user) > 7 else None
        await state.update_data(method=method)
        
        # Проверяем лимиты подписки
        can_use, message = self.check_subscription_limits(user, method)
        
        if not can_use:
            await callback.message.edit_text(
                f"❌ <b>ЛИМИТ ИСЧЕРПАН</b>\n\n{message}",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        # Продолжаем выбор цели
        await callback.message.edit_text(
            "🎯 <b>ВЫБЕРИТЕ ТИП ЦЕЛИ</b>\n\n"
            f"Метод: {method.upper()}\n"
            f"Подписка: {subscription_type}",
            parse_mode="HTML",
            reply_markup=Keyboards.target_types()
        )
        await state.set_state(UserStates.waiting_for_target_type)
    
    def check_subscription_limits(self, user, method: str) -> tuple:
        """
        Проверяет лимиты подписки
        """
        subscription_type = user[7] if len(user) > 7 else None
        
        if not subscription_type:
            return False, "Нет активной подписки"
        
        # Получаем текущие счетчики
        session_count = user[17] if len(user) > 17 else 0
        email_count = user[18] if len(user) > 18 else 0
        nuke_count = user[16] if len(user) > 16 else 0
        freeze_count = user[19] if len(user) > 19 else 0
        
        # Лимиты для разных подписок
        limits = {
            "BASIC": {"session": 20, "email": 10, "nuke": 0, "freeze": 0},
            "PREMIUM": {"session": 50, "email": 30, "nuke": 0, "freeze": 10},
            "NUKE": {"session": 999, "email": 999, "nuke": 100, "freeze": 999}
        }
        
        sub_limits = limits.get(subscription_type, limits["BASIC"])
        
        # Проверяем метод
        if method == "session" and session_count >= sub_limits["session"]:
            return False, f"📱 Лимит сессий исчерпан: {session_count}/{sub_limits['session']}"
        elif method == "email" and email_count >= sub_limits["email"]:
            return False, f"📧 Лимит почт исчерпан: {email_count}/{sub_limits['email']}"
        elif method == "nuke" and nuke_count >= sub_limits["nuke"]:
            return False, f"💣 Лимит сносов исчерпан: {nuke_count}/{sub_limits['nuke']}"
        elif method == "freeze" and freeze_count >= sub_limits["freeze"]:
            return False, f"❄️ Лимит фризов исчерпан: {freeze_count}/{sub_limits['freeze']}"
        elif method == "combo":
            if session_count >= sub_limits["session"]:
                return False, f"📱 Лимит сессий для комбо: {session_count}/{sub_limits['session']}"
            if email_count >= sub_limits["email"]:
                return False, f"📧 Лимит почт для комбо: {email_count}/{sub_limits['email']}"
        
        return True, "Лимиты в порядке"
    
    def _get_subscription_counters(self, user):
        """
        Возвращает счетчики для подписки
        """
        if not user:
            return "0/0"
        
        subscription_type = user[7] if len(user) > 7 else None
        nuke_count = user[16] if len(user) > 16 else 0
        session_count = user[17] if len(user) > 17 else 0
        email_count = user[18] if len(user) > 18 else 0
        freeze_count = user[19] if len(user) > 19 else 0
        
        if subscription_type == "NUKE":
            max_nukes = 100
            return f"💣 NUKE: {nuke_count}/{max_nukes}\n📱 Сессии: {session_count}/∞\n📧 Почты: {email_count}/∞\n❄️ Фриз: {freeze_count}/∞"
        elif subscription_type == "PREMIUM":
            return f"📱 Сессии: {session_count}/50\n📧 Почты: {email_count}/30\n❄️ Фриз: {freeze_count}/10"
        elif subscription_type == "BASIC":
            return f"📱 Сессии: {session_count}/20\n📧 Почты: {email_count}/10"
        else:
            return "Нет активной подписки"
    
    async def process_target_type(self, callback: CallbackQuery, state: FSMContext, target_type: str):
        """
        Обработать выбор типа цели
        """
        user_id = callback.from_user.id
        user_data = await state.get_data()
        method = user_data.get('method', 'session')
        
        await state.update_data(target_type=target_type)
        
        # Для NUKE метода - специальные причины
        if method == "nuke":
            await callback.message.edit_text(
                f"💣 <b>NUKE АТАКА НА {target_type.upper()}</b>\n\n"
                "Выберите причину для массового сноса:",
                parse_mode="HTML",
                reply_markup=Keyboards.nuke_reasons()
            )
            await state.set_state(UserStates.waiting_for_nuke_reason)
            return
        
        # Для каналов и групп - детальные причины
        if target_type in ["channel", "group"]:
            await callback.message.edit_text(
                f"🎯 <b>ЖАЛОБА НА {target_type.upper()}</b>\n\n"
                "Выберите основную причину жалобы:",
                parse_mode="HTML",
                reply_markup=Keyboards.main_reasons()
            )
            await state.set_state(UserStates.waiting_for_main_reason)
            return
        
        # Для пользователей и ботов - обычный ввод цели
        target_type_texts = {
            "user": "👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n• Укажите @username или ID\n• Жалоба только на публичные сообщения",
            "bot": "🤖 <b>БОТ</b>\n• Укажите @username бота"
        }
        
        await callback.message.edit_text(
            f"{target_type_texts.get(target_type, '🎯 Выбранный тип')}\n\n"
            "📝 <b>Введите цель для жалобы:</b>",
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_main()
        )
        await state.set_state(UserStates.waiting_for_target)
    
    async def process_target_input(self, message: Message, state: FSMContext):
        """
        Обработать ввод цели с проверкой типа
        """
        user_id = message.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, message=message):
            await state.clear()
            return
        
        target = message.text.strip()
        user_data = await state.get_data()
        target_type = user_data.get('target_type')
        method = user_data.get('method', 'session')
        
        if not target_type:
            await message.answer("❌ Ошибка: тип цели не выбран", reply_markup=Keyboards.back_to_main())
            await state.clear()
            return
        
        # Проверка черного списка
        if self.db.is_blacklisted(target):
            await message.answer(
                "❌ Эта цель в черном списке",
                reply_markup=Keyboards.back_to_main()
            )
            await state.clear()
            return
        
        # Проверка защищенных целей
        if any(protected in target for protected in self.config.PROTECTED_TARGETS): 
            await message.answer(
                "❌ Нельзя жаловаться на защищенные цели",
                reply_markup=Keyboards.back_to_main()
            )
            await state.clear()
            return
        
        await state.update_data(target=target)
        
        # Для ботов сразу переходим к выбору причины (ссылки не нужны)
        if target_type == "bot":
            await message.answer(
                f"🤖 <b>Цель (бот):</b> {target}\n\n"
                "🎯 <b>Выберите причину жалобы:</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.report_reasons()
            )
            await state.set_state(UserStates.waiting_for_reason)
            return
        
        # ДЛЯ ВСЕХ ОСТАЛЬНЫХ ТИПОВ - запрашиваем ссылки на нарушения
        link_requirements = {
            "user": {
                "min": 1,
                "max": 2,
                "description": "1-2 ссылки на публичные сообщения пользователя"
            },
            "group": {
                "min": 1,
                "max": 2,
                "description": "1-2 ссылки на сообщения в публичной группе"
            },
            "channel": {
                "min": 1,
                "max": 2,
                "description": "1-2 ссылки на посты в канале"
            }
        }
        
        req = link_requirements.get(target_type)
        if req:
            await message.answer(
                f"🔗 <b>ТРЕБУЮТСЯ ССЫЛКИ НА НАРУШЕНИЯ</b>\n\n"
                f"Для жалобы на {target_type} необходимо предоставить ссылки на конкретные нарушения.\n\n"
                f"📎 <b>Требования:</b>\n"
                f"• {req['description']}\n"
                f"• Группы/каналы должны быть публичными\n"
                f"• Сообщения должны быть видны всем\n\n"
                f"🔗 <b>Отправьте первую ссылку:</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            await state.set_state(UserStates.waiting_for_violation_link)
            return
        
        # Для других случаев - сразу выбор причины
        if method == "nuke":
            await message.answer(
                f"💣 <b>NUKE АТАКА НА {target}</b>\n\n"
                "Выберите причину:",
                parse_mode="HTML",
                reply_markup=Keyboards.nuke_reasons()
            )
            await state.set_state(UserStates.waiting_for_nuke_reason)
        else:
            await message.answer(
                f"🎯 <b>ЦЕЛЬ: {target}</b>\n\n"
                "Выберите причину жалобы:",
                parse_mode="HTML",
                reply_markup=Keyboards.report_reasons()
            )
            await state.set_state(UserStates.waiting_for_reason)
    
    async def process_violation_link(self, message: Message, state: FSMContext):
        """
        Обработать ввод ссылки на нарушение с проверкой приватности
        """
        user_id = message.from_user.id
        user_data = await state.get_data()
        target_type = user_data.get('target_type')
        target = user_data.get('target')
        method = user_data.get('method', 'session')
        
        link = message.text.strip()
        
        # Проверяем валидность ссылки
        if not self.is_valid_telegram_link(link):
            await message.answer(
                "❌ <b>НЕВЕРНАЯ ССЫЛКА</b>\n\n"
                "Отправьте корректную ссылку на сообщение в Telegram.\n"
                "Пример: https://t.me/username/123 или https://t.me/c/channel_id/123",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        # Проверяем, не приватный ли канал/группа
        is_private, privacy_error = await self.check_link_privacy(link)
        if is_private:
            await message.answer(
                f"❌ <b>ЧАСТНАЯ ГРУППА/КАНАЛ</b>\n\n"
                f"Ссылка ведет в приватный {target_type}.\n"
                f"Для жалобы нужны публичные группы/каналы.\n\n"
                f"🔗 <b>Отправьте ссылку из публичного {target_type}:</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        # Сохраняем ссылку в базу
        self.db.add_violation_link(user_id, target, link, target_type)
        
        # Проверяем, сколько ссылок уже сохранено
        links_count = self.db.get_violation_links_count(user_id, target)
        
        # Определяем сколько нужно ссылок
        link_requirements = {
            "user": {"min": 1, "max": 2},
            "group": {"min": 1, "max": 2},
            "channel": {"min": 1, "max": 2},
            "bot": {"min": 0, "max": 0}  # Для ботов не нужно
        }
        
        req = link_requirements.get(target_type, {"min": 1, "max": 1})
        
        if links_count < req["min"]:
            links_needed = req["min"] - links_count
            await message.answer(
                f"✅ <b>ССЫЛКА #{links_count} СОХРАНЕНА</b>\n\n"
                f"Нужно еще {links_needed} ссылок.\n\n"
                f"🔗 <b>Отправьте следующую ссылку:</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        # Все минимальные ссылки собраны
        if links_count < req["max"]:
            # Можно добавить еще ссылки, но минимальное количество уже есть
            await state.update_data(violation_links_collected=True)
            
            # Запрашиваем основную причину для детальных причин
            if target_type in ["channel", "group"]:
                await message.answer(
                    f"✅ <b>ССЫЛКИ СОБРАНЫ ({links_count}/{req['max']})</b>\n\n"
                    f"Выберите основную причину жалобы:",
                    parse_mode="HTML",
                    reply_markup=Keyboards.main_reasons()
                )
                await state.set_state(UserStates.waiting_for_main_reason)
            else:
                await message.answer(
                    f"✅ <b>ССЫЛКА СОХРАНЕНА</b>\n\n"
                    f"Теперь выберите причину жалобы:",
                    parse_mode="HTML",
                    reply_markup=Keyboards.report_reasons()
                )
                await state.set_state(UserStates.waiting_for_reason)
        else:
            # Достигнут максимум ссылок
            await state.update_data(violation_links_collected=True)
            
            if target_type in ["channel", "group"]:
                await message.answer(
                    f"✅ <b>ВСЕ ССЫЛКИ СОБРАНЫ ({links_count})</b>\n\n"
                    f"Выберите основную причину жалобы:",
                    parse_mode="HTML",
                    reply_markup=Keyboards.main_reasons()
                )
                await state.set_state(UserStates.waiting_for_main_reason)
            else:
                await message.answer(
                    f"✅ <b>ВСЕ ССЫЛКИ СОБРАНЫ</b>\n\n"
                    f"Теперь выберите причину жалобы:",
                    parse_mode="HTML",
                    reply_markup=Keyboards.report_reasons()
                )
                await state.set_state(UserStates.waiting_for_reason)
    
    async def check_link_privacy(self, link: str) -> Tuple[bool, str, Optional[str]]:
        """
        Проверяет, ведет ли ссылка в приватный канал/группу
        Возвращает (is_private, error_message, entity_type)
        """
        try:
            # Сначала быстрая проверка по формату ссылки
            quick_check = self._quick_privacy_check(link)
            if quick_check[0]:  # Если уже определили как приватный
                return quick_check[0], quick_check[1], quick_check[2]
            
            # Парсим ссылку
            parsed_info = self._parse_telegram_link(link)
            if not parsed_info:
                return False, "Невозможно распознать ссылку", None
            
            entity_type = parsed_info["type"]
            identifier = parsed_info["identifier"]
            
            # Для ссылок с приглашением - всегда приватные
            if entity_type == "invite":
                return True, "Ссылка с приглашением в приватный чат", "chat"
            
            # Пробуем получить информацию через API
            try:
                # Создаем временный клиент для проверки
                async with TelegramClient(
                    session='temp_check_session',
                    api_id=self.api_id,
                    api_hash=self.api_hash
                ) as temp_client:
                    await temp_client.connect()
                    
                    if entity_type == "channel":
                        # Пробуем получить канал
                        try:
                            entity = await temp_client.get_entity(identifier)
                            
                            if isinstance(entity, Channel):
                                # Проверяем права доступа
                                if entity.restricted:
                                    return True, "Канал ограничен/приватный", "channel"
                                if not entity.megagroup and entity.broadcast:
                                    # Это broadcast канал - проверяем доступ
                                    try:
                                        # Пробуем получить полную информацию
                                        full_info = await temp_client(GetFullChannelRequest(channel=entity))
                                        if hasattr(full_info.full_chat, 'hidden_prehistory'):
                                            return False, "", "channel"
                                    except:
                                        return True, "Не удалось получить информацию о канале", "channel"
                                return False, "", "channel"
                            
                        except Exception as e:
                            if "cannot find entity" in str(e).lower() or "channel is private" in str(e).lower():
                                return True, "Канал приватный или не существует", "channel"
                            raise
                    
                    elif entity_type == "group":
                        # Пробуем получить группу
                        try:
                            entity = await temp_client.get_entity(identifier)
                            
                            if isinstance(entity, Chat):
                                # Для групп проверяем количество участников (грубый индикатор)
                                if hasattr(entity, 'participants_count'):
                                    if entity.participants_count == 0:
                                        return True, "Группа пустая или приватная", "group"
                                return False, "", "group"
                            
                        except Exception as e:
                            if "cannot find entity" in str(e).lower() or "chat is private" in str(e).lower():
                                return True, "Группа приватная или не существует", "group"
                            raise
                    
                    elif entity_type == "user":
                        # Пользователи всегда публичны (если есть @username)
                        if identifier.startswith('@'):
                            return False, "", "user"
                        else:
                            # ID пользователя - сложно проверить
                            return False, "", "user"
                    
                    elif entity_type == "message":
                        # Проверяем доступ к сообщению
                        try:
                            # Пробуем получить сообщение
                            messages = await temp_client.get_messages(identifier["entity"], ids=identifier["message_id"])
                            if not messages:
                                return True, "Сообщение недоступно или приватный чат", "message"
                            return False, "", "message"
                        except Exception as e:
                            return True, f"Не удалось получить сообщение: {str(e)}", "message"
                
            except Exception as api_error:
                logger.warning(f"⚠️ Ошибка API проверки: {api_error}")
                # Возвращаем результат быстрой проверки как fallback
                return self._fallback_privacy_check(link)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка проверки приватности ссылки {link}: {e}")
            return True, f"Ошибка проверки: {str(e)}", "unknown"
        
        # По умолчанию считаем публичным
        return False, "", entity_type
    
    async def process_main_reason(self, callback: CallbackQuery, state: FSMContext, main_reason: str):
        """
        Обработать выбор основной причины и показать подпричины
        """
        user_id = callback.from_user.id
        user_data = await state.get_data()
        target_type = user_data.get('target_type')
        
        await state.update_data(main_reason=main_reason)
        
        # Получаем подпричины для выбранной основной причины
        sub_reasons_keyboard = self.get_sub_reasons_keyboard(main_reason)
        
        if sub_reasons_keyboard:
            reason_texts = {
                "violence": "🔫 <b>Насилие</b>",
                "children": "🚸 <b>Жестокое обращение с детьми</b>",
                "illegal_goods": "⚖️ <b>Незаконные товары или услуги</b>",
                "porn": "🔞 <b>Порнографические материалы</b>",
                "personal": "📊 <b>Персональные данные</b>",
                "fraud": "🎭 <b>Мошенничество</b>",
                "copyright": "©️ <b>Нарушение авторских прав</b>",
                "spam": "📧 <b>Спам</b>",
                "other": "📄 <b>Другое</b>"
            }
            
            await callback.message.edit_text(
                f"{reason_texts.get(main_reason, '🎯 Основная причина')}\n\n"
                "Выберите конкретную подпричину:",
                parse_mode="HTML",
                reply_markup=sub_reasons_keyboard
            )
            await state.set_state(UserStates.waiting_for_sub_reason)
        else:
            # Для причин без подпричин сразу переходим к выбору метода
            await self.process_sub_reason(callback, state, main_reason)
    
    def get_sub_reasons_keyboard(self, main_reason: str):
        """
        Возвращает клавиатуру с подпричинами для основной причины
        """
        sub_reasons = {
            "violence": [
                ["👊 Оскорбления или клевета", "sub_violence_insults"],
                ["🩸 Изображение насилия, жестокости", "sub_violence_images"],
                ["💀 Крайняя жестокость, расчленение", "sub_violence_extreme"],
                ["☠️ Пропаганда ненависти", "sub_violence_hate"],
                ["🔪 Призывы к насилию", "sub_violence_calls"],
                ["🎭 Организованная преступность", "sub_violence_crime"],
                ["💣 Терроризм", "sub_violence_terrorism"],
                ["🐾 Жестокое обращение с животными", "sub_violence_animals"]
            ],
            "children": [
                ["🔞 Сексуальное насилие", "sub_children_sexual"],
                ["👊 Физическое насилие", "sub_children_physical"]
            ],
            "illegal_goods": [
                ["🔫 Оружие", "sub_goods_weapons"],
                ["💊 Наркотики или психоактивные вещества", "sub_goods_drugs"],
                ["📄 Подделка документов", "sub_goods_docs"],
                ["💰 Фальшивомонетчество", "sub_goods_money"],
                ["🦠 Вредоносное ПО или средства взлома", "sub_goods_malware"],
                ["👕 Контрафактные товары", "sub_goods_counterfeit"],
                ["📦 Другие товары или услуги", "sub_goods_other"]
            ],
            "porn": [
                ["🚸 Жестокое обращение с детьми", "sub_porn_children"],
                ["💔 Незаконные интимные услуги", "sub_porn_services"],
                ["🐾 Жестокое обращение с животными", "sub_porn_animals"],
                ["📸 Интимные изображения без согласия", "sub_porn_nonconsent"],
                ["🔞 Порнографический контент", "sub_porn_content"],
                ["📦 Другие незаконные материалы", "sub_porn_other"]
            ],
            "personal": [
                ["🖼️ Личные изображения", "sub_personal_images"],
                ["🏠 Адрес", "sub_personal_address"],
                ["📱 Номера телефонов", "sub_personal_phones"],
                ["💳 Украденные учетные данные", "sub_personal_stolen"],
                ["📦 Другие личные данные", "sub_personal_other"]
            ],
            "fraud": [
                ["👤 Выдача себя за другое лицо", "sub_fraud_impersonation"],
                ["💸 Ложные финансовые обещания", "sub_fraud_promises"],
                ["🦠 Вредоносное ПО, фишинг", "sub_fraud_malware"],
                ["🛒 Сомнительный продавец, услуга, товар", "sub_fraud_seller"]
            ],
            "spam": [
                ["🤬 Оскорбления или клевета", "sub_spam_insults"],
                ["📢 Реклама незаконной продукции", "sub_spam_illegal_ads"],
                ["📣 Прочая реклама", "sub_spam_other_ads"]
            ],
            "other": [
                ["👎 Не нравится", "sub_other_dislike"],
                ["📰 Недостоверная информация, клевета", "sub_other_fake"],
                ["🔞 Порнографические материалы", "sub_other_porn"],
                ["⚖️ Незаконные товары и услуги", "sub_other_illegal"],
                ["🚫 Не нарушает закон, но надо удалить", "sub_other_remove"]
            ]
        }
        
        if main_reason in sub_reasons:
            keyboard = []
            for text, callback_data in sub_reasons[main_reason]:
                keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
            
            # Добавляем кнопку "Назад"
            keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main_reasons")])
            
            return InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        return None
    
    async def process_sub_reason(self, callback: CallbackQuery, state: FSMContext, sub_reason: str):
        """
        Обработать выбор подпричины и запустить отправку
        """
        user_id = callback.from_user.id
        
        # Проверка админ доступа
        is_admin = await self.check_admin_access(user_id)
        
        if not is_admin:
            # Проверка подписки для обычных пользователей
            if not await self._check_subscription_before_action(user_id, callback=callback):
                await state.clear()
                return
        
        user_data = await state.get_data()
        target = user_data.get('target')
        target_type = user_data.get('target_type')
        method = user_data.get('method', 'session')
        main_reason = user_data.get('main_reason')
        
        if not target:
            await callback.message.edit_text(
                "❌ Ошибка данных",
                reply_markup=Keyboards.back_to_main()
            )
            await state.clear()
            return
        
        # Получаем причину из подпричины
        reason_id = self.convert_sub_reason_to_id(sub_reason, main_reason)
        
        # Получаем сохраненные ссылки
        violation_links = self.db.get_violation_links(user_id, target)
        
        # ===== НОВАЯ ЛОГИКА С ОГРАНИЧЕНИЯМИ =====
        try:
            await callback.message.edit_text(
                f"🔍 <b>ПРОВЕРКА ОГРАНИЧЕНИЙ...</b>\n\n"
                f"🎯 <b>Цель:</b> {target}\n"
                f"📝 <b>Тип:</b> {target_type}\n"
                f"⚡ <b>Метод:</b> {method.upper()}\n"
                f"📄 <b>Причина:</b> {self.get_reason_text(sub_reason, main_reason)}\n\n"
                f"🔗 <b>Ссылок:</b> {len(violation_links)}\n"
                f"<i>Проверяю лимиты...</i>",
                parse_mode="HTML"
            )
            
            # Проверяем все лимиты (дневные, подписки, кулдаун)
            can_proceed, limit_message = await self.check_all_limits(
                user_id=user_id,
                method=method,
                is_admin=is_admin
            )
            
            if not can_proceed:
                await callback.message.edit_text(
                    f"❌ <b>НЕВОЗМОЖНО ОТПРАВИТЬ</b>\n\n{limit_message}",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_main()
                )
                await state.clear()
                return
            
            # Запускаем отправку в зависимости от метода
            await self.launch_report(
                callback=callback,
                user_id=user_id,
                target=target,
                target_type=target_type,
                method=method,
                reason_id=reason_id,
                violation_links=violation_links,
                is_admin=is_admin
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска жалобы: {e}")
            await callback.message.edit_text(
                "❌ <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
                "Произошла ошибка. Попробуйте позже.",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
        
        await state.clear()
    
    async def check_all_limits(self, user_id: int, method: str, is_admin: bool = False) -> Tuple[bool, str]:
        """
        Проверяет все типы лимитов
        """
        # Админы проходят без проверок
        if is_admin:
            return True, "👑 Админ режим"
        
        user = self.db.get_user(user_id)
        if not user:
            return False, "❌ Ошибка данных пользователя"
        
        # 1. Проверка лимитов подписки
        subscription_type = user[7] if len(user) > 7 else None
        
        if not subscription_type:
            return False, "❌ Нет активной подписки"
        
        can_use, sub_message = self.check_subscription_limits(user, method)
        if not can_use:
            return False, f"❌ Лимит подписки: {sub_message}"
        
        # 2. Проверка дневного лимита
        user_stats = await self.report_manager.get_user_report_stats(user_id)
        
        if user_stats["daily_used"] >= user_stats["daily_limit"]:
            return False, (
                f"❌ Дневной лимит исчерпан\n"
                f"Использовано: {user_stats['daily_used']}/{user_stats['daily_limit']}\n"
                f"Сбросится в 00:00 UTC"
            )
        
        # 3. Проверка кулдауна
        if user_stats.get("cooldown_active"):
            cooldown_msg = user_stats.get("cooldown_message", "Подождите 20 минут")
            return False, f"⏳ Кулдаун активен: {cooldown_msg}"
        
        # 4. Проверка баланса (если нет подписки)
        balance = user[2]
        if not subscription_type and balance <= 0:
            return False, f"❌ Недостаточно средств\nБаланс: ${balance:.2f}"
        
        return True, "✅ Все лимиты в порядке"
    
    async def launch_report(self, callback: CallbackQuery, user_id: int, target: str, 
                          target_type: str, method: str, reason_id: int, 
                          violation_links: List[str], is_admin: bool = False):
        """
        Запускает отправку жалобы в зависимости от метода
        """
        try:
            if method == "nuke":
                # NUKE через почты
                await callback.message.edit_text(
                    f"💣 <b>ЗАПУСК NUKE АТАКИ</b>\n\n"
                    f"🎯 Цель: {target}\n"
                    f"📝 Тип: {target_type}\n"
                    f"📊 Причина ID: {reason_id}\n"
                    f"🔗 Ссылок: {len(violation_links)}\n\n"
                    f"<i>Запускаю массовую отправку через почты...</i>",
                    parse_mode="HTML"
                )
                
                success, result = await self.report_manager.execute_nuke_report(
                    target=target,
                    reason=reason_id,
                    user_id=user_id
                )
                
            elif method == "session":
                # Отправка через сессии
                await callback.message.edit_text(
                    f"📱 <b>ЗАПУСК СЕССИЙ</b>\n\n"
                    f"🎯 Цель: {target}\n"
                    f"📝 Тип: {target_type}\n"
                    f"📊 Причина ID: {reason_id}\n"
                    f"🔗 Ссылок: {len(violation_links)}\n\n"
                    f"<i>Запускаю отправку через сессии...</i>",
                    parse_mode="HTML"
                )
                
                success, result = await self.report_manager.execute_session_report_with_links(
                    user_id=user_id,
                    target=target,
                    reason=reason_id,
                    target_type=target_type,
                    violation_links=violation_links
                )
                
            elif method == "email":
                # Отправка через почты
                await callback.message.edit_text(
                    f"📧 <b>ЗАПУСК ПОЧТОВОЙ ОТПРАВКИ</b>\n\n"
                    f"🎯 Цель: {target}\n"
                    f"📝 Тип: {target_type}\n"
                    f"📊 Причина ID: {reason_id}\n"
                    f"🔗 Ссылок: {len(violation_links)}\n\n"
                    f"<i>Запускаю отправку через почты...</i>",
                    parse_mode="HTML"
                )
                
                success, result = await self.report_manager.execute_email_report(
                    target=target,
                    reason=reason_id,
                    target_type=target_type,
                    user_id=user_id
                )
                
            elif method == "combo":
                # Комбо атака (сессии + почты)
                await callback.message.edit_text(
                    f"💥 <b>ЗАПУСК КОМБО АТАКИ</b>\n\n"
                    f"🎯 Цель: {target}\n"
                    f"📝 Тип: {target_type}\n"
                    f"📊 Причина ID: {reason_id}\n"
                    f"🔗 Ссылок: {len(violation_links)}\n\n"
                    f"<i>Запускаю комбо атаку (сессии + почты)...</i>",
                    parse_mode="HTML"
                )
                
                success, result = await self.report_manager.execute_combo_report(
                    user_id=user_id,
                    target=target,
                    reason=reason_id,
                    target_type=target_type,
                    violation_links=violation_links
                )
                
            else:
                await callback.message.edit_text(
                    "❌ <b>МЕТОД В РАЗРАБОТКЕ</b>\n\n"
                    "Этот метод пока не доступен.",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_main()
                )
                return
            
            # Обновляем статистику
            if success:
                # Увеличиваем счетчики
                if method == "nuke":
                    self.db.increment_nuke_count(user_id)
                elif method == "session":
                    self.db.increment_session_count(user_id)
                elif method == "email":
                    self.db.increment_email_count(user_id)
                elif method == "combo":
                    self.db.increment_session_count(user_id)
                    self.db.increment_email_count(user_id)
                
                # Обновляем дневной лимит
                self.db.increment_daily_report_count(user_id)
                
                # Устанавливаем кулдаун
                self.db.set_user_cooldown(user_id, minutes=20)
                
                # Формируем финальное сообщение
                final_message = f"✅ <b>ОТПРАВКА ЗАВЕРШЕНА</b>\n\n{result}"
                
                # Добавляем статистику
                user_stats = await self.report_manager.get_user_report_stats(user_id)
                final_message += f"\n\n📊 <b>Статистика:</b>"
                final_message += f"\n• Жалоб сегодня: {user_stats['daily_used']}/{user_stats['daily_limit']}"
                final_message += f"\n• Баланс: ${user_stats['balance']:.2f}"
                
                if user_stats.get("cooldown_active"):
                    final_message += f"\n⏳ {user_stats.get('cooldown_message', 'Следующая жалоба через 20 минут')}"
                
                if is_admin:
                    final_message += "\n\n👑 <b>Админ режим: лимиты не учитываются</b>"
                
            else:
                final_message = f"❌ <b>ОШИБКА ОТПРАВКИ</b>\n\n{result}"
            
            await callback.message.edit_text(
                final_message,
                parse_mode="HTML",
                reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS or is_admin)
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в launch_report: {e}")
            await callback.message.edit_text(
                "❌ <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
                "Произошла ошибка при запуске отправки.",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_main()
            )
    
    def convert_sub_reason_to_id(self, sub_reason: str, main_reason: str) -> int:
        """
        Конвертирует подпричину в ID причины
        """
        reason_map = {
            # Насилие
            "sub_violence_insults": 1,
            "sub_violence_images": 2,
            "sub_violence_extreme": 2,
            "sub_violence_hate": 1,
            "sub_violence_calls": 1,
            "sub_violence_crime": 1,
            "sub_violence_terrorism": 1,
            "sub_violence_animals": 2,
            
            # Дети
            "sub_children_sexual": 4,
            "sub_children_physical": 2,
            
            # Нелегальные товары
            "sub_goods_weapons": 5,
            "sub_goods_drugs": 5,
            "sub_goods_docs": 5,
            "sub_goods_money": 5,
            "sub_goods_malware": 5,
            "sub_goods_counterfeit": 5,
            "sub_goods_other": 5,
            
            # Порнография
            "sub_porn_children": 3,
            "sub_porn_services": 3,
            "sub_porn_animals": 3,
            "sub_porn_nonconsent": 3,
            "sub_porn_content": 3,
            "sub_porn_other": 3,
            
            # Персональные данные
            "sub_personal_images": 6,
            "sub_personal_address": 6,
            "sub_personal_phones": 6,
            "sub_personal_stolen": 6,
            "sub_personal_other": 6,
            
            # Мошенничество
            "sub_fraud_impersonation": 7,
            "sub_fraud_promises": 7,
            "sub_fraud_malware": 7,
            "sub_fraud_seller": 7,
            
            # Спам
            "sub_spam_insults": 8,
            "sub_spam_illegal_ads": 8,
            "sub_spam_other_ads": 8,
            
            # Другое
            "sub_other_dislike": 9,
            "sub_other_fake": 9,
            "sub_other_porn": 9,
            "sub_other_illegal": 9,
            "sub_other_remove": 9,
            
            # Основные причины без подпричин
            "dislike": 9,
            "copyright": 10,
            "spam": 8,
            "other": 9
        }
        
        return reason_map.get(sub_reason, 9)  # По умолчанию "Другое"
    
    def get_reason_text(self, sub_reason: str, main_reason: str) -> str:
        """
        Возвращает текстовое описание причины
        """
        # Здесь должна быть маппинг кодов причин на тексты
        # Для простоты возвращаем код
        return f"{main_reason}:{sub_reason}"
    
    def is_valid_telegram_link(self, link: str) -> bool:
        """
        Проверяет валидность Telegram ссылки
        """
        patterns = [
            r'https?://t\.me/[a-zA-Z0-9_]+/\d+',
            r'https?://t\.me/c/[-\d]+/\d+',
            r'https?://t\.me/\+[a-zA-Z0-9_]+',
            r'@[a-zA-Z0-9_]{5,32}'
        ]
        
        for pattern in patterns:
            if re.match(pattern, link):
                return True
        return False

    async def show_report_limits(self, callback: CallbackQuery):
        """Показать статистику по ограничениям жалоб"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        try:
            # Получаем статистику через новый метод
            limit_stats = await self.report_manager.get_user_report_stats(user_id)
            user = self.db.get_user(user_id)
            
            text = f"📊 <b>ВАШИ ЛИМИТЫ НА ЖАЛОБЫ</b>\n\n"
            
            # Дневной лимит
            daily_used = limit_stats["daily_used"]
            daily_limit = limit_stats["daily_limit"]
            daily_progress = "█" * int((daily_used / daily_limit) * 10)
            daily_progress += "░" * (10 - int((daily_used / daily_limit) * 10))
            
            text += f"📅 <b>Дневной лимит:</b> {daily_used}/{daily_limit}\n"
            text += f"   [{daily_progress}]\n\n"
            
            # Кулдаун
            if limit_stats.get("cooldown_active"):
                text += f"⏳ <b>Кулдаун активен:</b>\n"
                text += f"   {limit_stats.get('cooldown_message', 'Следующая жалоба через 20 минут')}\n\n"
            else:
                text += f"✅ <b>Кулдаун:</b> Готов к отправке\n\n"
            
            # Штрафы
            penalties = limit_stats.get("total_penalties", 0)
            text += f"💰 <b>Штрафы за спам:</b> ${penalties:.2f}\n\n"
            
            # Баланс и подписка
            balance = limit_stats.get("balance", 0.0)
            has_subscription = limit_stats.get("has_subscription", False)
            
            text += f"💵 <b>Баланс:</b> ${balance:.2f}\n"
            text += f"🎫 <b>Подписка:</b> {'✅ Активна' if has_subscription else '❌ Неактивна'}\n"
            
            if has_subscription:
                sub_end = user[8] if user and len(user) > 8 else None
                if sub_end:
                    try:
                        end_date = datetime.strptime(sub_end, '%Y-%m-%d %H:%M:%S')
                        days_left = (end_date - datetime.now()).days
                        text += f"📅 <b>Осталось дней:</b> {max(0, days_left)}\n"
                    except:
                        pass
            
            # Правила
            text += f"\n📋 <b>Правила отправки жалоб:</b>\n"
            text += f"• Максимум 10 жалоб в сутки\n"
            text += f"• 20 минут между жалобами\n"
            text += f"• 3 жалобы на одного пользователя (далее штраф $30)\n"
            text += f"• Штрафы списываются с основного баланса\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📤 Отправить жалобу", callback_data="send_report")],
                [InlineKeyboardButton(text="💰 Баланс", callback_data="balance_menu")],
                [InlineKeyboardButton(text="📊 Общая статистика", callback_data="user_stats")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
            ])
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа лимитов: {e}")
            await callback.message.edit_text(
                "❌ Ошибка загрузки статистики лимитов",
                reply_markup=Keyboards.back_to_main()
            )

    async def show_balance_menu(self, callback: CallbackQuery):
        """Показать меню баланса"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        user = self.db.get_user(user_id)
        
        if not user:
            await callback.answer("❌ Ошибка загрузки данных")
            return
        
        balance = user[2]  # Основной баланс
        ref_balance = user[3]  # Реферальный баланс
        
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
👥 <b>Рефералов:</b> {user[4]}

💡 <b>Реферальный баланс можно вывести с комиссией 10%</b>
        """
        
        await callback.message.edit_text(
            balance_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def start_deposit(self, callback: CallbackQuery, state: FSMContext):
        """Начать пополнение баланса"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        await state.set_state(UserStates.waiting_deposit_amount)
        min_deposit = self.config.BALANCE_CONFIG["min_deposit"]
        
        await callback.message.edit_text(
            f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
            f"Введите сумму в USD для пополнения:\n"
            f"<b>Минимальная сумма:</b> ${min_deposit}\n\n"
            f"<i>Пример: 5.50</i>",
            parse_mode="HTML",
            reply_markup=self.keyboards.back_to_balance()
        )

    async def process_deposit_amount(self, message: Message, state: FSMContext):
        """Обработать сумму пополнения"""
        user_id = message.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, message=message):
            await state.clear()
            return
        
        try:
            amount = float(message.text)
            min_deposit = self.config.BALANCE_CONFIG['min_deposit']
            
            if amount < min_deposit:
                await message.answer(
                    f"❌ <b>Сумма меньше минимальной!</b>\n\n"
                    f"Минимальное пополнение: <b>${min_deposit}</b>",
                    parse_mode="HTML",
                    reply_markup=self.keyboards.back_to_balance()
                )
                return

            # Создаем платеж через CryptoBot
            invoice = await self.payment_service.create_invoice(
                user_id=message.from_user.id,
                amount=amount,
                description=f"Пополнение баланса на ${amount:.2f}"
            )
            
            if invoice:
                # Сохраняем платеж в базу
                self.db.add_payment(message.from_user.id, amount, "balance", invoice['invoice_id'])
                
                await message.answer(
                    f"💳 <b>СЧЕТ НА ОПЛАТУ</b>\n\n"
                    f"💵 <b>Сумма:</b> ${amount:.2f}\n"
                    f"📊 <b>Статус:</b> Ожидание оплаты\n\n"
                    f"⚡ После оплаты нажмите \"Проверить оплату\"",
                    parse_mode="HTML",
                    reply_markup=self.keyboards.payment_keyboard(invoice['invoice_id'], invoice['pay_url']),
                    disable_web_page_preview=True
                )
            else:
                await message.answer(
                    "❌ Ошибка создания счета. Попробуйте позже.",
                    reply_markup=self.keyboards.back_to_balance()
                )
            
            await state.clear()
            
        except ValueError:
            await message.answer(
                "❌ Введите корректную сумму\nПример: 5.50",
                reply_markup=self.keyboards.back_to_balance()
            )

    async def withdraw_referral_balance(self, callback: CallbackQuery):
        """Вывод реферального баланса с комиссией 10%"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        # Используем реальный метод перевода
        success, amount_transferred, commission = self.db.transfer_referral_to_main(user_id)
        
        if not success:
            await callback.message.edit_text(
                "❌ <b>Нет средств для вывода</b>\n\n"
                "На вашем реферальным балансе нет средств",
                parse_mode="HTML",
                reply_markup=self.keyboards.back_to_balance()
            )
            return
        
        # Добавляем транзакцию
        self.db.add_transaction(user_id, "referral_withdraw", amount_transferred, 
                               f"Вывод реферальных с комиссией ${commission:.2f}")
        
        # Получаем обновленные данные
        user = self.db.get_user(user_id)
        new_balance = user[2] if user else amount_transferred
        
        await callback.message.edit_text(
            f"✅ <b>РЕФЕРАЛЬНЫЙ БАЛАНС ВЫВЕДЕН</b>\n\n"
            f"💵 <b>Сумма вывода:</b> ${amount_transferred + commission:.2f}\n"
            f"📊 <b>Комиссия (10%):</b> ${commission:.2f}\n"
            f"💰 <b>Зачислено:</b> ${amount_transferred:.2f}\n\n"
            f"💎 <b>Новый основной баланс:</b> ${new_balance:.2f}",
            parse_mode="HTML",
            reply_markup=self.keyboards.back_to_balance()
        )

    async def show_transaction_history(self, callback: CallbackQuery):
        """Показать историю транзакций"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
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
            type_emoji = "📥" if trans[0] == "deposit" else "📤"
            amount_color = "🟢" if trans[1] > 0 else "🔴"
            text += f"{type_emoji} {amount_color} <b>${trans[1]:.2f}</b>\n"
            text += f"   📝 {trans[2]}\n"
            text += f"   ⏰ {trans[3][:16]}\n\n"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=self.keyboards.back_to_balance()
        )

    async def show_balance_shop(self, callback: CallbackQuery):
        """Показать магазин за баланс"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        balance = self.db.get_user_balance(user_id)
        
        text = (
            f"🛒 <b>МАГАЗИН ЗА БАЛАНС</b>\n\n"
            f"💰 <b>Ваш баланс:</b> ${balance:.2f}\n\n"
            f"💡 <b>Все покупки списываются с вашего баланса</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Пакеты жалоб", callback_data="buy_single_reports")],
            [InlineKeyboardButton(text="🎫 Подписки", callback_data="buy_subscription")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit_balance")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="balance_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    async def show_subscription_types(self, callback: CallbackQuery):
        """Показать типы подписок"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        await callback.message.edit_text(
            "🎫 <b>ВЫБОР ПОДПИСКИ</b>\n\n"
            "Выберите категорию подписки:",
            parse_mode="HTML",
            reply_markup=Keyboards.subscription_types()
        )

    async def show_basic_plans(self, callback: CallbackQuery):
        """Показать BASIC планы"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        plans_text = "🟢 <b>BASIC ПЛАНЫ</b>\n\n"
        keyboard_buttons = []
        
        for plan_id, plan_data in self.config.SUBSCRIPTION_PLANS.items():
            if plan_id.startswith("basic_"):
                price = self.config.BALANCE_PRICES["subscriptions"].get(plan_id, 0)
                plans_text += f"• {plan_data['name']} - ${price:.2f}\n"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{plan_data['name']} - ${price:.2f}", 
                        callback_data=f"buy_{plan_id}"
                    )
                ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_subscription")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(plans_text, parse_mode="HTML", reply_markup=keyboard)

    async def show_premium_plans(self, callback: CallbackQuery):
        """Показать PREMIUM планы"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        plans_text = "🔴 <b>PREMIUM ПЛАНЫ</b>\n\n"
        keyboard_buttons = []
        
        for plan_id, plan_data in self.config.SUBSCRIPTION_PLANS.items():
            if plan_id.startswith("premium_"):
                price = self.config.BALANCE_PRICES["subscriptions"].get(plan_id, 0)
                plans_text += f"• {plan_data['name']} - ${price:.2f}\n"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{plan_data['name']} - ${price:.2f}", 
                        callback_data=f"buy_{plan_id}"
                    )
                ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_subscription")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(plans_text, parse_mode="HTML", reply_markup=keyboard)

    async def show_nuke_plans(self, callback: CallbackQuery):
        """Показать NUKE планы"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        plans_text = "💣 <b>NUKE ПЛАНЫ</b>\n\n"
        keyboard_buttons = []
        
        for plan_id, plan_data in self.config.SUBSCRIPTION_PLANS.items():
            if plan_id.startswith("nuke_"):
                price = self.config.BALANCE_PRICES["subscriptions"].get(plan_id, 0)
                plans_text += f"• {plan_data['name']} - ${price:.2f}\n"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{plan_data['name']} - ${price:.2f}", 
                        callback_data=f"buy_{plan_id}"
                    )
                ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_subscription")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(plans_text, parse_mode="HTML", reply_markup=keyboard)

    async def process_plan_purchase_balance(self, callback: CallbackQuery, data: str):
        """Покупка подписки за баланс"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        # Получаем ID плана
        plan_id = data.replace("buy_", "")
        plan_data = self.config.SUBSCRIPTION_PLANS.get(plan_id)
        price = self.config.BALANCE_PRICES["subscriptions"].get(plan_id)
        
        if not plan_data or not price:
            await callback.answer("❌ План не найден")
            return
        
        # Проверяем баланс
        balance = self.db.get_user_balance(user_id)
        if balance < price:
            await callback.message.edit_text(
                f"❌ <b>НЕДОСТАТОЧНО СРЕДСТВ</b>\n\n"
                f"💵 <b>Нужно:</b> ${price:.2f}\n"
                f"💰 <b>На балансе:</b> ${balance:.2f}\n\n"
                f"Пополните баланс для покупки",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_balance()
            )
            return
        
        # Списание средств
        self.db.set_user_balance(user_id, balance - price)
        self.db.add_transaction(user_id, "purchase", -price, f"Покупка подписки {plan_data['name']}")
        
        # Активируем подписку
        days = plan_data["days"]
        self.db.update_subscription(user_id, plan_id.upper(), days)
        
        await callback.message.edit_text(
            f"✅ <b>ПОДПИСКА АКТИВИРОВАНА!</b>\n\n"
            f"🎫 <b>План:</b> {plan_data['name']}\n"
            f"💰 <b>Списано:</b> ${price:.2f}\n"
            f"📅 <b>Срок:</b> {days} дней\n\n"
            f"💎 <b>Остаток на балансе:</b> ${self.db.get_user_balance(user_id):.2f}",
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_main()
        )

    async def process_single_purchase_balance(self, callback: CallbackQuery, data: str):
        """Покупка одиночных жалоб за баланс"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        pack_type = data.replace("buy_single_", "")
        
        price = self.config.BALANCE_PRICES["reports"].get(pack_type, 0)
        
        if not price:
            await callback.answer("❌ Пакет не найден")
            return
        
        # Проверяем баланс
        balance = self.db.get_user_balance(user_id)
        if balance < price:
            await callback.message.edit_text(
                f"❌ <b>НЕДОСТАТОЧНО СРЕДСТВ</b>\n\n"
                f"💵 <b>Нужно:</b> ${price:.2f}\n"
                f"💰 <b>На балансе:</b> ${balance:.2f}\n\n"
                f"Пополните баланс для покупки",
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_balance()
            )
            return
        
        # Списание средств
        self.db.set_user_balance(user_id, balance - price)
        self.db.add_transaction(user_id, "purchase", -price, f"Покупка пакета жалоб {pack_type}")
        
        await callback.message.edit_text(
            f"✅ <b>ПАКЕТ ЖАЛОБ КУПЛЕН!</b>\n\n"
            f"📦 <b>Тип:</b> {pack_type}\n"
            f"💰 <b>Списано:</b> ${price:.2f}\n\n"
            f"💎 <b>Остаток на балансе:</b> ${self.db.get_user_balance(user_id):.2f}",
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_main()
        )

    async def check_payment_status(self, callback: CallbackQuery, data: str):
        """Проверить статус платежа"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        invoice_id = data.replace("check_payment_", "")
        
        await callback.message.edit_text("🔄 <b>Проверка оплаты...</b>", parse_mode="HTML")
        
        try:
            invoice = await self.payment_service.check_invoice(invoice_id)
            
            if invoice and invoice.get('status') == 'paid':
                amount = float(invoice.get('amount', 0))
                
                # Зачисляем средства на баланс
                self.db.update_user_balance(user_id, amount)
                self.db.update_payment_status(invoice_id, 'completed')
                self.db.add_transaction(user_id, "deposit", amount, "Пополнение через CryptoBot")
                
                new_balance = self.db.get_user_balance(user_id)
                
                success_text = f"""
✅ <b>ПЛАТЕЖ ПОДТВЕРЖДЕН!</b>

💵 <b>Зачислено:</b> ${amount:.2f}
💰 <b>Текущий баланс:</b> ${new_balance:.2f}

🎉 Теперь вы можете покупать подписки и пакеты жалоб!
                """
                
                await callback.message.edit_text(
                    success_text,
                    parse_mode="HTML",
                    reply_markup=Keyboards.balance_menu()
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
                reply_markup=Keyboards.back_to_main()
            )

    async def show_single_reports(self, callback: CallbackQuery):
        """Показать пакеты одиночных жалоб"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        text = "🛒 <b>ПОКУПКА ОТДЕЛЬНЫХ ЖАЛОБ</b>\n\n"
        keyboard_buttons = []
        
        for pack_type, price in self.config.BALANCE_PRICES["reports"].items():
            text += f"• {pack_type.upper()} - ${price:.2f}\n"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{pack_type.upper()} - ${price:.2f}", 
                    callback_data=f"buy_single_{pack_type}"
                )
            ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="balance_shop")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    async def show_referral_system(self, callback: CallbackQuery):
        """Показать реферальную систему"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        user = self.db.get_user(user_id)
        
        if not user:
            return
        
        ref_code = user[5]
        bot_username = (await self.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={ref_code}"
        
        ref_text = f"""
👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>

💰 <b>Зарабатывайте 25% с покупок рефералов!</b>

🔗 <b>Ваша реферальная ссылка:</b>
<code>{ref_link}</code>

📊 <b>Ваша статистика:</b>
├─ Рефералов: {user[4]}
├─ Заработано: ${user[3]:.2f}
└─ Доступно к выводу: ${user[3]:.2f}

💡 <b>Как это работает:</b>
1. Делитесь своей ссылкой
2. Получаете 25% с каждой покупки реферала
3. Выводите средства с комиссией 10%
        """
        
        await callback.message.edit_text(
            ref_text,
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_main()
        )

    async def show_user_stats(self, callback: CallbackQuery):
        """Показать статистику пользователя"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        user = self.db.get_user(user_id)
        
        if not user:
            return
        
        stats_text = f"""
📊 <b>ВАША СТАТИСТИКА</b>

🎯 <b>Активность:</b>
├─ Всего жалоб: {user[14] or 0}
├─ Через сессии: {user[9] or 0}
├─ Через почту: {user[10] or 0}
└─ Комбо атак: {user[11] or 0}

💎 <b>Подписка:</b>
├─ Тип: {user[7] or 'Нет'}
├─ Осталось: {self.get_subscription_days_left(user[8]) if user[8] else '0'} дней
└─ Статус: {'🟢 Активна' if user[7] else '🔴 Неактивна'}

💰 <b>Финансы:</b>
├─ Основной баланс: ${user[2]:.2f}
├─ Реферальный баланс: ${user[3]:.2f}
└─ Рефералов: {user[4]}
        """
        
        await callback.message.edit_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
        )

    def get_subscription_days_left(self, subscription_end: str) -> int:
        """Получить количество оставшихся дней подписки"""
        if not subscription_end:
            return 0
        
        try:
            from datetime import datetime
            end_date = datetime.strptime(subscription_end, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            delta = end_date - now
            return max(0, delta.days)
        except:
            return 0

    async def show_help(self, callback: CallbackQuery):
        """Показать справку"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        help_text = """
ℹ️ <b>ПОМОЩЬ И ИНСТРУКЦИЯ</b>

🎯 <b>Как отправить жалобу:</b>
1. Нажмите "Отправить жалобу"
2. Выберите тип цели (группа, канал, человек, бот)
3. Введите цель (@username или ссылку)
4. Выберите метод отправки
5. Выберите причину
6. Ждите завершения отправки

💰 <b>Балансовая система:</b>
• Все покупки через баланс
• Минимальное пополнение: $1.00
• Реферальные выплаты: 25%
• Комиссия на вывод: 10%

🎫 <b>Подписки:</b>
• BASIC - базовый функционал
• PREMIUM - расширенные возможности  
• NUKE - максимальная мощность

📞 <b>Поддержка:</b>
По всем вопросам обращайтесь к администратору
        """
        
        await callback.message.edit_text(
            help_text,
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_main()
        )

    async def show_main_menu(self, callback: CallbackQuery):
        """Показать главное меню"""
        user_id = callback.from_user.id
        
        # Проверка подписки
        if not await self._check_subscription_before_action(user_id, callback):
            return
        
        await callback.message.edit_text(
            "🔧 <b>ГЛАВНОЕ МЕНЮ</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(user_id, user_id in self.config.ADMIN_IDS)
        )

    async def show_admin_panel(self, callback: CallbackQuery):
        """Показать админ панель"""
        user_id = callback.from_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        await callback.message.edit_text(
            "👑 <b>АДМИН ПАНЕЛЬ RABANOK</b>\n\nВыберите раздел:",
            parse_mode="HTML",
            reply_markup=Keyboards.admin_panel()
        )

    async def process_admin_callback(self, callback: CallbackQuery, state: FSMContext, data: str):
        """Обработать админ callback"""
        user_id = callback.from_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        admin_handler = AdminHandlers(self.bot, self.db, self.config)
        await admin_handler.process_admin_callbacks(callback, state)
    async def handle_back_to_main(self, callback: CallbackQuery, state: FSMContext):
        """Возврат в главное меню"""
        await state.clear()
        await callback.message.edit_text(
            "🏠 <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=self.keyboards.main_menu(
                callback.from_user.id, 
                callback.from_user.id in self.config.ADMIN_IDS
            )
        )

    async def handle_method_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработка выбора метода отправки"""
        method = callback.data.replace("method_", "")
        
        if method in ["session", "email", "combo", "freeze", "nuke"]:
            await self.process_report_method(callback, state, method)
        else:
            await callback.answer("❌ Неизвестный метод")

    async def process_target_type_group(self, callback: CallbackQuery, state: FSMContext):
        """Обработать выбор типа цели: группа"""
        await self.process_target_type(callback, state, "group")

    async def process_target_type_channel(self, callback: CallbackQuery, state: FSMContext):
        """Обработать выбор типа цели: канал"""
        await self.process_target_type(callback, state, "channel")

    async def process_target_type_user(self, callback: CallbackQuery, state: FSMContext):
        """Обработать выбор типа цели: пользователь"""
        await self.process_target_type(callback, state, "user")

    async def process_target_type_bot(self, callback: CallbackQuery, state: FSMContext):
        """Обработать выбор типа цели: бот"""
        await self.process_target_type(callback, state, "bot")

    async def handle_report_method_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработать выбор метода отчета"""
        method = callback.data.replace("report_method_", "")
        await self.process_report_method(callback, state, method)

    async def handle_report_reason_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработать выбор причины отчета"""
        reason = int(callback.data.replace("report_reason_", ""))
        await self.process_report_reason(callback, state, reason)

    async def process_admin_callback(self, callback: CallbackQuery, state: FSMContext, data: str):
        """Обработать админ callback"""
        user_id = callback.from_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        # Создаем экземпляр AdminHandlers для обработки админских функций
        admin_handler = AdminHandlers(self.bot, self.db, self.config)
        
        # Перенаправляем на соответствующий метод AdminHandlers
        if hasattr(admin_handler, 'process_admin_callbacks'):
            await admin_handler.process_admin_callbacks(callback, state)
        else:
            await callback.answer("❌ Админ функции недоступны")