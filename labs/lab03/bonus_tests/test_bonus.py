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

def test_custom_refusal_code():
    from app.domain.clearing import ClearingBatch
    from app.domain.eligibility import MaximumBatchCountRule
    from app.support.types import ClearingTransaction
    batch=ClearingBatch("B","EUR")
    tx=ClearingTransaction("T1","M1",money("1"),"APPROVED")
    batch.add_transaction(tx)
    assert MaximumBatchCountRule(1,code="CUSTOM").check(batch,tx).code=="CUSTOM"
