from decimal import Decimal, InvalidOperation

from django.db.models import DecimalField, ExpressionWrapper, F, FloatField, Value
from django.db.models.functions import ACos, Cast, Cos, Greatest, Least, Radians, Sin

EARTH_RADIUS_KM = 6371.0
LATITUDE_LIMIT = Decimal("90")
LONGITUDE_LIMIT = Decimal("180")
DISTANCE_PRECISION = 2


def parse_coordinates(params) -> tuple[Decimal, Decimal] | None:
    raw_lat, raw_lng = params.get("lat"), params.get("lng")
    if raw_lat is None or raw_lng is None:
        return None
    try:
        lat, lng = Decimal(str(raw_lat)), Decimal(str(raw_lng))
    except (InvalidOperation, ValueError):
        return None
    if abs(lat) > LATITUDE_LIMIT or abs(lng) > LONGITUDE_LIMIT:
        return None
    return lat, lng


def distance_km(*, lat: Decimal, lng: Decimal, lat_field: str, lng_field: str):
    origin_lat = Radians(Value(lat, output_field=DecimalField(max_digits=9, decimal_places=6)))
    origin_lng = Radians(Value(lng, output_field=DecimalField(max_digits=9, decimal_places=6)))
    target_lat = Radians(Cast(F(lat_field), FloatField()))
    target_lng = Radians(Cast(F(lng_field), FloatField()))

    cosine = Cos(origin_lat) * Cos(target_lat) * Cos(target_lng - origin_lng) + Sin(
        origin_lat
    ) * Sin(target_lat)
    clamped = Least(Value(1.0), Greatest(Value(-1.0), cosine))
    return ExpressionWrapper(ACos(clamped) * Value(EARTH_RADIUS_KM), output_field=FloatField())


def rounded(value: float | None) -> float | None:
    return round(value, DISTANCE_PRECISION) if value is not None else None
