from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Iterable, Literal, Optional, Tuple

from tick import Tick, Side
from parse_utils import parse_ts, parse_num


class RollingMarketProfile:
    """
    Rolling volume profile over a fixed time window (default 60s).
    Aggregates volume and trade counts by price and side (BID/ASK).
    """

    def __init__(
        self,
        window: timedelta = timedelta(seconds=60),
        price_tick: Optional[float] = None,
    ):
        self.window = window
        self.price_tick = price_tick
        self._ticks: Deque[Tick] = deque()
        self._current_time: Optional[datetime] = None  # Track latest timestamp
        self._agg: Dict[float, Dict[str, Any]] = defaultdict(
            lambda: {
                "BID": 0.0,
                "ASK": 0.0,
                "_BID_COUNT": 0,
                "_ASK_COUNT": 0,
                "_TRADES": {"BID": deque(), "ASK": deque()},
            }
        )

    # ----- Internal helpers -----

    def _bucket_price(self, price: float) -> float:
        if self.price_tick:
            return round(round(price / self.price_tick) * self.price_tick, 10)
        return price

    @staticmethod
    def _normalize_side(side: Side) -> Side:
        """Normalize side string to BID or ASK (optimization to avoid repeated str/upper calls)"""
        side_upper = str(side).upper()
        return "ASK" if side_upper == "ASK" else "BID"

    def _expire(self, now: datetime) -> None:
        cutoff = now - self.window
        while self._ticks and self._ticks[0].ts < cutoff:
            old = self._ticks.popleft()
            d = self._agg[old.price]
            d[old.side] -= old.vol
            d[f"_{old.side}_COUNT"] -= 1

            # NOTE: We don't remove from trades list here (O(n) operation)
            # Instead, trades will be filtered by timestamp when needed in profile()
            trades = d.get("_TRADES", {})
            side_trades: Optional[Deque[Tick]] = (
                trades.get(old.side) if trades else None
            )

            if side_trades:
                if side_trades and side_trades[0] is old:
                    side_trades.popleft()
                else:
                    # Fallback to removing by equality if order mismatch occurs
                    try:
                        side_trades.remove(old)
                    except ValueError:
                        pass

            # Clean up price level if empty
            if (
                d["BID"] <= 0
                and d["ASK"] <= 0
                and d["_BID_COUNT"] <= 0
                and d["_ASK_COUNT"] <= 0
            ):
                del self._agg[old.price]

    # ----- Public API -----

    def update(self, timestamp, price, volume, side: Side) -> None:
        ts = parse_ts(timestamp)
        px = self._bucket_price(parse_num(price))
        vol = float(parse_num(volume))
        sd = self._normalize_side(side)

        self._current_time = ts  # Track latest timestamp
        self._expire(ts)
        tick = Tick(ts=ts, price=px, side=sd, vol=vol)
        self._ticks.append(tick)
        entry = self._agg[px]
        entry[sd] += vol
        entry[f"_{sd}_COUNT"] += 1
        entry.setdefault("_TRADES", {"BID": deque(), "ASK": deque()})[sd].append(tick)

    def expire_until(self, timestamp) -> None:
        """Force expiration up to the provided timestamp without adding new ticks."""
        ts = parse_ts(timestamp)
        self._expire(ts)

    def profile(self, include_trades: bool = False) -> Dict[float, Dict[str, Any]]:
        out: Dict[float, Dict[str, Any]] = {}

        # Calculate cutoff time for filtering trades if needed
        cutoff = None
        if include_trades and self._current_time:
            cutoff = self._current_time - self.window

        for p, d in self._agg.items():
            bid = d["BID"]
            ask = d["ASK"]
            if bid > 0 or ask > 0:
                record: Dict[str, Any] = {"BID": bid, "ASK": ask, "Total": bid + ask}
                if include_trades:
                    trades = d.get("_TRADES", {"BID": deque(), "ASK": deque()})
                    record["Trades"] = {
                        side: [
                            {
                                "timestamp": t.ts,
                                "timestamp_str": t.ts.strftime("%H:%M:%S.%f")[:-3],
                                "volume": t.vol,
                                "side": t.side,
                            }
                            for t in trades.get(side, [])
                            if cutoff is None or t.ts >= cutoff  # Filter expired trades
                        ]
                        for side in ("BID", "ASK")
                    }
                out[p] = record
        return out

    def price_level(self, price) -> Optional[Dict[str, float]]:
        px = self._bucket_price(parse_num(price))
        d = self._agg.get(px)
        if not d:
            return None
        return {"BID": d["BID"], "ASK": d["ASK"], "Total": d["BID"] + d["ASK"]}

    def get_volume(self, price, side: Side) -> float:
        px = self._bucket_price(parse_num(price))
        sd = self._normalize_side(side)
        return float(self._agg.get(px, {}).get(sd, 0.0))

    def get_trade_count(self, price, side: Optional[Side] = None) -> int:
        px = self._bucket_price(parse_num(price))
        d = self._agg.get(px)
        if not d:
            return 0
        if side is None:
            return int(d["_BID_COUNT"] + d["_ASK_COUNT"])
        sd = self._normalize_side(side)
        return int(d.get(f"_{sd}_COUNT", 0))

    def get_bid_count(self, price) -> int:
        px = self._bucket_price(parse_num(price))
        return int(self._agg.get(px, {}).get("_BID_COUNT", 0))

    def get_ask_count(self, price) -> int:
        px = self._bucket_price(parse_num(price))
        return int(self._agg.get(px, {}).get("_ASK_COUNT", 0))

    def get_max_ask(self) -> Optional[Tuple[float, float]]:
        # Use generator expression to avoid creating full list
        try:
            return max(
                ((p, d["ASK"]) for p, d in self._agg.items() if d["ASK"] > 0),
                key=lambda x: x[0],
            )
        except ValueError:
            return None

    def get_min_bid(self) -> Optional[Tuple[float, float]]:
        # Use generator expression to avoid creating full list
        try:
            return min(
                ((p, d["BID"]) for p, d in self._agg.items() if d["BID"] > 0),
                key=lambda x: x[0],
            )
        except ValueError:
            return None

    def top_prices(self, n: int = 10) -> Iterable[Tuple[float, float]]:
        items = ((p, d["BID"] + d["ASK"]) for p, d in self._agg.items())
        return sorted(items, key=lambda x: x[1], reverse=True)[:n]
