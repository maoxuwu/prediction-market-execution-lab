"""Vary the second leg's available depth in a fictional unit-payout contract."""

import argparse
from decimal import Decimal
from typing import Iterable

from .depth import Level, plan_pair, settlement, sweep
from .ledger import Fill, Ledger


def ask(price: str, quantity: int) -> Level:
    return Level(Decimal(price), quantity)


def run(second_leg_depth: int) -> dict[str, Decimal | int]:
    if type(second_leg_depth) is not int or second_leg_depth < 0:
        raise ValueError("second-leg depth must be a non-negative integer")
    wallet = Ledger(Decimal("12"))
    fee = Decimal(".01")
    yes_book = [ask(".36", 5), ask(".48", 6)]
    no_book = [ask(".51", 4), ask(".54", 7)]
    plan = plan_pair(yes_book, no_book, 10, wallet.cash, fee)

    # The toy exchange confirms the first sweep. Before the NO order arrives,
    # only the specified number remain within the original price limit.
    yes = sweep(yes_book, plan.quantity, wallet.cash, fee, limit_price=Decimal(".36"))
    fresh_no = [ask(".73", 10)]
    if second_leg_depth:
        fresh_no.insert(0, ask(".51", second_leg_depth))
    no = sweep(fresh_no, yes.quantity, wallet.cash - yes.debit,
               fee, limit_price=Decimal(".54"))
    for side, leg in (("YES", yes), ("NO", no)):
        for i, level in enumerate(leg.levels):
            wallet.apply(Fill(f"{side}-{i}", "example", side, level.quantity,
                              level.price, fee * level.quantity))
    scenarios = settlement(yes, no)
    return {
        "planned pairs": plan.quantity,
        "planned all-in cost": plan.debit,
        "confirmed YES shares": yes.quantity,
        "confirmed NO shares": no.quantity,
        "open YES shares": wallet.position("example"),
        "cash after offsets": wallet.cash,
        "open FIFO cost": wallet.remaining_cost,
        "realised P&L": wallet.realized_pnl,
        "terminal P&L if YES": scenarios.pnl_if_yes,
        "terminal P&L if NO": scenarios.pnl_if_no,
    }


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--second-leg-depth", type=int, default=2,
                        help="shares still available at 0.51 when the second order arrives")
    args = parser.parse_args(argv)
    if args.second_leg_depth < 0:
        parser.error("--second-leg-depth must be non-negative")
    for name, value in run(args.second_leg_depth).items():
        formatted = f"{value:.2f}" if isinstance(value, Decimal) else str(value)
        print(f"{name:22} {formatted}")


if __name__ == "__main__":
    main()
