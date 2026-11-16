"""Replay fixed orders against fictional time-stamped ask books."""

from dataclasses import dataclass
from decimal import Decimal

from .depth import Fill, Level, _exact_calculation, sweep


D = Decimal
WALLET = D("31")
CASH_BUFFER = D("4")
LIMIT = D(".88")
FEE = D(".02")
CAPS = ((11, 6), (28, 6), (11, 14), (28, 14))


@dataclass(frozen=True)
class Window:
    """Two observations of one fresh batch of offers for a single trial."""
    trial: str
    pass_received: int
    decision_at: int
    arrives_at: int
    decision_asks: tuple[Level, ...]
    arrival_asks: tuple[Level, ...]


# The museum tests four clockwork animals. Each window contains new offers.
HERON = (Level(D(".73"), 11),)
OTTER = (Level(D(".68"), 9), Level(D(".82"), 17))
LYNX = (Level(D(".78"), 19),)
MARTEN = (Level(D(".85"), 3), Level(D(".91"), 12))
WINDOWS = (
    Window("Heron", 4, 7, 10, HERON, ()),
    Window("Otter", 14, 18, 21, OTTER, OTTER),
    Window("Lynx", 24, 31, 34, LYNX, LYNX),
    Window("Marten", 41, 47, 50, MARTEN, MARTEN),
)


@dataclass(frozen=True)
class Step:
    trial: str
    requested: int
    simulated_fill: Fill


@_exact_calculation
def replay(total_cap: int, trial_cap: int, windows: tuple[Window, ...] = WINDOWS,
           *, immediate: bool = False) -> tuple[Step, ...]:
    """Apply whole-credit spend limits. Set immediate for the zero-delay control."""
    if any(type(cap) is not int or cap < 0 for cap in (total_cap, trial_cap)):
        raise ValueError("caps must be non-negative whole credits")
    spent = D(0)
    by_trial: dict[str, Decimal] = {}
    previous_arrival = -1
    steps = []
    for window in windows:
        if not isinstance(window.trial, str) or not window.trial.strip():
            raise ValueError("a trial must have a non-blank identity")
        times = (window.pass_received, window.decision_at, window.arrives_at)
        if any(type(t) is not int or t < 0 for t in times):
            raise ValueError("receipt times must be non-negative integer seconds")
        if not previous_arrival < window.decision_at <= window.arrives_at:
            raise ValueError("windows must arrive in order and cannot overlap")
        previous_arrival = window.arrives_at

        trial_spend = by_trial.get(window.trial, D(0))
        allowance = min(WALLET - CASH_BUFFER - spent, total_cap - spent,
                        trial_cap - trial_spend)
        # Reserve the full limit and fee on every requested share before arrival.
        max_shares = int(allowance // (LIMIT + FEE))
        requested = 0
        if window.pass_received <= window.decision_at:
            plan = sweep(window.decision_asks, max_shares, allowance, FEE,
                         limit_price=LIMIT)
            requested = plan.quantity

        asks = window.decision_asks if immediate else window.arrival_asks
        fill = sweep(asks, requested, allowance, FEE, limit_price=LIMIT)
        spent += fill.debit
        by_trial[window.trial] = trial_spend + fill.debit
        steps.append(Step(window.trial, requested, fill))
    return tuple(steps)


def main() -> None:
    print("Fictional museum trials | requested orders arrive three seconds later")
    print("Total cap  Trial cap  Size by trial (Heron/Otter/Lynx/Marten)  Debit  Net if all pay 1")
    for total, trial in CAPS:
        steps = replay(total, trial)
        sizes = [step.simulated_fill.quantity for step in steps]
        debit = sum(step.simulated_fill.debit for step in steps)
        size_text = "/".join(map(str, sizes))
        print(f"{total:9}  {trial:9}  {size_text:>38}  {debit:5.2f}  {sum(sizes)-debit:16.2f}")
    early = replay(28, 14, immediate=True)[0]
    delayed = replay(28, 14)[0]
    print(f"Heron at caps 28/14 | requested {delayed.requested} | "
          f"zero-delay size {early.simulated_fill.quantity} | "
          f"three-second size {delayed.simulated_fill.quantity}")


if __name__ == "__main__":
    main()
