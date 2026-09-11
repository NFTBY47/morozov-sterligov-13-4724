# ЛР1: поля, конструктор и служебные проверки даны преподавателем.
# Завершите отмеченные методы; API пока использует старые функции.
from app.support.types import identifier,currency,total_money,ClearingTransaction
from app.support.errors import DomainError


class ClearingBatch:
    def __init__(self,batch_id,code):
        self._batch_id=identifier(batch_id)
        self._currency=currency(code)
        self._status="OPEN"
        self._transactions=[]

    @property
    def batch_id(self):return self._batch_id

    @property
    def currency(self):return self._currency

    @property
    def status(self):return self._status

    @property
    def transactions(self):return tuple(self._transactions)

    @property
    def transaction_count(self):return len(self._transactions)

    def validate_add(self,tx):
        if self.status!="OPEN":
            raise DomainError("BATCH_CLOSED")
        if not isinstance(tx,ClearingTransaction):
            raise DomainError("INVALID_CONTEXT")
        if tx.status!="APPROVED":
            raise DomainError("TRANSACTION_NOT_APPROVED")
        if tx.amount.currency!=self.currency:
            raise DomainError("CURRENCY_MISMATCH")
        if any(item.transaction_id==tx.transaction_id for item in self.transactions):
            raise DomainError("DUPLICATE_TRANSACTION")

    def add_transaction(self,tx):
        self.validate_add(tx)
        self._transactions.append(tx)


    def total(self):
        return total_money((tx.amount for tx in self.transactions), self.currency)

    def close(self):
        if self.status!="OPEN":
            raise DomainError("INVALID_STATE")
        if not self.transactions:
            raise DomainError("EMPTY_BATCH")
        self._status="CLOSED"
