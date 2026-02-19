from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from core.antiddos_system import antiddos
from services.telegram_logger import log_attack, log_user_action
import logging

logger = logging.getLogger(__name__)

async def setup_protection_middleware(dp: Dispatcher):
    """Настраивает middleware защиты"""
    
    @dp.middleware()
    async def protection_middleware(handler, event, data):
        """Middleware для защиты всех запросов"""
        
        # Пропускаем служебные обновления
        if not hasattr(event, 'from_user'):
            return await handler(event, data)
        
        user_id = event.from_user.id
        
        # Определяем команду
        command = 'other'
        if hasattr(event, 'text') and event.text:
            if event.text.startswith('/start'):
                command = 'start'
            elif event.text.startswith('/report'):
                command = 'report'
            elif event.text.startswith('/nuke'):
                command = 'nuke'
            elif event.text.startswith('/balance'):
                command = 'balance'
            elif event.text.startswith('/pay'):
                command = 'payment'
        
        # Проверяем защиту
        if await antiddos.protect_command(event, command):
            # Логируем успешный запрос
            await log_user_action(
                user_id,
                f"command_{command}",
                {'text': getattr(event, 'text', '')[:100]}
            )
            return await handler(event, data)
        
        # Если защита сработала, не вызываем хендлер
        return
    
    logger.info("Middleware защиты активирован")

async def handle_captcha_response(message: types.Message, state: FSMContext):
    """Обработчик ответов на капчу"""
    user_id = message.from_user.id
    
    # Проверяем, ожидается ли капча от этого пользователя
    if user_id in antiddos.active_captchas:
        # Проверка происходит в antiddos.verify_captcha
        pass
    else:
        await message.answer("Капча не требуется или время истекло.")

async def admin_check_attacks(message: types.Message):
    """Админ: проверка атак"""
    from core.config import ADMINS
    
    if message.from_user.id not in ADMINS:
        return
    
    # Получаем статистику атак
    attack_stats = await antiddos.get_attack_stats()
    
    text = (
        "📊 <b>Статистика атак</b>\n\n"
        f"Всего атак сегодня: {attack_stats.get('total', 0)}\n"
        f"Заблокировано пользователей: {attack_stats.get('banned', 0)}\n"
        f"Активных капч: {len(antiddos.active_captchas)}\n\n"
        f"Топ атакующих:\n"
    )
    
    for user_id, count in attack_stats.get('top_attackers', [])[:5]:
        text += f"• ID {user_id}: {count} атак\n"
    
    await message.answer(text, parse_mode='HTML')

async def admin_unban_user(message: types.Message):
    """Админ: разбан пользователя"""
    from core.config import ADMINS
    
    if message.from_user.id not in ADMINS:
        return
    
    args = message.get_args()
    if not args:
        await message.answer("Использование: /unban user_id")
        return
    
    try:
        user_id = int(args)
        await antiddos.redis.delete(f"ban:{user_id}")
        await message.answer(f"✅ Пользователь {user_id} разбанен")
    except ValueError:
        await message.answer("❌ Неверный ID пользователя")

def register_protection_handlers(dp: Dispatcher):
    """Регистрирует обработчики защиты"""
    dp.register_message_handler(
        handle_captcha_response,
        content_types=['text'],
        state="*"
    )
    
    dp.register_message_handler(
        admin_check_attacks,
        commands=['attacks'],
        state="*"
    )
    
    dp.register_message_handler(
        admin_unban_user,
        commands=['unban'],
        state="*"
    )