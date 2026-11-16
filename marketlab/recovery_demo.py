"""Reopen an offline journal and examine three invented account histories."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from .journal import Balance, Buy, History, IntentJournal, OrderRecord, Trade


def main():
    opening = Balance(at=10, cash_cents=600, shares=0)
    closing = Balance(at=31, cash_cents=600, shares=0)
    request = Buy("practice-wallet", "lantern", "YES", 4, 39, expires_at=30)
    history = History("page-A", "practice-wallet", "lantern", "YES", 10, closing, True, (), ())
    order = OrderRecord("order-A", request, accepted_at=13, terminal=True, filled=2)
    trade = Trade("trade-A", "order-A", 14, quantity=2, price_cents=37, fee_cents=1)
    matched = replace(history, closing=Balance(31, 525, 2), orders=(order,), trades=(trade,))
    ambiguous = replace(matched, orders=(order, replace(order, order_id="order-B")))

    cases = [
        ("One terminal order, 2 of 4 shares filled", matched),
        ("Expired, complete empty history and unchanged balance", history),
        ("Two orders match the original buy", ambiguous),
    ]
    with TemporaryDirectory() as tmp:
        for i, (label, evidence) in enumerate(cases):
            path = Path(tmp) / f"case-{i}.db"
            with IntentJournal(path) as sender:
                sender.prepare("buy", request, opening)
                if not sender.mark_maybe_sent("buy", at=12):
                    raise RuntimeError("demo send was already claimed")
            with IntentJournal(path) as restarted:
                # Check on restart while the original order can still be live.
                can_send = restarted.mark_maybe_sent("buy", at=15)
                result = restarted.recover("buy", evidence)
                print(f"{label} | {result} | repeat send allowed: {can_send}")


if __name__ == "__main__":
    main()
