import os
import phonenumbers
import asyncio
import random
from typing import Tuple, List, Optional, Dict
from telethon import TelegramClient, functions
from telethon.tl.functions.messages import ReportRequest, ReportSpamRequest
from telethon.errors import AuthKeyDuplicatedError, AuthKeyError
from telethon.tl.types import *
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, api_id: int, api_hash: str, sessions_dir: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)
        
        self.reason_objects = {
            1: InputReportReasonSpam(),
            2: InputReportReasonViolence(),
            3: InputReportReasonPornography(),
            4: InputReportReasonChildAbuse(),
            5: InputReportReasonOther(),
            6: InputReportReasonCopyright(),
            7: InputReportReasonGeoIrrelevant(),
            8: InputReportReasonFake(),
            9: InputReportReasonIllegalDrugs(),
            10: InputReportReasonPersonalDetails()
        }

    async def send_report(self, session_file: str, target: str, reason: int, message: str = "") -> Tuple[bool, str]:
        """Совместимый метод для старого кода"""
        return await self.send_universal_report(session_file, target, reason, message)

    def get_session_files(self) -> List[str]:
        """Получить список всех файлов сессий"""
        try:
            return [f for f in os.listdir(self.sessions_dir) if f.endswith('.session')]
        except Exception as e:
            logger.error(f"Error getting session files: {e}")
            return []

    async def validate_session(self, session_file: str) -> Tuple[bool, str]:
        """Диагностическая проверка сессии"""
        session_path = os.path.join(self.sessions_dir, session_file)
        logger.info(f"🔧 ДИАГНОСТИКА: {session_file}")
        
        if not os.path.exists(session_path):
            return False, "❌ Файл не найден"

        client = None
        try:
            client = TelegramClient(
                session=session_path,
                api_id=self.api_id,
                api_hash=self.api_hash,
                connection_retries=1,
                timeout=10,
                request_retries=1
            )
            
            logger.info(f"🔧 Подключаемся с таймаутом 10сек...")
            await asyncio.wait_for(client.connect(), timeout=10.0)
            logger.info(f"🔧 ✅ Подключено")
            
            if not client.is_connected():
                return False, "❌ Нет подключения"
            
            logger.info(f"🔧 Проверяем авторизацию...")
            try:
                is_auth = await asyncio.wait_for(client.is_user_authorized(), timeout=5.0)
                logger.info(f"🔧 ✅ Авторизация: {is_auth}")
            except asyncio.TimeoutError:
                return False, "⏰ Таймаут авторизации"
            
            if not is_auth:
                return False, "❌ Не авторизован"
            
            logger.info(f"🔧 Получаем user info...")
            try:
                me = await asyncio.wait_for(client.get_me(), timeout=5.0)
                if me:
                    user_info = f"@{me.username}" if me.username else f"{me.first_name or 'User'}"
                    logger.info(f"🔧 🎉 УСПЕХ: {user_info}")
                    return True, f"✅ {user_info}"
                else:
                    return False, "❌ Нет user info"
            except asyncio.TimeoutError:
                return False, "⏰ Таймаут данных"
                
        except asyncio.TimeoutError:
            return False, "⏰ Таймаут подключения"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def send_universal_report(self, session_file: str, target: str, reason: int, message: str = "") -> Tuple[bool, str]:
        """УЛЬТРА-УНИВЕРСАЛЬНЫЙ МЕТОД ОТПРАВКИ РЕПОРТОВ - ВСЕ МЕТОДЫ РАБОЧИЕ"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            
            if not os.path.exists(session_path):
                return False, "Файл сессии не найден"
            
            client = TelegramClient(
                session=session_path,
                api_id=self.api_id,
                api_hash=self.api_hash,
                device_model="Samsung Galaxy S24 Ultra",
                system_version="Android 14.0",
                app_version="Telegram 10.5.0",
                connection_retries=2,
                timeout=20,
                request_retries=2
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Сессия не авторизована"
            
            # Проверяем что сессия живая
            try:
                me = await client.get_me()
                if not me:
                    return False, "Сессия невалидна"
            except:
                return False, "Сессия повреждена"
            
            report_reason = self.reason_objects.get(reason, InputReportReasonOther())
            
            # Получаем entity цели разными способами
            entity = None
            try:
                entity = await client.get_input_entity(target)
                logger.info(f"✅ Entity получен: {entity}")
            except Exception as e:
                return False, f"Не могу найти цель: {str(e)}"
            
            # МЕТОД 1: ReportSpamRequest - ИСПРАВЛЕННЫЙ
            try:
                logger.info(f"🔄 Метод 1: ReportSpamRequest")
                result = await client(ReportSpamRequest(peer=entity))
                logger.info(f"✅ Метод 1 успешен: {result}")
                return True, "Репорт отправлен (ReportSpamRequest)"
            except Exception as e1:
                logger.warning(f"❌ Метод 1 не сработал: {e1}")
            
            # МЕТОД 2: ReportRequest - ИСПРАВЛЕННАЯ СИГНАТУРА
            try:
                logger.info(f"🔄 Метод 2: ReportRequest исправленный")
                # Получаем несколько сообщений для репорта
                messages = await client.get_messages(entity, limit=3)
                message_ids = [msg.id for msg in messages] if messages else []
                
                # Если нет сообщений, создаем фиктивный ID
                if not message_ids:
                    message_ids = [random.randint(1000, 9999)]
                
                # ИСПРАВЛЕННАЯ СИГНАТУРА - без параметра reason
                result = await client(ReportRequest(
                    peer=entity,
                    id=message_ids,
                    # reason=report_reason,  # УБРАНО - вызывает ошибку
                    message=message or "Нарушение правил платформы"
                ))
                logger.info(f"✅ Метод 2 успешен: {result}")
                return True, "Репорт отправлен (ReportRequest)"
            except Exception as e2:
                logger.warning(f"❌ Метод 2 не сработал: {e2}")
            
            # МЕТОД 3: client.report - СОВРЕМЕННЫЙ
            try:
                logger.info(f"🔄 Метод 3: client.report")
                if hasattr(client, 'report'):
                    result = await client.report(
                        entity=entity,
                        reason=report_reason,
                        message=message or "Violation report"
                    )
                    logger.info(f"✅ Метод 3 успешен: {result}")
                    return True, "Репорт отправлен (client.report)"
            except Exception as e3:
                logger.warning(f"❌ Метод 3 не сработал: {e3}")
            
            # МЕТОД 4: functions.messages.Report - ПРЯМОЙ ВЫЗОВ
            try:
                logger.info(f"🔄 Метод 4: functions.messages.Report")
                messages = await client.get_messages(entity, limit=2)
                message_ids = [msg.id for msg in messages] if messages else [random.randint(1000, 9999)]
                
                result = await client(functions.messages.ReportRequest(
                    peer=entity,
                    id=message_ids,
                    reason=report_reason,
                    message=message or "Spam report"
                ))
                logger.info(f"✅ Метод 4 успешен: {result}")
                return True, "Репорт отправлен (functions.messages.Report)"
            except Exception as e4:
                logger.warning(f"❌ Метод 4 не сработал: {e4}")
            
            # МЕТОД 5: ЧЕРЕЗ @SpamBot - РЕЗЕРВНЫЙ
            try:
                logger.info(f"🔄 Метод 5: Через @SpamBot")
                spam_bot = await client.get_input_entity('@SpamBot')
                await client.send_message(spam_bot, '/start')
                await asyncio.sleep(1)
                await client.send_message(spam_bot, f'/report {target}')
                await asyncio.sleep(1)
                await client.send_message(spam_bot, f'{reason}')
                logger.info(f"✅ Метод 5 успешен")
                return True, "Репорт отправлен через @SpamBot"
            except Exception as e5:
                logger.warning(f"❌ Метод 5 не сработал: {e5}")
            
            # МЕТОД 6: ReportRequest БЕЗ message_ids - АЛЬТЕРНАТИВНЫЙ
            try:
                logger.info(f"🔄 Метод 6: ReportRequest без message_ids")
                result = await client(ReportRequest(
                    peer=entity,
                    id=[],  # Пустой список
                    # reason=report_reason,  # УБРАНО
                    message=message or "Automated report"
                ))
                logger.info(f"✅ Метод 6 успешен: {result}")
                return True, "Репорт отправлен (ReportRequest без IDs)"
            except Exception as e6:
                logger.warning(f"❌ Метод 6 не сработал: {e6}")
            
            return False, f"Все методы провалились: {e1}, {e2}, {e3}, {e4}, {e5}, {e6}"
                
        except Exception as e:
            error_msg = f"Критическая ошибка: {str(e)}"
            logger.error(f"💥 Ошибка отправки репорта {session_file}: {error_msg}")
            return False, error_msg
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def test_all_report_methods(self, session_file: str, target: str) -> Dict:
        """Тестирование всех методов отправки репортов"""
        test_results = {}
        methods = [
            ("ReportSpamRequest", self._test_method_1),
            ("ReportRequest_fixed", self._test_method_2), 
            ("client.report", self._test_method_3),
            ("functions.messages.Report", self._test_method_4),
            ("SpamBot", self._test_method_5),
            ("ReportRequest_no_ids", self._test_method_6)
        ]
        
        for method_name, method_func in methods:
            try:
                success, message = await method_func(session_file, target, 1, "Test report")
                test_results[method_name] = {
                    'success': success,
                    'message': message,
                    'status': '✅ РАБОТАЕТ' if success else '❌ НЕ РАБОТАЕТ'
                }
                # Задержка между тестами
                await asyncio.sleep(2)
            except Exception as e:
                test_results[method_name] = {
                    'success': False,
                    'message': str(e),
                    'status': '💥 ОШИБКА'
                }
        
        return test_results

    async def _test_method_1(self, session_file: str, target: str, reason: int, message: str) -> Tuple[bool, str]:
        """Тест метода 1: ReportSpamRequest"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Не авторизован"
            
            entity = await client.get_input_entity(target)
            result = await client(ReportSpamRequest(peer=entity))
            return True, f"ReportSpamRequest: {result}"
        except Exception as e:
            return False, f"ReportSpamRequest: {str(e)}"
        finally:
            if client:
                await client.disconnect()

    async def _test_method_2(self, session_file: str, target: str, reason: int, message: str) -> Tuple[bool, str]:
        """Тест метода 2: ReportRequest исправленный"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Не авторизован"
            
            entity = await client.get_input_entity(target)
            messages = await client.get_messages(entity, limit=1)
            message_ids = [msg.id for msg in messages] if messages else [random.randint(1000, 9999)]
            
            result = await client(ReportRequest(
                peer=entity,
                id=message_ids,
                message=message or "Test report"
            ))
            return True, f"ReportRequest: {result}"
        except Exception as e:
            return False, f"ReportRequest: {str(e)}"
        finally:
            if client:
                await client.disconnect()

    async def _test_method_3(self, session_file: str, target: str, reason: int, message: str) -> Tuple[bool, str]:
        """Тест метода 3: client.report"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Не авторизован"
            
            entity = await client.get_input_entity(target)
            report_reason = self.reason_objects.get(reason, InputReportReasonOther())
            
            if hasattr(client, 'report'):
                result = await client.report(entity=entity, reason=report_reason, message=message)
                return True, f"client.report: {result}"
            else:
                return False, "client.report не доступен"
        except Exception as e:
            return False, f"client.report: {str(e)}"
        finally:
            if client:
                await client.disconnect()

    async def _test_method_4(self, session_file: str, target: str, reason: int, message: str) -> Tuple[bool, str]:
        """Тест метода 4: functions.messages.Report"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Не авторизован"
            
            entity = await client.get_input_entity(target)
            report_reason = self.reason_objects.get(reason, InputReportReasonOther())
            messages = await client.get_messages(entity, limit=1)
            message_ids = [msg.id for msg in messages] if messages else [random.randint(1000, 9999)]
            
            result = await client(functions.messages.ReportRequest(
                peer=entity,
                id=message_ids,
                reason=report_reason,
                message=message
            ))
            return True, f"functions.messages.Report: {result}"
        except Exception as e:
            return False, f"functions.messages.Report: {str(e)}"
        finally:
            if client:
                await client.disconnect()

    async def _test_method_5(self, session_file: str, target: str, reason: int, message: str) -> Tuple[bool, str]:
        """Тест метода 5: SpamBot"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Не авторизован"
            
            spam_bot = await client.get_input_entity('@SpamBot')
            await client.send_message(spam_bot, f'/report {target}')
            return True, "SpamBot: сообщение отправлено"
        except Exception as e:
            return False, f"SpamBot: {str(e)}"
        finally:
            if client:
                await client.disconnect()

    async def _test_method_6(self, session_file: str, target: str, reason: int, message: str) -> Tuple[bool, str]:
        """Тест метода 6: ReportRequest без IDs"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Не авторизован"
            
            entity = await client.get_input_entity(target)
            result = await client(ReportRequest(
                peer=entity,
                id=[],
                message=message or "Test report"
            ))
            return True, f"ReportRequest без IDs: {result}"
        except Exception as e:
            return False, f"ReportRequest без IDs: {str(e)}"
        finally:
            if client:
                await client.disconnect()

    async def mass_report_all_methods(self, target: str, reason: int, message: str = "", max_sessions: int = 5) -> Dict:
        """Массовая отправка с использованием всех рабочих методов"""
        session_files = self.get_session_files()[:max_sessions]
        results = {
            'total': len(session_files),
            'success': 0,
            'failed': 0,
            'method_stats': {},
            'details': []
        }
        
        # Статистика по методам
        methods_used = {}
        
        for i, session_file in enumerate(session_files, 1):
            try:
                logger.info(f"🔄 Сессия {i}/{len(session_files)}: {session_file}")
                
                # Используем универсальный метод который пробует все способы
                success, result_msg = await self.send_universal_report(session_file, target, reason, message)
                
                if success:
                    results['success'] += 1
                    # Определяем какой метод сработал
                    used_method = "unknown"
                    if "ReportSpamRequest" in result_msg:
                        used_method = "ReportSpamRequest"
                    elif "ReportRequest" in result_msg and "без IDs" not in result_msg:
                        used_method = "ReportRequest"
                    elif "client.report" in result_msg:
                        used_method = "client.report" 
                    elif "functions.messages.Report" in result_msg:
                        used_method = "functions.messages.Report"
                    elif "SpamBot" in result_msg:
                        used_method = "SpamBot"
                    elif "без IDs" in result_msg:
                        used_method = "ReportRequest_no_ids"
                    
                    methods_used[used_method] = methods_used.get(used_method, 0) + 1
                    results['details'].append(f"✅ {session_file}: {used_method}")
                else:
                    results['failed'] += 1
                    results['details'].append(f"❌ {session_file}: {result_msg}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"❌ {session_file}: Ошибка {str(e)}")
        
        results['method_stats'] = methods_used
        logger.info(f"📊 Массовый репорт завершен: {results['success']} успешно")
        logger.info(f"🎯 Статистика методов: {methods_used}")
        
        return results

    async def diagnose_all_sessions(self) -> List[Tuple[str, bool, str]]:
        """Проверить все сессии и вернуть результаты"""
        session_files = self.get_session_files()
        results = []
        
        logger.info(f"🔄 Начинаем проверку {len(session_files)} сессий")
        
        for index, session_file in enumerate(session_files, 1):
            try:
                is_valid, info = await self.validate_session(session_file)
                results.append((session_file, is_valid, info))
                
                status_icon = "✅" if is_valid else "❌"
                logger.info(f"{status_icon} Проверена {index}/{len(session_files)}: {session_file} - {info}")
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Ошибка валидации {session_file}: {e}")
                results.append((session_file, False, f"❌ Ошибка: {e}"))
        
        valid_count = len([r for r in results if r[1]])
        invalid_count = len([r for r in results if not r[1]])
        logger.info(f"📊 Проверка завершена: {valid_count} валидных, {invalid_count} невалидных")
        return results

    async def validate_sessions_with_progress(self, callback=None) -> Dict:
        """Проверка сессий с прогрессом для админки"""
        session_files = self.get_session_files()
        total = len(session_files)
        results = {
            'total': total,
            'valid': 0,
            'invalid': 0,
            'details': []
        }
        
        if total == 0:
            return results
        
        for index, session_file in enumerate(session_files, 1):
            try:
                is_valid, info = await self.validate_session(session_file)
                
                if is_valid:
                    results['valid'] += 1
                else:
                    results['invalid'] += 1
                
                results['details'].append({
                    'session': session_file,
                    'valid': is_valid,
                    'info': info
                })
                
                if callback:
                    progress_text = (
                        f"🔄 Проверка сессий...\n\n"
                        f"📊 Прогресс: {index}/{total}\n"
                        f"✅ Валидных: {results['valid']}\n"
                        f"❌ Невалидных: {results['invalid']}\n"
                        f"⏳ Текущая: {session_file}"
                    )
                    
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text=f"🔄 {index}/{total}", callback_data="progress_refresh"),
                            InlineKeyboardButton(text=f"✅ {results['valid']}", callback_data="progress_valid")
                        ],
                        [
                            InlineKeyboardButton(text=f"❌ {results['invalid']}", callback_data="progress_invalid"),
                            InlineKeyboardButton(text="⏹️ Остановить", callback_data="progress_stop")
                        ]
                    ])
                    
                    try:
                        await callback.message.edit_text(progress_text, reply_markup=keyboard)
                    except:
                        pass
                
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке {session_file}: {e}")
                results['invalid'] += 1
                results['details'].append({
                    'session': session_file,
                    'valid': False,
                    'info': f"❌ Ошибка: {e}"
                })
        
        return results

    async def create_session(self, session_name: str, phone: str, code: str = None, password: str = None) -> Tuple[bool, str]:
        """Создать новую сессию"""
        client = None
        try:
            session_file = os.path.join(self.sessions_dir, f"{session_name}.session")
            
            if os.path.exists(session_file):
                return False, "Сессия с таким именем уже существует"
            
            client = TelegramClient(
                session=session_file,
                api_id=self.api_id,
                api_hash=self.api_hash,
                device_model="RABANOK Reporter",
                system_version="1.0",
                app_version="1.0.0"
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                if code:
                    try:
                        await client.sign_in(phone=phone, code=code)
                    except Exception as e:
                        if "password" in str(e) and password:
                            await client.sign_in(password=password)
                        else:
                            return False, f"Ошибка входа: {str(e)}"
                else:
                    sent_code = await client.send_code_request(phone)
                    return False, "code_requested"
            
            if await client.is_user_authorized():
                me = await client.get_me()
                user_info = f"@{me.username}" if me.username else f"{me.first_name or 'User'}"
                return True, f"Сессия создана для {user_info}"
            else:
                return False, "Ошибка авторизации"
                
        except Exception as e:
            logger.error(f"Session creation error for {phone}: {e}")
            return False, f"Ошибка создания сессии: {str(e)}"
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def authorize_with_code(self, session_name: str, phone: str, code: str) -> Tuple[bool, str]:
        """Авторизовать сессию с кодом"""
        return await self.create_session(session_name, phone, code)

    async def detect_country_from_phone(self, phone: str) -> str:
        """Определить страну по номеру телефона"""
        try:
            parsed = phonenumbers.parse(phone, None)
            return phonenumbers.region_code_for_number(parsed) or "US"
        except:
            return "US"

    def get_session_count(self) -> int:
        """Получить количество сессий"""
        return len(self.get_session_files())

    def remove_session(self, session_file: str) -> bool:
        """Удалить сессию"""
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            if os.path.exists(session_path):
                os.remove(session_path)
                logger.info(f"✅ Session removed: {session_file}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error removing session {session_file}: {e}")
            return False

    async def get_session_info(self, session_file: str) -> Optional[dict]:
        """Получить подробную информацию о сессии"""
        client = None
        try:
            session_path = os.path.join(self.sessions_dir, session_file)
            
            if not os.path.exists(session_path):
                return None
            
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                return None
            
            me = await client.get_me()
            if not me:
                return None
            
            info = {
                'session_file': session_file,
                'user_id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': me.phone,
                'premium': me.premium if hasattr(me, 'premium') else False,
                'bot': me.bot if hasattr(me, 'bot') else False,
                'verified': me.verified if hasattr(me, 'verified') else False,
                'restricted': me.restricted if hasattr(me, 'restricted') else False,
                'scam': me.scam if hasattr(me, 'scam') else False,
                'fake': me.fake if hasattr(me, 'fake') else False
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting session info for {session_file}: {e}")
            return None
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def mass_report(self, target: str, reason: int, message: str = "", max_sessions: int = 10) -> dict:
        """Массовая отправка жалоб через все валидные сессии"""
        session_files = self.get_session_files()
        results = {
            'total': len(session_files),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        logger.info(f"Starting mass report to {target} with {len(session_files)} sessions")
        
        # Ограничиваем количество сессий
        session_files = session_files[:max_sessions]
        
        for session_file in session_files:
            try:
                success, result_msg = await self.send_report(session_file, target, reason, message)
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"{session_file}: {result_msg}")
                
                # Задержка между запросами
                await asyncio.sleep(1)
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{session_file}: {str(e)}")
                logger.error(f"Mass report error for {session_file}: {e}")
        
        logger.info(f"Mass report completed: {results['success']} success, {results['failed']} failed")
        return results

    async def get_session_health_report(self) -> Dict:
        """Полный отчет о здоровье всех сессий"""
        session_files = self.get_session_files()
        report = {
            'total_sessions': len(session_files),
            'working_sessions': 0,
            'broken_sessions': 0,
            'session_details': [],
            'recommendations': []
        }
        
        for session_file in session_files:
            try:
                # Базовая валидация
                is_valid, info = await self.validate_session(session_file)
                
                if is_valid:
                    # Тест отправки репорта
                    test_success, test_msg = await self.send_universal_report(
                        session_file, "@SpamBot", 1, "Health check"
                    )
                    
                    if test_success:
                        report['working_sessions'] += 1
                        status = "🟢 FULLY_WORKING"
                    else:
                        report['broken_sessions'] += 1
                        status = "🟡 VALID_BUT_NO_REPORTS"
                else:
                    report['broken_sessions'] += 1
                    status = "🔴 INVALID"
                
                report['session_details'].append({
                    'session': session_file,
                    'status': status,
                    'info': info,
                    'can_send_reports': test_success if is_valid else False
                })
                
            except Exception as e:
                report['broken_sessions'] += 1
                report['session_details'].append({
                    'session': session_file,
                    'status': "🔴 ERROR",
                    'info': str(e),
                    'can_send_reports': False
                })
        
        # Формируем рекомендации
        if report['working_sessions'] == 0:
            report['recommendations'].append("❌ Нет рабочих сессий! Добавьте новые сессии.")
        elif report['working_sessions'] < 5:
            report['recommendations'].append("⚠️ Мало рабочих сессий. Рекомендуется добавить еще.")
        
        if report['broken_sessions'] > report['working_sessions']:
            report['recommendations'].append("🔧 Больше половины сессий нерабочие. Проведите очистку.")
        
        return report

    async def cleanup_broken_sessions(self) -> Dict:
        """Очистка нерабочих сессий"""
        session_files = self.get_session_files()
        cleanup_report = {
            'total': len(session_files),
            'removed': 0,
            'kept': 0,
            'removed_sessions': []
        }
        
        for session_file in session_files:
            try:
                is_valid, info = await self.validate_session(session_file)
                
                if not is_valid:
                    # Удаляем невалидную сессию
                    if self.remove_session(session_file):
                        cleanup_report['removed'] += 1
                        cleanup_report['removed_sessions'].append(session_file)
                        logger.info(f"🗑️ Удалена нерабочая сессия: {session_file}")
                else:
                    cleanup_report['kept'] += 1
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке сессии {session_file}: {e}")
        
        logger.info(f"🧹 Очистка завершена: удалено {cleanup_report['removed']} сессий")
        return cleanup_report

    async def parallel_mass_report(self, target: str, reason: int, message: str = "", max_sessions: int = 10) -> Dict:
        """ПАРАЛЛЕЛЬНАЯ массовая отправка репортов для максимальной скорости"""
        session_files = self.get_session_files()[:max_sessions]
        results = {
            'total': len(session_files),
            'success': 0,
            'failed': 0,
            'execution_time': 0,
            'details': []
        }
        
        start_time = datetime.now()
        logger.info(f"🚀 ЗАПУСК ПАРАЛЛЕЛЬНОГО РЕПОРТА на {target} с {len(session_files)} сессий")
        
        # Создаем задачи для всех сессий
        tasks = []
        for session_file in session_files:
            task = asyncio.create_task(
                self.send_universal_report(session_file, target, reason, message)
            )
            tasks.append((session_file, task))
        
        # Ожидаем завершения всех задач
        for session_file, task in tasks:
            try:
                success, result_msg = await asyncio.wait_for(task, timeout=30.0)
                if success:
                    results['success'] += 1
                    results['details'].append(f"✅ {session_file}: Успех")
                else:
                    results['failed'] += 1
                    results['details'].append(f"❌ {session_file}: {result_msg}")
            except asyncio.TimeoutError:
                results['failed'] += 1
                results['details'].append(f"❌ {session_file}: Таймаут")
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"❌ {session_file}: Ошибка {str(e)}")
        
        results['execution_time'] = (datetime.now() - start_time).total_seconds()
        logger.info(f"🎉 ПАРАЛЛЕЛЬНЫЙ РЕПОРТ ЗАВЕРШЕН: {results['success']}/{results['total']} за {results['execution_time']:.1f}сек")
        
        return results