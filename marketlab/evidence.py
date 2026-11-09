"""Reconstruct the latest version of an external report known at a decision time."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class Report:
    proposition: str
    published: int   # Source clock, seconds on a shared illustrative timeline
    version: int     # Increases for corrections to one publication
    received: int    # First or repeated local observation of this version
    reference: Decimal   # An external quote or estimate, in units per share

    def __post_init__(self) -> None:
        if not isinstance(self.proposition, str) or not self.proposition.strip():
            raise ValueError("a proposition identifies one settlement definition")
        if not all(type(n) is int for n in (self.published, self.version, self.received)):
            raise ValueError("times and version must be integers")
        if self.published < 0 or self.version < 0 or self.received < self.published:
            raise ValueError("invalid publication timeline")
        if not isinstance(self.reference, Decimal) or not self.reference.is_finite():
            raise ValueError("use a finite Decimal for the reference")
        if not 0 <= self.reference <= 1:
            raise ValueError("reference outside [0, 1]")


def report_as_of(reports: Iterable[Report], proposition: str, at: int,
                 max_age: int) -> Report | None:
    """Return the first receipt of the freshest eligible publication and version.

    Each input stream is from one source. An exact proposition identifies both
    the subject and its payout definition. A revision becomes visible on receipt.
    Re-observing the same publication cannot make the source information younger.
    """
    if type(at) is not int or type(max_age) is not int or min(at, max_age) < 0:
        raise ValueError("at and max_age must be non-negative integer seconds")
    visible = [r for r in reports if r.proposition == proposition
               and r.received <= at and at - r.published <= max_age]
    if not visible:
        return None
    newest = max((r.published, r.version) for r in visible)
    versions = [r for r in visible if (r.published, r.version) == newest]
    if len({r.reference for r in versions}) != 1:
        raise ValueError("conflicting references for the same source version")
    return min(versions, key=lambda r: r.received)
