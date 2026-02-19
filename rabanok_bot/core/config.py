import os
from typing import Dict, List

class Config:
    # === ОСНОВНЫЕ НАСТРОЙКИ ===
    BOT_TOKEN: str = "8273213231:AAHoorseTorw4QBHvvt1_hrobAsnLsW9OLQ"
    ADMIN_IDS: List[int] = [5006629901, 773946041, 6753083375, 6222070752]
    
    # === TELEGRAM API ===
    API_ID: int = 23695534
    API_HASH: str = "08f5b069bb4fd8505b98a6b57f857868"
    
    # === ПУТИ ===
    SESSIONS_DIR: str = "sessions"
    EMAILS_DIR: str = "emails" 
    DB_PATH: str = "rabanok.db"
    
    # === CRYPTOBOT ===
    CRYPTOBOT_TOKEN: str = "500319:AA9i0IoPRtlKETNktwJSAzwN1793ZyHDKMw"
    
    # === ЗАЩИТА ОТ DDoS И СИСТЕМА ЛОГИРОВАНИЯ ===
    LOG_GROUP_ID: int = -1002996528027  # ID группы для логов с темами
    
    # Redis для защиты
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    
    # Включение систем защиты
    ENABLE_ANTIDDOS: bool = True
    CAPTCHA_ENABLED: bool = True
    AUTO_BAN_BOTNETS: bool = True
    
    # Лимиты запросов
    RATE_LIMITS: Dict = {
        'start': {'minute': 3, 'hour': 10, 'day': 50},
        'report': {'minute': 2, 'hour': 20, 'day': 200},
        'nuke': {'minute': 1, 'hour': 5, 'day': 20},
        'balance': {'minute': 5, 'hour': 30, 'day': 100},
        'payment': {'minute': 3, 'hour': 15, 'day': 50},
        'session': {'minute': 3, 'hour': 25, 'day': 150},
        'email': {'minute': 2, 'hour': 20, 'day': 100}
    }
    
    # Настройки капчи
    CAPTCHA_CONFIG: Dict = {
        'timeout': 120,  # секунд
        'max_attempts': 3,
        'ban_on_fail': 1800  # бан на 30 минут при провале
    }
    
    # Ботнет детекция
    BOTNET_DETECTION: Dict = {
        'max_starts_per_hour': 3,
        'max_similar_requests': 5,
        'temp_ban_duration': 3600,
        'perm_ban_threshold': 10  # 10 нарушений = перманентный бан
    }
    
    # Темы для логов
    LOG_TOPICS: Dict = {
        'ATTACKS': '🛡️ Атаки и защита',
        'REPORTS': '⚠️ Репорты и жалобы',
        'NUKE': '💣 NUKE операции',
        'PAYMENTS': '💰 Платежи',
        'SESSIONS': '🔐 Сессии',
        'SYSTEM': '⚙️ Системные логи',
        'ERRORS': '🚨 Критические ошибки',
        'MODERATION': '⚖️ Модерация',
        'USERS': '👤 Активность пользователей',
        'API': '🔌 API запросы',
        'EMAILS': '📧 Работа с почтами'
    }
    
    # Подозрительные паттерны для блокировки
    SUSPICIOUS_PATTERNS: List[str] = [
        'mass_report',
        'spam_nuke', 
        'flood_start',
        'rapid_commands',
        'same_text_repeated',
        'bot_username',
        'test_account'
    ]
    
    # Ботнет имена пользователей
    BOTNET_USERNAMES: List[str] = [
        'user', 'bot', 'test', 'temp', 'account',
        'admin', 'support', 'helper', 'service',
        'telegram', 'tg', 'сессия', 'session'
    ]
    
    # Экстренная защита при массовых атаках
    EMERGENCY_PROTECTION: Dict = {
        'max_attacks_per_minute': 50,  # Порог для активации экстренного режима
        'emergency_mode_duration': 600,  # 10 минут
        'auto_enable_captcha': True,
        'strict_rate_limits': True
    }
    
    # === БАЛАНСОВАЯ СИСТЕМА ===
    BALANCE_CONFIG: Dict = {
        "min_deposit": 0.25,
        "currency": "USD",
        "rates": {"USD": 1, "RUB": 90, "UAH": 38}
    }

    # === ЦЕНЫ ДЛЯ БАЛАНСОВОЙ СИСТЕМЫ ===
    BALANCE_PRICES: Dict = {
        # Одиночные жалобы
        "reports": {
            "single": 0.10,
            "pack_10": 0.80,
            "pack_50": 3.50, 
            "pack_100": 6.00
        },
        
        # Подписки (цена в USD)
        "subscriptions": {
            "basic_1day": 1.00,
            "basic_7days": 4.00,
            "basic_30days": 10.00,
            "basic_forever": 15.00,
            
            "premium_1day": 1.50,
            "premium_7days": 7.00,
            "premium_30days": 15.00,
            "premium_forever": 20.00,
            
            "nuke_1day": 1.00,
            "nuke_7days": 3.00,
            "nuke_30days": 8.00,
            "nuke_forever": 13.00
        },
        
        # Покупка методов
        "methods": {
            "session": 0.25,
            "email": 0.35,
            "combo": 0.50,
            "dsa": 0.75,
            "nuke": 0.50
        }
    }
    
    # === ПОДПИСКИ ===
    SUBSCRIPTION_PLANS: Dict = {
        # BASIC планы
        "basic_1day": {
            "price": 1.0, 
            "sessions": 2, 
            "emails": 1, 
            "combo": 0, 
            "dsa": 0,
            "nuke": 0,
            "days": 1, 
            "name": "BASIC 1 день"
        },
        "basic_7days": {
            "price": 4.0, 
            "sessions": 14, 
            "emails": 7, 
            "combo": 3, 
            "dsa": 0,
            "nuke": 0,
            "days": 7, 
            "name": "BASIC 7 дней"
        },
        "basic_30days": {
            "price": 10.0, 
            "sessions": 60, 
            "emails": 30, 
            "combo": 5, 
            "dsa": 0,
            "nuke": 0,
            "days": 30, 
            "name": "BASIC 30 дней"
        },
        "basic_forever": {
            "price": 15.0, 
            "sessions": -1, 
            "emails": 300, 
            "combo": 20, 
            "dsa": 0,
            "nuke": 0,
            "days": 36500, 
            "name": "BASIC НАВСЕГДА"
        },
        
        # PREMIUM планы
        "premium_1day": {
            "price": 1.5, 
            "sessions": 7, 
            "emails": 3, 
            "combo": 1, 
            "dsa": 2,
            "nuke": 0,
            "days": 1, 
            "name": "PREMIUM 1 день"
        },
        "premium_7days": {
            "price": 7.0, 
            "sessions": 45, 
            "emails": 20, 
            "combo": 5, 
            "dsa": 10,
            "nuke": 0,
            "days": 7, 
            "name": "PREMIUM 7 дней"
        },
        "premium_30days": {
            "price": 15.0, 
            "sessions": 70, 
            "emails": 35, 
            "combo": 10, 
            "dsa": 25,
            "nuke": 0,
            "days": 30, 
            "name": "PREMIUM 30 дней"
        },
        "premium_forever": {
            "price": 20.0, 
            "sessions": -1, 
            "emails": -1, 
            "combo": 200, 
            "dsa": -1,
            "nuke": 0,
            "days": 36500, 
            "name": "PREMIUM НАВСЕГДА"
        },
        
        # NUKE планы
        "nuke_1day": {
            "price": 1.0, 
            "sessions": 0, 
            "emails": 0, 
            "combo": 0, 
            "dsa": 0,
            "nuke": 4,
            "days": 1, 
            "name": "NUKE 1 день"
        },
        "nuke_7days": {
            "price": 3.0, 
            "sessions": 0, 
            "emails": 0, 
            "combo": 0, 
            "dsa": 0,
            "nuke": 24,
            "days": 7, 
            "name": "NUKE 7 дней"
        },
        "nuke_30days": {
            "price": 8.0, 
            "sessions": 0, 
            "emails": 0, 
            "combo": 0, 
            "dsa": 0,
            "nuke": 70,
            "days": 30, 
            "name": "NUKE 30 дней"
        },
        "nuke_forever": {
            "price": 13.0, 
            "sessions": 0, 
            "emails": 0, 
            "combo": 0, 
            "dsa": 0,
            "nuke": -1,
            "days": 36500, 
            "name": "NUKE НАВСЕГДА"
        }
    }
    
    # === ПОКУПКА ОТДЕЛЬНЫХ ЖАЛОБ ===
    PAY_PER_USE: Dict = {
        "session": 0.25,
        "email": 0.35, 
        "combo": 0.5,
        "dsa": 0.75,
        "nuke": 0.5
    }
    
    # === ПРИЧИНЫ ЖАЛОБ ===
    COMPLAINT_REASONS: Dict = {
        1: "🔞 Порнография",
        2: "💀 Насилие",
        3: "🚸 Детский контент", 
        4: "💊 Нелегальные товары",
        5: "📱 Персональные данные",
        6: "💣 Терроризм",
        7: "🎭 Мошенничество",
        8: "📝 Спам",
        9: "©️ Нарушение авторских прав",
        10: "❓ Другое"
    }
    
    # === ЗАЩИЩЕННЫЕ ЦЕЛИ ===
    PROTECTED_TARGETS: List[str] = [
        "@durov", "@telegram", "@RabanokNet",
        "Павел Дуров", "Telegram Support", "PressBot",
        "admin", "help", "service"
    ]
    
    # === ПОЧТЫ TELEGRAM ===
    TELEGRAM_SUPPORT_EMAILS: List[str] = [
        "abuse@telegram.org",
        "security@telegram.org", 
        "dmca@telegram.org",
        "recover@telegram.org",
        "sms@telegram.org",
        "stopCA@telegram.org",
        "support@telegram.org"
    ]
    
    # === ЯЗЫКИ ===
    SUPPORTED_LANGUAGES: Dict = {
        'RU': {'code': 'ru', 'flag': '🇷🇺', 'name': 'Русский'},
        'US': {'code': 'en', 'flag': '🇺🇸', 'name': 'Английский'},
        'DE': {'code': 'de', 'flag': '🇩🇪', 'name': 'Немецкий'},
        'FR': {'code': 'fr', 'flag': '🇫🇷', 'name': 'Французский'},
        'ES': {'code': 'es', 'flag': '🇪🇸', 'name': 'Испанский'},
        'IT': {'code': 'it', 'flag': '🇮🇹', 'name': 'Итальянский'},
        'PT': {'code': 'pt', 'flag': '🇵🇹', 'name': 'Португальский'},
        'PL': {'code': 'pl', 'flag': '🇵🇱', 'name': 'Польский'},
        'UA': {'code': 'uk', 'flag': '🇺🇦', 'name': 'Украинский'},
        'IL': {'code': 'he', 'flag': '🇮🇱', 'name': 'Иврит'},
        'GR': {'code': 'el', 'flag': '🇬🇷', 'name': 'Греческий'},
        'SE': {'code': 'sv', 'flag': '🇸🇪', 'name': 'Шведский'},
        'NO': {'code': 'no', 'flag': '🇳🇴', 'name': 'Норвежский'},
        'DK': {'code': 'da', 'flag': '🇩🇰', 'name': 'Датский'},
        'FI': {'code': 'fi', 'flag': '🇫🇮', 'name': 'Финский'},
        'NL': {'code': 'nl', 'flag': '🇳🇱', 'name': 'Нидерландский'},
        'CZ': {'code': 'cs', 'flag': '🇨🇿', 'name': 'Чешский'},
        'SK': {'code': 'sk', 'flag': '🇸🇰', 'name': 'Словацкий'},
        'HU': {'code': 'hu', 'flag': '🇭🇺', 'name': 'Венгерский'},
        'RO': {'code': 'ro', 'flag': '🇷🇴', 'name': 'Румынский'},
        'BG': {'code': 'bg', 'flag': '🇧🇬', 'name': 'Болгарский'},
        'RS': {'code': 'sr', 'flag': '🇷🇸', 'name': 'Сербский'},
        'HR': {'code': 'hr', 'flag': '🇭🇷', 'name': 'Хорватский'},
        'SI': {'code': 'sl', 'flag': '🇸🇮', 'name': 'Словенский'},
        'EE': {'code': 'et', 'flag': '🇪🇪', 'name': 'Эстонский'},
        'LV': {'code': 'lv', 'flag': '🇱🇻', 'name': 'Латышский'},
        'LT': {'code': 'lt', 'flag': '🇱🇹', 'name': 'Литовский'}
    }
    
    # === НАСТРОЙКИ СИСТЕМЫ ===
    MAX_REPORTS_PER_DAY: int = 1000
    REPORT_DELAY: int = 2  # seconds
    SESSION_VALIDATION_INTERVAL: int = 3600  # 1 hour
    
    # === DSA НАСТРОЙКИ ===
    DSA_WEB_URL: str = "https://telegram.org/dsa-report"
    DSA_SUPPORT_EMAILS: List[str] = [
        "dsa@telegram.org",
        "legal@telegram.org", 
        "eu-compliance@telegram.org"
    ]
    
    # === NUKE НАСТРОЙКИ ===
    NUKE_EMAILS: List[str] = [
        "support@telegram.org",
        "abuse@telegram.org", 
        "security@telegram.org",
        "recover@telegram.org",
        "sms@telegram.org"
    ]
    
    # === СИСТЕМА МОНИТОРИНГА ===
    MONITORING_CONFIG: Dict = {
        'check_interval': 60,  # Проверка каждые 60 секунд
        'alert_admins_on_attack': True,
        'log_all_requests': False,  # Логировать все запросы (осторожно!)
        'backup_logs': True,
        'backup_interval': 86400  # Бэкап логов каждые 24 часа
    }
    
    # === ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА ===
    EXTRA_PROTECTION: Dict = {
        'geo_blocking': False,  # Блокировка по странам
        'blocked_countries': ['CN', 'RU', 'IN', 'BR'],  # Страны для блокировки
        'proxy_detection': True,  # Обнаружение прокси/VPN
        'tor_blocking': True,  # Блокировка Tor
        'user_agent_checking': True,  # Проверка User-Agent
        'request_delay_suspicious': 2  # Задержка для подозрительных запросов
    }

# Создаем необходимые директории
def create_directories():
    """Создание необходимых директорий"""
    directories = [
        Config.SESSIONS_DIR, 
        Config.EMAILS_DIR,
        'logs/attacks',
        'logs/sessions', 
        'logs/payments',
        'logs/errors',
        'data'
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Создана директория: {directory}")
    
    # Создаем файлы данных если их нет
    data_files = {
        'data/banned_users.json': '{}',
        'data/botnet_patterns.json': '{}',
        'data/attack_stats.json': '{}'
    }
    
    for file_path, default_content in data_files.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(default_content)
            print(f"Создан файл: {file_path}")

# Автоматическое создание директорий при импорте
create_directories()