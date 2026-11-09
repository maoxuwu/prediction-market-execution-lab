"""Offline sizing from displayed binary-contract asks. No orders or network access.

Supported inputs use at most 30 decimal places, monetary amounts up to 10**36
and share counts up to 10**18. Calculations use a private decimal context.
"""

from dataclasses import dataclass
from decimal import (
    Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow,
    localcontext,
)
from functools import wraps
from typing import Iterable


ZERO = Decimal("0")
ONE = Decimal("1")
MAX_MONEY = Decimal("1e36")
MAX_SHARES = 10**18
# A supported fee times the largest order spans at most 85 significant
# digits. The largest cash / smallest tick quotient fits in 67 digits.
_EXACT = Context(prec=96, traps=[InvalidOperation, DivisionByZero, Overflow, Inexact])


def _exact_calculation(function):
    @wraps(function)
    def calculate(*args, **kwargs):
        with localcontext(_EXACT):
            return function(*args, **kwargs)
    return calculate


def _amount(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} must be a finite, non-negative Decimal")
    if value > MAX_MONEY or value.as_tuple().exponent < -30:
        raise ValueError(f"{name} exceeds supported magnitude or decimal scale")


def _shares(value: int) -> None:
    if type(value) is not int or not 0 <= value <= MAX_SHARES:
        raise ValueError("share quantity must be an integer between 0 and 10**18")


@dataclass(frozen=True)
class Level:
    price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        _amount(self.price, "price")
        _shares(self.quantity)
        if self.price > ONE or self.quantity == 0:
            raise ValueError("a level requires price <= 1 and positive quantity")


@dataclass(frozen=True)
class Fill:
    """Price tiers taken in a hypothetical sweep, with a flat fee per share."""

    levels: tuple[Level, ...]
    fee_per_share: Decimal

    def __post_init__(self) -> None:
        _amount(self.fee_per_share, "fee_per_share")
        _shares(self.quantity)

    @property
    def quantity(self) -> int:
        return sum(level.quantity for level in self.levels)

    @property
    @_exact_calculation
    def principal(self) -> Decimal:
        return sum((level.price * level.quantity for level in self.levels), ZERO)

    @property
    @_exact_calculation
    def fees(self) -> Decimal:
        return self.fee_per_share * self.quantity

    @property
    @_exact_calculation
    def debit(self) -> Decimal:
        return self.principal + self.fees


def _affordable(available: int, unit_cost: Decimal, cash: Decimal) -> int:
    if unit_cost == ZERO:
        return available
    return min(available, int(cash // unit_cost))


@_exact_calculation
def sweep(
    asks: Iterable[Level],
    quantity: int,
    cash: Decimal,
    fee_per_share: Decimal = ZERO,
    *,
    limit_price: Decimal = ONE,
) -> Fill:
    """Walk asks cheapest first up to the share, cash and price limits."""
    _shares(quantity)
    _amount(cash, "cash")
    _amount(fee_per_share, "fee_per_share")
    _amount(limit_price, "limit_price")
    if limit_price > ONE:
        raise ValueError("limit_price must be <= 1")
    taken = []
    for level in sorted(asks, key=lambda item: item.price):
        if level.price > limit_price or quantity == 0:
            break
        all_in = level.price + fee_per_share
        shares = _affordable(min(quantity, level.quantity), all_in, cash)
        if shares == 0:
            break
        taken.append(Level(level.price, shares))
        cash -= shares * all_in
        quantity -= shares
    return Fill(tuple(taken), fee_per_share)


@dataclass(frozen=True)
class PairPlan:
    yes: Fill
    no: Fill

    @property
    def quantity(self) -> int:
        return self.yes.quantity

    @property
    @_exact_calculation
    def debit(self) -> Decimal:
        return self.yes.debit + self.no.debit


@_exact_calculation
def plan_pair(
    yes_asks: Iterable[Level],
    no_asks: Iterable[Level],
    quantity: int,
    cash: Decimal,
    fee_per_share: Decimal = ZERO,
    max_pair_debit: Decimal = ONE,
) -> PairPlan:
    """Size equal legs against one wallet and an all-in marginal price per pair.

    Both displayed books are assumed available for this calculation. A caller
    simulating sequential orders must sweep each leg against its own snapshot.
    """
    _shares(quantity)
    _amount(cash, "cash")
    _amount(fee_per_share, "fee_per_share")
    _amount(max_pair_debit, "max_pair_debit")
    yes = iter(sorted(yes_asks, key=lambda item: item.price))
    no = iter(sorted(no_asks, key=lambda item: item.price))
    y, n = next(yes, None), next(no, None)
    used_y = used_n = 0
    yes_taken, no_taken = [], []
    while quantity and y is not None and n is not None:
        pair_cost = y.price + n.price + 2 * fee_per_share
        if pair_cost > max_pair_debit:
            break
        available = min(quantity, y.quantity - used_y, n.quantity - used_n)
        shares = _affordable(available, pair_cost, cash)
        if shares == 0:
            break
        yes_taken.append(Level(y.price, shares))
        no_taken.append(Level(n.price, shares))
        cash -= shares * pair_cost
        quantity -= shares
        used_y += shares
        used_n += shares
        if used_y == y.quantity:
            y, used_y = next(yes, None), 0
        if used_n == n.quantity:
            n, used_n = next(no, None), 0
    return PairPlan(Fill(tuple(yes_taken), fee_per_share),
                    Fill(tuple(no_taken), fee_per_share))


@dataclass(frozen=True)
class Settlement:
    matched_quantity: int
    yes_unmatched: int
    no_unmatched: int
    pnl_if_yes: Decimal
    pnl_if_no: Decimal


@_exact_calculation
def settlement(yes_fill: Fill, no_fill: Fill) -> Settlement:
    """Evaluate purchased quantities under complementary unit-payout outcomes.

    This assumes precisely one side pays 1 and a losing share pays 0. It
    excludes voids, settlement fees and interest, and assumes no early sale.
    """
    yes, no = yes_fill.quantity, no_fill.quantity
    matched = min(yes, no)
    total_cost = yes_fill.debit + no_fill.debit
    return Settlement(matched, yes - matched, no - matched,
                      Decimal(yes) - total_cost, Decimal(no) - total_cost)
