from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from app.support.errors import DomainError


def currency(value):
    if value not in ("EUR", "USD"):
        raise DomainError("INVALID_CURRENCY")
    return value


def decimal_value(value, code="INVALID_AMOUNT"):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise DomainError(code)
    return value


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "EUR"

    def __post_init__(self):
        currency(self.currency)
        decimal_value(self.amount)
        if self.amount < 0:
            raise DomainError("INVALID_AMOUNT")
        try:
            with localcontext() as ctx:
                ctx.prec = 28
                normalized = self.amount.quantize(Decimal("0.01"))
        except InvalidOperation as error:
            raise DomainError("INVALID_AMOUNT") from error
        if normalized != self.amount:
            raise DomainError("INVALID_AMOUNT")
        object.__setattr__(self, "amount", abs(normalized) if normalized == 0 else normalized)

    def same_currency(self, other):
        if not isinstance(other, Money) or self.currency != other.currency:
            raise DomainError("CURRENCY_MISMATCH")

    def add(self, other):
        self.same_currency(other)
        with localcontext() as ctx:
            ctx.prec = 28
            return Money(self.amount + other.amount, self.currency)

    def subtract(self, other):
        self.same_currency(other)
        with localcontext() as ctx:
            ctx.prec = 28
            return Money(self.amount - other.amount, self.currency)

    def __str__(self):
        return f"{self.amount:.2f} {self.currency}"


def money(text, code="EUR"):
    if not isinstance(text, str):
        raise DomainError("INVALID_AMOUNT")
    try:
        return Money(Decimal(text), code)
    except InvalidOperation as error:
        raise DomainError("INVALID_AMOUNT") from error


def rounded_money(value, code):
    decimal_value(value)
    with localcontext() as ctx:
        ctx.prec = 28
        return Money(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), code)


def total_money(values, code):
    result = money("0", code)
    for item in values:
        result = result.add(item)
    return result
