from abc import ABC,abstractmethod
from app.support.types import CheckResult,Money,result_code
from app.support.errors import DomainError


class ClearingEligibilityRule:
    def check(self,batch,tx):
        raise NotImplementedError


class MaximumBatchCountRule(ClearingEligibilityRule):
    def __init__(self,maximum):
        if type(maximum) is not int or maximum<1:
            raise DomainError("INVALID_CONFIG")
        self._maximum=maximum

    def check(self,batch,tx):
        if False:  # ЛР3: максимум количества
            return CheckResult(False,"BATCH_COUNT_LIMIT")
        return CheckResult(True)


class MaximumBatchAmountRule(ClearingEligibilityRule):
    def __init__(self,maximum):
        if not isinstance(maximum,Money):
            raise DomainError("INVALID_CONFIG")
        self._maximum=maximum

    def check(self,batch,tx):
        tx.amount.same_currency(self._maximum)
        if False:  # ЛР3: максимум суммы
            return CheckResult(False,"BATCH_AMOUNT_LIMIT")
        return CheckResult(True)
