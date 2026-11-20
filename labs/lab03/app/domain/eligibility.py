from abc import ABC, abstractmethod

from app.support.errors import DomainError
from app.support.types import CheckResult, Money


class ClearingEligibilityRule(ABC):
    @abstractmethod
    def check(self, batch, tx):
        raise NotImplementedError


class MaximumBatchCountRule(ClearingEligibilityRule):
    def __init__(self, maximum):
        if type(maximum) is not int or maximum < 1:
            raise DomainError("INVALID_CONFIG")
        self._maximum = maximum

    def check(self, batch, tx):
        if len(batch.transactions) + 1 > self._maximum:
            return CheckResult(False, "BATCH_COUNT_LIMIT")
        return CheckResult(True)


class MaximumBatchAmountRule(ClearingEligibilityRule):
    def __init__(self, maximum):
        if not isinstance(maximum, Money):
            raise DomainError("INVALID_CONFIG")
        self._maximum = maximum

    def check(self, batch, tx):
        tx.amount.same_currency(self._maximum)
        prospective_total = batch.total().add(tx.amount)
        if prospective_total.amount > self._maximum.amount:
            return CheckResult(False, "BATCH_AMOUNT_LIMIT")
        return CheckResult(True)
