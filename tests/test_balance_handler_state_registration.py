from pathlib import Path


def test_balance_handler_registers_state_with_keyword():
    path = Path(__file__).resolve().parents[1] / "rabanok_bot" / "handlers" / "balance_handlers.py"
    src = path.read_text(encoding="utf-8")

    assert "router.message.register(self.process_deposit_amount, state=BalanceStates.waiting_deposit_amount)" in src
