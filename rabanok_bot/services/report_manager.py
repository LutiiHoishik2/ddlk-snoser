import random
import re 
import asyncio
import logging
from typing import List, Tuple, Dict, Optional, Any
from telethon import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import InputPeerChannel, InputPeerChat, InputPeerUser
from telethon.errors import FloodWaitError, SessionPasswordNeededError, AuthKeyError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import Channel, Chat
from .session_manager import SessionManager
from .email_manager import EmailManager
from .translation_service import TranslationService
from core.database import Database
from core.config import Config
import sqlite3
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ReportManager:
    def __init__(self, session_manager=None, email_manager=None, translator=None, db=None):
        self.session_manager = session_manager
        self.email_manager = email_manager
        self.translator = translator
        self.db = db
        self.max_reports_per_target = 3
        self.penalty_amount = 30.0
        self.daily_limit = 10
        self.cooldown_minutes = 20
        self.link_checker = None
        
        logger.info("✅ ReportManager инициализирован")
        
    async def initialize_link_checker(self, api_id: int, api_hash: str):
        """Инициализация проверщика ссылок"""
        if self.session_manager and hasattr(self.session_manager, 'api_id'):
            from services.link_privacy_checker import LinkPrivacyChecker
            self.link_checker = LinkPrivacyChecker(
                api_id=api_id,
                api_hash=api_hash
            )
            await self.link_checker.initialize()
            logger.info("✅ LinkPrivacyChecker инициализирован")

    def get_random_session(self) -> Tuple[str, str]:
        """Получить случайную валидную сессию из базы"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_file FROM admin_sessions 
                WHERE validity = "valid"
                ORDER BY RANDOM() LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0], "US"
            return None, "US"
            
        except Exception as e:
            logger.error(f"Error getting random session: {e}")
            return None, "US"
            
    async def get_user_report_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики жалоб пользователя"""
        try:
            if self.db:
                stats = self.db.get_user_report_stats(user_id)
                # Получаем дополнительную информацию из базы
                balance = self.db.get_user_balance(user_id) if hasattr(self.db, 'get_user_balance') else 0.0
                sub_info = self.db.get_subscription_info(user_id) if hasattr(self.db, 'get_subscription_info') else {}
                
                return {
                    "daily_used": stats.get("daily_used", 0),
                    "daily_limit": stats.get("daily_limit", self.daily_limit),
                    "total_penalties": self.db.get_user_penalties_total(user_id) if hasattr(self.db, 'get_user_penalties_total') else 0.0,
                    "balance": balance,
                    "has_subscription": sub_info.get('is_active', False),
                    "cooldown_active": stats.get("cooldown_active", False),
                    "cooldown_message": "",
                    "target_stats": stats.get("target_stats", []),
                    "has_double_complaints": stats.get("has_double_complaints", False),
                    "total_targets": stats.get("total_targets", 0)
                }
            else:
                return {
                    "daily_used": 0,
                    "daily_limit": self.daily_limit,
                    "total_penalties": 0.0,
                    "balance": 0.0,
                    "has_subscription": False,
                    "cooldown_active": False,
                    "cooldown_message": "",
                    "target_stats": [],
                    "has_double_complaints": False,
                    "total_targets": 0
                }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {
                "daily_used": 0,
                "daily_limit": self.daily_limit,
                "total_penalties": 0.0,
                "balance": 0.0,
                "has_subscription": False,
                "cooldown_active": False,
                "cooldown_message": "",
                "target_stats": [],
                "has_double_complaints": False,
                "total_targets": 0
            }
            
    def get_all_valid_sessions(self, limit: int = 50) -> List[str]:
        """Получить все валидные сессии для массовой атаки"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_file FROM admin_sessions 
                WHERE validity = "valid"
                LIMIT ?
            ''', (limit,))
            results = cursor.fetchall()
            conn.close()
            
            return [result[0] for result in results]
        except Exception as e:
            logger.error(f"Error getting all valid sessions: {e}")
            return []

    def get_random_email(self) -> Tuple[str, str]:
        """Получить случайную валидную почту из базы"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT email, password FROM admin_emails 
                WHERE status = "active"
                ORDER BY RANDOM() LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0], result[1]
            return None, None
            
        except Exception as e:
            logger.error(f"Error getting random email: {e}")
            return None, None

    async def execute_session_report(self, session_file: str, target: str, reason: int, country_code: str = "US") -> Tuple[bool, str]:
        """Выполнить жалобу через сессию - РЕАЛЬНАЯ ОТПРАВКА"""
        if not session_file:
            return False, "Нет доступных сессий"
        
        try:
            # РЕАЛЬНАЯ ОТПРАВКА ЧЕРЕЗ TELEGRAM API
            success, result = await self.session_manager.send_report(session_file, target, reason)
            
            if success:
                logger.info(f"✅ Report sent via {session_file} to {target}")
                return True, "Жалоба успешно отправлена через сессию"
            else:
                logger.error(f"❌ Report failed via {session_file}: {result}")
                return False, f"Ошибка сессии: {result}"
                
        except Exception as e:
            logger.error(f"❌ Session report error for {session_file}: {e}")
            return False, f"Ошибка отправки: {str(e)}"

    async def execute_email_report(self, email_data: Tuple[str, str], target: str, reason: int, country_code: str = "US") -> Tuple[bool, str]:
        """Выполнить жалобу через почту - РЕАЛЬНАЯ ОТПРАВКА"""
        email, password = email_data
        if not email or not password:
            return False, "Нет доступных почт"
        
        try:
            # РЕАЛЬНАЯ ОТПРАВКА ЧЕРЕЗ EMAIL
            success, result = await self.email_manager.send_complaint(email, password, target, reason)
            
            if success:
                logger.info(f"✅ Email report sent via {email} to {target}")
                return True, "Жалоба успешно отправлена через почту"
            else:
                logger.error(f"❌ Email report failed via {email}: {result}")
                return False, f"Ошибка почты: {result}"
                
        except Exception as e:
            logger.error(f"❌ Email report error for {email}: {e}")
            return False, f"Ошибка отправки: {str(e)}"

    async def execute_combo_report(self, session_file: str, email_data: Tuple[str, str], target: str, reason: int, country_code: str = "US") -> Tuple[bool, str]:
        """Выполнить комбо жалобу (сессия + почта) - РЕАЛЬНАЯ ОТПРАВКА"""
        try:
            # Параллельная отправка через сессию и почту
            session_task = asyncio.create_task(
                self.execute_session_report(session_file, target, reason, country_code)
            )
            email_task = asyncio.create_task(
                self.execute_email_report(email_data, target, reason, country_code)
            )
            
            # Ожидаем завершения обеих задач
            session_result = await session_task
            email_result = await email_task
            
            session_success, session_msg = session_result
            email_success, email_msg = email_result
            
            if session_success or email_success:
                success_count = sum([session_success, email_success])
                return True, f"Успешно: {success_count}/2 (сессия: {session_success}, почта: {email_success})"
            else:
                return False, f"Все методы не сработали: сессия - {session_msg}, почта - {email_msg}"
                
        except Exception as e:
            logger.error(f"❌ Combo report error: {e}")
            return False, f"Ошибка комбо атаки: {str(e)}"

    async def execute_dsa_report(self, target: str, reason: int, country_code: str = "DE") -> Tuple[bool, str]:
        """Выполнить DSA жалобу - РЕАЛЬНАЯ ОТПРАВКА"""
        try:
            # РЕАЛЬНАЯ ЛОГИКА DSA ЖАЛОБ
            success, result = await self.email_manager.send_dsa_complaint(target, reason, country_code)
            
            if success:
                logger.info(f"✅ DSA report sent for {target} to {country_code}")
                return True, f"DSA жалоба отправлена в регуляторы {country_code}"
            else:
                logger.error(f"❌ DSA report failed for {target}: {result}")
                return False, f"Ошибка DSA: {result}"
                
        except Exception as e:
            logger.error(f"❌ DSA report error: {e}")
            return False, f"Ошибка DSA отправки: {str(e)}"

    async def execute_nuke_report(self, target: str, reason: str, user_id: int) -> Tuple[bool, str]:
        """
        Выполнить снос сессий через ПОЧТУ (не сессии!)
        """
        try:
            # 1. Получаем ВСЕ активные почты
            email_count = self.email_manager.get_email_count()
            
            if email_count < 10:
                return False, "❌ Недостаточно почт для NUKE атаки (минимум 10)"
            
            # 2. Берем все почты
            all_emails = self.email_manager.get_emails(email_count)
            
            # 3. Отправляем жалобы через ВСЕ почты
            success_count = 0
            total_emails = len(all_emails)
            
            logger.info(f"💣 Запуск NUKE атаки на {target} с {total_emails} почтами")
            
            for i, email_data in enumerate(all_emails[:50], 1):  # Ограничиваем 50 почтами
                try:
                    email = email_data['email']
                    password = email_data['password']
                    
                    # Конвертируем причину NUKE в стандартный reason_id
                    reason_id = self.convert_nuke_reason_to_id(reason)
                    
                    success, result = await self.email_manager.send_complaint(
                        email, password, target, reason_id
                    )
                    
                    if success:
                        success_count += 1
                        logger.info(f"✅ NUKE почта #{i}/{total_emails} отправлена с {email}")
                    else:
                        logger.warning(f"⚠️ NUKE почта #{i} failed: {result}")
                    
                    # Задержка между отправками
                    await asyncio.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка NUKE почты #{i}: {e}")
                    continue
            
            # 4. Обновляем счетчик NUKE у пользователя
            self.db.increment_nuke_count(user_id)
            
            success_rate = (success_count / total_emails) * 100
            return True, f"💣 NUKE завершен: {success_count}/{total_emails} почт ({success_rate:.1f}%)"
            
        except Exception as e:
            logger.error(f"❌ NUKE attack error: {e}")
            return False, f"Ошибка сноса: {str(e)}"

    def convert_nuke_reason_to_id(self, nuke_reason: str) -> int:
        """
        Конвертирует причину NUKE в стандартный reason_id
        """
        nuke_reason_map = {
            "nuke_reason_hack": 5,    # Взлом аккаунта
            "nuke_reason_spam": 3,    # Спам рассылка
            "nuke_reason_scam": 4,    # Мошенничество
            "nuke_reason_illegal": 7, # Нелегальный контент
            "nuke_reason_other": 8    # Другая причина
        }
        return nuke_reason_map.get(nuke_reason, 8)

    # ===== НОВЫЕ МЕТОДЫ ДЛЯ СИСТЕМЫ ОГРАНИЧЕНИЙ =====
    
    async def process_report(self, user_id: int, target: str, target_type: str, reason: int, method: str) -> Dict[str, Any]:
        """Обработка отправки жалобы"""
        try:
            if self.db:
                result = self.db.add_report(user_id, target, target_type, reason, method)
                return result
            else:
                return {
                    "success": False,
                    "message": "❌ База данных не доступна"
                }
        except Exception as e:
            logger.error(f"❌ Ошибка обработки жалобы {user_id}->{target}: {e}")
            return {
                "success": False,
                "message": f"❌ Ошибка отправки жалобы: {str(e)}"
            }
    
    def get_limit_info(self) -> Dict[str, Any]:
        """Получение информации о лимитах"""
        return {
            "max_reports_per_target": self.max_reports_per_target,
            "penalty_amount": self.penalty_amount,
            "daily_limit": self.daily_limit,
            "cooldown_minutes": self.cooldown_minutes
        }
        
    async def can_make_report(self, user_id: int, target: str) -> Dict[str, Any]:
        """Проверка возможности отправки жалобы"""
        try:
            if self.db:
                return self.db.can_make_report_with_limits(user_id, target)
            else:
                return {
                    "can_report": True,
                    "messages": [],
                    "penalty_applied": False,
                    "penalty_amount": self.penalty_amount,
                    "target_limit_exceeded": False,
                    "subscription_will_be_removed": False
                }
        except Exception as e:
            logger.error(f"❌ Ошибка проверки возможности отправки жалобы {user_id}: {e}")
            return {
                "can_report": False,
                "messages": ["❌ Ошибка проверки ограничений"],
                "penalty_applied": False,
                "penalty_amount": self.penalty_amount,
                "target_limit_exceeded": False,
                "subscription_will_be_removed": False
            }
    
    async def check_report_limits(self, user_id: int, target: str) -> Dict[str, Any]:
        """
        Проверка всех ограничений перед отправкой жалобы
        Возвращает словарь с результатами проверок
        """
        try:
            # СНАЧАЛА проверяем подписку и старую систему доступа
            can_report_old = self.db.can_make_report(user_id, "session")
            
            if not can_report_old:
                return {
                    "can_report": False,
                    "messages": ["❌ Нет доступа к отправке жалоб. Проверьте подписку или баланс"],
                    "penalty_applied": False,
                    "penalty_amount": self.penalty_amount,
                    "target_limit_exceeded": False
                }
            
            # ТОЛЬКО если есть доступ, проверяем новые ограничения
            result = self.db.can_make_report_with_limits(user_id, target)
            
            # Дополнительная проверка баланса для штрафов
            if result["penalty_applied"]:
                user_balance = self.db.get_user_balance(user_id)
                if user_balance < self.penalty_amount:
                    result["can_report"] = False
                    result["messages"] = [f"❌ Недостаточно средств для штрафа. Нужно: {self.penalty_amount}, есть: {user_balance}"]
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error checking report limits for {user_id}: {e}")
            # В случае ошибки - разрешаем по старой системе
            user = self.db.get_user(user_id)
            if user and (user[7] or user[2] > 0):  # subscription_type или баланс
                return {
                    "can_report": True,
                    "messages": ["⚠️ Проверка ограничений не сработала, но у вас есть доступ"],
                    "penalty_applied": False,
                    "penalty_amount": self.penalty_amount,
                    "target_limit_exceeded": False
                }
            else:
                return {
                    "can_report": False,
                    "messages": [f"❌ Ошибка проверки ограничений: {str(e)}"],
                    "penalty_applied": False,
                    "penalty_amount": self.penalty_amount,
                    "target_limit_exceeded": False
                }
                
    async def process_report_with_limits(self, user_id: int, target: str, method: str, reason: int, target_type: str = "user") -> Dict[str, Any]:
        """
        Основной метод для обработки жалоб с учетом ограничений
        """
        try:
            # 1. Проверяем ОСНОВНОЙ доступ (подписка/баланс)
            if not self.db.can_make_report(user_id, method):
                user = self.db.get_user(user_id)
                balance = user[2] if user else 0
                has_subscription = bool(user[7] if user and len(user) > 7 else None)
                
                error_msg = "❌ <b>НЕТ ДОСТУПА К ОТПРАВКЕ ЖАЛОБ</b>\n\n"
                
                if self.db.is_user_banned(user_id):
                    error_msg += "🚫 Ваш аккаунт заблокирован\n"
                elif not has_subscription and balance <= 0:
                    error_msg += "💎 <b>Для отправки жалоб необходимо:</b>\n"
                    error_msg += "• Активная подписка ИЛИ\n"
                    error_msg += "• Положительный баланс\n\n"
                    error_msg += f"💰 Ваш баланс: ${balance:.2f}\n"
                    error_msg += f"🎫 Подписка: {'✅ Активна' if has_subscription else '❌ Неактивна'}"
                elif has_subscription:
                    # Проверяем срок подписки
                    sub_end = user[8] if user and len(user) > 8 else None
                    if sub_end:
                        try:
                            end_date = datetime.strptime(sub_end, '%Y-%m-%d %H:%M:%S')
                            if datetime.now() > end_date:
                                error_msg += "📅 <b>Срок вашей подписки истек!</b>\n"
                                error_msg += f"💰 Ваш баланс: ${balance:.2f}\n\n"
                                error_msg += "💡 Пополните баланс или купите новую подписку"
                        except:
                            error_msg += "❌ Ошибка проверки подписки"
                
                return {
                    "success": False,
                    "message": error_msg,
                    "penalty_applied": False,
                    "daily_limit_exceeded": False
                }
            
            # 2. Проверяем новые ограничения
            limit_check = await self.check_report_limits(user_id, target)
            
            if not limit_check["can_report"]:
                return {
                    "success": False,
                    "message": "\n".join(limit_check["messages"]),
                    "penalty_applied": False,
                    "daily_limit_exceeded": "дневной лимит" in limit_check["messages"][0].lower() if limit_check["messages"] else False
                }
            
            # 3. Валидация цели
            valid, validation_msg = await self.validate_target(target, target_type)
            if not valid:
                return {
                    "success": False,
                    "message": validation_msg,
                    "penalty_applied": False
                }
            
            # 4. Проверяем, нужно ли применять штраф
            penalty_to_apply = limit_check["penalty_applied"]
            
            if penalty_to_apply:
                # Списание штрафа
                current_balance = self.db.get_user_balance(user_id)
                self.db.update_user_balance(user_id, -self.penalty_amount)
                self.db.add_report_penalty(user_id, target, self.penalty_amount)
                self.db.add_transaction(
                    user_id, 
                    "penalty", 
                    -self.penalty_amount, 
                    f"Штраф за превышение лимита жалоб на {target}"
                )
                logger.info(f"💰 Штраф {self.penalty_amount} списан с {user_id} за жалобу на {target}")
            
            # 5. Выполняем жалобу
            success, report_message = await self.execute_report_by_method(method, target, reason, target_type)
            
            if success:
                # 6. Обновляем статистику и ограничения
                self.db.add_report_usage(user_id, method)
                self.db.increment_daily_report(user_id)
                self.db.increment_target_report(user_id, target)
                self.db.set_report_cooldown(user_id, self.cooldown_minutes)
                
                # 7. Добавляем запись в reports
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO reports (user_id, target, target_type, reason, method, status) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, target, target_type, reason, method, "success" if success else "failed"))
                conn.commit()
                conn.close()
                
                # 8. Формируем финальное сообщение
                final_message = f"✅ {report_message}"
                if penalty_to_apply:
                    final_message += f"\n⚠️ Списано {self.penalty_amount} за превышение лимита жалоб на этого пользователя"
                
                return {
                    "success": True,
                    "message": final_message,
                    "penalty_applied": penalty_to_apply,
                    "penalty_amount": self.penalty_amount if penalty_to_apply else 0
                }
            else:
                # Если жалоба не прошла, но штраф уже списан - возвращаем средства
                if penalty_to_apply:
                    self.db.update_user_balance(user_id, self.penalty_amount)
                    self.db.add_transaction(
                        user_id, 
                        "refund", 
                        self.penalty_amount, 
                        f"Возврат штрафа за неудачную жалобу на {target}"
                    )
                    logger.info(f"💰 Штраф {self.penalty_amount} возвращен {user_id}")
                
                return {
                    "success": False,
                    "message": f"❌ {report_message}",
                    "penalty_applied": False
                }
                
        except Exception as e:
            logger.error(f"❌ Error processing report for {user_id}: {e}")
            return {
                "success": False,
                "message": f"❌ Критическая ошибка: {str(e)}",
                "penalty_applied": False
            }
            
    async def get_user_report_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику по ограничениям для пользователя"""
        try:
            # Используем новый метод из Database
            limit_stats = self.db.get_report_limit_stats(user_id)
            user_info = self.db.get_user(user_id)
            
            stats = {
                "daily_used": limit_stats["daily_used"],
                "daily_limit": limit_stats["daily_limit"],
                "cooldown_active": limit_stats["cooldown_active"],
                "total_penalties": limit_stats["penalties_total"],
                "balance": self.db.get_user_balance(user_id) if user_info else 0.0,
                "has_subscription": bool(user_info[7] if user_info and len(user_info) > 7 else None) if user_info else False,
                "is_banned": self.db.is_user_banned(user_id)
            }
            
            # Если кулдаун активен, получаем оставшееся время
            if stats["cooldown_active"]:
                cooldown_ok, cooldown_msg = self.db.check_report_cooldown(user_id)
                if not cooldown_ok:
                    stats["cooldown_message"] = cooldown_msg
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting report stats for {user_id}: {e}")
            return {
                "daily_used": 0,
                "daily_limit": 10,
                "cooldown_active": False,
                "total_penalties": 0,
                "balance": 0.0,
                "has_subscription": False,
                "is_banned": False
            }
    
    async def mass_session_attack(self, target: str, reason: int, max_sessions: int = 10) -> Dict:
        """Массовая атака через сессии с прогрессом"""
        try:
            valid_sessions = self.get_all_valid_sessions(max_sessions)
            
            if not valid_sessions:
                return {
                    'success': False,
                    'message': 'Нет валидных сессий',
                    'stats': {'total': 0, 'success': 0, 'failed': 0}
                }
            
            logger.info(f"🎯 Starting mass session attack on {target} with {len(valid_sessions)} sessions")
            
            results = {
                'total': len(valid_sessions),
                'success': 0,
                'failed': 0,
                'errors': []
            }
            
            # Отправляем через все сессии
            for i, session_file in enumerate(valid_sessions, 1):
                try:
                    success, result = await self.session_manager.send_report(session_file, target, reason)
                    
                    if success:
                        results['success'] += 1
                        logger.info(f"✅ Mass attack #{i}/{len(valid_sessions)} success via {session_file}")
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"{session_file}: {result}")
                        logger.warning(f"⚠️ Mass attack #{i}/{len(valid_sessions)} failed: {result}")
                    
                    # Задержка для избежания флуда
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"{session_file}: {str(e)}")
                    logger.error(f"❌ Mass attack #{i}/{len(valid_sessions)} error: {e}")
                    continue
            
            success_rate = (results['success'] / results['total']) * 100
            return {
                'success': results['success'] > 0,
                'message': f"Массовая атака завершена: {results['success']}/{results['total']} успешно ({success_rate:.1f}%)",
                'stats': results
            }
            
        except Exception as e:
            logger.error(f"❌ Mass session attack error: {e}")
            return {
                'success': False,
                'message': f'Ошибка массовой атаки: {str(e)}',
                'stats': {'total': 0, 'success': 0, 'failed': 0}
            }
            
    async def create_client_from_session(self, session_file: str) -> TelegramClient:
        """
        Создает клиент из сессии
        """
        client = TelegramClient(
            session=session_file,
            api_id=self.api_id,
            api_hash=self.api_hash
        )
        
        try:
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.error(f"❌ Сессия {session_file} не авторизована")
                await client.disconnect()
                return None
                
            logger.info(f"✅ Сессия {session_file} успешно подключена")
            return client
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения сессии {session_file}: {e}")
            return None
    
    def parse_message_link(self, link: str) -> dict:
        """
        Парсит ссылку на сообщение Telegram
        Возвращает: {'type': 'user/channel/group', 'entity': str, 'message_id': int}
        """
        try:
            # Примеры ссылок:
            # https://t.me/username/123
            # https://t.me/c/chat_id/456
            # https://t.me/+invite_hash/message_id
            
            if link.startswith('https://t.me/'):
                parts = link.split('/')
                
                if parts[3] == 'c':  # Канал/группа
                    chat_id = int(parts[4].replace('-100', ''))
                    message_id = int(parts[5])
                    return {'type': 'channel', 'chat_id': chat_id, 'message_id': message_id}
                elif parts[3].startswith('+'):  # Приватная ссылка
                    invite_hash = parts[3][1:]  # Убираем +
                    message_id = int(parts[4]) if len(parts) > 4 else None
                    return {'type': 'private', 'invite_hash': invite_hash, 'message_id': message_id}
                else:  # Пользователь/бот
                    username = parts[3]
                    message_id = int(parts[4]) if len(parts) > 4 else None
                    return {'type': 'user', 'username': username, 'message_id': message_id}
            
            elif link.startswith('@'):  # Только username
                username = link[1:]
                return {'type': 'user', 'username': username, 'message_id': None}
                
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга ссылки {link}: {e}")
            return None
    
    async def get_input_peer(self, client: TelegramClient, parsed_link: dict):
        """
        Получает InputPeer для сущности
        """
        try:
            if parsed_link['type'] == 'user':
                # Получаем пользователя по username
                entity = await client.get_entity(parsed_link['username'])
                return InputPeerUser(user_id=entity.id, access_hash=entity.access_hash)
                
            elif parsed_link['type'] == 'channel':
                # Получаем канал по ID
                entity = await client.get_entity(parsed_link['chat_id'])
                return InputPeerChannel(
                    channel_id=entity.id,
                    access_hash=entity.access_hash
                )
                
            elif parsed_link['type'] == 'private':
                # Для приватных ссылок нужна авторизация
                await client.join_chat(parsed_link['invite_hash'])
                entity = await client.get_entity(parsed_link['invite_hash'])
                
                if hasattr(entity, 'channel_id'):
                    return InputPeerChannel(
                        channel_id=entity.id,
                        access_hash=entity.access_hash
                    )
                else:
                    return InputPeerChat(chat_id=entity.id)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения InputPeer: {e}")
            return None
    
    def convert_reason_to_telethon(self, reason_id: int) -> str:
        """
        Конвертирует наш reason_id в причину для Telethon
        """
        reason_map = {
            1: "spam",           # Спам
            2: "violence",       # Насилие
            3: "pornography",    # Порнография
            4: "childAbuse",     # Жестокое обращение с детьми
            5: "illegalDrugs",   # Незаконные товары
            6: "personalDetails", # Персональные данные
            7: "copyright",      # Нарушение авторских прав
            8: "other",          # Другое
            9: "geoIrrelevant",  # Не относится к теме
            10: "fake",          # Фейк
            11: "scam",          # Мошенничество
            12: "impersonation"  # Выдача за другое лицо
        }
        return reason_map.get(reason_id, "other")
    
    async def report_message(
        self,
        session_file: str,
        message_link: str,
        reason: int,
        comment: str = ""
    ) -> Tuple[bool, str]:
        """
        Основной метод отправки жалобы через сессию
        """
        client = None
        try:
            # 1. Подключаем клиент
            client = await self.create_client_from_session(session_file)
            if not client:
                return False, f"Ошибка подключения сессии"
            
            # 2. Парсим ссылку
            parsed_link = self.parse_message_link(message_link)
            if not parsed_link:
                return False, f"Неверный формат ссылки"
            
            # 3. Получаем InputPeer
            input_peer = await self.get_input_peer(client, parsed_link)
            if not input_peer:
                return False, f"Не удалось получить информацию о цели"
            
            # 4. Конвертируем причину
            telethon_reason = self.convert_reason_to_telethon(reason)
            
            # 5. Отправляем жалобу
            message_ids = [parsed_link['message_id']] if parsed_link['message_id'] else []
            
            await client(ReportRequest(
                peer=input_peer,
                id=message_ids,
                reason=telethon_reason,
                message=comment[:512] if comment else ""
            ))
            
            logger.info(f"✅ Жалоба отправлена через {session_file} на {message_link}")
            return True, "Жалоба успешно отправлена"
            
        except FloodWaitError as e:
            logger.warning(f"⚠️ Flood wait {e.seconds} секунд для {session_file}")
            await asyncio.sleep(e.seconds + 5)
            return False, f"Flood wait: {e.seconds} секунд"
            
        except SessionPasswordNeededError:
            logger.error(f"❌ Сессия {session_file} требует пароль 2FA")
            return False, "Требуется пароль 2FA"
            
        except AuthKeyError:
            logger.error(f"❌ Сессия {session_file} недействительна")
            return False, "Сессия недействительна"
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки жалобы через {session_file}: {e}")
            return False, str(e)
            
        finally:
            if client:
                await client.disconnect()

class ReportManager:
    def __init__(self, db_manager, session_manager: SessionManager):
        """
        Инициализация менеджера отчетов
        """
        self.db = db_manager
        self.session_manager = session_manager
        
    async def execute_session_report_with_links(
        self,
        user_id: int,
        target: str,
        reason: int,
        target_type: str,
        violation_links: List[str]
    ) -> Tuple[bool, str]:
        """
        Отправка жалобы через сессии с переходами по ссылкам
        """
        try:
            # 1. Получаем ВСЕ валидные сессии из базы данных
            valid_sessions = self.db.get_all_valid_sessions(limit=100)
            
            if not valid_sessions:
                return False, "❌ Нет валидных сессий в базе"
            
            logger.info(f"📱 Начало атаки с {len(valid_sessions)} сессиями на {len(violation_links)} ссылок")
            
            # 2. Для каждой сессии переходим по ссылкам и жалуемся
            success_count = 0
            total_sessions = len(valid_sessions)
            processed_links = 0
            
            for i, session_data in enumerate(valid_sessions, 1):
                session_file = session_data['session_file']
                phone = session_data['phone']
                
                try:
                    logger.info(f"🎯 Обработка сессии {i}/{total_sessions}: {phone}")
                    
                    # Проверяем валидность каждой сессии перед использованием
                    if not self.db.check_session_validity(session_file):
                        logger.warning(f"⚠️ Сессия {session_file} невалидна, пропускаем")
                        continue
                    
                    session_success = False
                    session_processed = 0
                    
                    # 3. Для каждой ссылки отправляем жалобу
                    for link_idx, link in enumerate(violation_links, 1):
                        try:
                            logger.debug(f"🔗 Ссылка {link_idx}/{len(violation_links)}: {link}")
                            
                            # Отправляем жалобу через Telethon
                            success, result = await self.session_manager.report_message(
                                session_file=session_file,
                                message_link=link,
                                reason=reason,
                                comment=f"Нарушение правил Telegram по причине {reason}"
                            )
                            
                            if success:
                                session_success = True
                                session_processed += 1
                                processed_links += 1
                                logger.info(f"✅ Сессия {phone} отправила жалобу на ссылку {link_idx}")
                                
                                # Обновляем статистику сессии
                                self.db.update_session_stats(
                                    session_file=session_file,
                                    reports_sent=1,
                                    last_used=True
                                )
                                
                            else:
                                logger.warning(f"⚠️ Сессия {phone} не смогла отправить жалобу: {result}")
                            
                            # Случайная задержка между жалобами
                            await asyncio.sleep(random.uniform(3, 7))
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка обработки ссылки {link} сессией {phone}: {e}")
                            continue
                    
                    # 4. Если сессия выполнила хотя бы одну успешную жалобу
                    if session_success:
                        success_count += 1
                        logger.info(f"✅ Сессия {phone} завершила {session_processed} жалоб")
                    else:
                        logger.warning(f"⚠️ Сессия {phone} не выполнила ни одной жалобы")
                    
                    # 5. Задержка между сессиями
                    delay = random.uniform(8, 15)
                    logger.debug(f"⏳ Задержка {delay:.1f} сек перед следующей сессией")
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"❌ Критическая ошибка в сессии {i}: {e}")
                    continue
            
            # 6. Обновляем счетчик сессий пользователя
            self.db.increment_session_count(user_id, success_count)
            
            # 7. Сохраняем статистику атаки
            attack_stats = {
                'user_id': user_id,
                'target': target,
                'target_type': target_type,
                'reason': reason,
                'sessions_used': success_count,
                'total_sessions': total_sessions,
                'links_processed': processed_links,
                'success_rate': (success_count / total_sessions * 100) if total_sessions > 0 else 0
            }
            
            self.db.save_attack_statistics(attack_stats)
            
            # 8. Формируем результат
            if success_count > 0:
                success_rate = (success_count / total_sessions) * 100
                return True, (
                    f"✅ <b>АТАКА ЗАВЕРШЕНА УСПЕШНО</b>\n\n"
                    f"🎯 Цель: {target}\n"
                    f"📱 Использовано сессий: {success_count}/{total_sessions}\n"
                    f"🔗 Обработано ссылок: {processed_links}/{len(violation_links)}\n"
                    f"📊 Успешность: {success_rate:.1f}%\n"
                    f"💾 Статистика сохранена в базе"
                )
            else:
                return False, (
                    f"❌ <b>АТАКА НЕ УДАЛАСЬ</b>\n\n"
                    f"🎯 Цель: {target}\n"
                    f"📱 Активных сессий: {total_sessions}\n"
                    f"🔗 Ссылок для обработки: {len(violation_links)}\n"
                    f"⚠️ Ни одна сессия не смогла отправить жалобы"
                )
                
        except Exception as e:
            logger.error(f"❌ Session attack error: {e}", exc_info=True)
            return False, f"Ошибка атаки сессиями: {str(e)}"
    
    async def validate_and_prepare_links(
        self,
        violation_links: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Валидирует ссылки и разделяет на валидные/невалидные
        """
        valid_links = []
        invalid_links = []
        
        for link in violation_links:
            parsed = self.session_manager.parse_message_link(link)
            if parsed:
                valid_links.append(link)
            else:
                invalid_links.append(link)
        
        return valid_links, invalid_links

    async def mass_email_attack(self, target: str, reason: int, max_emails: int = 5) -> Dict:
        """Массовая атака через почты"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT email, password FROM admin_emails 
                WHERE status = "active"
                LIMIT ?
            ''', (max_emails,))
            email_results = cursor.fetchall()
            conn.close()
            
            if not email_results:
                return {
                    'success': False,
                    'message': 'Нет активных почт',
                    'stats': {'total': 0, 'success': 0, 'failed': 0}
                }
            
            results = {
                'total': len(email_results),
                'success': 0,
                'failed': 0,
                'errors': []
            }
            
            logger.info(f"📧 Starting mass email attack on {target} with {len(email_results)} emails")
            
            for i, (email, password) in enumerate(email_results, 1):
                try:
                    success, result = await self.email_manager.send_complaint(email, password, target, reason)
                    
                    if success:
                        results['success'] += 1
                        logger.info(f"✅ Email attack #{i}/{len(email_results)} success via {email}")
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"{email}: {result}")
                        logger.warning(f"⚠️ Email attack #{i}/{len(email_results)} failed: {result}")
                    
                    # Задержка между отправками
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"{email}: {str(e)}")
                    logger.error(f"❌ Email attack #{i}/{len(email_results)} error: {e}")
                    continue
            
            success_rate = (results['success'] / results['total']) * 100
            return {
                'success': results['success'] > 0,
                'message': f"Email атака завершена: {results['success']}/{results['total']} успешно ({success_rate:.1f}%)",
                'stats': results
            }
            
        except Exception as e:
            logger.error(f"❌ Mass email attack error: {e}")
            return {
                'success': False,
                'message': f'Ошибка email атаки: {str(e)}',
                'stats': {'total': 0, 'success': 0, 'failed': 0}
            }

    async def execute_report_by_method(self, method: str, target: str, reason: int, target_type: str = "user") -> Tuple[bool, str]:
        """Выполнить жалобу по выбранному методу - ГЛАВНЫЙ МЕТОД ДЛЯ USER_HANDLERS"""
        try:
            logger.info(f"🎯 Executing {method} report for {target} ({target_type}) with reason {reason}")
            
            if method == "session":
                session_file, country = self.get_random_session()
                return await self.execute_session_report(session_file, target, reason, country)
                
            elif method == "email":
                email_data = self.get_random_email()
                return await self.execute_email_report(email_data, target, reason)
                
            elif method == "combo":
                session_file, country = self.get_random_session()
                email_data = self.get_random_email()
                return await self.execute_combo_report(session_file, email_data, target, reason, country)
                
            elif method == "dsa":
                # Для DSA выбираем EU страну
                eu_countries = ["DE", "FR", "IT", "ES", "PL"]
                country = random.choice(eu_countries)
                return await self.execute_dsa_report(target, reason, country)
                
            elif method == "nuke":
                return await self.execute_nuke_report(target, reason)
                
            else:
                return False, f"Неизвестный метод: {method}"
                
        except Exception as e:
            logger.error(f"❌ Report execution error for {method}: {e}")
            return False, f"Ошибка выполнения: {str(e)}"

    def get_available_sessions_count(self) -> int:
        """Получить количество доступных сессий"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM admin_sessions WHERE validity = "valid"')
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
        except Exception as e:
            logger.error(f"Error getting sessions count: {e}")
            return 0

    def get_available_emails_count(self) -> int:
        """Получить количество доступных почт"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM admin_emails WHERE status = "active"')
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
        except Exception as e:
            logger.error(f"Error getting emails count: {e}")
            return 0

    def get_system_stats(self) -> Dict[str, int]:
        """Получить статистику системы для отображения"""
        return {
            'sessions': self.get_available_sessions_count(),
            'emails': self.get_available_emails_count(),
            'total_reports': self.get_total_reports_count()
        }

    def get_total_reports_count(self) -> int:
        """Получить общее количество отправленных жалоб"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT SUM(total_reports) FROM users')
            result = cursor.fetchone()[0]
            conn.close()
            
            return result or 0
        except Exception as e:
            logger.error(f"Error getting total reports count: {e}")
            return 0

    async def validate_target(self, target: str, target_type: str) -> Tuple[bool, str]:
        """Валидация цели перед отправкой"""
        try:
            # Проверка формата цели в зависимости от типа
            if target_type == "user" and not (target.startswith('@') or target.isdigit()):
                return False, "Для пользователя укажите @username или ID"
                
            elif target_type == "bot" and not target.startswith('@'):
                return False, "Для бота укажите @username"
                
            elif target_type in ["group", "channel"] and not (target.startswith('@') or 't.me/' in target):
                return False, "Для группы/канала укажите @username или ссылку"
            
            # Проверка длины
            if len(target) < 3:
                return False, "Слишком короткая цель"
                
            if len(target) > 100:
                return False, "Слишком длинная цель"
            
            return True, "Цель валидна"
            
        except Exception as e:
            logger.error(f"Target validation error: {e}")
            return False, f"Ошибка валидации: {str(e)}"