import pytest
pytest.importorskip("aiohttp")

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "rabanok_bot"))

from services.stars_payment_service import StarsPaymentService


class DummyConfig:
    BOT_TOKEN = "123:abc"
    PAYMENT_PROVIDER_TOKEN = "provider-token"
    SUBSCRIPTION_PLANS = {"basic_1": {"name": "Basic", "days": 30}}


class DummyDB:
    def __init__(self):
        self.invoice = {
            "invoice_id": "inv1",
            "user_id": 1,
            "product_id": "basic_1",
            "stars_amount": 500,
            "status": "created",
        }
        self.status = None
        self.balance_updates = []

    def get_invoice_by_id(self, invoice_id):
        return self.invoice if invoice_id == self.invoice["invoice_id"] else None

    def update_invoice_status(self, invoice_id, status):
        self.status = (invoice_id, status)

    def update_user_balance(self, user_id, amount):
        self.balance_updates.append((user_id, amount))

    def update_user_subscription(self, **kwargs):
        return True


class DummyBot:
    async def send_message(self, *args, **kwargs):
        return None


def test_signed_payload_roundtrip():
    svc = StarsPaymentService(DummyBot(), DummyDB(), DummyConfig())
    signed = svc._build_payload(user_id=1, product_id="basic_1", stars_amount=500, invoice_id="inv1")
    parsed = svc._parse_signed_payload(signed)

    assert parsed is not None
    assert parsed["invoice_id"] == "inv1"
    assert parsed["product_id"] == "basic_1"



@pytest.mark.asyncio
async def test_webhook_uses_signed_invoice_id_and_updates_balance():
    db = DummyDB()
    svc = StarsPaymentService(DummyBot(), db, DummyConfig())

    called = {}

    async def fake_answer(pre_checkout_query_id, ok):
        called["id"] = pre_checkout_query_id
        called["ok"] = ok

    svc._answer_pre_checkout_query = fake_answer

    signed_payload = svc._build_payload(user_id=1, product_id="basic_1", stars_amount=500, invoice_id="inv1")
    update = {
        "pre_checkout_query": {
            "id": "pcq-1",
            "invoice_payload": signed_payload,
            "from": {"id": 1},
            "total_amount": 50000,
        }
    }

    ok, _ = await svc.process_stars_payment_webhook(update)

    assert ok is True
    assert called == {"id": "pcq-1", "ok": True}
    assert db.status == ("inv1", "paid")
    assert db.balance_updates == [(1, 5.0)]
