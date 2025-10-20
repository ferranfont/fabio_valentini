from datetime import datetime, timezone


def parse_ts(ts) -> datetime:
    """Parse timestamp string or datetime; assumes UTC."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    ts = str(ts).strip().replace(",", ".")
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in ts.split()[-1] else "%Y-%m-%d %H:%M:%S"
    return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)


def parse_num(x) -> float:
    """Parse float or string with comma decimal separator."""
    return float(str(x).replace(",", "."))
