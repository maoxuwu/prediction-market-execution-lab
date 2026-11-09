"""In-memory replay of confirmed binary-contract fills in one prefunded wallet.

Each matched YES/NO pair redeems one unit immediately. Settlement pays one unit
per winning share. Prices, cash and fees support up to six decimal places.
"""

from dataclasses import dataclass
from decimal import Decimal


SCALE = 1_000_000


def _units(value):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ValueError("money must be a Decimal or integer")
    value = Decimal(value)
    if not value.is_finite() or value < 0:
        raise ValueError("money must be finite and nonnegative")
    numerator, denominator = value.as_integer_ratio()
    units, remainder = divmod(numerator * SCALE, denominator)
    if remainder:
        raise ValueError("money supports at most six decimal places")
    return units


def _money(units):
    return Decimal(f"{units}e-6")


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty identifier")


def _side(value):
    if value not in ("YES", "NO"):
        raise ValueError("expected YES or NO")


@dataclass(frozen=True)
class Fill:
    """One confirmed buy at one price. Fee is the total for the entire fill."""

    fill_id: str
    market: str
    side: str
    quantity: int
    price: Decimal
    fee: Decimal = Decimal(0)

    def __post_init__(self):
        _name(self.fill_id)
        _name(self.market)
        _side(self.side)
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        if _units(self.price) > SCALE:
            raise ValueError("binary price exceeds one")
        _units(self.fee)

    def _cost(self, start, stop):
        """Cost of shares [start, stop), with rounding remainder retained."""
        fees = _units(self.fee)
        fee_part = (fees * stop // self.quantity) - (fees * start // self.quantity)
        return (stop - start) * _units(self.price) + fee_part


@dataclass(frozen=True)
class Lot:
    """The open suffix of a fill. Shares before 'start' have been offset."""

    fill: Fill
    start: int

    @property
    def quantity(self):
        return self.fill.quantity - self.start

    @property
    def cost(self):
        return _money(self.fill._cost(self.start, self.fill.quantity))


class Ledger:
    """Events are supplied in execution order. Replaying an exact fill is safe."""

    def __init__(self, initial_cash):
        self._opening = self._cash = _units(initial_cash)
        self._realized = self._fees = 0
        self._seen = {}
        self._positions = {}
        self._outcomes = {}

    @property
    def initial_cash(self):
        return _money(self._opening)

    @property
    def cash(self):
        return _money(self._cash)

    @property
    def realized_pnl(self):
        return _money(self._realized)

    @property
    def total_fees(self):
        return _money(self._fees)

    @property
    def remaining_cost(self):
        units = sum(
            lot.fill._cost(lot.start, lot.fill.quantity)
            for lots in self._positions.values() for lot in lots
        )
        return _money(units)

    def lots(self, market):
        """Read-only view of the remaining FIFO lots."""
        return self._positions.get(market, ())

    def position(self, market):
        """Number of net open YES shares. A NO position has a negative sign."""
        return sum(lot.quantity if lot.fill.side == "YES" else -lot.quantity
                   for lot in self.lots(market))

    def apply(self, fill):
        """Apply one fill. Require the entire debit in cash before pair redemption."""
        if not isinstance(fill, Fill):
            raise ValueError("expected a confirmed Fill")
        if fill.fill_id in self._seen:
            if self._seen[fill.fill_id] != fill:
                raise ValueError("conflicting event for fill ID")
            return False
        if fill.market in self._outcomes:
            raise ValueError("market is settled")
        debit = fill._cost(0, fill.quantity)
        if debit > self._cash:
            raise ValueError("insufficient cash to prefund fill")

        matched = old_cost = 0
        remaining = []
        for lot in self.lots(fill.market):
            if lot.fill.side == fill.side or matched == fill.quantity:
                remaining.append(lot)
                continue
            count = min(lot.quantity, fill.quantity - matched)
            stop = lot.start + count
            old_cost += lot.fill._cost(lot.start, stop)
            matched += count
            if count < lot.quantity:
                remaining.append(Lot(lot.fill, stop))
        if matched < fill.quantity:
            remaining.append(Lot(fill, matched))

        proceeds = matched * SCALE
        self._cash += proceeds - debit
        self._realized += proceeds - old_cost - fill._cost(0, matched)
        self._fees += _units(fill.fee)
        self._positions[fill.market] = tuple(remaining)
        self._seen[fill.fill_id] = fill
        return True

    def settle(self, market, winner):
        """Redeem remaining winning shares and recognise the full remaining basis."""
        _name(market)
        _side(winner)
        if market in self._outcomes:
            if self._outcomes[market] != winner:
                raise ValueError("conflicting settlement")
            return False
        lots = self.lots(market)
        payout = sum(lot.quantity * SCALE for lot in lots if lot.fill.side == winner)
        basis = sum(lot.fill._cost(lot.start, lot.fill.quantity) for lot in lots)
        self._cash += payout
        self._realized += payout - basis
        self._positions.pop(market, None)
        self._outcomes[market] = winner
        return True
