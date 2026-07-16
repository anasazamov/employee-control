"""Geo-yordamchilar. EWKT bitta joyda quriladi — lon/lat tartibini
adashtirish (klassik PostGIS xatosi) va SRID-magic takrorlanishi oldini oladi."""


def point_ewkt(*, lat: float, lon: float) -> str:
    """PostGIS uchun EWKT nuqta. Argumentlar ataylab keyword-only."""
    return f"SRID=4326;POINT({lon} {lat})"
