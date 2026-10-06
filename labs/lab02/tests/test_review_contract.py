import pytest
from decimal import Decimal
from datetime import date, datetime, timezone, timedelta
from app import api
from app.support.errors import DomainError


def assert_code(code, action):
    with pytest.raises(DomainError) as caught:
        action()
    assert caught.value.code == code

from app.support.types import money

def test_review_repeat_close_is_rejected_without_changes():
    from app.domain.clearing import ClearingBatch
    from app.support.types import ClearingTransaction
    item=ClearingBatch("B","EUR")
    item.add_transaction(ClearingTransaction("T","M",money("1"),"APPROVED"))
    item.close()
    before=api.view(item)
    assert_code("INVALID_STATE",item.close)
    assert api.view(item) == before
