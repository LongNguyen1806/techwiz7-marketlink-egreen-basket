from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, Role, RoleCode
from marketlink_core.exceptions import ErrorCode
from notifications.models import Notification, NotificationType
from notifications.services import serialize_notification

URL = "/api/notifications/"
NOTIFICATION_KEYS = {"id", "type", "title", "message", "target_url", "is_read", "read_at", "created_at"}


class NotificationsAPITestCase(TestCase):
    """NO-01 -> NO-04 (Pass 4B §4.6, N-01, C-09 / F-10)."""

    def setUp(self):
        self.client = APIClient()
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        admin_role, _ = Role.objects.get_or_create(code=RoleCode.ADMIN, defaults={"name": "Administrator"})

        self.customer = CustomUser.objects.create(email="notif_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(user=self.customer, full_name="Khach N", phone="0911300100", address="1 N Road")
        self.farmer = CustomUser.objects.create(email="notif_farmer@marketlink.local", role=farmer_role)
        FarmerProfile.objects.create(
            user=self.farmer,
            stall_name="Notif Stall",
            contact_person="Farmer N",
            phone="0977300100",
            address="2 N Road",
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        self.admin = CustomUser.objects.create(email="notif_admin@marketlink.local", role=admin_role)

        # 12 for the customer (oldest first), 3 of them already read; 2 for the farmer.
        base = timezone.now() - timedelta(hours=1)
        self.customer_items = []
        for index in range(12):
            item = self._notify(self.customer, f"Customer #{index}", is_read=index < 3)
            Notification.objects.filter(pk=item.pk).update(created_at=base + timedelta(minutes=index))
            self.customer_items.append(item)
        self.farmer_items = [self._notify(self.farmer, f"Farmer #{index}") for index in range(2)]
        self.client.force_authenticate(user=self.customer)

    def _notify(self, user, title, *, is_read=False) -> Notification:
        return Notification.objects.create(
            recipient=user,
            type=NotificationType.ORDER_ACCEPTED,
            title=title,
            message="Message",
            target_url="/customer/orders/1",
            is_read=is_read,
            read_at=timezone.now() if is_read else None,
        )

    # --- NO-01 ---

    def test_list_is_paginated_newest_first_and_only_mine(self):
        res = self.client.get(URL, {"page_size": 5})
        self.assertEqual(res.status_code, 200)
        data = res.data["data"]
        self.assertEqual(data["count"], 12)
        self.assertEqual(data["total_pages"], 3)
        titles = [item["title"] for item in data["results"]]
        self.assertEqual(titles, ["Customer #11", "Customer #10", "Customer #9", "Customer #8", "Customer #7"])
        self.assertEqual(set(data["results"][0]), NOTIFICATION_KEYS)

    def test_filter_by_read_state(self):
        unread = self.client.get(URL, {"is_read": "false"}).data["data"]
        read = self.client.get(URL, {"is_read": "true"}).data["data"]
        self.assertEqual((unread["count"], read["count"]), (9, 3))
        self.assertTrue(all(item["read_at"] for item in read["results"]))

    def test_limit_returns_plain_list_for_dropdown(self):
        res = self.client.get(URL, {"limit": 10})
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data["data"], list)
        self.assertEqual(len(res.data["data"]), 10)
        self.assertEqual(res.data["data"][0]["title"], "Customer #11")
        res = self.client.get(URL, {"limit": 3, "is_read": "true"})
        self.assertEqual([item["title"] for item in res.data["data"]], ["Customer #2", "Customer #1", "Customer #0"])

    def test_invalid_query_parameters(self):
        for params, field in (
            ({"limit": 11}, "limit"),
            ({"limit": 0}, "limit"),
            ({"limit": "abc"}, "limit"),
            ({"is_read": "yes"}, "is_read"),
        ):
            with self.subTest(params=params):
                res = self.client.get(URL, params)
                self.assertEqual(res.status_code, 400)
                self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR)
                self.assertIn(field, res.data["errors"])

    # --- NO-02 ---

    def test_unread_count(self):
        res = self.client.get(f"{URL}unread-count/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"], {"unread_count": 9})

    # --- NO-03 ---

    def test_mark_one_as_read_is_idempotent(self):
        target = self.customer_items[5]
        res = self.client.post(f"{URL}{target.pk}/read/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["data"]["is_read"])
        first_read_at = res.data["data"]["read_at"]
        self.assertIsNotNone(first_read_at)

        res = self.client.post(f"{URL}{target.pk}/read/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["read_at"], first_read_at)
        self.assertEqual(self.client.get(f"{URL}unread-count/").data["data"]["unread_count"], 8)

    def test_cannot_read_someone_elses_notification(self):
        res = self.client.post(f"{URL}{self.farmer_items[0].pk}/read/")
        self.assertEqual(res.status_code, 404)
        self.farmer_items[0].refresh_from_db()
        self.assertFalse(self.farmer_items[0].is_read)

    # --- NO-04 ---

    def test_mark_all_as_read_only_touches_mine(self):
        res = self.client.post(f"{URL}read-all/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"], {"updated_count": 9})
        self.assertFalse(Notification.objects.filter(recipient=self.customer, is_read=False).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.customer, read_at__isnull=True).exists())
        self.assertEqual(Notification.objects.filter(recipient=self.farmer, is_read=False).count(), 2)
        self.assertEqual(self.client.post(f"{URL}read-all/").data["data"], {"updated_count": 0})

    # --- access ---

    def test_farmer_uses_the_same_endpoints(self):
        self.client.force_authenticate(user=self.farmer)
        self.assertEqual(self.client.get(f"{URL}unread-count/").data["data"], {"unread_count": 2})

    def test_admin_reads_own_notifications_and_anonymous_is_rejected(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["count"], 0)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f"{URL}unread-count/").status_code, 401)

    # --- WebSocket payload ---

    def test_websocket_payload_matches_api_shape(self):
        payload = serialize_notification(self.customer_items[0])
        self.assertEqual(set(payload), NOTIFICATION_KEYS)
        self.assertIsNotNone(payload["read_at"])
        self.assertIsNone(serialize_notification(self.customer_items[5])["read_at"])
