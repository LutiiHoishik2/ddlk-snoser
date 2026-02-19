import smtplib
import asyncio

async def check_email_smtp(email, password):
    """Протестировать одну почту"""
    print(f"\n🔍 Тестируем {email}")
    
    try:
        domain = email.split('@')[1].lower()
        
        if 'gmail' in domain:
            server, port = 'smtp.gmail.com', 587
        elif 'mail.ru' in domain:
            server, port = 'smtp.mail.ru', 587
        elif 'yandex' in domain:
            server, port = 'smtp.yandex.ru', 587
        else:
            server, port = 'smtp.gmail.com', 587
        
        with smtplib.SMTP(server, port, timeout=10) as smtp:
            print(f"  Подключаюсь к {server}:{port}...")
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            print(f"  Пытаюсь войти...")
            smtp.login(email, password)
            print(f"  ✅ Успешно! {email} валидна")
            return True
            
    except smtplib.SMTPAuthenticationError:
        print(f"  ❌ Ошибка аутентификации: неверный пароль")
        return False
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

async def main():
    print("📧 ТЕСТИРОВАНИЕ SMTP ПОЧТ")
    print("=" * 50)
    
    # Тестовые данные - ЗАМЕНИТЕ НА СВОИ
    test_accounts = [
        {"email": "dqum3220@gmail.com", "password": "5656yuij13"},
    ]
    
    valid_count = 0
    for account in test_accounts:
        if await check_email_smtp(account["email"], account["password"]):
            valid_count += 1
    
    print(f"\n{'='*50}")
    print(f"📊 РЕЗУЛЬТАТ: {valid_count}/{len(test_accounts)} валидных")

if __name__ == "__main__":
    asyncio.run(main())