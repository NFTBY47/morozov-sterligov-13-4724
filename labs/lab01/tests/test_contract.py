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

from app.support.types import ClearingTransaction,BatchSnapshot

def transaction(key="T1",amount="10",merchant="M1",status="APPROVED",code="EUR"):
    return ClearingTransaction(key,merchant,money(amount,code),status)

def prepared():
    service=api.create()
    invoke(service,"create_batch","B1","EUR")
    return service

def test_batch_sum_snapshot_and_isolation():
    service=prepared()
    empty=invoke(service,"get_batch","B1")
    assert empty.total==money("0") and empty.transactions==()
    first,second=transaction(),transaction("T2","20")
    invoke(service,"add","B1",first)
    snapshot=invoke(service,"add","B1",second)
    assert snapshot.total==money("30") and snapshot.transactions==(first,second)
    assert invoke(service,"get_batch","B1")==snapshot
    assert invoke(service,"create_batch","B2","EUR").transactions==()
    assert empty.transactions==()
    with pytest.raises((AttributeError,TypeError)):snapshot.status="CLOSED"

def test_new_repository_empty():
    prepared()
    error("NOT_FOUND",lambda:invoke(api.create(),"get_batch","B1"))
