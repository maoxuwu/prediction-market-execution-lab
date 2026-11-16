"""A durable intent journal and an offline lost-acknowledgement exercise.

The recovery exercise follows one isolated buy in a single wallet. Prices,
fees and cash use integer cents. Shares are holdings of the purchased side;
the opening wallet has no position on its opposite side.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3


def _require_text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("a non-blank string is required")


def _natural(value: int) -> bool:
    return type(value) is int and 0 <= value <= 2**63 - 1


def _encode(record) -> str:
    return json.dumps(asdict(record), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Buy:
    wallet: str
    market: str
    side: str
    quantity: int
    limit_cents: int
    expires_at: int

    def __post_init__(self):
        _require_text(self.wallet)
        _require_text(self.market)
        if self.side not in ("YES", "NO"):
            raise ValueError("unknown outcome")
        if not _natural(self.quantity) or self.quantity == 0:
            raise ValueError("expected positive whole shares")
        if not _natural(self.limit_cents) or self.limit_cents > 100:
            raise ValueError("expected a limit in cents from 0 to 100")
        if not _natural(self.expires_at):
            raise ValueError("expected an integer expiry")


@dataclass(frozen=True)
class Balance:
    at: int
    cash_cents: int
    shares: int

    def __post_init__(self):
        if not all(_natural(value) for value in (self.at, self.cash_cents, self.shares)):
            raise ValueError("expected nonnegative integer time, cash and shares")


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    request: Buy
    accepted_at: int
    terminal: bool
    filled: int


@dataclass(frozen=True)
class Trade:
    fill_id: str
    order_id: str
    at: int
    quantity: int
    price_cents: int
    fee_cents: int


@dataclass(frozen=True)
class History:
    """Complete means all order and trade pages are final through closing.at.

    The closing balance is independently observed for this wallet/market/side.
    All activity in the window must be explained by this one isolated buy.
    """
    receipt: str
    wallet: str
    market: str
    side: str
    starts_at: int
    closing: Balance
    complete: bool
    orders: tuple[OrderRecord, ...]
    trades: tuple[Trade, ...]


def _outcome(request, opening, sent_at, history):
    if (history.wallet, history.market, history.side) != (request.wallet, request.market, request.side):
        return None
    if (not isinstance(history.closing, Balance) or not isinstance(history.orders, tuple)
            or not isinstance(history.trades, tuple)
            or any(not isinstance(record, OrderRecord) for record in history.orders)
            or any(not isinstance(fill, Trade) for fill in history.trades)):
        return None
    closing = history.closing
    if (history.complete is not True or not _natural(history.starts_at)
            or history.starts_at > opening.at or closing.at < sent_at):
        return None

    if not history.orders:
        if (closing.at > request.expires_at and not history.trades
                and (closing.cash_cents, closing.shares) == (opening.cash_cents, opening.shares)):
            return "NO_EFFECT", None
        return None
    # Multiple candidates or unrelated activity break the isolated-window proof.
    if len(history.orders) != 1:
        return None
    order = history.orders[0]
    if (order.request != request or order.terminal is not True
            or not _natural(order.accepted_at)
            or not sent_at <= order.accepted_at <= min(request.expires_at, closing.at)
            or not _natural(order.filled) or order.filled > request.quantity):
        return None
    _require_text(order.order_id)

    count = debit = 0
    seen = set()
    for fill in history.trades:
        _require_text(fill.fill_id)
        if (fill.fill_id in seen or fill.order_id != order.order_id
                or not _natural(fill.at)
                or not order.accepted_at <= fill.at <= min(request.expires_at, closing.at)
                or not _natural(fill.quantity) or fill.quantity == 0
                or not _natural(fill.price_cents) or fill.price_cents > request.limit_cents
                or not _natural(fill.fee_cents)):
            return None
        seen.add(fill.fill_id)
        count += fill.quantity
        debit += fill.quantity * fill.price_cents + fill.fee_cents
    if (count != order.filled or closing.cash_cents != opening.cash_cents - debit
            or closing.shares != opening.shares + count):
        return None
    return "MATCHED_ORDER", order.order_id


class IntentJournal:
    def __init__(self, path: Path):
        self._db = sqlite3.connect(path)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS intents (
                intent_id TEXT PRIMARY KEY NOT NULL,
                payload TEXT NOT NULL,
                terminal_receipt TEXT UNIQUE
            )
        """)
        # Older claims might have reached the venue. Only explicit preparations
        # get a row here and become eligible for the one-time send transition.
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS recovery (
                intent_id TEXT PRIMARY KEY NOT NULL REFERENCES intents(intent_id),
                wallet TEXT NOT NULL,
                opening TEXT NOT NULL,
                sent_at INTEGER,
                outcome TEXT,
                order_id TEXT UNIQUE,
                proof TEXT
            )
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._db.close()

    def claim(self, intent_id: str, payload: str) -> bool:
        """Claim an opaque intent once. A structured buy in flight blocks new claims."""
        _require_text(intent_id)
        _require_text(payload)
        with self._db:
            cursor = self._db.execute("""
                INSERT INTO intents(intent_id, payload)
                SELECT ?, ? WHERE NOT EXISTS (
                    SELECT 1 FROM recovery WHERE sent_at IS NOT NULL AND outcome IS NULL
                )
                ON CONFLICT(intent_id) DO NOTHING
            """, (intent_id, payload))
            if cursor.rowcount == 1:
                return True
            row = self._db.execute(
                "SELECT payload FROM intents WHERE intent_id = ?", (intent_id,)
            ).fetchone()
            if row is not None and row[0] != payload:
                raise ValueError("an existing intent has a different payload")
            return False

    def unresolved(self) -> tuple[str, ...]:
        rows = self._db.execute(
            "SELECT intent_id FROM intents WHERE terminal_receipt IS NULL ORDER BY intent_id"
        )
        return tuple(row[0] for row in rows)

    def confirm(self, intent_id: str, receipt: str) -> None:
        """Close an opaque claim using a caller-verified terminal receipt."""
        _require_text(intent_id)
        _require_text(receipt)
        with self._db:
            cursor = self._db.execute("""
                UPDATE intents SET terminal_receipt = ? WHERE intent_id = ?
                    AND (terminal_receipt IS NULL OR terminal_receipt = ?)
                    AND NOT EXISTS (SELECT 1 FROM recovery WHERE intent_id = ?)
            """, (receipt, intent_id, receipt, intent_id))
            if cursor.rowcount != 1:
                raise ValueError("unknown intent, structured buy or conflicting receipt")

    def prepare(self, intent_id: str, request: Buy, opening: Balance) -> bool:
        """Durably bind the request and independent opening balance before send."""
        _require_text(intent_id)
        if not isinstance(request, Buy) or not isinstance(opening, Balance):
            raise ValueError("expected a buy request and an opening balance")
        if opening.at >= request.expires_at:
            raise ValueError("buy has expired")
        payload, baseline = _encode(request), _encode(opening)
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("""
                SELECT payload, opening FROM intents LEFT JOIN recovery USING (intent_id)
                WHERE intent_id = ?
            """, (intent_id,)).fetchone()
            if row:
                if row != (payload, baseline):
                    raise ValueError("intent already bound to a different request or balance")
                return False
            self._db.execute("INSERT INTO intents(intent_id,payload) VALUES (?,?)", (intent_id, payload))
            self._db.execute("INSERT INTO recovery(intent_id,wallet,opening) VALUES (?,?,?)",
                             (intent_id, request.wallet, baseline))
            return True

    def mark_maybe_sent(self, intent_id: str, at: int) -> bool:
        """Only the caller receiving True can attempt the hypothetical send."""
        if not _natural(at):
            raise ValueError("expected an integer send time")
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("""
                SELECT payload, opening, sent_at FROM intents JOIN recovery USING(intent_id)
                WHERE intent_id = ?
            """, (intent_id,)).fetchone()
            if not row or row[2] is not None:
                return False
            request = Buy(**json.loads(row[0]))
            if not json.loads(row[1])["at"] <= at < request.expires_at:
                return False
            # Only one structured buy may be in flight in this wallet. An older
            # opaque claim has no identifiable wallet and must be reconciled first.
            prior = self._db.execute("""
                SELECT 1 FROM intents LEFT JOIN recovery USING(intent_id)
                WHERE terminal_receipt IS NULL AND
                      (opening IS NULL OR (wallet = ? AND sent_at IS NOT NULL))
            """, (request.wallet,)).fetchone()
            if prior:
                return False
            self._db.execute("UPDATE recovery SET sent_at = ? WHERE intent_id = ?", (at, intent_id))
            return True

    def status(self, intent_id: str) -> str:
        row = self._db.execute("""
            SELECT terminal_receipt, opening, sent_at, outcome
            FROM intents LEFT JOIN recovery USING(intent_id) WHERE intent_id = ?
        """, (intent_id,)).fetchone()
        if row is None:
            raise ValueError("unknown intent")
        receipt, opening, sent_at, outcome = row
        if opening is None:
            return "CONFIRMED" if receipt is not None else "POSSIBLY_SENT"
        if outcome is not None:
            return outcome
        return "PREPARED" if sent_at is None else "POSSIBLY_SENT"

    def recover(self, intent_id: str, history: History) -> str:
        """Resolve a structured buy under a single write transaction. Never sends."""
        _require_text(history.receipt)
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("""
                SELECT payload, opening, sent_at, outcome, proof
                FROM intents JOIN recovery USING(intent_id) WHERE intent_id = ?
            """, (intent_id,)).fetchone()
            if row is None or row[2] is None:
                raise ValueError("expected a structured possibly-sent buy")
            payload, opening, sent_at, outcome, proof = row
            if outcome is not None:
                if _encode(history) != proof:
                    raise ValueError("intent already resolved with different proof")
                return outcome
            result = _outcome(Buy(**json.loads(payload)), Balance(**json.loads(opening)), sent_at, history)
            if result is None:
                return "POSSIBLY_SENT"
            outcome, order_id = result
            self._db.execute("UPDATE intents SET terminal_receipt = ? WHERE intent_id = ?",
                             (history.receipt, intent_id))
            self._db.execute("UPDATE recovery SET outcome=?, order_id=?, proof=? WHERE intent_id=?",
                             (outcome, order_id, _encode(history), intent_id))
            return outcome
