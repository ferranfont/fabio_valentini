from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Side = Literal["BID", "ASK"]


@dataclass
class Tick:
    ts: datetime
    price: float
    side: Side
    vol: float
