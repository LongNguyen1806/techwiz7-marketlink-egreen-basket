import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from rest_framework import serializers

from notifications.messages import NOTIFICATION_SPECS, render_notification
from notifications.models import Notification

logger = logging.getLogger("marketlink")

# Bulk admin actions send one email per order; the pool keeps them off the request thread.
_email_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="marketlink-email")

DEFAULT_FRONTEND_URL = "http://localhost:5173"
_DATETIME_FIELD = serializers.DateTimeField()


def notify(*, recipient: Any, event_type: str, context: dict[str, Any]) -> Notification:
    title, message, target_url = render_notification(event_type, context)
    notification = Notification.objects.create(
        recipient=recipient,
        type=event_type,
        title=title,
        message=message,
        target_url=target_url,
    )
    transaction.on_commit(partial(_push_realtime, recipient.pk, serialize_notification(notification)))

    template = NOTIFICATION_SPECS[event_type].email_template
    if template and recipient.email:
        email_context = {
            **context,
            "title": title,
            "message": message,
            "action_url": _absolute_url(target_url),
            "recipient_email": recipient.email,
        }
        transaction.on_commit(partial(_send_email, recipient.email, title, template, email_context))
    return notification


def serialize_notification(notification: Notification) -> dict[str, Any]:
    """Notification (Pass 4B §3.x): the same shape for NO-01 / NO-03 and the WebSocket push."""
    return {
        "id": notification.pk,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "target_url": notification.target_url,
        "is_read": notification.is_read,
        # Same datetime format as every other API field (local timezone, ISO 8601).
        "read_at": _DATETIME_FIELD.to_representation(notification.read_at) if notification.read_at else None,
        "created_at": _DATETIME_FIELD.to_representation(notification.created_at),
    }


def user_group(user_id: int) -> str:
    return f"user_{user_id}"


def session_group(session_id: str) -> str:
    return f"session_{session_id}"


def _push_realtime(user_id: int, payload: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            user_group(user_id), {"type": "notify", "data": payload}
        )
    except Exception:  # noqa: BLE001 - the row is already saved; the bell reloads it later
        logger.exception("WebSocket push failed for user %s", user_id)


def disconnect_realtime(*, user_id: int | None = None, session_id: str | None = None) -> None:
    """Close live notification sockets after a lock (every device) or a logout (one device).

    Runs after the commit, so a rolled-back lock never disconnects anyone.
    """
    groups = []
    if user_id is not None:
        groups.append(user_group(user_id))
    if session_id:
        groups.append(session_group(session_id))
    for group in groups:
        transaction.on_commit(partial(_send_disconnect, group))


def _send_disconnect(group: str) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(group, {"type": "force.disconnect"})
    except Exception:  # noqa: BLE001 - access tokens still expire; the socket carries no data back
        logger.exception("WebSocket disconnect failed for group %s", group)


def _absolute_url(path: str | None) -> str | None:
    if not path:
        return None
    base = getattr(settings, "FRONTEND_URL", DEFAULT_FRONTEND_URL).rstrip("/")
    return f"{base}{path}"


def _send_email(to_email: str, subject: str, template: str, context: dict[str, Any]) -> None:
    text_body = render_to_string(f"emails/{template}.txt", context)
    html_body = render_to_string(f"emails/{template}.html", context)
    email = EmailMultiAlternatives(
        subject=f"[MarketLink] {subject}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_body, "text/html")
    if getattr(settings, "EMAIL_ASYNC", True):
        _email_pool.submit(_deliver, email)
    else:
        _deliver(email)


def _deliver(email: EmailMultiAlternatives) -> None:
    try:
        email.send(fail_silently=False)
    except Exception:  # noqa: BLE001 - email is a secondary channel; in-app already delivered
        logger.exception("Email delivery failed to %s", email.to)
