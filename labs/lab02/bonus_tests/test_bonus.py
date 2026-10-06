import pytest
from decimal import Decimal
from datetime import date, datetime, timezone, timedelta
from app import api
from app.support.errors import DomainError
from app.support.types import Repository, CheckResult, Money, money


def error(code, operation):
    with pytest.raises(DomainError) as caught:
        operation()
    assert caught.value.code == code


def invoke(service, method, *args, **kwargs):
    return api.call(service, method, *args, **kwargs)

def test_repeat_close_preserves_snapshot():
    from app.domain.clearing import ClearingBatch
    from app.support.types import ClearingTransaction
    batch=ClearingBatch("B1","EUR")
    batch.add_transaction(ClearingTransaction("T1","M1",money("1"),"APPROVED"))
    batch.close()
    error("INVALID_STATE",batch.close)
    assert batch.status=="CLOSED" and batch.total()==money("1")
