from core.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_mixed_emails():
    db = Database("rabanok_bot.db")
    
    # Твои данные (первые 100 для примера)
    emails_data = {
        '-1982@gmail.com' : 'sanchous'
    }
    
    added = 0
    duplicates = 0
    errors = 0
    
    for email, password in emails_data.items():
        try:
            # Пропускаем пустые пароли
            if not password or password.strip() == '':
                logger.warning(f"⚠️ Пустой пароль: {email}")
                continue
                
            # Проверяем дубликаты
            existing = db.fetchone("SELECT 1 FROM admin_emails WHERE email = ?", (email,))
            if existing:
                logger.warning(f"⚠️ Дубликат: {email}")
                duplicates += 1
                continue
                
            # Добавляем в базу
            db.add_email(email, password.strip(), "active")
            logger.info(f"✅ Добавлена: {email}")
            added += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка {email}: {e}")
            errors += 1
    
    logger.info(f"🎉 Результат: Добавлено {added}, Дубликатов {duplicates}, Ошибок {errors}")

if __name__ == "__main__":
    add_mixed_emails()