"""P-b: live notification sockets close when the account is locked or the session logs out."""

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import CustomerProfile, CustomUser, Role, RoleCode
from accounts.services.customer_status_service import deactivate_customer
from marketlink_core.asgi import application
from marketlink_core.services.ws_ticket import create_ws_ticket, verify_and_consume_ws_ticket
from notifications.services import disconnect_realtime

PASSWORD = "Mango2026x"
CLOSED_UNAUTHORIZED = 4401


class WebSocketDisconnectTests(TransactionTestCase):
    def setUp(self):
        role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        self.user = CustomUser.objects.create_user(email="ws_lock@marketlink.local", password=PASSWORD, role=role)
        CustomerProfile.objects.create(user=self.user, full_name="WS Lock", phone="0911777888", address="WS Lane")

    async def _connect(self, ticket: str) -> WebsocketCommunicator:
        communicator = WebsocketCommunicator(application, f"/ws/notifications/?ticket={ticket}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        return communicator

    async def _assert_closed(self, communicator: WebsocketCommunicator) -> None:
        message = await communicator.receive_output(timeout=3)
        self.assertEqual((message["type"], message["code"]), ("websocket.close", CLOSED_UNAUTHORIZED))

    async def test_ticket_of_a_locked_account_is_refused(self):
        ticket = create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER)
        await sync_to_async(CustomUser.objects.filter(pk=self.user.pk).update)(is_active=False)

        communicator = await self._connect(ticket)

        await self._assert_closed(communicator)

    async def test_locking_the_account_closes_every_socket_of_the_user(self):
        phone = await self._connect(create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER, session_id="a1"))
        laptop = await self._connect(create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER, session_id="b2"))

        await sync_to_async(deactivate_customer)(customer_id=self.user.pk, reason="Repeated no-shows", actor=None)

        await self._assert_closed(phone)
        await self._assert_closed(laptop)

    async def test_logout_closes_only_the_sockets_of_that_session(self):
        this_device = await self._connect(
            create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER, session_id="a1")
        )
        other_device = await self._connect(
            create_ws_ticket(user_id=self.user.pk, role=RoleCode.CUSTOMER, session_id="b2")
        )

        await sync_to_async(disconnect_realtime)(session_id="a1")

        await self._assert_closed(this_device)
        self.assertTrue(await other_device.receive_nothing(timeout=0.5))
        await other_device.disconnect()

    def test_ticket_carries_the_session_of_the_signed_in_device(self):
        client = APIClient()
        tokens = client.post(
            "/api/auth/login/", {"email": "ws_lock@marketlink.local", "password": PASSWORD}, format="json"
        ).json()["data"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        ticket = client.post("/api/auth/ws-ticket/").json()["data"]["ticket"]

        payload = verify_and_consume_ws_ticket(ticket=ticket)
        self.assertEqual(payload["user_id"], self.user.pk)
        self.assertTrue(payload["sid"])

    async def test_logout_endpoint_closes_the_socket_of_that_device(self):
        client = APIClient()
        tokens = (
            await sync_to_async(client.post)(
                "/api/auth/login/", {"email": "ws_lock@marketlink.local", "password": PASSWORD}, format="json"
            )
        ).json()["data"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        ticket = (await sync_to_async(client.post)("/api/auth/ws-ticket/")).json()["data"]["ticket"]
        communicator = await self._connect(ticket)

        response = await sync_to_async(client.post)(
            "/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json"
        )

        self.assertEqual(response.status_code, 204)
        await self._assert_closed(communicator)
