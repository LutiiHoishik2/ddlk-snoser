import json
from datetime import datetime
from aiogram import Bot
from core.config import BOT_TOKEN, LOG_GROUP_ID

bot = Bot(token=BOT_TOKEN)

# Темы для логов
TOPICS = {
    'ATTACK': '🛡️ Атаки и защита',
    'REPORT': '⚠️ Репорты и жалобы',
    'NUKE': '💣 NUKE операции',
    'PAYMENT': '💰 Платежи',
    'SESSION': '🔐 Сессии',
    'SYSTEM': '⚙️ Система',
    'ERROR': '🚨 Ошибки',
    'MODERATION': '⚖️ Модерация',
    'USER': '👤 Пользователи'
}

# Кэш ID тем
topic_ids = {}

async def get_topic_id(topic_name: str) -> int:
    """Получает ID темы"""
    if topic_name in topic_ids:
        return topic_ids[topic_name]
    
    try:
        # Ищем существующую тему
        # (В реальности нужно сохранять ID тем при создании)
        return 1  # Основная тема
    except:
        return 1

async def send_log(log_type: str, message: str, data: dict = None):
    """Отправляет лог в Telegram"""
    try:
        topic_id = await get_topic_id(log_type)
        
        # Форматируем сообщение
        formatted = format_log_message(log_type, message, data)
        
        # Отправляем
        await bot.send_message(
            chat_id=LOG_GROUP_ID,
            message_thread_id=topic_id,
            text=formatted,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        print(f"Ошибка отправки лога: {e}")

def format_log_message(log_type: str, message: str, data: dict = None) -> str:
    """Форматирует сообщение лога"""
    icon = {
        'ATTACK': '🛡️',
        'REPORT': '⚠️',
        'NUKE': '💣',
        'PAYMENT': '💰',
        'SESSION': '🔐',
        'SYSTEM': '⚙️',
        'ERROR': '🚨',
        'MODERATION': '⚖️',
        'USER': '👤'
    }.get(log_type, '📝')
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    lines = [
        f"{icon} <b>{TOPICS.get(log_type, log_type)}</b>",
        f"Время: {timestamp}",
        "",
        message
    ]
    
    if data:
        lines.append("")
        lines.append("<b>Данные:</b>")
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False, indent=2)
                if len(value_str) > 500:
                    value_str = value_str[:500] + "..."
                lines.append(f"{key}: <code>{value_str}</code>")
            else:
                lines.append(f"{key}: {value}")
    
    lines.append("─" * 30)
    
    return "\n".join(lines)

# Специализированные методы
async def log_attack(user_id: int, attack_type: str, details: dict):
    """Логирование атаки"""
    await send_log(
        'ATTACK',
        f"{attack_type} атака от пользователя",
        {'user_id': user_id, **details}
    )

async def log_report(user_id: int, target: str, result: str):
    """Логирование репорта"""
    await send_log(
        'REPORT',
        f"Репорт отправлен",
        {
            'user_id': user_id,
            'target': target,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
    )

async def log_nuke(user_id: int, target: str, method: str):
    """Логирование NUKE операции"""
    await send_log(
        'NUKE',
        f"NUKE операция выполнена",
        {
            'user_id': user_id,
            'target': target,
            'method': method,
            'timestamp': datetime.now().isoformat()
        }
    )

async def log_payment(user_id: int, amount: float, method: str):
    """Логирование платежа"""
    await send_log(
        'PAYMENT',
        f"Платеж получен",
        {
            'user_id': user_id,
            'amount': amount,
            'method': method,
            'timestamp': datetime.now().isoformat()
        }
    )

async def log_session_activity(user_id: int, action: str, session_id: str = None):
    """Логирование активности сессий"""
    await send_log(
        'SESSION',
        f"Действие с сессией: {action}",
        {
            'user_id': user_id,
            'session_id': session_id,
            'action': action,
            'timestamp': datetime.now().isoformat()
        }
    )

async def log_error(error: Exception, context: str = ""):
    """Логирование ошибки"""
    import traceback
    tb = traceback.format_exception(type(error), error, error.__traceback__)
    
    await send_log(
        'ERROR',
        f"Ошибка: {context}",
        {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': "".join(tb[-3:])
        }
    )