from app import api
from app.support.errors import DomainError
from app.support.types import money
from decimal import Decimal
import pytest

def error(code, action):
    with pytest.raises(DomainError) as exc:
        action()
    assert exc.value.code == code

from app.domain.clearing import ClearingBatch
from app.support.types import ClearingTransaction

def removable_batch():
    batch = ClearingBatch("B", "EUR")
    assert hasattr(batch, "remove_transaction"), "Реализуйте бонусное удаление из OPEN-пакета"
    transactions = [ClearingTransaction("T1", "M", money("10"), "APPROVED"),
                    ClearingTransaction("T2", "M", money("20"), "APPROVED"),
                    ClearingTransaction("T3", "M", money("30"), "APPROVED")]
    for tx in transactions: batch.add_transaction(tx)
    return batch, transactions

def test_bonus_remove_preserves_remaining_order_and_total():
    batch, items = removable_batch()
    assert batch.remove_transaction("T2") is items[1]
    assert batch.transactions == (items[0], items[2])
    assert batch.total() == money("40")
    batch.add_transaction(items[1])  # Удалённый ID не остаётся занятым в этом пакете.
    assert batch.transactions == (items[0], items[2], items[1])

def test_bonus_remove_unknown_or_closed_is_atomic():
    batch, items = removable_batch()
    error("NOT_FOUND", lambda: batch.remove_transaction("UNKNOWN"))
    assert batch.transactions == tuple(items) and batch.total() == money("60")
    batch.close()
    error("BATCH_CLOSED", lambda: batch.remove_transaction("T1"))
    error("BATCH_CLOSED", lambda: batch.remove_transaction("UNKNOWN"))
    assert batch.transactions == tuple(items) and batch.status == "CLOSED"

def test_bonus_remove_last_makes_batch_empty():
    batch, items = removable_batch()
    for tx in items: batch.remove_transaction(tx.transaction_id)
    assert batch.transactions == () and batch.total() == money("0")
    error("EMPTY_BATCH", batch.close)
    assert batch.status == "OPEN"
