from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import CustomUser, FarmerProfile, FarmerStatus, Role, RoleCode


class FarmerOperatingDaysTestCase(TestCase):
    """D-031: operating_days is JSON, so FarmerProfile.clean()/save() enforce the rules."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        self.counter = 0

    def _profile(self, operating_days) -> FarmerProfile:
        self.counter += 1
        user = CustomUser.objects.create(email=f"days{self.counter}@marketlink.local", role=self.role)
        return FarmerProfile(
            user=user,
            stall_name=f"Days Stall {self.counter}",
            contact_person="Nguyen Van Days",
            phone=f"09770000{self.counter:02d}",
            address="1 Days Road",
            operating_days=operating_days,
        )

    def test_invalid_values_are_rejected_on_save(self):
        for bad in ([], None, "1,2", {"1": True}, [0], [8], [2, 2], [True], ["2"], [1.5]):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError) as ctx:
                    self._profile(bad).save()
                self.assertIn("operating_days", ctx.exception.message_dict)
        self.assertFalse(FarmerProfile.objects.exists())

    def test_valid_value_is_sorted(self):
        profile = self._profile([6, 2, 4])
        profile.save()
        profile.refresh_from_db()
        self.assertEqual(profile.operating_days, [2, 4, 6])

    def test_clean_reports_form_error(self):
        with self.assertRaises(ValidationError) as ctx:
            self._profile([]).full_clean()
        self.assertIn("operating_days", ctx.exception.message_dict)

    def test_partial_save_without_operating_days_is_not_blocked(self):
        profile = self._profile([1])
        profile.save()
        FarmerProfile.objects.filter(pk=profile.pk).update(operating_days=[])
        profile.refresh_from_db()

        profile.status = FarmerStatus.APPROVED
        profile.save(update_fields=["status", "updated_at"])
        profile.refresh_from_db()
        self.assertEqual(profile.status, FarmerStatus.APPROVED)

        with self.assertRaises(ValidationError):
            profile.save()
        with self.assertRaises(ValidationError):
            profile.save(update_fields=["operating_days"])
