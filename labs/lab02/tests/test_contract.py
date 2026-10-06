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

from app.domain.clearing import ClearingBatch

def test_local_closed_and_duplicate_guards():
    batch=ClearingBatch("B1","EUR")
    tx=transaction()
    batch.add_transaction(tx)
    error("DUPLICATE_TRANSACTION",lambda:batch.add_transaction(tx))
    batch.close()
    error("BATCH_CLOSED",lambda:batch.add_transaction(transaction("T2")))
    assert batch.transactions==(tx,) and batch.total()==money("10")

def test_local_currency_and_declined_guards():
    batch=ClearingBatch("B1","EUR")
    error("CURRENCY_MISMATCH",lambda:batch.add_transaction(transaction(code="USD")))
    error("TRANSACTION_NOT_APPROVED",lambda:batch.add_transaction(transaction(status="DECLINED")))
    assert batch.transactions==()
    error("EMPTY_BATCH",batch.close)

def test_global_duplicate_and_failure_does_not_reserve_id():
    service=prepared()
    invoke(service,"create_batch","B2","EUR")
    bad=transaction(status="DECLINED")
    error("TRANSACTION_NOT_APPROVED",lambda:service.add("B1",bad))
    service.add("B2",transaction())
    error("DUPLICATE_TRANSACTION",lambda:service.add("B1",transaction()))
    assert service.get_batch("B1").transactions==()
