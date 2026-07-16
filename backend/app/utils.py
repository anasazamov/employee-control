from datetime import UTC, datetime


def iso_utc(ts: datetime) -> str:
    """Wire-format timestamp — WS/last-loc hodisalarida YAGONA format."""
    return ts.astimezone(UTC).isoformat()
