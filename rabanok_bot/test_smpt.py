import asyncio
import os
import smtplib
from typing import Tuple


def resolve_smtp_endpoint(email: str) -> Tuple[str, int]:
    """Вернуть SMTP сервер и порт по email домену."""
    try:
        domain = email.split("@", 1)[1].lower()
    except IndexError as exc:
        raise ValueError(f"Некорректный email: {email}") from exc

    providers = {
        "gmail": ("smtp.gmail.com", 587),
        "mail.ru": ("smtp.mail.ru", 587),
        "yandex": ("smtp.yandex.ru", 587),
    }

    for marker, endpoint in providers.items():
        if marker in domain:
            return endpoint

    return "smtp.gmail.com", 587


async def check_email_smtp(email: str, password: str) -> bool:
    """Протестировать одну почту."""
    print(f"\n🔍 Тестируем {email}")

    try:
        server, port = resolve_smtp_endpoint(email)

        with smtplib.SMTP(server, port, timeout=10) as smtp:
            print(f"  Подключаюсь к {server}:{port}...")
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            print("  Пытаюсь войти...")
            smtp.login(email, password)
            print(f"  ✅ Успешно! {email} валидна")
            return True

    except smtplib.SMTPAuthenticationError:
        print("  ❌ Ошибка аутентификации: неверный пароль")
        return False
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


async def main() -> None:
    print("📧 ТЕСТИРОВАНИЕ SMTP ПОЧТ")
    print("=" * 50)

    email = os.getenv("SMTP_TEST_EMAIL")
    password = os.getenv("SMTP_TEST_PASSWORD")

    if not email or not password:
        print("⚠️ Для запуска задайте SMTP_TEST_EMAIL и SMTP_TEST_PASSWORD")
        return

    is_valid = await check_email_smtp(email, password)
    print(f"\n{'=' * 50}")
    print(f"📊 РЕЗУЛЬТАТ: {'валидна' if is_valid else 'невалидна'}")


if __name__ == "__main__":
    asyncio.run(main())
