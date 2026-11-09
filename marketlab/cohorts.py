"""Estimate fixed-horizon exits from an observed inventory flow.

Each stream identifies fungible inventory, such as a contract and side.
Quantities are filled units. Time is elapsed calendar seconds on the input
clock, including intervals when the trader was offline.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable


def _nonnegative_integer(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True)
class Flow:
    second: int
    stream: str
    kind: str
    quantity: int

    def __post_init__(self) -> None:
        _nonnegative_integer(self.second, "second")
        if not isinstance(self.stream, str) or not self.stream.strip():
            raise ValueError("a non-blank inventory stream is required")
        if self.kind not in ("entry", "normal", "repair"):
            raise ValueError(f"unknown flow kind: {self.kind}")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("quantity must be a positive integer")


@dataclass(frozen=True)
class ExitAllocation:
    second: int
    kind: str
    quantity: int


@dataclass(frozen=True)
class Cohort:
    entry: Flow
    exits: tuple[ExitAllocation, ...]


@dataclass(frozen=True)
class CohortReport:
    cohorts: tuple[Cohort, ...]
    mature_quantity: int
    normal_by_horizon: int
    repair_by_horizon: int
    too_young_quantity: int

    @property
    def unexited_by_horizon(self) -> int:
        return self.mature_quantity - self.normal_by_horizon - self.repair_by_horizon

    @property
    def normal_exit_fraction(self) -> Fraction | None:
        if self.mature_quantity == 0:
            return None
        return Fraction(self.normal_by_horizon, self.mature_quantity)


@dataclass
class _Lot:
    entry: Flow
    remaining: int
    exits: list[ExitAllocation] = field(default_factory=list)


def analyse(events: Iterable[Flow], *, as_of: int, horizon: int) -> CohortReport:
    """Allocate observed exits FIFO, then score all sufficiently old entries.

    Supply events in observation order, using receipt order to break ties.
    Only records through `as_of` are visible. The horizon endpoint is
    inclusive. Young entries are reported separately, even if they exited
    early. Repairs count toward their own column in the mature denominator.
    """
    _nonnegative_integer(as_of, "as_of")
    _nonnegative_integer(horizon, "horizon")
    open_lots = defaultdict(deque)
    lots = []
    previous_second = -1
    for flow in events:
        if flow.second > as_of:
            continue
        if flow.second < previous_second:
            raise ValueError("visible flows must be in chronological receipt order")
        previous_second = flow.second
        stream_lots = open_lots[flow.stream]
        if flow.kind == "entry":
            lot = _Lot(flow, flow.quantity)
            lots.append(lot)
            stream_lots.append(lot)
            continue
        quantity = flow.quantity
        while quantity:
            if not stream_lots:
                raise ValueError(f"exit exceeds observed inventory in {flow.stream}")
            lot = stream_lots[0]
            taken = min(quantity, lot.remaining)
            lot.exits.append(ExitAllocation(flow.second, flow.kind, taken))
            lot.remaining -= taken
            quantity -= taken
            if lot.remaining == 0:
                stream_lots.popleft()

    mature = normal = repair = too_young = 0
    for lot in lots:
        deadline = lot.entry.second + horizon
        if deadline > as_of:
            too_young += lot.entry.quantity
            continue
        mature += lot.entry.quantity
        for exit_fill in lot.exits:
            if exit_fill.second > deadline:
                break
            if exit_fill.kind == "normal":
                normal += exit_fill.quantity
            else:
                repair += exit_fill.quantity
    cohorts = tuple(Cohort(lot.entry, tuple(lot.exits)) for lot in lots)
    return CohortReport(cohorts, mature, normal, repair, too_young)
