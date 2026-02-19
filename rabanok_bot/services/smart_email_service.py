import random
import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Tuple, Optional
from googletrans import Translator

logger = logging.getLogger(__name__)

class SmartEmailComplaintService:
    def __init__(self, email_manager):
        """
        Инициализация умного сервиса жалоб
        
        Args:
            email_manager: Экземпляр EmailManager для получения почт
        """
        self.email_manager = email_manager
        self.translator = Translator()
        
        # Умное распределение почт поддержки по категориям
        self.email_categories = {
            "child_exploitation": {
                "emails": ["stopCA@telegram.org", "abuse@telegram.org", "security@telegram.org"],
                "priority": "URGENT",
                "response_time": "1-2 hours"
            },
            
            "violence": {
                "emails": ["abuse@telegram.org", "security@telegram.org"],
                "priority": "HIGH", 
                "response_time": "2-4 hours"
            },
            
            "terrorism": {
                "emails": ["abuse@telegram.org", "security@telegram.org"],
                "priority": "URGENT",
                "response_time": "1-3 hours"
            },
            
            "illegal_goods": {
                "emails": ["abuse@telegram.org"],
                "priority": "MEDIUM",
                "response_time": "6-12 hours"
            },
            
            "personal_data": {
                "emails": ["abuse@telegram.org", "security@telegram.org"],
                "priority": "HIGH",
                "response_time": "3-6 hours"
            },
            
            "fraud_spam": {
                "emails": ["abuse@telegram.org"],
                "priority": "MEDIUM", 
                "response_time": "4-8 hours"
            },
            
            "copyright": {
                "emails": ["dmca@telegram.org"],
                "priority": "MEDIUM",
                "response_time": "12-24 hours"
            },
            
            "other": {
                "emails": ["abuse@telegram.org"],
                "priority": "LOW",
                "response_time": "24-48 hours"
            },
            
            "dislike": {
                "emails": ["support@telegram.org"],
                "priority": "LOW",
                "response_time": "48+ hours"
            },
            
            "should_be_removed": {
                "emails": ["support@telegram.org"],
                "priority": "LOW", 
                "response_time": "48+ hours"
            }
        }
        
        self.email_providers = {
            "gmail": {"smtp": "smtp.gmail.com", "port": 587},
            "mailru": {"smtp": "smtp.mail.ru", "port": 587},
            "yandex": {"smtp": "smtp.yandex.ru", "port": 587},
            "outlook": {"smtp": "smtp-mail.outlook.com", "port": 587},
            "yahoo": {"smtp": "smtp.mail.yahoo.com", "port": 587},
            "icloud": {"smtp": "smtp.mail.me.com", "port": 587}
        }
        
        logger.info("✅ SmartEmailComplaintService инициализирован")
    
    def _get_provider_from_email(self, email: str) -> Tuple[str, int]:
        """Определяет SMTP сервер по email"""
        email_lower = email.lower()
        
        if "gmail.com" in email_lower:
            return self.email_providers["gmail"]["smtp"], self.email_providers["gmail"]["port"]
        elif "mail.ru" in email_lower or "bk.ru" in email_lower or "inbox.ru" in email_lower:
            return self.email_providers["mailru"]["smtp"], self.email_providers["mailru"]["port"]
        elif "yandex.ru" in email_lower or "ya.ru" in email_lower:
            return self.email_providers["yandex"]["smtp"], self.email_providers["yandex"]["port"]
        elif "outlook.com" in email_lower or "hotmail.com" in email_lower:
            return self.email_providers["outlook"]["smtp"], self.email_providers["outlook"]["port"]
        elif "yahoo.com" in email_lower:
            return self.email_providers["yahoo"]["smtp"], self.email_providers["yahoo"]["port"]
        else:
            # Пробуем Gmail как запасной вариант
            logger.warning(f"⚠️ Неизвестный провайдер для {email}, использую Gmail SMTP")
            return self.email_providers["gmail"]["smtp"], self.email_providers["gmail"]["port"]
    
    def _generate_urgency_header(self, priority: str) -> str:
        """Генерирует заголовки срочности"""
        headers = {
            "URGENT": "URGENT: Requires Immediate Action - Potential Legal Violations",
            "HIGH": "HIGH PRIORITY: Serious Policy Violation - Quick Response Requested", 
            "MEDIUM": "Policy Violation Report - Standard Review Requested",
            "LOW": "Content Concern Report - Community Guidelines Review"
        }
        return headers.get(priority, "Policy Violation Report")
    
    def _get_category_from_reason(self, reason_id: int) -> str:
        """Конвертирует ID причины в категорию для умной отправки"""
        reason_to_category = {
            1: "child_exploitation",  # порнография
            2: "violence",            # насилие
            3: "child_exploitation",  # детская эксплуатация
            4: "illegal_goods",       # нелегальные товары
            5: "personal_data",       # персональные данные
            6: "terrorism",           # терроризм
            7: "fraud_spam",          # мошенничество
            8: "fraud_spam",          # спам
            9: "copyright",           # авторские права
            10: "other"               # систематические нарушения
        }
        return reason_to_category.get(reason_id, "other")
    
    def _get_complaint_text(self, reason_id: int, target: str) -> str:
        """Генерирует текст жалобы на основе причины"""
        complaint_templates = {
            1: f"Обнаружен порнографический контент, включая материалы сексуального характера с участием несовершеннолетних. Аккаунт {target} распространяет неприемлемые материалы.",
            2: f"Контент аккаунта {target} содержит пропаганду насилия, жестокости и агрессии, что нарушает правила безопасности платформы.",
            3: f"Аккаунт {target} связан с детской эксплуатацией и распространением контента, нарушающего защиту несовершеннолетних.",
            4: f"Пользователь {target} рекламирует и продает нелегальные товары и услуги, включая наркотики и запрещенные вещества.",
            5: f"Аккаунт {target} нарушает конфиденциальность, публикуя персональные данные пользователей без их согласия.",
            6: f"Обнаружена пропаганда терроризма и экстремизма. Аккаунт {target} распространяет опасные материалы.",
            7: f"Аккаунт {target} вовлечен в мошеннические схемы и обман пользователей с финансовыми целями.",
            8: f"Пользователь {target} осуществляет массовый спам и рассылку навязчивой рекламы.",
            9: f"Контент аккаунта {target} нарушает авторские права и интеллектуальную собственность.",
            10: f"Аккаунт {target} систематически нарушает правила платформы и создает негативный опыт для сообщества."
        }
        return complaint_templates.get(reason_id, f"Аккаунт {target} нарушает правила сообщества Telegram.")
    
    async def generate_smart_email(self, target: str, reason_id: int, language: str = "ru") -> Dict[str, str]:
        """Генерирует умное письмо с учетом причины жалобы"""
        
        # Определяем категорию по причине
        category = self._get_category_from_reason(reason_id)
        complaint_text = self._get_complaint_text(reason_id, target)
        
        category_info = self.email_categories.get(category, self.email_categories["other"])
        priority = category_info["priority"]
        response_time = category_info["response_time"]
        
        # Базовые шаблоны для разных приоритетов
        templates = {
            "URGENT": [
                f"""СРОЧНО: {self._generate_urgency_header(priority)}

Уважаемая команда безопасности Telegram,

Я пишу, чтобы сообщить о серьезном нарушении, требующем немедленного внимания.

ЦЕЛЬ: {target}
КАТЕГОРИЯ: {category.upper()}
ПРИОРИТЕТ: {priority}
ОЖИДАЕМОЕ ВРЕМЯ ОТВЕТА: {response_time}

АНАЛИЗ КОНТЕНТА:
{complaint_text}

Этот контент представляет собой серьезное нарушение Условий использования Telegram и может включать противоправную деятельность, требующую внимания правоохранительных органов. Характер этого контента предполагает потенциальные правовые последствия, если не принять срочные меры.

ТРЕБУЕМЫЕ ДЕЙСТВИЯ:
1. Немедленная проверка и удаление контента при подтверждении нарушений
2. Приостановка аккаунта до завершения расследования
3. Координация с соответствующими органами, если применимо
4. Внедрение профилактических мер

Учитывая серьезность данного отчета, настоятельно рекомендую отнестись к этому вопросу с наивысшим приоритетом.

С уважением,
Ответственный пользователь Telegram
Отчет через официальные каналы""",

                f"""ЭКСТРЕННЫЙ ОТЧЕТ: {self._generate_urgency_header(priority)}

В отдел безопасности Telegram,

Я сообщаю о контенте, требующем экстренной проверки и действий.

ДЕТАЛИ ОТЧЕТА:
- Цель: {target}
- Тип нарушения: {category.replace('_', ' ').title()}
- Уровень приоритета: {priority}
- Ожидаемый ответ: {response_time}

СОДЕРЖАНИЕ ОТЧЕТА:
{complaint_text}

Этот материал нарушает несколько разделов правил сообщества Telegram и может включать действия, угрожающие безопасности пользователей или нарушающие применимые законы.

РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ:
• Немедленное удаление контента
• Расследование аккаунта пользователя
• Усиленный мониторинг подобного контента
• Возможное юридическое информирование

Серьезность этого контента требует ускоренной проверки и решительных действий.

С уважением,
Сознательный участник сообщества"""
            ],
            
            "HIGH": [
                f"""ОТЧЕТ ВЫСОКОГО ПРИОРИТЕТА: {self._generate_urgency_header(priority)}

Уважаемая команда поддержки Telegram,

Я сообщаю о контенте, нарушающем политику Telegram и требующем оперативного внимания.

ИНФОРМАЦИЯ ОТЧЕТА:
- Цель: {target}
- Категория проблемы: {category.replace('_', ' ').title()}
- Приоритет: {priority}
- Время ответа: {response_time}

ПОДРОБНЫЙ ОТЧЕТ:
{complaint_text}

Этот контент нарушает правила сообщества и Условия использования Telegram. Характер этих нарушений предполагает потенциальный вред для пользователей или экосистемы платформы.

ЗАПРОШЕННЫЙ ОТВЕТ:
1. Проверка контента в указанные сроки
2. Соответствующие меры при подтверждении нарушений
3. Уведомление пользователя при принятии мер в отношении аккаунта
4. Последующие профилактические меры

Спасибо за оперативное рассмотрение этого вопроса.

С наилучшими пожеланиями,
Пользователь Telegram, заботящийся о безопасности платформы"""
            ],
            
            "MEDIUM": [
                f"""Отчет о нарушении политики: {target}

Уважаемая команда Telegram,

Я хотел бы сообщить о контенте, который, по-видимому, нарушает Условия использования Telegram.

Детали отчета:
- Цель: {target}
- Категория: {category.replace('_', ' ').title()}
- Приоритет: {priority}
- Ожидаемая проверка: {response_time}

Содержание отчета:
{complaint_text}

После ознакомления с правилами сообщества Telegram я считаю, что этот контент может противоречить политике платформы. Данные материалы, по-видимому, требуют проверки модерации.

Запрошенные действия:
• Проверка контента по стандартным процедурам
• Оценка нарушения политики
• Соответствующие действия модерации
• Стандартные сроки ответа

Пожалуйста, расследуйте этот отчет в соответствии со стандартными процедурами модерации.

Искренне,
Участник сообщества Telegram"""
            ],
            
            "LOW": [
                f"""Сообщение о проблемном контенте

Здравствуйте, поддержка Telegram,

Я пишу, чтобы поделиться опасениями по поводу контента, который может повлиять на качество работы сообщества.

Детали контента:
- Цель: {target}
- Тип проблемы: {category.replace('_', ' ').title()}
- Приоритет: Обратная связь сообщества
- Срок проверки: {response_time}

Описание проблемы:
{complaint_text}

Этот контент вызывает вопросы о его уместности в сообществе Telegram. Хотя он может не представлять срочных нарушений, он может повлиять на пользовательский опыт и стандарты сообщества.

Предлагаемая проверка:
- Оценка соответствия правилам сообщества
- Оценка уместности контента
- Учет пользовательского опыта

Спасибо за рассмотрение этой обратной связи в рамках вашего постоянного управления сообществом.

С наилучшими пожеланиями,
Пользователь Telegram"""
            ]
        }
        
        # Выбираем шаблон по приоритету
        template_group = templates.get(priority, templates["MEDIUM"])
        email_body = random.choice(template_group)
        
        # Генерируем тему
        subjects = {
            "URGENT": [
                f"СРОЧНО: Нарушение {category.replace('_', ' ').title()} - Требуются немедленные действия",
                f"ЭКСТРЕННО: Контент {category.replace('_', ' ').title()} - Проблема для правоохранительных органов",
                f"КРИТИЧЕСКИЙ: Отчет {category.replace('_', ' ').title()} - Потенциальные юридические проблемы"
            ],
            "HIGH": [
                f"ВЫСОКИЙ ПРИОРИТЕТ: Нарушение политики {category.replace('_', ' ').title()}",
                f"Серьезное нарушение {category.replace('_', ' ').title()} - Отчет", 
                f"Срочная проблема с контентом {category.replace('_', ' ').title()}"
            ],
            "MEDIUM": [
                f"Отчет о нарушении политики: {category.replace('_', ' ').title()}",
                f"Запрос на модерацию контента: {category.replace('_', ' ').title()}",
                f"Отчет о правилах сообщества: {category.replace('_', ' ').title()}"
            ],
            "LOW": [
                f"Проблема с контентом: {category.replace('_', ' ').title()}",
                f"Обратная связь сообщества: {category.replace('_', ' ').title()}",
                f"Отчет о пользовательском опыте: {category.replace('_', ' ').title()}"
            ]
        }
        
        subject = random.choice(subjects.get(priority, subjects["MEDIUM"]))
        
        # Переводим если нужно
        if language != "ru":
            try:
                subject = self.translator.translate(subject, dest=language).text
                email_body = self.translator.translate(email_body, dest=language).text
            except Exception as e:
                logger.error(f"Ошибка перевода email: {e}")
        
        return {
            "subject": subject,
            "body": email_body,
            "emails": category_info["emails"],
            "priority": priority,
            "response_time": response_time,
            "category": category
        }
    
    async def send_smart_complaint(self, target: str, reason_id: int, 
                                 email_count: int = 3, language: str = "ru") -> Dict[str, any]:
        """
        Умная отправка жалобы с использованием реальных почт пользователей
        
        Args:
            target: Цель жалобы
            reason_id: ID причины жалобы
            email_count: Количество почт для использования
            language: Язык отправки
        """
        
        try:
            # Получаем реальные почты из EmailManager
            available_emails = self.email_manager.get_emails(email_count)
            
            if not available_emails:
                logger.error("❌ Нет доступных почт для отправки!")
                return {
                    "success": False,
                    "message": "Нет доступных почт для отправки",
                    "sent_count": 0,
                    "error": "No emails available"
                }
            
            # Генерируем умное письмо
            email_data = await self.generate_smart_email(target, reason_id, language)
            
            logger.info(f"📧 Использую {len(available_emails)} почт для отправки на {len(email_data['emails'])} адресов поддержки")
            logger.info(f"🎯 Приоритет: {email_data['priority']}, Категория: {email_data['category']}")
            
            results = {
                "success": False,
                "message": "",
                "sent_count": 0,
                "failed_count": 0,
                "from_emails": [],
                "to_emails": email_data["emails"],
                "priority": email_data["priority"],
                "estimated_response": email_data["response_time"],
                "category": email_data["category"],
                "details": []
            }
            
            total_success = 0
            
            # Отправляем с каждой доступной почты
            for i, email_acc in enumerate(available_emails, 1):
                from_email = email_acc['email']
                password = email_acc['password']
                
                logger.info(f"📤 Отправка с почты {i}/{len(available_emails)}: {from_email}")
                
                # Получаем SMTP сервер для этой почты
                smtp_server, port = self._get_provider_from_email(from_email)
                
                email_success = 0
                email_failed = 0
                
                # Отправляем на все адреса поддержки для этой категории
                for tg_email in email_data["emails"]:
                    success = await self._send_single_email(
                        from_email, password, tg_email,
                        email_data["subject"], email_data["body"],
                        smtp_server, port
                    )
                    
                    if success:
                        email_success += 1
                        total_success += 1
                        results["details"].append(f"✅ {from_email} -> {tg_email}")
                    else:
                        email_failed += 1
                        results["details"].append(f"❌ {from_email} -> {tg_email}")
                    
                    # Случайная задержка между отправками
                    await asyncio.sleep(random.uniform(2, 5))
                
                results["from_emails"].append(from_email)
                logger.info(f"📊 Почта {from_email}: отправлено {email_success}, не отправлено {email_failed}")
            
            results["sent_count"] = total_success
            results["failed_count"] = sum(len(email_data["emails"]) for _ in available_emails) - total_success
            
            if total_success > 0:
                results["success"] = True
                results["message"] = f"Отправлено {total_success} писем с {len(available_emails)} почт"
                logger.info(f"✅ Успешно отправлено {total_success} писем")
            else:
                results["message"] = "Не удалось отправить ни одного письма"
                logger.error("❌ Не удалось отправить ни одного письма")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка умной отправки email: {e}")
            return {
                "success": False,
                "message": f"Ошибка отправки: {str(e)}",
                "sent_count": 0,
                "error": str(e)
            }
    
    async def _send_single_email(self, from_email: str, password: str, to_email: str,
                               subject: str, body: str, smtp_server: str, port: int) -> bool:
        """Отправляет одно письмо"""
        try:
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['X-Priority'] = '1'  # Высокий приоритет
            msg['Importance'] = 'high'
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            logger.debug(f"🔧 Подключение к {smtp_server}:{port} с {from_email}")
            
            # Добавляем задержку для естественности
            delay = random.uniform(1, 3)
            await asyncio.sleep(delay)
            
            server = smtplib.SMTP(smtp_server, port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(from_email, password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Email отправлен: {from_email} -> {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ Ошибка аутентификации для {from_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка отправки с {from_email} на {to_email}: {e}")
            return False
    
    def get_category_analytics(self, reason_id: int) -> Dict[str, str]:
        """Возвращает аналитику по категории на основе причины"""
        category = self._get_category_from_reason(reason_id)
        category_info = self.email_categories.get(category, self.email_categories["other"])
        return {
            "category": category,
            "emails": category_info["emails"],
            "priority": category_info["priority"],
            "response_time": category_info["response_time"],
            "description": self._get_category_description(category)
        }
    
    def _get_category_description(self, category: str) -> str:
        """Описание категории для пользователя"""
        descriptions = {
            "child_exploitation": "🚸 Высший приоритет - отправка в stopCA и abuse",
            "violence": "💀 Высокий приоритет - отправка в abuse и security", 
            "terrorism": "💣 Высший приоритет - срочная отправка в abuse",
            "illegal_goods": "💊 Средний приоритет - отправка в abuse",
            "personal_data": "📱 Высокий приоритет - отправка в abuse и security",
            "fraud_spam": "🎭 Средний приоритет - отправка в abuse",
            "copyright": "©️ Средний приоритет - отправка в dmca",
            "other": "❓ Низкий приоритет - отправка в abuse",
            "dislike": "👎 Низкий приоритет - отправка в support",
            "should_be_removed": "🗑️ Низкий приоритет - отправка в support"
        }
        return descriptions.get(category, "Отправка в соответствующие отделы")