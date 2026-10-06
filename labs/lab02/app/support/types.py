from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from app.support.errors import DomainError
from app.support.money import Money, money, currency, decimal_value, rounded_money, total_money


def identifier(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise DomainError("INVALID_ID")
    return value


def name(value):
    if not isinstance(value, str) or not value.strip():
        raise DomainError("INVALID_NAME")
    return value.strip()


def country(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Z]{2}", value) is None:
        raise DomainError("INVALID_COUNTRY")
    return value


def choice(value, values, code="INVALID_CONTEXT"):
    if value not in values:
        raise DomainError(code)
    return value


def boolean(value):
    if type(value) is not bool:
        raise DomainError("INVALID_CONTEXT")
    return value


def utc_seconds(value):
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0) or value.microsecond != 0):
        raise DomainError("INVALID_TIMESTAMP")
    return value


def date_only(value):
    if type(value) is not date:
        raise DomainError("INVALID_CONTEXT")
    return value


def positive(amount):
    if not isinstance(amount, Money) or amount.amount <= 0:
        raise DomainError("INVALID_AMOUNT")
    return amount


def result_code(value):
    if not isinstance(value, str) or not value.strip():
        raise DomainError("INVALID_CONFIG")
    return value


@dataclass(frozen=True)
class CheckResult:
    allowed: bool
    code: str | None = None

    def __post_init__(self):
        if type(self.allowed) is not bool:
            raise DomainError("INVALID_RESULT")
        if self.allowed and self.code is not None:
            raise DomainError("INVALID_RESULT")
        if not self.allowed and (not isinstance(self.code, str) or not self.code.strip()):
            raise DomainError("INVALID_RESULT")


def checked(result):
    if not isinstance(result, CheckResult):
        raise DomainError("INVALID_RESULT")
    return result


class Repository:
    """Готовое in-memory хранилище. Дубликат никогда не перезаписывает данные."""

    def __init__(self, key, duplicate_code="DUPLICATE_ID"):
        self._key = key
        self._duplicate_code = duplicate_code
        self._items = {}

    def add(self, item):
        key = item[self._key] if isinstance(item, dict) else getattr(item, self._key)
        if key in self._items:
            raise DomainError(self._duplicate_code)
        self._items[key] = item
        return item

    def get(self, key):
        if key not in self._items:
            raise DomainError("NOT_FOUND")
        return self._items[key]

    def all(self):
        return tuple(self._items.values())

@dataclass(frozen=True)
class ClearingTransaction:
    transaction_id: str
    merchant_id: str
    amount: Money
    status: str

    def __post_init__(self):
        identifier(self.transaction_id)
        identifier(self.merchant_id)
        positive(self.amount)
        choice(self.status,("APPROVED","DECLINED"),"INVALID_STATUS")


@dataclass(frozen=True)
class BatchSnapshot:
    batch_id: str
    currency: str
    status: str
    transactions: tuple
    total: Money

    def __post_init__(self):
        object.__setattr__(self,"transactions",tuple(self.transactions))


def batch_snapshot(batch):
    if isinstance(batch,dict):
        items=tuple(batch["transactions"])
        return BatchSnapshot(batch["batch_id"],batch["currency"],batch["status"],items,
                             total_money((tx.amount for tx in items),batch["currency"]))
    return BatchSnapshot(batch.batch_id,batch.currency,batch.status,batch.transactions,batch.total())


def ensure_unassigned(repository,transaction_id):
    for batch in repository.all():
        items=batch["transactions"] if isinstance(batch,dict) else batch.transactions
        if any(tx.transaction_id==transaction_id for tx in items):
            raise DomainError("DUPLICATE_TRANSACTION")


def totals_by_merchant(items,code):
    result={}
    for tx in items:
        result[tx.merchant_id]=result.get(tx.merchant_id,money("0",code)).add(tx.amount)
    return result
