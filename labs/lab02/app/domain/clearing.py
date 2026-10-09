from app.support.errors import DomainError
from app.support.money import Money, currency, total_money
from app.support.types import ClearingTransaction, identifier


class ClearingBatch:
    """Пакет, контролирующий допустимость изменения своего состава."""

    def __init__(self, batch_id: str, code: str) -> None:
        self._batch_id = identifier(batch_id)
        self._currency = currency(code)
        self._status = "OPEN"
        self._transactions: list[ClearingTransaction] = []

    @property
    def batch_id(self) -> str:
        return self._batch_id

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def status(self) -> str:
        return self._status

    @property
    def transactions(self) -> tuple[ClearingTransaction, ...]:
        return tuple(self._transactions)

    @property
    def transaction_count(self) -> int:
        return len(self._transactions)

    def validate_add(self, tx: ClearingTransaction) -> None:
        """Проверить условия добавления без изменения состояния пакета."""
        if self.status != "OPEN":
            raise DomainError("BATCH_CLOSED")
        if not isinstance(tx, ClearingTransaction):
            raise DomainError("INVALID_CONTEXT")
        if tx.status != "APPROVED":
            raise DomainError("TRANSACTION_NOT_APPROVED")
        if tx.amount.currency != self.currency:
            raise DomainError("CURRENCY_MISMATCH")
        if any(item.transaction_id == tx.transaction_id for item in self._transactions):
            raise DomainError("DUPLICATE_TRANSACTION")

    def add_transaction(self, tx: ClearingTransaction) -> None:
        self.validate_add(tx)
        self._transactions.append(tx)

    def total(self) -> Money:
        return total_money((tx.amount for tx in self.transactions), self.currency)

    def close(self) -> None:
        if self.status != "OPEN":
            raise DomainError("INVALID_STATE")
        if not self.transactions:
            raise DomainError("EMPTY_BATCH")
        self._status = "CLOSED"

    def remove_transaction(self, transaction_id: str) -> ClearingTransaction:
        """Remove an operation from an open batch without reordering the others."""
        if self.status != "OPEN":
            raise DomainError("BATCH_CLOSED")
        for index, tx in enumerate(self._transactions):
            if tx.transaction_id == transaction_id:
                return self._transactions.pop(index)
        raise DomainError("NOT_FOUND")
