import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "rabanok_bot"))

from test_smpt import resolve_smtp_endpoint


def test_resolve_gmail_endpoint():
    assert resolve_smtp_endpoint("user@gmail.com") == ("smtp.gmail.com", 587)


def test_resolve_mail_ru_endpoint():
    assert resolve_smtp_endpoint("user@mail.ru") == ("smtp.mail.ru", 587)


def test_resolve_unknown_provider_fallback():
    assert resolve_smtp_endpoint("user@example.com") == ("smtp.gmail.com", 587)
