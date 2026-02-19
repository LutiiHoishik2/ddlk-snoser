import smtplib
import random
import asyncio
import logging
import os
import time
import aiofiles
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Tuple, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.config import Config
from utils.progress import EmailProgress

logger = logging.getLogger(__name__)

class EmailManager:
    def __init__(self, emails_file: str = "emails/emails.txt"):
        self.emails_file = emails_file
        self.emails = []  # Список почт в формате [{'email': '', 'password': ''}, ...]
        self.loaded = False
        self.valid_emails_cache = []
        self.bot = None  # Бот для отправки сообщений о прогрессе
        
        # Загружаем почты при инициализации
        self.load_emails()
        
        # Пул потоков для массовой проверки
        self.thread_pool = ThreadPoolExecutor(max_workers=100)  # 100 параллельных потоков
        
        # Кэш валидных почт
        self.valid_cache_file = "emails/valid_emails.txt"
        self.load_valid_cache()
        
        self.complaint_texts = [
            "Обнаружены материалы, нарушающие правила платформы и законодательство",
            "Контент содержит запрещенную информацию и противоправные материалы",
            "Публикация нарушает пользовательское соглашение Telegram",
            "Обнаружена противоправная деятельность и нарушения",
            "Материалы не соответствуют политике сообщества и нормам",
            "Выявлено систематическое нарушение правил платформы",
            "Контент представляет угрозу для пользователей и сообщества",
            "Обнаружена мошенническая деятельность и обман",
            "Публикация содержит недопустимые и опасные материалы",
            "Выявлены серьезные нарушения законодательства и правил"
        ]
        
        self.reason_texts = {
            1: "распространение порнографического контента",
            2: "пропаганда насилия и жестокости", 
            3: "контент, связанный с детской эксплуатацией",
            4: "реклама нелегальных товаров и услуг",
            5: "нарушение конфиденциальности персональных данных",
            6: "пропаганда терроризма и экстремизма",
            7: "мошеннические схемы и обман пользователей",
            8: "массовый спам и навязчивая реклама",
            9: "нарушение авторских прав и интеллектуальной собственности",
            10: "систематическое нарушение правил платформы"
        }
        
        logger.info(f"📧 EmailManager инициализирован. Загружено {len(self.emails)} почт, валидных в кэше: {len(self.valid_emails_cache)}")

    def set_bot(self, bot):
        """Установить бота для отправки сообщений о прогрессе"""
        self.bot = bot
        logger.info("🤖 Бот установлен для отображения прогресса почт")

    def load_emails(self):
        """Загрузка почт из файла - ОПТИМИЗИРОВАННАЯ версия"""
        try:
            if not os.path.exists(self.emails_file):
                logger.error(f"❌ Файл с почтами не найден: {self.emails_file}")
                logger.info(f"📁 Текущая рабочая директория: {os.getcwd()}")
                return
            
            start_time = asyncio.get_event_loop().time()
            
            # Быстрая загрузка с использованием asyncio
            with open(self.emails_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            self.emails = []
            loaded_count = 0
            error_count = 0
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                
                # Быстрый парсинг
                if ':' in line:
                    parts = line.split(':', 1)
                elif ';' in line:
                    parts = line.split(';', 1)
                elif '|' in line:
                    parts = line.split('|', 1)
                elif '\t' in line:
                    parts = line.split('\t', 1)
                else:
                    parts = line.split()
                
                if len(parts) >= 2:
                    email = parts[0].strip()
                    password = parts[1].strip()
                    
                    # Быстрая базовая валидация email
                    if '@' in email and '.' in email.split('@')[1] and password:
                        self.emails.append({
                            'email': email,
                            'password': password,
                            'line': line_num
                        })
                        loaded_count += 1
                        
                        # Логируем прогресс для больших файлов
                        if loaded_count % 5000 == 0:
                            logger.info(f"📥 Загружено {loaded_count} почт...")
                    else:
                        error_count += 1
                else:
                    error_count += 1
            
            elapsed = asyncio.get_event_loop().time() - start_time
            self.loaded = True
            logger.info(f"📧 Успешно загружено {loaded_count} почт за {elapsed:.2f} сек. Ошибок: {error_count}")
            
            if loaded_count == 0:
                logger.error("❌ Не загружено ни одной почты! Проверьте формат файла.")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки почт из {self.emails_file}: {e}")
            self.emails = []
            self.loaded = False

    def load_valid_cache(self):
        """Загрузка кэша валидных почт"""
        try:
            if os.path.exists(self.valid_cache_file):
                with open(self.valid_cache_file, 'r', encoding='utf-8') as f:
                    self.valid_emails_cache = [line.strip() for line in f if line.strip()]
                logger.info(f"✅ Загружен кэш {len(self.valid_emails_cache)} валидных почт")
            else:
                self.valid_emails_cache = []
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша: {e}")
            self.valid_emails_cache = []

    def save_valid_cache(self):
        """Сохранение кэша валидных почт"""
        try:
            with open(self.valid_cache_file, 'w', encoding='utf-8') as f:
                for email in self.valid_emails_cache:
                    f.write(email + '\n')
            logger.info(f"💾 Кэш сохранен: {len(self.valid_emails_cache)} почт")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша: {e}")

    async def validate_email_fast(self, email: str, password: str) -> Tuple[bool, str]:
        """Быстрая проверка email через SMTP с таймаутом 5 секунд"""
        try:
            domain = email.split('@')[1].lower() if '@' in email else ''
            
            # Определяем SMTP сервер по домену
            if 'gmail' in domain:
                server, port = 'smtp.gmail.com', 587
            elif 'mail.ru' in domain or 'bk.ru' in domain or 'inbox.ru' in domain:
                server, port = 'smtp.mail.ru', 587
            elif 'yandex' in domain or 'ya.ru' in domain:
                server, port = 'smtp.yandex.ru', 587
            elif 'outlook' in domain or 'hotmail' in domain:
                server, port = 'smtp.office365.com', 587
            else:
                server, port = 'smtp.gmail.com', 587  # Запасной вариант
            
            # Быстрая проверка с таймаутом
            with smtplib.SMTP(server, port, timeout=5) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(email, password)
                return True, f"✅ {email} валиден"
                
        except smtplib.SMTPAuthenticationError:
            return False, f"❌ {email} - неверный пароль"
        except (smtplib.SMTPException, ConnectionRefusedError, TimeoutError) as e:
            return False, f"⚠️ {email} - ошибка подключения"
        except Exception as e:
            return False, f"❌ {email} - ошибка: {str(e)[:50]}"

    async def validate_email_batch(self, email_batch: List[Dict]) -> List[Tuple[str, bool, str]]:
        """Пакетная проверка группы почт"""
        tasks = []
        for email_data in email_batch:
            task = asyncio.create_task(
                self.validate_email_fast(email_data['email'], email_data['password'])
            )
            tasks.append((email_data['email'], task))
        
        results = []
        for email, task in tasks:
            try:
                is_valid, message = await asyncio.wait_for(task, timeout=7)
                results.append((email, is_valid, message))
                
                # Кэшируем валидные почты
                if is_valid and email not in self.valid_emails_cache:
                    self.valid_emails_cache.append(email)
                    
            except asyncio.TimeoutError:
                results.append((email, False, f"❌ {email} - таймаут"))
            except Exception as e:
                results.append((email, False, f"❌ {email} - ошибка: {str(e)[:30]}"))
        
        return results

    async def mass_validate_emails(self, batch_size: int = 500, max_concurrent: int = 100) -> Dict[str, Any]:
        """
        Массовая параллельная проверка всех почт
        
        Args:
            batch_size: Размер пакета для проверки
            max_concurrent: Максимальное количество параллельных проверок
        """
        if not self.emails:
            logger.error("❌ Нет почт для проверки")
            return {"total": 0, "valid": 0, "invalid": 0, "time": 0}
        
        total_emails = len(self.emails)
        logger.info(f"🚀 Начинаю МАССОВУЮ проверку {total_emails} почт...")
        
        start_time = asyncio.get_event_loop().time()
        
        # Разбиваем на пакеты
        batches = []
        for i in range(0, total_emails, batch_size):
            batch = self.emails[i:i + batch_size]
            batches.append(batch)
        
        total_valid = 0
        total_invalid = 0
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_batch(batch):
            async with semaphore:
                return await self.validate_email_batch(batch)
        
        # Запускаем все пакеты параллельно
        tasks = [process_batch(batch) for batch in batches]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        for i, batch_result in enumerate(all_results):
            if isinstance(batch_result, Exception):
                logger.error(f"❌ Ошибка в пакете {i}: {batch_result}")
                continue
            
            for email, is_valid, message in batch_result:
                if is_valid:
                    total_valid += 1
                else:
                    total_invalid += 1
            
            # Логируем прогресс
            if (i + 1) % 10 == 0 or i == len(batches) - 1:
                elapsed = asyncio.get_event_loop().time() - start_time
                processed = min((i + 1) * batch_size, total_emails)
                logger.info(f"📊 Прогресс: {processed}/{total_emails} | Валидных: {total_valid} | Затрачено: {elapsed:.1f}с")
        
        # Сохраняем кэш
        self.save_valid_cache()
        
        elapsed = asyncio.get_event_loop().time() - start_time
        emails_per_second = total_emails / elapsed if elapsed > 0 else 0
        
        result = {
            "total": total_emails,
            "valid": total_valid,
            "invalid": total_invalid,
            "time": elapsed,
            "speed": f"{emails_per_second:.1f} почт/сек",
            "estimated_50k": f"{(50000 / emails_per_second / 60):.1f} минут на 50к почт"
        }
        
        logger.info(f"🎯 Проверка завершена за {elapsed:.1f} секунд")
        logger.info(f"📈 Скорость: {emails_per_second:.1f} почт/сек")
        logger.info(f"✅ Валидных: {total_valid} | ❌ Невалидных: {total_invalid}")
        
        return result

    async def mass_validate_emails_with_progress(self, chat_id: int, batch_size: int = 100, 
                                                max_concurrent: int = 50) -> Dict[str, Any]:
        """
        Массовая проверка почт с отображением прогресса в реальном времени
        
        Args:
            chat_id: ID чата для отправки сообщений о прогрессе
            batch_size: Размер пакета для проверки
            max_concurrent: Максимальное количество параллельных проверок
        """
        if not self.emails:
            logger.error("❌ Нет почт для проверки")
            if self.bot:
                await self.bot.send_message(chat_id, "❌ Нет почт для проверки")
            return {"total": 0, "valid": 0, "invalid": 0, "time": 0}
        
        if not self.bot:
            logger.error("❌ Бот не установлен для отображения прогресса")
            return await self.mass_validate_emails(batch_size, max_concurrent)
        
        total_emails = len(self.emails)
        
        # Создаем прогресс-бар
        progress = EmailProgress(total_emails)
        
        # Отправляем стартовое сообщение
        try:
            start_msg = await self.bot.send_message(
                chat_id,
                f"🚀 НАЧИНАЕМ МАССОВУЮ ПРОВЕРКУ {total_emails} ПОЧТ...\n\n"
                f"⏱️ Подготовка системы...\n"
                f"⚡ Параллельных потоков: {max_concurrent}\n"
                f"📦 Размер пакета: {batch_size} почт"
            )
            progress_message = start_msg
        except Exception as e:
            logger.error(f"❌ Не удалось отправить стартовое сообщение: {e}")
            progress_message = None
        
        start_time = asyncio.get_event_loop().time()
        
        # Разбиваем на пакеты
        batches = []
        for i in range(0, total_emails, batch_size):
            batch = self.emails[i:i + batch_size]
            batches.append(batch)
        
        total_valid = 0
        total_invalid = 0
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_batch(batch):
            async with semaphore:
                return await self.validate_email_batch(batch)
        
        # Запускаем все пакеты параллельно
        batch_tasks = []
        for i, batch in enumerate(batches):
            task = asyncio.create_task(process_batch(batch))
            batch_tasks.append((i, task))
        
        last_update_time = time.time()
        
        for i, task in batch_tasks:
            try:
                batch_result = await task
                
                if isinstance(batch_result, Exception):
                    logger.error(f"❌ Ошибка в пакете {i}: {batch_result}")
                    continue
                
                # Обновляем статистику
                batch_valid = sum(1 for _, is_valid, _ in batch_result if is_valid)
                batch_invalid = len(batch_result) - batch_valid
                
                total_valid += batch_valid
                total_invalid += batch_invalid
                
                # Обновляем прогресс
                for _, is_valid, _ in batch_result:
                    progress.update(is_valid)
                
                # Обновляем сообщение каждую секунду или каждые 500 почт
                current_time = time.time()
                if current_time - last_update_time >= 1.0 or progress.checked % 500 == 0:
                    if progress_message:
                        try:
                            await self.bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=progress_message.message_id,
                                text=progress.get_stats_text()
                            )
                        except Exception as e:
                            logger.debug(f"Не удалось обновить прогресс: {e}")
                    
                    last_update_time = current_time
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки пакета {i}: {e}")
        
        # Сохраняем кэш
        self.save_valid_cache()
        
        elapsed = asyncio.get_event_loop().time() - start_time
        emails_per_second = total_emails / elapsed if elapsed > 0 else 0
        efficiency = total_valid / total_emails * 100 if total_emails > 0 else 0
        
        # Отправляем финальный отчет
        report = f"""
✅ МАССОВАЯ ПРОВЕРКА ПОЧТ ЗАВЕРШЕНА!

📊 РЕЗУЛЬТАТЫ:
├─ Всего почт: {total_emails}
├─ 🟢 Валидных: {total_valid}
├─ 🔴 Невалидных: {total_invalid}
├─ 💯 Эффективность: {efficiency:.1f}%
├─ ⚡ Скорость: {emails_per_second:.1f} почт/сек
└─ ⏱️ Общее время: {progress.format_time(elapsed)}

💡 СТАТИСТИКА:
• Валидных: {total_valid} ({efficiency:.1f}%)
• Уникальных доменов: {self._count_unique_domains()}
• Лучший домен: {self._get_best_domain()}
• Сохранено в кэш: {len(self.valid_emails_cache)} почт

📈 РЕКОМЕНДАЦИИ:
{f"• Отличный результат! >50% валидных" if efficiency > 50 else f"• Низкая эффективность. Рассмотрите другие источники почт" if efficiency < 10 else "• Средний результат. Можно улучшить"}
"""
        
        try:
            if progress_message:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_message.message_id,
                    text=report
                )
            else:
                await self.bot.send_message(chat_id, report)
        except Exception as e:
            logger.error(f"❌ Не удалось отправить финальный отчет: {e}")
        
        result = {
            "total": total_emails,
            "valid": total_valid,
            "invalid": total_invalid,
            "time": elapsed,
            "speed": emails_per_second,
            "efficiency": efficiency,
            "cache_size": len(self.valid_emails_cache)
        }
        
        return result

    def get_emails(self, count: int = 1, use_cache: bool = True) -> List[Dict[str, str]]:
        """Получить указанное количество почт (приоритет валидным из кэша)"""
        if not self.loaded:
            self.load_emails()
        
        if not self.emails:
            logger.error("❌ Нет доступных почт!")
            return []
        
        # Используем кэш валидных почт если нужно
        if use_cache and self.valid_emails_cache:
            valid_emails = []
            for email in self.valid_emails_cache[:count * 2]:  # Берем с запасом
                # Ищем полные данные
                for email_data in self.emails:
                    if email_data['email'] == email:
                        valid_emails.append(email_data)
                        break
            
            if valid_emails:
                if len(valid_emails) >= count:
                    return valid_emails[:count]
                else:
                    # Добираем остальные
                    remaining = count - len(valid_emails)
                    other_emails = [e for e in self.emails if e['email'] not in self.valid_emails_cache]
                    return valid_emails + other_emails[:remaining]
        
        # Обычная выборка
        if count >= len(self.emails):
            return self.emails
        else:
            return random.sample(self.emails, count)

    def get_email_count(self) -> int:
        """Получить количество доступных почт"""
        return len(self.emails)

    def test_all_emails(self) -> List[Tuple[str, bool, str]]:
        """Протестировать все почты (формат) - ОПТИМИЗИРОВАННЫЙ"""
        results = []
        for i, email_data in enumerate(self.emails):
            if i >= 1000:  # Ограничиваем для скорости
                break
                
            email = email_data['email']
            if '@' in email and '.' in email.split('@')[1]:
                results.append((email, True, "✅ Формат корректный"))
            else:
                results.append((email, False, "❌ Неверный формат email"))
        return results

    async def validate_email(self, email: str, password: str) -> Tuple[bool, str]:
        """Проверить валидность email аккаунта через SMTP"""
        return await self.validate_email_fast(email, password)

    async def validate_all_emails(self) -> List[Tuple[str, bool, str]]:
        """Проверить все загруженные email аккаунты через SMTP"""
        if not self.emails:
            logger.error("❌ Нет почт для проверки")
            return []
        
        # Используем массовую проверку
        result = await self.mass_validate_emails(batch_size=1000, max_concurrent=200)
        
        # Форматируем результаты
        results = []
        valid_emails = self.valid_emails_cache[:100]  # Показываем только первые 100
        
        for email in valid_emails:
            results.append((email, True, "✅ Валидная почта"))
        
        # Добавляем статистику
        results.append(("STATS", True, f"Всего: {result['total']}, Валидных: {result['valid']}, Время: {result['time']:.1f}с"))
        
        return results

    async def send_complaint(self, email: str, password: str, target: str, reason: int) -> Tuple[bool, str]:
        """Отправить жалобу через email"""
        try:
            if not hasattr(Config, 'TELEGRAM_SUPPORT_EMAILS') or not Config.TELEGRAM_SUPPORT_EMAILS:
                logger.error("❌ Не настроены email поддержки Telegram в конфиге!")
                return False, "Не настроены email поддержки"
            
            complaint_text = random.choice(self.complaint_texts)
            reason_detail = self.reason_texts.get(reason, "нарушение правил платформы")
            
            success_count = 0
            total_emails = len(Config.TELEGRAM_SUPPORT_EMAILS)
            
            for tg_email in Config.TELEGRAM_SUPPORT_EMAILS:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = email
                    msg['To'] = tg_email
                    msg['Subject'] = f"Жалоба на нарушение: {target}"
                    
                    body = f"""
Уважаемая поддержка Telegram,

{complaint_text}

Детали нарушения:
- Нарушитель: {target}
- Тип нарушения: {reason_detail}
- Характер: {Config.COMPLAINT_REASONS[reason] if hasattr(Config, 'COMPLAINT_REASONS') else 'нарушение правил'}

Контент представляет угрозу для сообщества и нарушает пользовательское соглашение Telegram.

Прошу принять соответствующие меры.

С уважением,
Пользователь Telegram
                    """
                    
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    
                    # Определяем SMTP сервер
                    domain = email.split('@')[1].lower() if '@' in email else ''
                    
                    if 'gmail' in domain:
                        server, port = 'smtp.gmail.com', 587
                    elif 'mail.ru' in domain:
                        server, port = 'smtp.mail.ru', 587
                    elif 'yandex' in domain:
                        server, port = 'smtp.yandex.ru', 587
                    else:
                        server, port = 'smtp.office365.com', 587
                    
                    # Быстрая отправка с таймаутом
                    with smtplib.SMTP(server, port, timeout=10) as smtp:
                        smtp.ehlo()
                        smtp.starttls()
                        smtp.ehlo()
                        smtp.login(email, password)
                        smtp.send_message(msg)
                    
                    success_count += 1
                    await asyncio.sleep(random.uniform(0.5, 1.5))  # Минимальная задержка
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки на {tg_email} с {email}: {e}")
                    continue
            
            if success_count > 0:
                return True, f"Отправлено {success_count}/{total_emails} писем"
            else:
                return False, "Не удалось отправить ни одного письма"
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка отправки с {email}: {e}")
            return False, f"Ошибка отправки: {str(e)}"

    def _count_unique_domains(self) -> int:
        """Посчитать количество уникальных доменов"""
        domains = set()
        for email_data in self.emails:
            email = email_data['email']
            if '@' in email:
                domain = email.split('@')[1].lower()
                domains.add(domain)
        return len(domains)

    def _get_best_domain(self) -> str:
        """Получить домен с наибольшим количеством валидных почт"""
        domain_stats = {}
        
        # Сначала собираем статистику по всем почтам
        all_domains = {}
        for email_data in self.emails:
            email = email_data['email']
            if '@' in email:
                domain = email.split('@')[1].lower()
                all_domains[domain] = all_domains.get(domain, 0) + 1
        
        # Теперь считаем только валидные
        for email in self.valid_emails_cache:
            if '@' in email:
                domain = email.split('@')[1].lower()
                domain_stats[domain] = domain_stats.get(domain, 0) + 1
        
        if not domain_stats:
            return "Нет валидных почт"
        
        # Находим домен с максимальным количеством валидных
        best_domain = max(domain_stats.items(), key=lambda x: x[1])
        total_in_domain = all_domains.get(best_domain[0], 0)
        percentage = (best_domain[1] / total_in_domain * 100) if total_in_domain > 0 else 0
        
        return f"{best_domain[0]} ({best_domain[1]}/{total_in_domain}, {percentage:.1f}%)"

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику по почтам"""
        valid_count = len(self.valid_emails_cache)
        total_count = len(self.emails)
        efficiency = (valid_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "total": total_count,
            "valid": valid_count,
            "invalid": total_count - valid_count,
            "efficiency": efficiency,
            "unique_domains": self._count_unique_domains(),
            "best_domain": self._get_best_domain(),
            "cache_file_exists": os.path.exists(self.valid_cache_file),
            "loaded": self.loaded
        }

# Создаем глобальный экземпляр
email_manager = EmailManager()