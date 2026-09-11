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

def test_description():
    from app.domain.clearing import ClearingBatch
    from app.support.types import ClearingTransaction
    batch=ClearingBatch("B1","EUR")
    for key in ("T1","T2"):batch.add_transaction(ClearingTransaction(key,"M1",money("1"),"APPROVED"))
    assert batch.describe()=="B1:OPEN:2 transactions"
