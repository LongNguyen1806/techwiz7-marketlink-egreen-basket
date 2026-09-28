import logging
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model

from marketlink_core.services.ws_ticket import verify_and_consume_ws_ticket
from notifications.services import session_group, user_group

logger = logging.getLogger("marketlink")

CLOSE_CODE_UNAUTHORIZED = 4401


@database_sync_to_async
def _is_active_user(user_id: int) -> bool:
    return get_user_model().objects.filter(pk=user_id, is_active=True).exists()


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id: int | None = None
        self.groups_joined: list[str] = []

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        ticket = query_params.get("ticket", [None])[0]

        if not ticket:
            await self._reject()
            return

        payload = await sync_to_async(verify_and_consume_ws_ticket, thread_sensitive=False)(ticket=ticket)
        if not payload or "user_id" not in payload:
            await self._reject()
            return
        if not await _is_active_user(payload["user_id"]):
            await self._reject()
            return

        self.user_id = payload["user_id"]
        self.groups_joined = [user_group(self.user_id)]
        if payload.get("sid"):
            self.groups_joined.append(session_group(payload["sid"]))
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if self.channel_layer:
            for group in self.groups_joined:
                await self.channel_layer.group_discard(group, self.channel_name)

    async def notify(self, event):
        payload = {
            "event": "NEW_NOTIFICATION",
            "data": event.get("data", {}),
        }
        await self.send_json(payload)

    async def force_disconnect(self, event):
        await self.close(code=CLOSE_CODE_UNAUTHORIZED)

    async def _reject(self):
        await self.accept()
        await self.close(code=CLOSE_CODE_UNAUTHORIZED)
