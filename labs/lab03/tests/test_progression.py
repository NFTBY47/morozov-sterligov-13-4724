import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from app import api
from app.support.errors import DomainError


def code(expected, operation):
    with pytest.raises(DomainError) as caught:
        operation()
    assert caught.value.code == expected

from app.support.types import ClearingTransaction, money

def test_progression_failed_add_does_not_reserve_id_or_change_snapshot():
    service = api.create()
    service.create_batch("B", "EUR")
    first = service.add("B", ClearingTransaction("T1", "M", money("20"), "APPROVED"))
    code("BATCH_AMOUNT_LIMIT", lambda: service.add("B", ClearingTransaction("T2", "M", money("101"), "APPROVED")))
    assert service.get_batch("B") == first
    after = service.add("B", ClearingTransaction("T2", "M", money("30"), "APPROVED"))
    assert len(after.transactions) == 2 and len(first.transactions) == 1
