import sqlite3
import logging
from typing import List, Tuple, Optional
from core.database import Database

logger = logging.getLogger(__name__)

class BalanceService:
    def __init__(self, db: Database):
        self.db = db
        self._init_transactions_table()
    
    def _init_transactions_table(self):
        """Инициализация таблицы транзакций"""
        # Используем метод из Database вместо прямого подключения
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def get_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        try:
            result = self.db.fetchone(
                'SELECT balance FROM users WHERE user_id = ?', 
                (user_id,)
            )
            return float(result[0]) if result else 0.0
        except Exception as e:
            logger.error(f"Ошибка получения баланса {user_id}: {e}")
            return 0.0
    
    def get_referral_balance(self, user_id: int) -> float:
        """Получить реферальный баланс пользователя"""
        try:
            result = self.db.fetchone(
                'SELECT referral_balance FROM users WHERE user_id = ?', 
                (user_id,)
            )
            return float(result[0]) if result else 0.0
        except Exception as e:
            logger.error(f"Ошибка получения реферального баланса {user_id}: {e}")
            return 0.0
    
    def add_balance(self, user_id: int, amount: float, description: str = "Пополнение") -> bool:
        """Добавить баланс"""
        try:
            # Обновляем баланс
            self.db.execute(
                'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                (amount, user_id)
            )
            
            # Добавляем транзакцию
            self.db.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, "deposit", amount, description))
            
            logger.info(f"Баланс пользователя {user_id} пополнен на {amount}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка пополнения баланса {user_id}: {e}")
            return False
    
    def subtract_balance(self, user_id: int, amount: float, description: str = "Покупка") -> bool:
        """Списать баланс"""
        try:
            # Проверяем достаточно ли средств
            current_balance = self.get_balance(user_id)
            if current_balance < amount:
                logger.warning(f"Недостаточно средств у пользователя {user_id}: {current_balance} < {amount}")
                return False
            
            # Списание баланса
            self.db.execute(
                'UPDATE users SET balance = balance - ? WHERE user_id = ?',
                (amount, user_id)
            )
            
            # Добавляем транзакцию
            self.db.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, "purchase", -amount, description))
            
            logger.info(f"Списание баланса пользователя {user_id}: {amount}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка списания баланса {user_id}: {e}")
            return False
    
    def add_referral_balance(self, user_id: int, amount: float, description: str = "Реферальное вознаграждение") -> bool:
        """Добавить реферальный баланс"""
        try:
            # Обновляем реферальный баланс
            self.db.execute(
                'UPDATE users SET referral_balance = referral_balance + ? WHERE user_id = ?',
                (amount, user_id)
            )
            
            # Добавляем транзакцию
            self.db.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, "referral_bonus", amount, description))
            
            logger.info(f"Реферальный баланс пользователя {user_id} пополнен на {amount}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка пополнения реферального баланса {user_id}: {e}")
            return False
    
    def transfer_referral_to_main(self, user_id: int) -> Tuple[bool, float, float]:
        """
        Перевести реферальный баланс на основной с комиссией 10%
        Возвращает: (успех, сумма перевода, комиссия)
        """
        try:
            # Получаем текущий реферальный баланс
            ref_balance = self.get_referral_balance(user_id)
            
            if ref_balance <= 0:
                return False, 0.0, 0.0
            
            # Вычисляем комиссию 10%
            commission = ref_balance * 0.10
            amount_to_transfer = ref_balance - commission
            
            # Выполняем перевод
            self.db.execute(
                'UPDATE users SET balance = balance + ?, referral_balance = 0 WHERE user_id = ?',
                (amount_to_transfer, user_id)
            )
            
            # Добавляем запись в транзакции
            self.db.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, "referral_withdraw", amount_to_transfer, 
                  f"Вывод реферальных ${ref_balance:.2f} (комиссия ${commission:.2f})"))
            
            logger.info(f"Перевод реферального баланса пользователя {user_id}: {amount_to_transfer} (комиссия: {commission})")
            return True, amount_to_transfer, commission
            
        except Exception as e:
            logger.error(f"Ошибка перевода реферального баланса {user_id}: {e}")
            return False, 0.0, 0.0
    
    def can_purchase(self, user_id: int, price: float) -> bool:
        """Проверить возможность покупки"""
        return self.get_balance(user_id) >= price
    
    def get_transactions(self, user_id: int, limit: int = 10) -> List[Tuple]:
        """Получить историю транзакций"""
        try:
            return self.db.fetchall('''
                SELECT type, amount, description, created_at 
                FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
        except Exception as e:
            logger.error(f"Ошибка получения транзакций {user_id}: {e}")
            return []
    
    def get_total_income(self) -> float:
        """Получить общий доход системы"""
        try:
            result = self.db.fetchone('''
                SELECT SUM(amount) FROM transactions 
                WHERE type IN ('deposit', 'purchase') AND amount > 0
            ''')
            return float(result[0]) if result and result[0] else 0.0
        except Exception as e:
            logger.error(f"Ошибка получения общего дохода: {e}")
            return 0.0
    
    def get_user_transaction_stats(self, user_id: int) -> dict:
        """Получить статистику транзакций пользователя"""
        try:
            # Общее количество транзакций
            total_count = self.db.fetchone(
                'SELECT COUNT(*) FROM transactions WHERE user_id = ?', 
                (user_id,)
            )[0]
            
            # Сумма пополнений
            total_deposits = self.db.fetchone(
                'SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "deposit"', 
                (user_id,)
            )[0] or 0.0
            
            # Сумма покупок
            total_purchases = self.db.fetchone(
                'SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "purchase"', 
                (user_id,)
            )[0] or 0.0
            
            # Последняя транзакция
            last_transaction = self.db.fetchone('''
                SELECT type, amount, description, created_at 
                FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (user_id,))
            
            return {
                'total_count': total_count,
                'total_deposits': float(total_deposits),
                'total_purchases': float(abs(total_purchases)),
                'last_transaction': last_transaction
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики транзакций {user_id}: {e}")
            return {
                'total_count': 0,
                'total_deposits': 0.0,
                'total_purchases': 0.0,
                'last_transaction': None
            }
    
    def set_user_balance(self, user_id: int, new_balance: float) -> bool:
        """Установить точное значение баланса (для админ-панели)"""
        try:
            if new_balance < 0:
                logger.warning(f"Попытка установить отрицательный баланс для пользователя {user_id}")
                return False
            
            # Получаем старый баланс для логирования
            old_balance = self.get_balance(user_id)
            
            # Устанавливаем новый баланс
            self.db.execute(
                'UPDATE users SET balance = ? WHERE user_id = ?',
                (new_balance, user_id)
            )
            
            # Добавляем транзакцию для аудита
            self.db.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, "admin_set", new_balance - old_balance, 
                  f"Админ: установка баланса ${new_balance:.2f}"))
            
            logger.info(f"Баланс пользователя {user_id} установлен: {old_balance} -> {new_balance}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка установки баланса {user_id}: {e}")
            return False
    
    def get_system_balance_stats(self) -> dict:
        """Получить общую статистику по балансам системы"""
        try:
            # Общий баланс всех пользователей
            total_balance = self.db.fetchone('SELECT SUM(balance) FROM users')[0] or 0.0
            
            # Общий реферальный баланс
            total_referral_balance = self.db.fetchone('SELECT SUM(referral_balance) FROM users')[0] or 0.0
            
            # Количество пользователей с положительным балансом
            users_with_balance = self.db.fetchone('SELECT COUNT(*) FROM users WHERE balance > 0')[0]
            
            # Общее количество транзакций
            total_transactions = self.db.fetchone('SELECT COUNT(*) FROM transactions')[0]
            
            return {
                'total_balance': float(total_balance),
                'total_referral_balance': float(total_referral_balance),
                'users_with_balance': users_with_balance,
                'total_transactions': total_transactions
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения системной статистики: {e}")
            return {
                'total_balance': 0.0,
                'total_referral_balance': 0.0,
                'users_with_balance': 0,
                'total_transactions': 0
            }