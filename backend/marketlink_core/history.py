"""Audit trail helpers (simple_history) — v1.8.

Tracked models: FarmerProfile, Product, Order, OrderItem, FarmerMarket, PickupSlot, FarmerClosure.
Every write to them must go through save() / delete() (never QuerySet.update() or plain
bulk_create, which skip the history row). These helpers stamp the history row with a reason
("Order #12 accepted (T2)") and, for system actions, an explicit user (None = system).
"""

from typing import Any

UNSET: Any = object()
_STAMP_ATTRS = ("_change_reason", "_history_user")


def _stamp(instance: Any, reason: str | None, user: Any) -> None:
    if reason is not None:
        instance._change_reason = reason
    if user is not UNSET:
        instance._history_user = user


def _clear(instance: Any) -> None:
    for attr in _STAMP_ATTRS:
        instance.__dict__.pop(attr, None)


def save_with_history(
    instance: Any, *, update_fields: list[str] | None = None, reason: str | None = None, user: Any = UNSET
) -> None:
    _stamp(instance, reason, user)
    try:
        if update_fields is None:
            instance.save()
        else:
            instance.save(update_fields=update_fields)
    finally:
        _clear(instance)


def delete_with_history(instance: Any, *, reason: str | None = None, user: Any = UNSET) -> None:
    _stamp(instance, reason, user)
    try:
        instance.delete()
    finally:
        _clear(instance)
