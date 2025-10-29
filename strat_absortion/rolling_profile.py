from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Iterable, List, Literal, Optional, Tuple

from tick import Tick, Side
from utils import parse_ts, parse_num


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

    def _expire(self, now: datetime) -> None:
        cutoff = now - self.window
        while self._ticks and self._ticks[0].ts < cutoff:
            old = self._ticks.popleft()
            d = self._agg[old.price]
            d[old.side] -= old.vol
            d[f"_{old.side}_COUNT"] -= 1
            trades = d.get("_TRADES", {})
            side_trades: Optional[Deque[Tick]] = trades.get(old.side) if trades else None

            if side_trades:
                if side_trades and side_trades[0] is old:
                    side_trades.popleft()
                else:
                    # Fallback to removing by equality if order mismatch occurs
                    try:
                        side_trades.remove(old)
                    except ValueError:
                        pass

            if (
                d["BID"] <= 0
                and d["ASK"] <= 0
                and d["_BID_COUNT"] <= 0
                and d["_ASK_COUNT"] <= 0
                and not trades.get("BID")
                and not trades.get("ASK")
            ):
                del self._agg[old.price]

    # ----- Public API -----

    def update(self, timestamp, price, volume, side: Side) -> None:
        ts = parse_ts(timestamp)
        px = self._bucket_price(parse_num(price))
        vol = float(parse_num(volume))
        sd: Side = "ASK" if str(side).upper() == "ASK" else "BID"

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
        sd: Side = "ASK" if str(side).upper() == "ASK" else "BID"
        return float(self._agg.get(px, {}).get(sd, 0.0))

    def get_trade_count(self, price, side: Optional[Side] = None) -> int:
        px = self._bucket_price(parse_num(price))
        d = self._agg.get(px)
        if not d:
            return 0
        if side is None:
            return int(d["_BID_COUNT"] + d["_ASK_COUNT"])
        sd: Side = "ASK" if str(side).upper() == "ASK" else "BID"
        return int(d.get(f"_{sd}_COUNT", 0))

    def get_bid_count(self, price) -> int:
        px = self._bucket_price(parse_num(price))
        return int(self._agg.get(px, {}).get("_BID_COUNT", 0))

    def get_ask_count(self, price) -> int:
        px = self._bucket_price(parse_num(price))
        return int(self._agg.get(px, {}).get("_ASK_COUNT", 0))

    def get_max_ask(self) -> Optional[Tuple[float, float]]:
        asks = [(p, d["ASK"]) for p, d in self._agg.items() if d["ASK"] > 0]
        if not asks:
            return None
        return max(asks, key=lambda x: x[0])

    def get_min_bid(self) -> Optional[Tuple[float, float]]:
        bids = [(p, d["BID"]) for p, d in self._agg.items() if d["BID"] > 0]
        if not bids:
            return None
        return min(bids, key=lambda x: x[0])

    def top_prices(self, n: int = 10) -> Iterable[Tuple[float, float]]:
        items = ((p, d["BID"] + d["ASK"]) for p, d in self._agg.items())
        return sorted(items, key=lambda x: x[1], reverse=True)[:n]
