import asyncio
import importlib
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.methods import AnswerCallbackQuery
from aiogram.enums import ParseMode
import sys
import os

from core.config import Config
from core.database import Database
from handlers.user_handlers import UserHandlers
from handlers.admin_handlers import AdminHandlers
from handlers.balance_handlers import setup_balance_handlers
from handlers.payment_handlers import setup_payment_handlers
from utils.states import UserStates, AdminStates, EmailStates
from utils.keyboards import Keyboards
from services.payment_service import initialize_payment_service
from services.translation_service import initialize_translation_service
from services.email_manager import email_manager

# Принудительная перезагрузка модулей
if 'services.report_manager' in sys.modules:
    importlib.reload(sys.modules['services.report_manager'])

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rabanok.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class RabanokBot:
    def __init__(self):
        self.config = Config()
        self.bot = Bot(token=self.config.BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = Database(self.config.DB_PATH)
        
        # Передаем бота в EmailManager
        email_manager.set_bot(self.bot)
        
        # Инициализация хендлеров
        self.user_handlers = UserHandlers(self.bot, self.db, self.config)
        self.admin_handlers = AdminHandlers(self.bot, self.db, self.config)
        
        # Инициализация баланс хендлеров через setup функцию
        self.balance_router = setup_balance_handlers(self.db)
        
        # Инициализация платежных обработчиков
        self.payment_handlers = setup_payment_handlers(self.bot, self.db, self.config)
        
        # Инициализация клавиатур
        self.keyboards = Keyboards()
        
        # Создаем отдельный роутер для вебхуков
        self.webhook_router = Router()
        self.register_handlers()

    def register_handlers(self):
        """Регистрация всех обработчиков"""
    
        # === ВКЛЮЧАЕМ РОУТЕРЫ ===
        self.dp.include_router(self.balance_router)
        
        # === КОМАНДЫ ПОЛЬЗОВАТЕЛЕЙ ===
        self.dp.message.register(self.user_handlers.start_handler, Command("start"))
        self.dp.message.register(self.user_handlers.start_handler, Command("menu"))
        self.dp.message.register(self.user_handlers.start_handler, Command("balance"))
        
        # === КОМАНДЫ ДЛЯ ОТЛАДКИ ПОЧТЫ ===
        self.dp.message.register(self.user_handlers.check_emails_status_command, Command("check_emails"))
        self.dp.message.register(self.user_handlers.test_email_sending_command, Command("test_email"))
        self.dp.message.register(self.user_handlers.validate_emails_command, Command("validate_emails"))
        
        # Админская команда /admin
        self.dp.message.register(self.handle_admin_command, Command("admin"))
        
        # === ОБЩИЕ CALLBACK ОБРАБОТЧИКИ ===
        self.dp.callback_query.register(self.user_handlers.process_callback)
        
        # Пользовательская статистика
        self.dp.callback_query.register(self.user_handlers.show_user_stats, F.data == "user_stats")
        
        # === ОСНОВНОЙ ОБРАБОТЧИК АДМИН CALLBACK'ОВ ===
        self.dp.callback_query.register(self.admin_handlers.process_admin_callbacks)
        
        # === ВСЕ АДМИН CALLBACK ОБРАБОТЧИКИ ===
        
        # Основные разделы админки
        self.dp.callback_query.register(self.admin_handlers.show_admin_panel, F.data == "admin_panel")
        self.dp.callback_query.register(self.admin_handlers.show_admin_stats, F.data == "admin_stats")
        self.dp.callback_query.register(self.admin_handlers.show_admin_users, F.data == "admin_users")
        self.dp.callback_query.register(self.admin_handlers.show_admin_sessions, F.data == "admin_sessions")
        self.dp.callback_query.register(self.admin_handlers.show_admin_emails, F.data == "admin_emails")
        self.dp.callback_query.register(self.admin_handlers.show_admin_blacklist, F.data == "admin_blacklist")
        self.dp.callback_query.register(self.admin_handlers.show_admin_finance, F.data == "admin_finance")
        self.dp.callback_query.register(self.admin_handlers.show_admin_settings, F.data == "admin_settings")
        self.dp.callback_query.register(self.admin_handlers.validate_sessions, F.data == "admin_validate")
        
        # Управление пользователями
        self.dp.callback_query.register(self.admin_handlers.admin_manage_users, F.data == "admin_manage_users")
        self.dp.callback_query.register(self.admin_handlers.admin_add_balance_handler, F.data == "admin_add_balance")
        self.dp.callback_query.register(self.admin_handlers.admin_ban_user_handler, F.data == "admin_ban_user")
        self.dp.callback_query.register(self.admin_handlers.admin_unban_user_handler, F.data == "admin_unban_user")
        self.dp.callback_query.register(self.admin_handlers.admin_delete_user_handler, F.data == "admin_delete_user")
        self.dp.callback_query.register(self.admin_handlers.admin_give_subscription, F.data == "admin_give_subscription")
        
        # Управление сессиями
        self.dp.callback_query.register(self.admin_handlers.start_add_session, F.data == "admin_add_session")
        self.dp.callback_query.register(self.admin_handlers.list_sessions, F.data == "admin_list_sessions")
        self.dp.callback_query.register(self.admin_handlers.mass_validate_sessions, F.data == "admin_mass_validate")
        self.dp.callback_query.register(self.admin_handlers.remove_invalid_sessions, F.data == "admin_remove_invalid")
        
        # Управление почтами - ВСЕ КНОПКИ
        self.dp.callback_query.register(self.admin_handlers.show_admin_emails, F.data == "admin_emails")
        self.dp.callback_query.register(self.admin_handlers.admin_emails_stats, F.data == "admin_emails_stats")
        self.dp.callback_query.register(self.admin_handlers.admin_clean_emails, F.data == "admin_clean_emails")
        self.dp.callback_query.register(self.admin_handlers.admin_export_emails, F.data == "admin_export_emails")
        self.dp.callback_query.register(self.admin_handlers.start_manual_emails, F.data == "admin_manual_emails")
        self.dp.callback_query.register(self.admin_handlers.admin_upload_emails, F.data == "admin_upload_emails")
        self.dp.callback_query.register(self.admin_handlers.list_emails, F.data == "admin_list_emails")
        self.dp.callback_query.register(self.admin_handlers.test_emails, F.data == "admin_test_emails")
        self.dp.callback_query.register(self.admin_handlers.show_admin_emails, F.data == "admin_emails_menu")
        self.dp.callback_query.register(self.admin_handlers.show_admin_sessions, F.data == "admin_sessions_menu")
        self.dp.callback_query.register(self.admin_handlers.show_admin_users, F.data == "admin_users_menu")
        
        # === НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ПРОВЕРКИ ПОЧТ С ПРОГРЕССОМ ===
        self.dp.callback_query.register(self.handle_mass_validate_emails, F.data == "admin_mass_validate_emails")
        self.dp.callback_query.register(self.handle_email_stats, F.data == "admin_email_stats")
    
        # === СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ===
        self.dp.message.register(
            self.user_handlers.process_target_input, 
            state=UserStates.waiting_for_target
        )
        self.dp.message.register(         
            self.user_handlers.process_deposit_amount,
            state=UserStates.waiting_deposit_amount
        )
        
        # === ДОБАВЛЕННОЕ СОСТОЯНИЕ ДЛЯ ПРИЧИНЫ ЖАЛОБЫ ===
        self.dp.message.register(
            self.user_handlers.process_reason_input,
            state=UserStates.waiting_for_reason
        )
    
        # === СОСТОЯНИЯ АДМИНОВ ===
        # Управление подписками
        self.dp.message.register(
            self.admin_handlers.process_subscription_user,
            state=AdminStates.waiting_for_subscription_user
        )

        # Управление сессиями
        self.dp.message.register(
            self.admin_handlers.process_session_phone,
            state=AdminStates.waiting_for_session_phone
        )
        self.dp.message.register(
            self.admin_handlers.process_session_code,
            state=AdminStates.waiting_for_session_code
        )
        self.dp.message.register(
            self.admin_handlers.process_session_password,
            state=AdminStates.waiting_for_session_password
        )

        # Управление почтами
        self.dp.message.register(
            self.admin_handlers.process_emails_file,
            state=AdminStates.waiting_for_emails_file
        )
        self.dp.message.register(
            self.admin_handlers.process_email_input,
            state=AdminStates.waiting_for_manual_emails
        )
        self.dp.message.register(
            self.admin_handlers.process_email_password,
            state=AdminStates.waiting_for_email_password
        )
        self.dp.message.register(
            self.admin_handlers.process_single_email,
            state=AdminStates.waiting_for_single_email
        )
    
        # === ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД ===
        self.dp.message.register(self.unknown_command_handler)

    async def handle_admin_command(self, message: Message):
        """Обработка команды /admin"""
        if message.from_user.id in self.config.ADMIN_IDS:
            # Показываем админ-панель
            await message.answer(
                "👨‍💻 Админ-панель",
                reply_markup=self.keyboards.admin_main_menu()
            )
        else:
            await message.answer("⛔ У вас нет доступа к админ-панели")

    async def handle_mass_validate_emails(self, callback_query: CallbackQuery):
        """Обработчик массовой проверки почт с прогрессом"""
        if callback_query.from_user.id not in self.config.ADMIN_IDS:
            await callback_query.answer("⛔ У вас нет доступа к админ-панели", show_alert=True)
            return
        
        await callback_query.answer("🚀 Запускаю массовую проверку почт...")
        
        try:
            # Получаем статистику перед началом
            stats = email_manager.get_stats()
            total_emails = stats["total"]
            
            if total_emails == 0:
                await callback_query.message.answer("❌ Нет почт для проверки")
                return
            
            # Запускаем проверку с прогрессом
            result = await email_manager.mass_validate_emails_with_progress(
                chat_id=callback_query.message.chat.id,
                batch_size=50,
                max_concurrent=30
            )
            
            # Дополнительное сообщение о результате
            await callback_query.message.answer(
                f"✅ Проверка завершена!\n"
                f"📊 Итог: {result['valid']}/{result['total']} валидных ({result['efficiency']:.1f}%)"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка при массовой проверке почт: {e}")
            await callback_query.message.answer(f"❌ Ошибка при проверке почт: {str(e)[:200]}")

    async def handle_email_stats(self, callback_query: CallbackQuery):
        """Обработчик отображения статистики почт"""
        if callback_query.from_user.id not in self.config.ADMIN_IDS:
            await callback_query.answer("⛔ У вас нет доступа к админ-панели", show_alert=True)
            return
        
        await callback_query.answer("📊 Получаю статистику...")
        
        try:
            stats = email_manager.get_stats()
            
            message_text = f"""
📧 СТАТИСТИКА ПОЧТ

📊 ОБЩАЯ СТАТИСТИКА:
├─ Всего почт: {stats['total']}
├─ 🟢 Валидных: {stats['valid']}
├─ 🔴 Невалидных: {stats['invalid']}
├─ 💯 Эффективность: {stats['efficiency']:.1f}%
├─ 🌐 Уникальных доменов: {stats['unique_domains']}
└─ 🏆 Лучший домен: {stats['best_domain']}

📁 ФАЙЛЫ:
├─ Файл с почтами: {email_manager.emails_file}
├─ Кэш валидных: {stats['cache_file_exists']}
└─ Статус загрузки: {"✅ Загружено" if stats['loaded'] else "❌ Не загружено"}

💡 РЕКОМЕНДАЦИИ:
{self._get_email_recommendation(stats['efficiency'])}
"""
            
            await callback_query.message.answer(message_text)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики почт: {e}")
            await callback_query.message.answer(f"❌ Ошибка при получении статистики: {str(e)[:200]}")

    def _get_email_recommendation(self, efficiency: float) -> str:
        """Получить рекомендацию по эффективности почт"""
        if efficiency > 50:
            return "• Отличный результат! Более 50% валидных почт"
        elif efficiency > 30:
            return "• Хороший результат. Можно использовать для работы"
        elif efficiency > 10:
            return "• Средний результат. Рекомендуется найти дополнительные источники почт"
        elif efficiency > 0:
            return "• Низкая эффективность. Рекомендуется заменить базу почт"
        else:
            return "• Нет валидных почт. Требуется загрузка новых почт"

    async def unknown_command_handler(self, message: Message):
        """Обработка неизвестных команд"""
        await message.answer(
            "❌ Неизвестная команда\n\n"
            "Используйте /start для начала работы",
            reply_markup=self.keyboards.main_menu(message.from_user.id, message.from_user.id in self.config.ADMIN_IDS)
        )

    async def stars_payment_webhook_handler(self, update_data: dict):
        """Обработчик вебхука для платежей Telegram Stars"""
        try:
            # Проверяем, что это pre_checkout_query
            if "pre_checkout_query" in update_data:
                # Обработка через payment_handlers
                success, message = await self.user_handlers.stars_service.process_stars_payment_webhook(update_data)
                
                if success:
                    return {"status": "success", "message": message}
                else:
                    return {"status": "error", "message": message}
            
            return {"status": "ignored", "message": "Not a payment webhook"}
        
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def initialize_services(self):
        """Инициализация всех сервисов"""
        logger.info("🔄 Инициализация сервисов...")
        
        # Инициализация платежной системы
        payment_ok = await initialize_payment_service(self.config.CRYPTOBOT_TOKEN)
        if not payment_ok:
            logger.warning("⚠️ Платежная система не инициализирована корректно")
        
        # Инициализация сервиса переводов
        translation_ok = await initialize_translation_service()
        if not translation_ok:
            logger.warning("⚠️ Сервис переводов не инициализирован корректно")
        
        # Инициализация Stars платежей
        await self.user_handlers.stars_service.initialize()

        # Автоматическая проверка части почт при старте
        logger.info("📧 Проверка части почт на валидность...")
        
        # Проверяем первые 100 почт для быстрой оценки
        sample_size = min(100, email_manager.get_email_count())
        if sample_size > 0:
            sample_emails = email_manager.emails[:sample_size]
            valid_count = 0
            
            for email_data in sample_emails:
                email = email_data['email']
                password = email_data['password']
                
                if await email_manager.validate_email_fast(email, password):
                    valid_count += 1
            
            logger.info(f"📊 Проверено {sample_size} почт из {email_manager.get_email_count()}")
            logger.info(f"✅ Валидных в выборке: {valid_count} ({valid_count/sample_size*100:.1f}%)")
            
            # Прогноз на все почты
            estimated_valid = int((valid_count / sample_size) * email_manager.get_email_count())
            logger.info(f"📈 Прогноз валидных почт всего: ~{estimated_valid}")
        
        logger.info("✅ Все сервисы инициализированы")

    async def run(self):
        """Запуск бота"""
        logger.info("🚀 RABANOK REPORTER v6.0 запускается...")
        
        try:
            # Инициализация сервисов
            await self.initialize_services()
            
            # Проверка подключения бота
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Бот @{bot_info.username} успешно подключен")
            
            # Проверка базы данных (тестовый запрос)
            try:
                test_user = self.db.get_user(123)
                logger.info("✅ База данных подключена успешно")
            except Exception as db_error:
                logger.error(f"❌ Ошибка базы данных: {db_error}")
            
            # Проверка директорий
            if not os.path.exists(self.config.SESSIONS_DIR):
                os.makedirs(self.config.SESSIONS_DIR)
                logger.info("✅ Создана директория sessions")
            
            if not os.path.exists(self.config.EMAILS_DIR):
                os.makedirs(self.config.EMAILS_DIR) 
                logger.info("✅ Создана директория emails")
            
            # Статистика системы
            try:
                session_files = len([f for f in os.listdir(self.config.SESSIONS_DIR) if f.endswith('.session')])
                logger.info(f"📊 Загружено сессий: {session_files}")
            except Exception as e:
                logger.warning(f"Не удалось посчитать сессии: {e}")
            
            # Статистика почт
            email_stats = email_manager.get_stats()
            logger.info(f"📧 Загружено почт: {email_stats['total']}, Валидных в кэше: {email_stats['valid']}")
            
            # Запуск поллинга
            logger.info("🔄 Запуск обработки сообщений...")
            await self.dp.start_polling(
                self.bot, 
                allowed_updates=["message", "callback_query"],
                skip_updates=True
            )
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка запуска бота: {e}", exc_info=True)
            raise
        finally:
            if hasattr(self, 'user_handlers') and getattr(self.user_handlers, 'stars_service', None):
                await self.user_handlers.stars_service.close()
            if hasattr(self, 'bot'):
                await self.bot.session.close()
                logger.info("🔌 Сессия бота закрыта")

async def main():
    """Основная функция запуска"""
    try:
        bot = RabanokBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}", exc_info=True)
    finally:
        logger.info("👋 RABANOK REPORTER завершил работу")

if __name__ == "__main__":
    # Настройка event loop для Windows
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")