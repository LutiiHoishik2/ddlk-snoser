import asyncio
import json
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from aiogram import types

logger = logging.getLogger(__name__)

class AntiDDOSSystem:
    """
    Основная система защиты от DDoS атак для Rabanok Bot
    """
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379):
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True
        )
        
        # Лимиты для разных команд
        self.limits = {
            'start': {'minute': 3, 'hour': 10, 'day': 50},
            'report': {'minute': 2, 'hour': 20, 'day': 200},
            'nuke': {'minute': 1, 'hour': 5, 'day': 20},
            'balance': {'minute': 5, 'hour': 30, 'day': 100},
            'payment': {'minute': 3, 'hour': 15, 'day': 50}
        }
        
        # Ботнет паттерны
        self.botnet_patterns = self._load_botnet_patterns()
        
        # Активные капчи
        self.active_captchas = {}
        
        # Группа для логов
        self.log_group_id = -1002996528027
    
    def _load_botnet_patterns(self) -> Dict:
        """Загружает паттерны ботнетов"""
        try:
            with open('data/botnet_patterns.json', 'r') as f:
                return json.load(f)
        except:
            return {
                'common_usernames': ['user', 'bot', 'test', 'temp', 'account'],
                'suspicious_patterns': [
                    'mass_report', 'spam_nuke', 'flood_start'
                ]
            }
    
    async def protect_command(self, message: types.Message, command: str) -> bool:
        """
        Защита для конкретной команды
        Возвращает True если доступ разрешен
        """
        user_id = message.from_user.id
        
        # 1. Проверка бана
        if await self.is_user_banned(user_id):
            await message.answer("🚫 Ваш аккаунт заблокирован за нарушение правил.")
            return False
        
        # 2. Проверка лимитов
        if not await self.check_rate_limit(user_id, command):
            await self.handle_flood(user_id, command)
            return False
        
        # 3. Проверка на ботнет
        if await self.detect_botnet_activity(user_id, message, command):
            await self.handle_botnet(user_id)
            return False
        
        # 4. Капча для подозрительных
        if await self.requires_captcha(user_id):
            if not await self.verify_captcha(user_id, message):
                return False
        
        return True
    
    async def check_rate_limit(self, user_id: int, command: str) -> bool:
        """Проверяет лимиты запросов"""
        now = datetime.now()
        limits = self.limits.get(command)
        if not limits:
            # Нет лимитов для этой команды — разрешаем
            return True
        
        # Минутный лимит
        minute_key = f"limit:{user_id}:{command}:{now.strftime('%Y%m%d%H%M')}"
        minute_count = await self.redis.incr(minute_key)
        await self.redis.expire(minute_key, 60)
        
        if minute_count > limits['minute']:
            logger.warning(f"Минутный лимит превышен: user={user_id}, command={command}")
            return False
        
        # Часовой лимит
        hour_key = f"limit:{user_id}:{command}:{now.strftime('%Y%m%d%H')}"
        hour_count = await self.redis.incr(hour_key)
        await self.redis.expire(hour_key, 3600)
        
        if hour_count > limits['hour']:
            logger.warning(f"Часовой лимит превышен: user={user_id}, command={command}")
            return False

        # Дневной лимит
        day_key = f"limit:{user_id}:{command}:{now.strftime('%Y%m%d')}"
        day_count = await self.redis.incr(day_key)
        await self.redis.expire(day_key, 86400)
        if day_count > limits.get('day', float('inf')):
            logger.warning(f"Дневной лимит превышен: user={user_id}, command={command}")
            return False
        
        return True
    
    async def detect_botnet_activity(self, user_id: int, message: types.Message, command: str) -> bool:
        """Обнаружение ботнет-активности"""
        user = message.from_user
        
        # Проверка username
        if user.username:
            username_lower = user.username.lower()
            for pattern in self.botnet_patterns['common_usernames']:
                if pattern in username_lower:
                    await self.log_suspicious(user_id, f"botnet_username: {username_lower}")
                    return True
        
        # Проверка частоты запросов
        request_key = f"requests:{user_id}:all"
        request_count = await self.redis.incr(request_key)
        await self.redis.expire(request_key, 300)
        
        if request_count > 50:  # 50+ запросов за 5 минут
            await self.log_suspicious(user_id, f"high_frequency: {request_count}")
            return True
        
        # Проверка команд /start
        if command == 'start':
            start_key = f"starts:{user_id}:{datetime.now().strftime('%Y%m%d')}"
            start_count = await self.redis.incr(start_key)
            await self.redis.expire(start_key, 86400)
            
            if start_count > 10:  # 10+ стартов в день
                return True
        
        return False
    
    async def handle_flood(self, user_id: int, command: str):
        """Обработка флуда"""
        # Временный бан на 30 минут
        await self.redis.setex(
            f"ban:{user_id}",
            1800,
            f"flood_{command}"
        )
        
        # Логирование
        await self.log_to_telegram(
            'ATTACK',
            f"Флуд защита: user={user_id}, command={command}",
            {'user_id': user_id, 'command': command, 'action': 'temp_ban_30min'}
        )
    
    async def handle_botnet(self, user_id: int):
        """Обработка ботнет-атаки"""
        # Бан на 24 часа
        await self.redis.setex(
            f"ban:{user_id}",
            86400,
            "botnet_activity"
        )
        
        # Сохраняем в файл
        await self.save_to_blacklist(user_id, "botnet")
        
        await self.log_to_telegram(
            'CRITICAL',
            f"Ботнет заблокирован: user={user_id}",
            {'user_id': user_id, 'action': 'ban_24h', 'reason': 'botnet'}
        )
    
    async def requires_captcha(self, user_id: int) -> bool:
        """Проверяет, нужна ли капча"""
        suspicious_key = f"suspicious:{user_id}"
        count = await self.redis.get(suspicious_key)
        try:
            return int(count or 0) >= 3
        except (TypeError, ValueError):
            return False
    
    async def verify_captcha(self, user_id: int, message: types.Message) -> bool:
        """Верификация капчи"""
        from utils.captcha_generator import generate_captcha
        
        if user_id not in self.active_captchas:
            # Генерируем новую капчу
            captcha = generate_captcha()
            self.active_captchas[user_id] = captcha
            
            await message.answer(
                f"🔐 <b>Требуется проверка безопасности</b>\n\n"
                f"Решите пример: <code>{captcha['question']}</code>\n\n"
                f"У вас есть 2 минуты.",
                parse_mode='HTML'
            )
            
            # Таймер для капчи
            asyncio.create_task(self.clear_captcha(user_id, 120))
            return False
        
        # Проверяем ответ
        if not message.text:
            await message.answer("❌ Отправьте число.")
            return False
        try:
            user_answer = int(message.text.strip())
            correct_answer = self.active_captchas[user_id]['answer']
            
            if user_answer == correct_answer:
                del self.active_captchas[user_id]
                await self.redis.delete(f"suspicious:{user_id}")
                await message.answer("✅ Проверка пройдена!")
                return True
            else:
                # Неверная капча
                fails_key = f"captcha_fails:{user_id}"
                fails = await self.redis.incr(fails_key)
                await self.redis.expire(fails_key, 3600)
                
                if fails >= 5:
                    await self.redis.setex(f"ban:{user_id}", 7200, "captcha_fail")
                    await message.answer("🚫 Слишком много ошибок. Бан на 2 часа.")
                else:
                    await message.answer(f"❌ Неверно. Попыток: {5 - fails}")
                
                return False
                
        except (ValueError, TypeError):
            await message.answer("❌ Отправьте число.")
            return False
    
    async def clear_captcha(self, user_id: int, timeout: int = 120):
        """Очистка капчи по таймауту"""
        await asyncio.sleep(timeout)
        if user_id in self.active_captchas:
            del self.active_captchas[user_id]
            await self.redis.setex(f"ban:{user_id}", 600, "captcha_timeout")
    
    async def is_user_banned(self, user_id: int) -> bool:
        """Проверяет бан пользователя"""
        return bool(await self.redis.exists(f"ban:{user_id}"))
    
    async def log_suspicious(self, user_id: int, reason: str):
        """Логирование подозрительной активности"""
        key = f"suspicious:{user_id}"
        await self.redis.incr(key)
        await self.redis.expire(key, 3600)
        
        await self.redis.rpush(
            "suspicious_logs",
            json.dumps({
                'user_id': user_id,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            })
        )
    
    async def log_to_telegram(self, log_type: str, message: str, data: Dict = None):
        """Отправляет лог в Telegram группу"""
        try:
            from services.telegram_logger import send_log
            await send_log(log_type, message, data)
        except Exception as e:
            logger.error(f"Ошибка отправки лога в Telegram: {e}")
    
    async def save_to_blacklist(self, user_id: int, reason: str):
        """Сохраняет в черный список"""
        try:
            with open('data/banned_users.json', 'r+') as f:
                banned = json.load(f)
                if not isinstance(banned, dict):
                    banned = {}
                banned[str(user_id)] = {
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                }
                f.seek(0)
                f.truncate()
                json.dump(banned, f, indent=2)
        except Exception:
            with open('data/banned_users.json', 'w') as f:
                json.dump({str(user_id): {
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                }}, f, indent=2)
    
    async def get_user_stats(self, user_id: int) -> Dict:
        """Статистика пользователя"""
        stats = {
            'banned': await self.is_user_banned(user_id),
            'suspicious_score': int(await self.redis.get(f"suspicious:{user_id}") or 0),
            'requests_today': await self.get_requests_today(user_id)
        }
        
        # Если есть бан, получаем причину
        if stats['banned']:
            stats['ban_reason'] = await self.redis.get(f"ban:{user_id}")
        
        return stats
    
    async def get_requests_today(self, user_id: int) -> int:
        """Количество запросов сегодня"""
        pattern = f"limit:{user_id}:*:{datetime.now().strftime('%Y%m%d')}*"
        keys = await self.redis.keys(pattern)
        total = 0
        
        for key in keys:
            count = await self.redis.get(key)
            if count:
                total += int(count)
        
        return total

# Синглтон
antiddos = AntiDDOSSystem()