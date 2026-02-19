import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "database.db"):
        """Инициализация базы данных"""
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def get_connection(self) -> sqlite3.Connection:
        """Создает или возвращает существующее подключение к базе данных"""
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                # Включаем поддержку внешних ключей
                self.conn.execute("PRAGMA foreign_keys = ON")
                logger.debug("✅ Создано новое подключение к БД")
            
            # Проверяем, что соединение не закрыто
            try:
                self.conn.execute("SELECT 1")
            except sqlite3.ProgrammingError:
                # Если соединение закрыто, создаем новое
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self.conn.execute("PRAGMA foreign_keys = ON")
                logger.debug("✅ Восстановлено подключение к БД")
            
            return self.conn
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise
    
    def close_connection(self):
        """Закрывает подключение к базе данных"""
        if self.conn:
            try:
                self.conn.close()
                logger.debug("✅ Подключение к БД закрыто")
            except:
                pass
            finally:
                self.conn = None
    
    def execute(self, query: str, params: tuple = (), commit: bool = True):
        """Выполнить SQL запрос с возвратом курсора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            result = cursor.execute(query, params)
            if commit:
                conn.commit()
            return result
        except Exception as e:
            if commit:
                conn.rollback()
            logger.error(f"❌ Ошибка выполнения запроса: {query[:100]}... | Параметры: {params}: {e}")
            raise
    
    def fetchone(self, query: str, params: tuple = ()):
        """Получить одну строку результата"""
        try:
            cursor = self.execute(query, params, commit=False)
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ Ошибка fetchone: {query[:100]}...: {e}")
            return None
    
    def fetchall(self, query: str, params: tuple = ()):
        """Получить все строки результата"""
        try:
            cursor = self.execute(query, params, commit=False)
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка fetchall: {query[:100]}...: {e}")
            return []
    
    def init_db(self):
        """Инициализация всех таблиц базы данных"""
        logger.info("🔄 Начало инициализации базы данных...")
        
        try:
            # ===== ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0.0,
                    referral_balance REAL DEFAULT 0.0,
                    referrals INTEGER DEFAULT 0,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    subscription_type TEXT,
                    subscription_end TEXT,
                    sessions_used INTEGER DEFAULT 0,
                    emails_used INTEGER DEFAULT 0,
                    combo_used INTEGER DEFAULT 0,
                    dsa_used INTEGER DEFAULT 0,
                    nuke_used INTEGER DEFAULT 0,
                    total_reports INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_active TEXT,
                    is_banned INTEGER DEFAULT 0,
                    ban_reason TEXT,
                    language TEXT DEFAULT 'ru',
                    subscription_name TEXT
                )
            ''')
            logger.info("✅ Таблица 'users' создана/проверена")
            
            # Проверяем и добавляем недостающие колонки в users
            columns_to_check = [
                'is_banned', 'ban_reason', 'language', 'subscription_name', 
                'last_active', 'referral_balance', 'referrals', 'referral_code',
                'sessions_used', 'emails_used', 'combo_used', 'dsa_used', 'nuke_used'
            ]
            
            for column in columns_to_check:
                try:
                    self.execute(f"SELECT {column} FROM users LIMIT 1")
                except sqlite3.OperationalError:
                    # Определяем тип колонки по ее названию
                    if column in ['is_banned', 'referrals', 'sessions_used', 'emails_used', 'combo_used', 'dsa_used', 'nuke_used']:
                        col_type = 'INTEGER DEFAULT 0'
                    elif column in ['balance', 'referral_balance']:
                        col_type = 'REAL DEFAULT 0.0'
                    elif column == 'language':
                        col_type = 'TEXT DEFAULT \'ru\''
                    else:
                        col_type = 'TEXT'
                    
                    self.execute(f'ALTER TABLE users ADD COLUMN {column} {col_type}')
                    logger.info(f"✅ Добавлена колонка '{column}' в таблицу 'users'")
            
            # ===== ТАБЛИЦА ТРАНЗАКЦИЙ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    amount REAL,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'transactions' создана/проверена")
            
            # ===== ТАБЛИЦА АДМИН СЕССИЙ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_file TEXT UNIQUE,
                    validity TEXT DEFAULT 'unknown',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Таблица 'admin_sessions' создана/проверена")
            
            # ===== ТАБЛИЦА АДМИН ПОЧТ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS admin_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Таблица 'admin_emails' создана/проверена")
            
            # ===== ТАБЛИЦА ЖАЛОБ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    target TEXT,
                    target_type TEXT,
                    reason INTEGER,
                    method TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'reports' создана/проверена")
            
            # ===== ТАБЛИЦА ПЛАТЕЖЕЙ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT DEFAULT 'USD',
                    plan TEXT,
                    status TEXT DEFAULT 'pending',
                    invoice_id TEXT UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'payments' создана/проверена")
            
            # ===== ТАБЛИЦА ЧЕРНОГО СПИСКА =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT UNIQUE,
                    target_type TEXT,
                    reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Таблица 'blacklist' создана/проверена")
            
            # ===== ТАБЛИЦА ЛОГОВ АДМИНОВ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT,
                    target_id INTEGER,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Таблица 'admin_logs' создана/проверена")
            
            # ===== ТАБЛИЦА КЭША ПОДПИСОК НА КАНАЛ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS subscription_cache (
                    user_id INTEGER PRIMARY KEY,
                    is_subscribed BOOLEAN,
                    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'subscription_cache' создана/проверена")
            
            # ===== ТАБЛИЦА ИСТОРИИ ПРОВЕРОК ПОДПИСКИ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS subscription_checks (
                    user_id INTEGER PRIMARY KEY,
                    is_subscribed BOOLEAN,
                    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    check_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'subscription_checks' создана/проверена")
            
            # ===== ТАБЛИЦА КУЛДАУНОВ МЕЖДУ ЖАЛОБАМИ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS report_cooldowns (
                    user_id INTEGER PRIMARY KEY,
                    last_report_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cooldown_end DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'report_cooldowns' создана/проверена")
            
            # ===== ТАБЛИЦА ЖАЛОБ НА КОНКРЕТНЫХ ПОЛЬЗОВАТЕЛЕЙ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS targeted_reports (
                    reporter_id INTEGER,
                    target_id TEXT,
                    report_count INTEGER DEFAULT 1,
                    last_report DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(reporter_id, target_id),
                    FOREIGN KEY (reporter_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'targeted_reports' создана/проверена")
            
            # ===== ТАБЛИЦА ДНЕВНЫХ ЛИМИТОВ ЖАЛОБ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS daily_report_limits (
                    user_id INTEGER,
                    report_date DATE DEFAULT CURRENT_DATE,
                    report_count INTEGER DEFAULT 0,
                    PRIMARY KEY(user_id, report_date),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'daily_report_limits' создана/проверена")
            
            # ===== ТАБЛИЦА ШТРАФОВ ЗА ЗЛОУПОТРЕБЛЕНИЕ ЖАЛОБАМИ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS report_penalties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    target_id TEXT,
                    amount REAL DEFAULT 30.0,
                    reason TEXT DEFAULT 'spam_report',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'report_penalties' создана/проверена")
            
            # ===== ТАБЛИЦА ДЛЯ NUKE СНОСОВ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS nuke_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'nuke_reports' создана/проверена")
            
            # ===== ТАБЛИЦА ДЛЯ TARGET_REPORTS (старая версия) =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS target_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    target TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'target_reports' создана/проверена")
            
            # ===== ТАБЛИЦА USER_COOLDOWNS =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS user_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    cooldown_until TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'user_cooldowns' создана/проверена")
            
            # ===== ТАБЛИЦА ДЛЯ ХРАНЕНИЯ ИНВОЙСОВ =====
            self.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    invoice_id TEXT UNIQUE NOT NULL,
                    product_id TEXT NOT NULL,
                    stars_amount INTEGER NOT NULL,
                    usd_amount REAL NOT NULL,
                    status TEXT DEFAULT 'created',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            logger.info("✅ Таблица 'invoices' создана/проверена")
            
            # ===== ИНДЕКСЫ ДЛЯ БЫСТРОГО ПОИСКА =====
            self.execute("CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices (user_id)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices (status)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices (created_at)")
            
            logger.info("🎉 База данных успешно инициализирована со всеми таблицами!")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации базы данных: {e}")
            raise
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ =====
    
    def add_user(self, user_id: int, username: str, referred_by: int = None) -> bool:
        """Добавление нового пользователя в базу данных"""
        try:
            referral_code = f"REF{user_id}{datetime.now().strftime('%H%M%S')}"
            
            self.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, referral_code, referred_by, created_at) 
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (user_id, username, referral_code, referred_by))
            
            # Обновляем счетчик рефералов у пригласившего
            if referred_by:
                self.execute('''
                    UPDATE users SET referrals = referrals + 1 
                    WHERE user_id = ?
                ''', (referred_by,))
                
                # Добавляем реферальный бонус
                self.execute('''
                    UPDATE users SET referral_balance = referral_balance + 1.0 
                    WHERE user_id = ?
                ''', (referred_by,))
            
            logger.info(f"✅ Добавлен новый пользователь: {user_id} (@{username})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя {user_id}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        """Получение данных пользователя по ID"""
        try:
            result = self.fetchone('SELECT * FROM users WHERE user_id = ?', (user_id,))
            if result:
                logger.debug(f"✅ Получены данные пользователя {user_id}")
            else:
                logger.debug(f"⚠️ Пользователь {user_id} не найден")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
            return None
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """Обновление данных пользователя"""
        try:
            if not kwargs:
                return True
            
            set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
            values = list(kwargs.values())
            values.append(user_id)
            
            query = f'UPDATE users SET {set_clause} WHERE user_id = ?'
            self.execute(query, tuple(values))
            
            logger.info(f"✅ Обновлены данные пользователя {user_id}: {list(kwargs.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления пользователя {user_id}: {e}")
            return False
    
    def update_user_last_active(self, user_id: int) -> bool:
        """Обновление времени последней активности пользователя"""
        try:
            self.execute(
                "UPDATE users SET last_active = datetime('now') WHERE user_id = ?", 
                (user_id,)
            )
            logger.debug(f"✅ Обновлено время активности пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления активности пользователя {user_id}: {e}")
            return False
    
    def is_user_banned(self, user_id: int) -> bool:
        """Проверка заблокирован ли пользователь"""
        try:
            result = self.fetchone(
                'SELECT is_banned FROM users WHERE user_id = ?', 
                (user_id,)
            )
            is_banned = bool(result[0]) if result and result[0] is not None else False
            logger.debug(f"🔍 Проверка бана пользователя {user_id}: {is_banned}")
            return is_banned
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бана пользователя {user_id}: {e}")
            return False
    
    def ban_user(self, user_id: int, reason: str = "") -> bool:
        """Блокировка пользователя"""
        try:
            self.execute(
                'UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?',
                (reason, user_id)
            )
            self.add_admin_log(0, 'ban_user', user_id, f"Заблокирован. Причина: {reason}")
            logger.info(f"🚫 Заблокирован пользователь: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка блокировки пользователя {user_id}: {e}")
            return False
    
    def unban_user(self, user_id: int) -> bool:
        """Разблокировка пользователя"""
        try:
            self.execute(
                'UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?',
                (user_id,)
            )
            self.add_admin_log(0, 'unban_user', user_id, "Разблокирован")
            logger.info(f"✅ Разблокирован пользователь: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка разблокировки пользователя {user_id}: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя из базы данных"""
        try:
            self.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            self.add_admin_log(0, 'delete_user', user_id, "Удален из системы")
            logger.info(f"🗑️ Удален пользователь: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления пользователя {user_id}: {e}")
            return False
    
    def get_user_balance(self, user_id: int) -> float:
        """Получение баланса пользователя"""
        try:
            result = self.fetchone(
                'SELECT balance FROM users WHERE user_id = ?', 
                (user_id,)
            )
            balance = float(result[0]) if result and result[0] is not None else 0.0
            logger.debug(f"💰 Баланс пользователя {user_id}: {balance}")
            return balance
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса пользователя {user_id}: {e}")
            return 0.0
    
    def get_user_referral_balance(self, user_id: int) -> float:
        """Получение реферального баланса пользователя"""
        try:
            result = self.fetchone(
                'SELECT referral_balance FROM users WHERE user_id = ?', 
                (user_id,)
            )
            balance = float(result[0]) if result and result[0] is not None else 0.0
            logger.debug(f"👥 Реферальный баланс пользователя {user_id}: {balance}")
            return balance
        except Exception as e:
            logger.error(f"❌ Ошибка получения реферального баланса пользователя {user_id}: {e}")
            return 0.0
    
    def update_user_balance(self, user_id: int, amount: float) -> bool:
        """Обновление баланса пользователя (добавление/списание)"""
        try:
            self.execute(
                'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                (amount, user_id)
            )
            
            # Добавляем запись в транзакции
            if amount > 0:
                self.add_transaction(user_id, 'deposit', amount, 'Пополнение баланса')
            elif amount < 0:
                self.add_transaction(user_id, 'withdrawal', amount, 'Списание с баланса')
            
            logger.info(f"✅ Обновлен баланс пользователя {user_id}: {amount:+}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления баланса пользователя {user_id}: {e}")
            return False
    
    def set_user_balance(self, user_id: int, new_balance: float) -> bool:
        """Установка точного значения баланса пользователя"""
        try:
            current_balance = self.get_user_balance(user_id)
            difference = new_balance - current_balance
            
            self.execute(
                'UPDATE users SET balance = ? WHERE user_id = ?',
                (new_balance, user_id)
            )
            
            # Логируем изменение
            if difference != 0:
                self.add_transaction(
                    user_id, 
                    'adjustment', 
                    difference, 
                    f'Корректировка баланса: {current_balance} -> {new_balance}'
                )
            
            logger.info(f"✅ Установлен баланс пользователя {user_id}: {new_balance}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка установки баланса пользователя {user_id}: {e}")
            return False
            
    def save_invoice(self, user_id: int, invoice_id: str, product_id: str, 
                     stars_amount: int, usd_amount: float, status: str = "created"):
        """Сохраняет информацию о инвойсе"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO invoices 
                (user_id, invoice_id, product_id, stars_amount, usd_amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (user_id, invoice_id, product_id, stars_amount, usd_amount, status))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка save_invoice: {e}")
            return False
    
    def get_invoice_by_id(self, invoice_id: str):
        """Получает инвойс по ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "invoice_id": row[2],
                    "product_id": row[3],
                    "stars_amount": row[4],
                    "usd_amount": row[5],
                    "status": row[6],
                    "created_at": row[7]
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка get_invoice_by_id: {e}")
            return None
    
    def update_invoice_status(self, invoice_id: str, status: str):
        """Обновляет статус инвойса"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE invoices SET status = ?, updated_at = datetime('now')
                WHERE invoice_id = ?
            """, (status, invoice_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка update_invoice_status: {e}")
            return False
    
    def get_user_invoices(self, user_id: int, limit: int = 10):
        """Получает историю инвойсов пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM invoices 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            logger.error(f"❌ Ошибка get_user_invoices: {e}")
            return []
    
    def get_user_by_referral_code(self, referral_code: str) -> Optional[int]:
        """Получить ID пользователя по реферальному коду"""
        try:
            result = self.fetchone(
                'SELECT user_id FROM users WHERE referral_code = ?',
                (referral_code,)
            )
            user_id = result[0] if result else None
            logger.debug(f"🔍 Поиск по реферальному коду {referral_code}: {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"❌ Ошибка поиска по реферальному коду {referral_code}: {e}")
            return None
    
    def get_user_referrals(self, user_id: int) -> List[Tuple]:
        """Получить список рефералов пользователя"""
        try:
            result = self.fetchall(
                'SELECT user_id, username, created_at FROM users WHERE referred_by = ? ORDER BY created_at DESC',
                (user_id,)
            )
            logger.debug(f"📊 Получено {len(result)} рефералов для пользователя {user_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения рефералов пользователя {user_id}: {e}")
            return []
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[sqlite3.Row]:
        """Получение списка всех пользователей"""
        try:
            result = self.fetchall(
                '''SELECT user_id, username, balance, subscription_type, 
                   created_at, is_banned, last_active 
                   FROM users ORDER BY user_id DESC LIMIT ? OFFSET ?''',
                (limit, offset)
            )
            logger.info(f"✅ Получено {len(result)} пользователей")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка пользователей: {e}")
            return []
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение полной статистики пользователя"""
        try:
            user = self.get_user(user_id)
            if not user:
                return {}
            
            # Основная статистика
            stats = {
                'user_id': user_id,
                'username': user['username'],
                'balance': user['balance'],
                'referral_balance': user['referral_balance'],
                'referrals': user['referrals'],
                'subscription_type': user['subscription_type'],
                'subscription_end': user['subscription_end'],
                'total_reports': user['total_reports'],
                'created_at': user['created_at'],
                'is_banned': bool(user['is_banned']),
                'language': user['language'],
                'subscription_name': user['subscription_name']
            }
            
            # Статистика по методам
            stats.update({
                'sessions_used': user['sessions_used'],
                'emails_used': user['emails_used'],
                'combo_used': user['combo_used'],
                'dsa_used': user['dsa_used'],
                'nuke_used': user['nuke_used']
            })
            
            # Статистика жалоб
            daily_reports = self.get_daily_report_count(user_id)
            target_stats = self.get_user_report_stats(user_id)
            
            stats.update({
                'daily_reports': daily_reports,
                'daily_limit': 10,
                'target_stats': target_stats,
                'penalties_total': self.get_user_penalties_total(user_id)
            })
            
            logger.debug(f"📊 Получена статистика пользователя {user_id}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {}
    
    # ===== МЕТОДЫ ДЛЯ ПОДПИСОК =====
    
    def update_subscription(self, user_id: int, plan: str, days: int, subscription_name: str = "") -> bool:
        """Обновление подписки пользователя"""
        try:
            # Вычисляем дату окончания
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            
            self.execute('''
                UPDATE users SET 
                subscription_type = ?,
                subscription_end = ?,
                subscription_name = ?
                WHERE user_id = ?
            ''', (plan, end_date, subscription_name, user_id))
            
            # Добавляем транзакцию
            self.add_transaction(
                user_id, 
                'subscription', 
                0, 
                f'Активирована подписка: {plan} на {days} дней'
            )
            
            logger.info(f"✅ Обновлена подписка пользователя {user_id}: {plan} на {days} дней")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления подписки {user_id}: {e}")
            return False
    
    def remove_subscription(self, user_id: int) -> bool:
        """Удаление подписки у пользователя"""
        try:
            self.execute('''
                UPDATE users SET 
                subscription_type = NULL,
                subscription_end = NULL,
                subscription_name = NULL
                WHERE user_id = ?
            ''', (user_id,))
            
            self.add_transaction(user_id, 'subscription', 0, 'Подписка удалена')
            
            logger.info(f"✅ Удалена подписка пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления подписки {user_id}: {e}")
            return False
    
    def get_subscription_name(self, user_id: int) -> str:
        """Получает название подписки пользователя"""
        try:
            result = self.fetchone(
                'SELECT subscription_name FROM users WHERE user_id = ?', 
                (user_id,)
            )
            name = result[0] if result and result[0] else ""
            logger.debug(f"📝 Название подписки пользователя {user_id}: {name}")
            return name
        except Exception as e:
            logger.error(f"❌ Ошибка получения названия подписки {user_id}: {e}")
            return ""
    
    def has_active_subscription(self, user_id: int) -> bool:
        """Проверка наличия активной подписки"""
        try:
            result = self.fetchone('''
                SELECT subscription_end FROM users 
                WHERE user_id = ? AND subscription_type IS NOT NULL
            ''', (user_id,))
            
            if result and result[0]:
                try:
                    end_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                    has_active = datetime.now() <= end_date
                    logger.debug(f"🔍 Активная подписка пользователя {user_id}: {has_active}")
                    return has_active
                except:
                    return False
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки активной подписки {user_id}: {e}")
            return False
    
    def get_subscription_info(self, user_id: int) -> Dict[str, Any]:
        """Получение информации о подписке пользователя"""
        try:
            result = self.fetchone('''
                SELECT subscription_type, subscription_end, subscription_name 
                FROM users WHERE user_id = ?
            ''', (user_id,))
            
            if not result:
                return {'has_subscription': False}
            
            info = {
                'has_subscription': result['subscription_type'] is not None,
                'type': result['subscription_type'],
                'name': result['subscription_name'],
                'end_date': result['subscription_end']
            }
            
            if info['end_date']:
                try:
                    end_date = datetime.strptime(info['end_date'], '%Y-%m-%d %H:%M:%S')
                    now = datetime.now()
                    info['is_active'] = now <= end_date
                    if info['is_active']:
                        info['days_left'] = (end_date - now).days
                        info['hours_left'] = int((end_date - now).total_seconds() / 3600)
                except:
                    info['is_active'] = False
            else:
                info['is_active'] = False
            
            logger.debug(f"📋 Информация о подписке пользователя {user_id}: {info}")
            return info
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о подписке {user_id}: {e}")
            return {'has_subscription': False}
    
    # ===== МЕТОДЫ ДЛЯ ЖАЛОБ И ОТЧЕТОВ =====
    
    def can_make_report(self, user_id: int, method: str) -> bool:
        """Проверка возможности отправки жалобы"""
        try:
            # Проверка бана
            if self.is_user_banned(user_id):
                logger.warning(f"🚫 Пользователь {user_id} заблокирован")
                return False
            
            # Проверка подписки
            sub_info = self.get_subscription_info(user_id)
            if sub_info.get('is_active', False):
                logger.info(f"✅ Пользователь {user_id} имеет активную подписку")
                return True
            
            # Если нет подписки - проверяем баланс
            balance = self.get_user_balance(user_id)
            can_report = balance > 0
            logger.info(f"💰 Пользователь {user_id} без подписки, баланс: {balance}, может отправлять: {can_report}")
            return can_report
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки возможности отправки жалобы {user_id}: {e}")
            return False
    
    def add_report(self, user_id: int, target: str, target_type: str, reason: int, method: str) -> Dict[str, Any]:
        """Добавление жалобы с учетом всех ограничений"""
        try:
            # Проверяем можно ли отправить жалобу
            check_result = self.can_make_report_with_limits(user_id, target)
            
            if not check_result["can_report"]:
                return {
                    "success": False,
                    "message": " | ".join(check_result["messages"])
                }
            
            # Получаем данные пользователя
            user = self.get_user(user_id)
            if not user:
                return {
                    "success": False,
                    "message": "Пользователь не найден"
                }
            
            # Проверяем количество жалоб на эту цель
            target_count = self.get_target_report_count(user_id, target)
            
            # Проверяем подписку
            sub_info = self.get_subscription_info(user_id)
            has_active_subscription = sub_info.get('is_active', False)
            
            # Если применяется штраф за превышение лимита
            penalty_amount = 0
            if check_result["penalty_applied"]:
                penalty_amount = check_result["penalty_amount"]
                if not has_active_subscription:
                    # Проверяем достаточно ли средств для штрафа
                    current_balance = self.get_user_balance(user_id)
                    if current_balance < penalty_amount:
                        return {
                            "success": False,
                            "message": f"❌ Недостаточно средств для штрафа. Нужно: {penalty_amount}, доступно: {current_balance}"
                        }
                    # Списание штрафа
                    self.update_user_balance(user_id, -penalty_amount)
                    self.add_report_penalty(user_id, target, penalty_amount)
            
            # Добавляем запись о жалобе
            self.execute('''
                INSERT INTO reports (user_id, target, target_type, reason, method, status) 
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (user_id, target, target_type, reason, method))
            
            # Увеличиваем счетчики
            self.increment_target_report(user_id, target)
            self.increment_daily_report(user_id)
            self.add_report_usage(user_id, method)
            
            # Устанавливаем кулдаун
            self.set_report_cooldown(user_id, 20)
            
            # Обновляем общий счетчик отчетов
            self.execute(
                'UPDATE users SET total_reports = total_reports + 1 WHERE user_id = ?',
                (user_id,)
            )
            
            # Формируем сообщение
            messages = ["✅ Жалоба успешно отправлена"]
            
            if target_count == 1:  # Если это была вторая жалоба
                messages.append("⚠️ Ваша подписка была снята за злоупотребление жалобами на одного пользователя")
            
            if penalty_amount > 0:
                messages.append(f"💰 Списано {penalty_amount} за превышение лимита")
            
            logger.info(f"✅ Добавлена жалоба: {user_id} -> {target} ({method})")
            
            return {
                "success": True,
                "message": " | ".join(messages),
                "penalty": penalty_amount,
                "subscription_removed": target_count == 1
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления жалобы {user_id}->{target}: {e}")
            return {
                "success": False,
                "message": f"Ошибка отправки жалобы: {str(e)}"
            }
    
    def add_report_usage(self, user_id: int, method: str) -> bool:
        """Добавление использования жалобы"""
        try:
            method_column = {
                "session": "sessions_used",
                "email": "emails_used",
                "combo": "combo_used",
                "dsa": "dsa_used",
                "nuke": "nuke_used"
            }.get(method)
            
            if method_column:
                self.execute(f'''
                    UPDATE users SET {method_column} = {method_column} + 1 
                    WHERE user_id = ?
                ''', (user_id,))
                
                logger.info(f"✅ Добавлено использование {method} для пользователя {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Неизвестный метод: {method}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка добавления использования {method} для {user_id}: {e}")
            return False
    
    def get_daily_reports_count(self, user_id: int) -> int:
        """Получает количество жалоб пользователя за сегодня"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            result = self.fetchone('''
                SELECT COUNT(*) FROM reports 
                WHERE user_id = ? AND DATE(created_at) = ?
            ''', (user_id, today))
            
            count = result[0] if result else 0
            logger.debug(f"📊 Дневные жалобы пользователя {user_id}: {count}")
            return count
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_daily_reports_count: {e}")
            return 0
    
    def get_last_report_time(self, user_id: int) -> Optional[datetime]:
        """Получает время последней жалобы пользователя"""
        try:
            result = self.fetchone('''
                SELECT created_at FROM reports 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (user_id,))
            
            if result and result[0]:
                last_time = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                logger.debug(f"⏰ Время последней жалобы пользователя {user_id}: {last_time}")
                return last_time
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_last_report_time: {e}")
            return None
    
    def get_reports_to_target(self, user_id: int, target: str) -> int:
        """Получает количество жалоб пользователя на конкретную цель"""
        try:
            result = self.fetchone('''
                SELECT COUNT(*) FROM target_reports 
                WHERE user_id = ? AND target = ?
            ''', (user_id, target))
            
            count = result[0] if result else 0
            logger.debug(f"🎯 Жалоб пользователя {user_id} на цель {target}: {count}")
            return count
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_reports_to_target: {e}")
            return 0
    
    def increment_daily_reports(self, user_id: int) -> bool:
        """Увеличивает счетчик дневных жалоб"""
        try:
            self.execute('''
                INSERT INTO target_reports (user_id, target, created_at)
                VALUES (?, 'daily_counter', datetime('now'))
            ''', (user_id,))
            
            logger.debug(f"📈 Увеличен счетчик дневных жалоб пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка increment_daily_reports: {e}")
            return False
    
    def add_report_to_target(self, user_id: int, target: str) -> bool:
        """Добавляет запись о жалобе на цель"""
        try:
            self.execute('''
                INSERT INTO target_reports (user_id, target, created_at)
                VALUES (?, ?, datetime('now'))
            ''', (user_id, target))
            
            logger.debug(f"➕ Добавлена жалоба пользователя {user_id} на цель {target}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка add_report_to_target: {e}")
            return False
    
    def get_user_report_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику жалоб пользователя"""
        try:
            # Статистика по целям
            result = self.fetchall('''
                SELECT target_id, report_count, last_report 
                FROM targeted_reports 
                WHERE reporter_id = ?
                ORDER BY report_count DESC
            ''', (user_id,))
            
            target_stats = []
            has_double_complaints = False
            
            for row in result:
                target_id, count, last_report = row
                if count >= 2:
                    has_double_complaints = True
                target_stats.append({
                    "target": target_id,
                    "count": count,
                    "last_report": last_report,
                    "status": "⚠️ Подписка снята" if count >= 2 else "✅ Активна"
                })
            
            # Дневная статистика
            daily_used = self.get_daily_report_count(user_id)
            
            stats = {
                "daily_used": daily_used,
                "daily_limit": 10,
                "target_stats": target_stats,
                "has_double_complaints": has_double_complaints,
                "total_targets": len(target_stats)
            }
            
            logger.debug(f"📈 Статистика жалоб пользователя {user_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики жалоб {user_id}: {e}")
            return {
                "daily_used": 0,
                "daily_limit": 10,
                "target_stats": [],
                "has_double_complaints": False,
                "total_targets": 0
            }
    
    # ===== МЕТОДЫ ДЛЯ СИСТЕМЫ ОГРАНИЧЕНИЙ =====
    
    def check_report_cooldown(self, user_id: int) -> Tuple[bool, str]:
        """Проверка 20-минутного кулдауна между жалобами"""
        try:
            result = self.fetchone('''
                SELECT cooldown_end FROM report_cooldowns 
                WHERE user_id = ?
            ''', (user_id,))
            
            if result and result[0]:
                try:
                    cooldown_end = datetime.fromisoformat(result[0])
                    now = datetime.now()
                    
                    if now < cooldown_end:
                        remaining = cooldown_end - now
                        minutes = int(remaining.total_seconds() / 60)
                        seconds = int(remaining.total_seconds() % 60)
                        message = f"⏳ Жди {minutes} мин {seconds} сек до следующей жалобы"
                        logger.debug(f"⏱️ Кулдаун пользователя {user_id}: {message}")
                        return False, message
                except ValueError as e:
                    logger.warning(f"⚠️ Ошибка парсинга времени кулдауна для {user_id}: {e}")
                    # Если формат времени некорректен, удаляем запись
                    self.execute('DELETE FROM report_cooldowns WHERE user_id = ?', (user_id,))
            
            return True, ""
        except Exception as e:
            logger.error(f"❌ Ошибка проверки кулдауна {user_id}: {e}")
            return False, "Ошибка проверки времени"
    
    def set_report_cooldown(self, user_id: int, minutes: int = 20) -> bool:
        """Установка кулдауна после жалобы"""
        try:
            cooldown_end = (datetime.now() + timedelta(minutes=minutes)).isoformat()
            self.execute('''
                INSERT OR REPLACE INTO report_cooldowns (user_id, cooldown_end)
                VALUES (?, ?)
            ''', (user_id, cooldown_end))
            
            logger.debug(f"✅ Установлен кулдаун {minutes} мин для пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка установки кулдауна {user_id}: {e}")
            return False
    
    def get_target_report_count(self, reporter_id: int, target_id: str) -> int:
        """Получить количество жалоб на конкретного пользователя"""
        try:
            result = self.fetchone('''
                SELECT report_count FROM targeted_reports 
                WHERE reporter_id = ? AND target_id = ?
            ''', (reporter_id, target_id))
            
            count = result[0] if result else 0
            logger.debug(f"🎯 Жалоб пользователя {reporter_id} на цель {target_id}: {count}")
            return count
        except Exception as e:
            logger.error(f"❌ Ошибка получения счетчика жалоб {reporter_id}->{target_id}: {e}")
            return 0
    
    def increment_target_report(self, reporter_id: int, target_id: str) -> bool:
        """Увеличить счетчик жалоб на цель и проверяет снятие подписки"""
        try:
            # Сначала увеличиваем счетчик
            self.execute('''
                INSERT INTO targeted_reports (reporter_id, target_id, last_report)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(reporter_id, target_id) 
                DO UPDATE SET 
                report_count = report_count + 1,
                last_report = datetime('now')
            ''', (reporter_id, target_id))
            
            # Получаем обновленное количество жалоб
            result = self.fetchone('''
                SELECT report_count FROM targeted_reports 
                WHERE reporter_id = ? AND target_id = ?
            ''', (reporter_id, target_id))
            
            report_count = result[0] if result else 0
            
            # Если это вторая жалоба на цель - снимаем подписку
            if report_count == 2:
                self.remove_subscription(reporter_id)
                logger.warning(f"⚠️ Снята подписка пользователя {reporter_id} после 2-й жалобы на {target_id}")
            
            logger.debug(f"📈 Увеличен счетчик жалоб {reporter_id}->{target_id}: {report_count}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка увеличения счетчика жалоб {reporter_id}->{target_id}: {e}")
            return False
    
    def can_make_report_with_limits(self, user_id: int, target_id: str) -> Dict[str, Any]:
        """
        Комплексная проверка возможности отправки жалобы
        Возвращает словарь с результатами проверок
        """
        result = {
            "can_report": True,
            "messages": [],
            "penalty_applied": False,
            "penalty_amount": 30.0,
            "target_limit_exceeded": False,
            "subscription_will_be_removed": False
        }
        
        try:
            # 1. Проверка бана
            if self.is_user_banned(user_id):
                result["can_report"] = False
                result["messages"].append("🚫 Ваш аккаунт заблокирован")
                logger.warning(f"🚫 Пользователь {user_id} заблокирован, жалоба отклонена")
                return result
            
            # 2. Проверка подписки/баланса
            user = self.get_user(user_id)
            if not user:
                result["can_report"] = False
                result["messages"].append("❌ Пользователь не найден")
                return result
            
            sub_info = self.get_subscription_info(user_id)
            has_active_subscription = sub_info.get('is_active', False)
            
            # Если нет активной подписки, проверяем баланс
            if not has_active_subscription:
                balance = self.get_user_balance(user_id)
                if balance <= 0:
                    result["can_report"] = False
                    result["messages"].append("❌ Недостаточно средств на балансе")
                    return result
            
            # 3. Проверка дневного лимита (10 жалоб)
            daily_ok, daily_msg = self.check_daily_limit(user_id, 10)
            if not daily_ok:
                result["can_report"] = False
                result["messages"].append(daily_msg)
                return result
            
            # 4. Проверка кулдауна (20 минут)
            cooldown_ok, cooldown_msg = self.check_report_cooldown(user_id)
            if not cooldown_ok:
                result["can_report"] = False
                result["messages"].append(cooldown_msg)
                return result
            
            # 5. Проверка лимита на конкретную цель
            target_count = self.get_target_report_count(user_id, target_id)
            
            # Если это будет вторая жалоба - предупреждаем о снятии подписки
            if target_count == 1:
                result["subscription_will_be_removed"] = True
                result["messages"].append(
                    "⚠️ Внимание! Это будет вторая жалоба на этого пользователя. "
                    "После отправки ваша подписка будет автоматически снята."
                )
            
            # Если это третья и далее жалоба - применяем штраф
            elif target_count >= 2:
                result["target_limit_exceeded"] = True
                result["messages"].append(
                    f"⚠️ Превышен лимит жалоб на этого пользователя ({target_count+1}/2 макс). "
                    f"Эта жалоба спишет {result['penalty_amount']} с баланса, "
                    f"а ваша подписка уже снята."
                )
                result["penalty_applied"] = True
            
            logger.debug(f"🔍 Проверка ограничений пользователя {user_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки ограничений {user_id}: {e}")
            result["can_report"] = False
            result["messages"].append("❌ Ошибка проверки ограничений")
            return result
    
    def get_daily_report_count(self, user_id: int) -> int:
        """Получить количество жалоб за сегодня"""
        try:
            today = datetime.now().date().isoformat()
            result = self.fetchone('''
                SELECT report_count FROM daily_report_limits 
                WHERE user_id = ? AND report_date = ?
            ''', (user_id, today))
            
            count = result[0] if result else 0
            logger.debug(f"📅 Дневных жалоб пользователя {user_id}: {count}")
            return count
        except Exception as e:
            logger.error(f"❌ Ошибка получения дневного лимита {user_id}: {e}")
            return 0
    
    def increment_daily_report(self, user_id: int) -> bool:
        """Увеличить счетчик дневных жалоб"""
        try:
            today = datetime.now().date().isoformat()
            self.execute('''
                INSERT INTO daily_report_limits (user_id, report_date, report_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, report_date) 
                DO UPDATE SET report_count = report_count + 1
            ''', (user_id, today))
            
            logger.debug(f"📈 Увеличен дневной счетчик жалоб пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка увеличения дневного счетчика {user_id}: {e}")
            return False
    
    def check_daily_limit(self, user_id: int, max_limit: int = 10) -> Tuple[bool, str]:
        """Проверка превышения дневного лимита (10 жалоб)"""
        try:
            count = self.get_daily_report_count(user_id)
            if count >= max_limit:
                # Рассчитываем время до сброса (завтра в 00:00)
                now = datetime.now()
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                remaining = tomorrow - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                message = f"❌ Достигнут дневной лимит ({max_limit} жалоб). Сброс через {hours}ч {minutes}м"
                logger.warning(f"⚠️ Превышен дневной лимит пользователя {user_id}: {count}/{max_limit}")
                return False, message
            return True, ""
        except Exception as e:
            logger.error(f"❌ Ошибка проверки дневного лимита {user_id}: {e}")
            return False, "Ошибка проверки лимита"
    
    def add_report_penalty(self, user_id: int, target_id: str, amount: float = 30.0) -> bool:
        """Добавить запись о штрафе"""
        try:
            self.execute('''
                INSERT INTO report_penalties (user_id, target_id, amount)
                VALUES (?, ?, ?)
            ''', (user_id, target_id, amount))
            
            self.add_transaction(user_id, "penalty", -amount, f"Штраф за превышение лимита жалоб на {target_id}")
            
            logger.info(f"💰 Добавлен штраф {user_id}->{target_id}: {amount}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления штрафа {user_id}: {e}")
            return False
    
    def get_user_penalties_total(self, user_id: int) -> float:
        """Получить общую сумму штрафов пользователя"""
        try:
            result = self.fetchone('''
                SELECT SUM(amount) FROM report_penalties 
                WHERE user_id = ?
            ''', (user_id,))
            
            total = float(result[0]) if result and result[0] is not None else 0.0
            logger.debug(f"💰 Общая сумма штрафов пользователя {user_id}: {total}")
            return total
        except Exception as e:
            logger.error(f"❌ Ошибка получения штрафов {user_id}: {e}")
            return 0.0
    
    def reset_old_limits(self) -> bool:
        """Автоматический сброс старых данных"""
        try:
            # Удаляем кулдауны старше 24 часов
            self.execute('''
                DELETE FROM report_cooldowns 
                WHERE cooldown_end < datetime('now', '-1 day')
            ''')
            
            # Удаляем таргетед репорты старше 30 дней
            self.execute('''
                DELETE FROM targeted_reports 
                WHERE last_report < datetime('now', '-30 days')
            ''')
            
            # Удаляем дневные лимиты старше 2 дней
            self.execute('''
                DELETE FROM daily_report_limits 
                WHERE report_date < date('now', '-2 days')
            ''')
            
            logger.info("✅ Очищены старые данные ограничений")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки старых данных: {e}")
            return False
    
    def get_report_limit_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику по ограничениям для пользователя"""
        try:
            stats = {
                "daily_used": self.get_daily_report_count(user_id),
                "daily_limit": 10,
                "cooldown_active": not self.check_report_cooldown(user_id)[0],
                "penalties_total": self.get_user_penalties_total(user_id),
                "can_report": self.can_make_report_with_limits(user_id, "check")["can_report"]
            }
            
            logger.debug(f"📊 Статистика ограничений пользователя {user_id}: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики ограничений {user_id}: {e}")
            return {
                "daily_used": 0,
                "daily_limit": 10,
                "cooldown_active": False,
                "penalties_total": 0.0,
                "can_report": False
            }
    
    def set_user_cooldown(self, user_id: int, minutes: int = 20) -> bool:
        """Устанавливает время кулдауна для пользователя"""
        try:
            cooldown_until = datetime.now() + timedelta(minutes=minutes)
            
            self.execute('''
                INSERT OR REPLACE INTO user_cooldowns 
                (user_id, cooldown_until, created_at)
                VALUES (?, ?, datetime('now'))
            ''', (user_id, cooldown_until.strftime('%Y-%m-%d %H:%M:%S')))
            
            logger.debug(f"⏱️ Установлен кулдаун для пользователя {user_id}: {minutes} минут")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка set_user_cooldown: {e}")
            return False
    
    # ===== МЕТОДЫ ДЛЯ NUKE СНОСОВ =====
    
    def get_daily_nuke_count(self, user_id: int) -> int:
        """Получает количество NUKE сносов за сегодня"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            result = self.fetchone('''
                SELECT COUNT(*) FROM nuke_reports 
                WHERE user_id = ? AND DATE(created_at) = ?
            ''', (user_id, today))
            
            count = result[0] if result else 0
            logger.debug(f"💣 Дневных NUKE сносов пользователя {user_id}: {count}")
            return count
        except Exception as e:
            logger.error(f"❌ Ошибка получения daily nuke count: {e}")
            return 0
    
    def increment_nuke_count(self, user_id: int) -> bool:
        """Увеличивает счетчик NUKE сносов"""
        try:
            # Обновляем в таблице users
            self.execute('''
                UPDATE users SET nuke_used = COALESCE(nuke_used, 0) + 1 
                WHERE user_id = ?
            ''', (user_id,))
            
            # Записываем в историю NUKE
            self.execute('''
                INSERT INTO nuke_reports (user_id, created_at)
                VALUES (?, datetime('now'))
            ''', (user_id,))
            
            logger.info(f"💣 Увеличен счетчик NUKE сносов пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка увеличения nuke count: {e}")
            return False
    
    # ===== МЕТОДЫ ДЛЯ ПРОВЕРКИ ПОДПИСКИ НА КАНАЛ =====
    
    def update_user_subscription_check(self, user_id: int, is_subscribed: bool) -> bool:
        """Обновляет статус проверки подписки пользователя на канал"""
        try:
            self.execute('''
            INSERT OR REPLACE INTO subscription_checks 
            (user_id, is_subscribed, last_check, check_count) 
            VALUES (?, ?, datetime('now'), COALESCE((SELECT check_count + 1 FROM subscription_checks WHERE user_id = ?), 1))
            ''', (user_id, is_subscribed, user_id))
            
            logger.debug(f"✅ Обновлена проверка подписки пользователя {user_id}: {is_subscribed}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления проверки подписки {user_id}: {e}")
            return False
    
    def get_cached_subscription(self, user_id: int) -> Optional[bool]:
        """Получает кэшированный статус подписки на канал"""
        try:
            result = self.fetchone('''
            SELECT is_subscribed 
            FROM subscription_cache 
            WHERE user_id = ? 
            AND expires_at > datetime('now')
            ''', (user_id,))
            
            if result:
                is_subscribed = bool(result[0])
                logger.debug(f"✅ Получен кэш подписки пользователя {user_id}: {is_subscribed}")
                return is_subscribed
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения кэша подписки {user_id}: {e}")
            return None
    
    def cache_subscription(self, user_id: int, is_subscribed: bool, hours: int = 12) -> bool:
        """Кэширует статус подписки на указанное количество часов"""
        try:
            self.execute('''
            INSERT OR REPLACE INTO subscription_cache 
            (user_id, is_subscribed, expires_at) 
            VALUES (?, ?, datetime('now', ?))
            ''', (user_id, is_subscribed, f'+{hours} hours'))
            
            logger.debug(f"✅ Закэширована подписка пользователя {user_id}: {is_subscribed} на {hours} часов")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка кэширования подписки {user_id}: {e}")
            return False
    
    def get_subscription_check_info(self, user_id: int) -> Optional[sqlite3.Row]:
        """Получает информацию о проверке подписки на канал"""
        try:
            result = self.fetchone('''
            SELECT is_subscribed, last_check, check_count 
            FROM subscription_checks 
            WHERE user_id = ?
            ''', (user_id,))
            
            if result:
                logger.debug(f"📋 Информация о проверке подписки пользователя {user_id}: {dict(result)}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о проверке подписки {user_id}: {e}")
            return None
    
    def clear_subscription_cache(self, user_id: int = None) -> bool:
        """Очищает кэш подписок на канал"""
        try:
            if user_id:
                self.execute("DELETE FROM subscription_cache WHERE user_id = ?", (user_id,))
                logger.info(f"✅ Очищен кэш подписки для пользователя {user_id}")
            else:
                self.execute("DELETE FROM subscription_cache WHERE expires_at < datetime('now')")
                logger.info("✅ Очищен кэш подписок для всех пользователей")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша подписок: {e}")
            return False
    
    def get_subscription_stats(self) -> dict:
        """Получает статистику по подпискам на канал"""
        try:
            result_total = self.fetchone("SELECT COUNT(*) FROM subscription_checks")
            total = result_total[0] if result_total else 0
            
            result_subscribed = self.fetchone("SELECT COUNT(*) FROM subscription_checks WHERE is_subscribed = 1")
            subscribed = result_subscribed[0] if result_subscribed else 0
            
            result_recent = self.fetchone("SELECT COUNT(*) FROM subscription_checks WHERE last_check > datetime('now', '-1 day')")
            recent = result_recent[0] if result_recent else 0
            
            subscription_rate = (subscribed / total * 100) if total > 0 else 0
            
            stats = {
                "total_checks": total,
                "subscribed": subscribed,
                "recent_checks": recent,
                "subscription_rate": round(subscription_rate, 2)
            }
            
            logger.debug(f"📊 Статистика подписок на канал: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики подписок: {e}")
            return {
                "total_checks": 0,
                "subscribed": 0,
                "recent_checks": 0,
                "subscription_rate": 0
            }
    
    # ===== МЕТОДЫ ДЛЯ ЧЕРНОГО СПИСКА =====
    
    def add_to_blacklist(self, target: str, target_type: str = "user", reason: str = "") -> bool:
        """Добавление в черный список"""
        try:
            self.execute('''
                INSERT OR REPLACE INTO blacklist (target, target_type, reason) 
                VALUES (?, ?, ?)
            ''', (target, target_type, reason))
            
            logger.info(f"✅ Добавлено в черный список: {target} ({target_type})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления в черный список {target}: {e}")
            return False
    
    def get_blacklist(self, limit: int = 100) -> List[sqlite3.Row]:
        """Получение черного списка"""
        try:
            result = self.fetchall('''
                SELECT target, target_type, reason, created_at 
                FROM blacklist 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            logger.info(f"📋 Получен черный список ({len(result)} записей)")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения черного списка: {e}")
            return []
    
    def is_blacklisted(self, target: str) -> bool:
        """Проверка наличия в черном списке"""
        try:
            result = self.fetchone('SELECT 1 FROM blacklist WHERE target = ?', (target,))
            is_blacklisted = result is not None
            logger.debug(f"🔍 Проверка черного списка {target}: {is_blacklisted}")
            return is_blacklisted
        except Exception as e:
            logger.error(f"❌ Ошибка проверки черного списка {target}: {e}")
            return False
    
    # ===== МЕТОДЫ ДЛЯ АДМИН СЕССИЙ =====
    
    def add_session(self, session_file: str, validity: str = "unknown") -> bool:
        """Добавление сессии в базу"""
        try:
            self.execute('''
                INSERT OR REPLACE INTO admin_sessions (session_file, validity) 
                VALUES (?, ?)
            ''', (session_file, validity))
            
            logger.info(f"✅ Добавлена сессия: {session_file} ({validity})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления сессии {session_file}: {e}")
            return False
    
    def get_sessions(self, limit: int = 50) -> List[sqlite3.Row]:
        """Получение списка сессий"""
        try:
            result = self.fetchall('''
                SELECT session_file, validity, created_at 
                FROM admin_sessions 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            logger.debug(f"📋 Получено {len(result)} сессий")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка сессий: {e}")
            return []
    
    def update_session_validity(self, session_file: str, validity: str) -> bool:
        """Обновление статуса валидности сессии"""
        try:
            self.execute('''
                UPDATE admin_sessions SET validity = ? WHERE session_file = ?
            ''', (validity, session_file))
            
            logger.info(f"✅ Обновлена валидность сессии {session_file}: {validity}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления валидности сессии {session_file}: {e}")
            return False
    
    def delete_session(self, session_file: str) -> bool:
        """Удаление сессии из базы"""
        try:
            self.execute('DELETE FROM admin_sessions WHERE session_file = ?', (session_file,))
            
            logger.info(f"🗑️ Удалена сессия: {session_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления сессии {session_file}: {e}")
            return False
    
    # ===== МЕТОДЫ ДЛЯ АДМИН ПОЧТ =====
    
    def add_email(self, email: str, password: str, status: str = "pending") -> bool:
        """Добавление почты в базу"""
        try:
            self.execute('''
                INSERT OR REPLACE INTO admin_emails (email, password, status) 
                VALUES (?, ?, ?)
            ''', (email, password, status))
            
            logger.info(f"✅ Добавлена почта: {email} ({status})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления почты {email}: {e}")
            return False
    
    def get_emails(self, status: str = None, limit: int = 100) -> List[sqlite3.Row]:
        """Получение списка почт"""
        try:
            if status:
                result = self.fetchall('''
                    SELECT email, status, created_at 
                    FROM admin_emails 
                    WHERE status = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (status, limit))
            else:
                result = self.fetchall('''
                    SELECT email, status, created_at 
                    FROM admin_emails 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
            
            logger.debug(f"📧 Получено {len(result)} почт")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка почт: {e}")
            return []
    
    def update_email_status(self, email: str, status: str) -> bool:
        """Обновление статуса почты"""
        try:
            self.execute('''
                UPDATE admin_emails SET status = ? WHERE email = ?
            ''', (status, email))
            
            logger.info(f"✅ Обновлен статус почты {email}: {status}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса почты {email}: {e}")
            return False
    
    def delete_email(self, email: str) -> bool:
        """Удаление почты из базы"""
        try:
            self.execute('DELETE FROM admin_emails WHERE email = ?', (email,))
            
            logger.info(f"🗑️ Удалена почта: {email}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления почты {email}: {e}")
            return False
    
    def get_email_stats(self) -> Dict[str, int]:
        """Получение статистики по email"""
        try:
            result = self.fetchall('SELECT status, COUNT(*) FROM admin_emails GROUP BY status')
            stats = dict(result)
            logger.debug(f"📊 Статистика почт: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики email: {e}")
            return {}
    
    # ===== МЕТОДЫ ДЛЯ ПЛАТЕЖЕЙ =====
    
    def add_payment(self, user_id: int, amount: float, plan: str, invoice_id: str, status: str = "pending") -> bool:
        """Добавление записи о платеже"""
        try:
            self.execute('''
                INSERT INTO payments (user_id, amount, plan, invoice_id, status) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, amount, plan, invoice_id, status))
            
            logger.info(f"✅ Добавлен платеж: {user_id} - {amount} - {plan}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления платежа {user_id}: {e}")
            return False
    
    def update_payment_status(self, invoice_id: str, status: str) -> bool:
        """Обновление статуса платежа"""
        try:
            self.execute('''
                UPDATE payments SET status = ? 
                WHERE invoice_id = ?
            ''', (status, invoice_id))
            
            logger.info(f"✅ Обновлен статус платежа {invoice_id}: {status}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса платежа {invoice_id}: {e}")
            return False
    
    def get_payment(self, invoice_id: str) -> Optional[sqlite3.Row]:
        """Получение информации о платеже"""
        try:
            result = self.fetchone('''
                SELECT * FROM payments WHERE invoice_id = ?
            ''', (invoice_id,))
            
            if result:
                logger.debug(f"💰 Получена информация о платеже {invoice_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения платежа {invoice_id}: {e}")
            return None
    
    def get_user_payments(self, user_id: int, limit: int = 10) -> List[sqlite3.Row]:
        """Получение истории платежей пользователя"""
        try:
            result = self.fetchall('''
                SELECT amount, plan, status, created_at 
                FROM payments 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            logger.debug(f"💰 Получено {len(result)} платежей пользователя {user_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения платежей пользователя {user_id}: {e}")
            return []
    
    # ===== МЕТОДЫ ДЛЯ ТРАНЗАКЦИЙ =====
    
    def add_transaction(self, user_id: int, transaction_type: str, amount: float, description: str) -> bool:
        """Добавление транзакции"""
        try:
            self.execute('''
                INSERT INTO transactions (user_id, type, amount, description) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, transaction_type, amount, description))
            
            logger.info(f"✅ Добавлена транзакция: {user_id} - {transaction_type} - {amount}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления транзакции {user_id}: {e}")
            return False
    
    def get_transactions(self, user_id: int, limit: int = 10) -> List[sqlite3.Row]:
        """Получение истории транзакций пользователя"""
        try:
            result = self.fetchall('''
                SELECT type, amount, description, created_at 
                FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            logger.debug(f"💳 Получено {len(result)} транзакций пользователя {user_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения транзакций пользователя {user_id}: {e}")
            return []
    
    def transfer_referral_to_main(self, user_id: int) -> Tuple[bool, float, float]:
        """
        Перевести реферальный баланс на основной с комиссией 10%
        Возвращает: (успех, сумма перевода, комиссия)
        """
        try:
            # Получаем текущий реферальный баланс
            ref_balance = self.get_user_referral_balance(user_id)
            
            if ref_balance <= 0:
                logger.warning(f"⚠️ Нулевой реферальный баланс пользователя {user_id}")
                return False, 0.0, 0.0
            
            # Вычисляем комиссию 10%
            commission = ref_balance * 0.10
            amount_to_transfer = ref_balance - commission
            
            # Выполняем перевод
            self.execute('''
                UPDATE users SET 
                balance = balance + ?, 
                referral_balance = 0 
                WHERE user_id = ?
            ''', (amount_to_transfer, user_id))
            
            # Добавляем транзакции
            self.add_transaction(user_id, 'referral_transfer', amount_to_transfer, 'Перевод реферального баланса')
            self.add_transaction(user_id, 'commission', -commission, 'Комиссия за перевод реферального баланса')
            
            logger.info(f"✅ Перевод реферального баланса пользователя {user_id}: {amount_to_transfer} (комиссия: {commission})")
            return True, amount_to_transfer, commission
            
        except Exception as e:
            logger.error(f"❌ Ошибка перевода реферального баланса {user_id}: {e}")
            return False, 0.0, 0.0
    
    # ===== МЕТОДЫ ДЛЯ АДМИН ЛОГОВ =====
    
    def add_admin_log(self, admin_id: int, action: str, target_id: int = None, details: str = "") -> bool:
        """Добавление лога админских действий"""
        try:
            self.execute('''
                INSERT INTO admin_logs (admin_id, action, target_id, details) 
                VALUES (?, ?, ?, ?)
            ''', (admin_id, action, target_id, details))
            
            logger.info(f"📝 Добавлен лог админа {admin_id}: {action}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления лога админа {admin_id}: {e}")
            return False
    
    def get_admin_logs(self, limit: int = 50) -> List[sqlite3.Row]:
        """Получение логов админских действий"""
        try:
            result = self.fetchall('''
                SELECT admin_id, action, target_id, details, created_at 
                FROM admin_logs 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            logger.debug(f"📋 Получено {len(result)} логов админов")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения логов админов: {e}")
            return []
    
    # ===== МЕТОДЫ ДЛЯ СТАТИСТИКИ СИСТЕМЫ =====
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Получение статистики системы"""
        try:
            # Общее количество пользователей
            result = self.fetchone('SELECT COUNT(*) FROM users')
            total_users = result[0] if result else 0
            
            # Пользователи с подписками
            result = self.fetchone('SELECT COUNT(*) FROM users WHERE subscription_type IS NOT NULL')
            active_users = result[0] if result else 0
            
            # Заблокированные пользователи
            result = self.fetchone('SELECT COUNT(*) FROM users WHERE is_banned = 1')
            banned_users = result[0] if result else 0
            
            # Общий баланс
            result = self.fetchone('SELECT SUM(balance) FROM users')
            total_balance = float(result[0]) if result and result[0] is not None else 0.0
            
            # Общий доход
            result = self.fetchone('SELECT SUM(amount) FROM payments WHERE status = "completed"')
            total_income = float(result[0]) if result and result[0] is not None else 0.0
            
            # Общее количество жалоб
            result = self.fetchone('SELECT SUM(total_reports) FROM users')
            total_reports = result[0] if result else 0
            
            # Валидные сессии
            result = self.fetchone('SELECT COUNT(*) FROM admin_sessions WHERE validity = "valid"')
            valid_sessions = result[0] if result else 0
            
            # Все сессии
            result = self.fetchone('SELECT COUNT(*) FROM admin_sessions')
            total_sessions = result[0] if result else 0
            
            # Активные почты
            result = self.fetchone('SELECT COUNT(*) FROM admin_emails WHERE status = "active"')
            active_emails = result[0] if result else 0
            
            # Жалобы в работе
            result = self.fetchone('SELECT COUNT(*) FROM reports WHERE status = "pending"')
            pending_reports = result[0] if result else 0
            
            # Успешные жалобы
            result = self.fetchone('SELECT COUNT(*) FROM reports WHERE status = "success"')
            success_reports = result[0] if result else 0
            
            # Статистика по методам
            result = self.fetchone('SELECT SUM(sessions_used) FROM users')
            sessions_used = result[0] if result else 0
            
            result = self.fetchone('SELECT SUM(emails_used) FROM users')
            emails_used = result[0] if result else 0
            
            result = self.fetchone('SELECT SUM(combo_used) FROM users')
            combo_used = result[0] if result else 0
            
            result = self.fetchone('SELECT SUM(nuke_used) FROM users')
            nuke_used = result[0] if result else 0
            
            stats = {
                'total_users': total_users,
                'active_users': active_users,
                'banned_users': banned_users,
                'total_balance': total_balance,
                'total_income': total_income,
                'total_reports': total_reports,
                'valid_sessions': valid_sessions,
                'total_sessions': total_sessions,
                'active_emails': active_emails,
                'pending_reports': pending_reports,
                'success_reports': success_reports,
                'sessions_used': sessions_used,
                'emails_used': emails_used,
                'combo_used': combo_used,
                'nuke_used': nuke_used,
                'success_rate': round((success_reports / total_reports * 100) if total_reports > 0 else 0, 2)
            }
            
            logger.info(f"📊 Статистика системы: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики системы: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'banned_users': 0,
                'total_balance': 0.0,
                'total_income': 0.0,
                'total_reports': 0,
                'valid_sessions': 0,
                'total_sessions': 0,
                'active_emails': 0,
                'pending_reports': 0,
                'success_reports': 0,
                'sessions_used': 0,
                'emails_used': 0,
                'combo_used': 0,
                'nuke_used': 0,
                'success_rate': 0
            }
    
    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====
    
    def backup_database(self, backup_path: str = None) -> bool:
        """Создание резервной копии базы данных"""
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"backup_database_{timestamp}.db"
            
            # Закрываем текущее соединение
            self.close_connection()
            
            # Копируем файл базы данных
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            # Восстанавливаем соединение
            self.get_connection()
            
            logger.info(f"✅ Создана резервная копия базы данных: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии: {e}")
            # Восстанавливаем соединение в случае ошибки
            try:
                self.get_connection()
            except:
                pass
            return False
    
    def optimize_database(self) -> bool:
        """Оптимизация базы данных (VACUUM)"""
        try:
            self.execute('VACUUM')
            logger.info("✅ База данных оптимизирована (VACUUM)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации базы данных: {e}")
            return False
    
    def check_database_integrity(self) -> Tuple[bool, str]:
        """Проверка целостности базы данных"""
        try:
            result = self.fetchone('PRAGMA integrity_check')
            integrity_ok = result and result[0] == 'ok'
            message = result[0] if result else 'unknown'
            
            if integrity_ok:
                logger.info(f"✅ Целостность базы данных: {message}")
            else:
                logger.error(f"❌ Проблемы с целостностью базы данных: {message}")
            
            return integrity_ok, message
        except Exception as e:
            logger.error(f"❌ Ошибка проверки целостности базы данных: {e}")
            return False, str(e)
    
    def get_database_size(self) -> int:
        """Получение размера файла базы данных в байтах"""
        try:
            if os.path.exists(self.db_path):
                size = os.path.getsize(self.db_path)
                logger.debug(f"📦 Размер файла базы данных: {size} байт")
                return size
            return 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения размера базы данных: {e}")
            return 0
    
    def __del__(self):
        """Деструктор - закрывает соединение при удалении объекта"""
        self.close_connection()