from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Iterable, Literal, Optional, Tuple

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
        self._agg: Dict[float, Dict[str, float]] = defaultdict(
            lambda: {"BID": 0.0, "ASK": 0.0, "_BID_COUNT": 0, "_ASK_COUNT": 0}
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
        sd: Side = "ASK" if str(side).upper() == "ASK" else "BID"

        self._expire(ts)
        self._ticks.append(Tick(ts=ts, price=px, side=sd, vol=vol))
        self._agg[px][sd] += vol
        self._agg[px][f"_{sd}_COUNT"] += 1

    def profile(self) -> Dict[float, Dict[str, float]]:
        out: Dict[float, Dict[str, float]] = {}
        for p, d in self._agg.items():
            bid = d["BID"]
            ask = d["ASK"]
            if bid > 0 or ask > 0:
                out[p] = {"BID": bid, "ASK": ask, "Total": bid + ask}
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
