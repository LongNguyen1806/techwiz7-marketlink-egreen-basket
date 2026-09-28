import json
from decimal import Decimal
from unittest import mock

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, Role, RoleCode
from marketlink_core.exceptions import ErrorCode
from marketlink_core.asgi import application
from marketlink_core.services import ws_ticket
from marketlink_core.services.ws_ticket import create_ws_ticket, verify_and_consume_ws_ticket
from notifications.models import NotificationType
from notifications.services import notify
from system.models import AuditAction, AuditLog


class WebSocketTicketTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        self.user = CustomUser.objects.create(
            email="ws_user@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.user,
            full_name="WS User",
            phone="0911888999",
            address="WS Lane",
        )

    def test_create_and_consume_ticket(self):
        ticket = create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER)
        self.assertTrue(len(ticket) > 20)

        payload = verify_and_consume_ws_ticket(ticket=ticket)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], self.user.pk)
        self.assertEqual(payload["role"], RoleCode.CUSTOMER)

        second_attempt = verify_and_consume_ws_ticket(ticket=ticket)
        self.assertIsNone(second_attempt)

    def test_ws_ticket_endpoint_au08(self):
        res = self.client.post("/api/auth/ws-ticket/")
        self.assertEqual(res.status_code, 401)

        self.client.force_authenticate(user=self.user)
        res_auth = self.client.post("/api/auth/ws-ticket/")
        self.assertEqual(res_auth.status_code, 200)
        data = res_auth.data["data"]
        self.assertIn("ticket", data)
        self.assertEqual(data["expires_in"], 30)

        payload = verify_and_consume_ws_ticket(ticket=data["ticket"])
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], self.user.pk)

    def test_ws_ticket_admin_forbidden(self):
        admin_role, _ = Role.objects.get_or_create(code=RoleCode.ADMIN, defaults={"name": "Admin"})
        admin = CustomUser.objects.create(email="ws_admin@marketlink.local", role=admin_role)
        self.client.force_authenticate(user=admin)

        res = self.client.post("/api/auth/ws-ticket/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], ErrorCode.PERMISSION_DENIED)
        self.assertNotIn("ticket", res.data.get("data") or {})
        self.assertEqual(
            AuditLog.objects.filter(user=admin, action=AuditAction.ACCESS_DENIED).count(), 1
        )

    def test_ws_ticket_farmer_allowed(self):
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        farmer_user = CustomUser.objects.create(email="ws_farmer@marketlink.local", role=farmer_role)
        FarmerProfile.objects.create(
            user=farmer_user,
            stall_name="WS Stall",
            contact_person="WS Farmer",
            phone="0911777666",
            address="WS Farm Road",
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        self.client.force_authenticate(user=farmer_user)

        res = self.client.post("/api/auth/ws-ticket/")
        self.assertEqual(res.status_code, 200)
        payload = verify_and_consume_ws_ticket(ticket=res.data["data"]["ticket"])
        self.assertEqual(payload, {"user_id": farmer_user.pk, "role": RoleCode.FARMER})

    async def test_websocket_consumer_invalid_ticket_closes_4401(self):
        communicator = WebsocketCommunicator(application, "/ws/notifications/?ticket=invalid-uuid-123")
        connected, close_code = await communicator.connect()
        self.assertTrue(connected)
        message = await communicator.receive_output()
        self.assertEqual(message["type"], "websocket.close")
        self.assertEqual(message["code"], 4401)
        await communicator.disconnect()

    async def test_websocket_consumer_valid_ticket_receives_event(self):
        ticket = create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER)
        communicator = WebsocketCommunicator(application, f"/ws/notifications/?ticket={ticket}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        notification = await sync_to_async(notify)(
            recipient=self.user,
            event_type=NotificationType.ACCOUNT_STATUS_CHANGED,
            context={"status_label": "Active", "reason": "Welcome!"},
        )

        response = await communicator.receive_json_from()
        self.assertEqual(response["event"], "NEW_NOTIFICATION")
        self.assertEqual(response["data"]["id"], notification.pk)
        self.assertEqual(response["data"]["type"], NotificationType.ACCOUNT_STATUS_CHANGED)

        await communicator.disconnect()


class _FakeRedis:
    """Minimal redis-py stand-in: stores bytes like the real client (no decode_responses)."""

    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.calls: list[tuple] = []

    def set(self, key, value, ex=None):
        self.calls.append(("set", key, ex))
        self.store[key] = value.encode("utf-8")
        return True

    def getdel(self, key):
        self.calls.append(("getdel", key))
        return self.store.pop(key, None)


class WsTicketServiceTestCase(SimpleTestCase):
    def test_malformed_ticket_never_reaches_cache(self):
        with mock.patch.object(ws_ticket, "cache") as fake_cache, mock.patch.object(ws_ticket, "_redis") as fake_redis:
            for bad in (None, "", "invalid-uuid-123", "x" * 5000, 123):
                with self.subTest(ticket=bad):
                    self.assertIsNone(verify_and_consume_ws_ticket(ticket=bad))
            fake_cache.get.assert_not_called()
            fake_redis.assert_not_called()

    @override_settings(USE_REDIS=False)
    def test_locmem_lost_delete_race_is_rejected(self):
        with mock.patch.object(ws_ticket, "cache") as fake_cache:
            fake_cache.get.return_value = {"user_id": 1, "role": "CUSTOMER"}
            fake_cache.delete.return_value = False
            ticket = "0f8fad5b-d9cb-469f-a165-70867728950e"
            self.assertIsNone(verify_and_consume_ws_ticket(ticket=ticket))

    @override_settings(USE_REDIS=True)
    def test_redis_uses_set_ex_and_single_getdel(self):
        fake = _FakeRedis()
        with mock.patch.object(ws_ticket, "_redis", return_value=fake):
            ticket = create_ws_ticket(user_id=7, role="FARMER")
            key = f"ws_ticket:{ticket}"
            self.assertEqual(fake.calls, [("set", key, ws_ticket.DEFAULT_TTL)])
            self.assertEqual(json.loads(fake.store[key]), {"user_id": 7, "role": "FARMER"})

            payload = verify_and_consume_ws_ticket(ticket=f"  {ticket.upper()}  ")
            self.assertEqual(payload, {"user_id": 7, "role": "FARMER"})
            self.assertIsNone(verify_and_consume_ws_ticket(ticket=ticket))
            self.assertEqual([call[0] for call in fake.calls], ["set", "getdel", "getdel"])

    @override_settings(USE_REDIS=True)
    def test_redis_error_fails_closed(self):
        fake = mock.Mock()
        fake.getdel.side_effect = RedisConnectionError("down")
        with mock.patch.object(ws_ticket, "_redis", return_value=fake), self.assertLogs("marketlink", "ERROR"):
            self.assertIsNone(
                verify_and_consume_ws_ticket(ticket="0f8fad5b-d9cb-469f-a165-70867728950e")
            )
