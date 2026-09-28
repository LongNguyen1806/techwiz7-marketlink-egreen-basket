"""#6 the AI decides the clear cases, #8 admins see and can undo what it decided."""

import pytest
from django.urls import reverse

from catalog.ai_review import gemini
from catalog.ai_review.gemini import AIResult, AIUnavailable
from catalog.ai_review.service import review_product
from catalog.ai_review.types import Finding
from catalog.models import AIAutoAction, AIVerdict, Category, Product, ReviewStatus, Unit
from notifications.models import Notification, NotificationType
from system.models import FlagTarget, ModerationFlag

NOT_FOOD = Finding(source="ai", check="NOT_FARM_PRODUCE", severity="HIGH", message="A phone, not food.")


def _model(findings=(), error=None):
    def ask(listing, category_names, *, image_only=False):
        if error:
            raise AIUnavailable(error)
        return AIResult(findings=list(findings), suggested_category=None, summary="", model_name="fake")

    return ask


@pytest.fixture
def category(db):
    return Category.objects.create(name="Greens", icon="carrot", display_order=1)


@pytest.fixture
def stall(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = "APPROVED"
    profile.save(update_fields=["status"])
    return profile


def _pending(stall, category, name="Cucumber"):
    return Product.objects.create(
        farmer=stall, category=category, name=name, price="1.50", unit=Unit.KG, stock_quantity=30
    )


@pytest.mark.django_db
class TestTheAIDecides:
    def test_a_pass_goes_on_sale_and_tells_the_stall(self, stall, category, monkeypatch, farmer_user):
        monkeypatch.setattr(gemini, "ask_model", _model())
        product = _pending(stall, category)

        review = review_product(product.pk)

        product.refresh_from_db()
        assert product.review_status == ReviewStatus.APPROVED
        assert product.reviewed_by is None
        assert review.auto_action == AIAutoAction.APPROVED
        assert Notification.objects.filter(
            recipient=farmer_user, type=NotificationType.PRODUCT_APPROVED
        ).exists()

    def test_a_likely_violation_stays_off_sale_and_is_queued(self, stall, category, monkeypatch):
        monkeypatch.setattr(gemini, "ask_model", _model([NOT_FOOD]))
        product = _pending(stall, category, name="iPhone 12")

        review = review_product(product.pk)

        product.refresh_from_db()
        assert product.review_status == ReviewStatus.PENDING
        assert review.auto_action == AIAutoAction.HELD
        assert ModerationFlag.objects.filter(target_type=FlagTarget.PRODUCT, target_id=product.pk).exists()

    def test_when_the_ai_cannot_answer_an_admin_decides(self, stall, category, monkeypatch):
        monkeypatch.setattr(gemini, "ask_model", _model(error="quota"))
        product = _pending(stall, category)

        review = review_product(product.pk)

        product.refresh_from_db()
        assert review.verdict == AIVerdict.UNAVAILABLE
        assert product.review_status == ReviewStatus.PENDING
        assert review.auto_action is None

    def test_an_admin_decision_made_first_stands(self, stall, category, monkeypatch):
        monkeypatch.setattr(gemini, "ask_model", _model())
        product = _pending(stall, category)
        Product.objects.filter(pk=product.pk).update(review_status=ReviewStatus.REJECTED)

        review_product(product.pk)

        product.refresh_from_db()
        assert product.review_status == ReviewStatus.REJECTED

    def test_auto_approval_can_be_switched_off(self, stall, category, monkeypatch, settings):
        settings.AI_AUTO_APPROVE = False
        monkeypatch.setattr(gemini, "ask_model", _model())
        product = _pending(stall, category)

        review_product(product.pk)

        product.refresh_from_db()
        assert product.review_status == ReviewStatus.PENDING


@pytest.mark.django_db
class TestAdminsAreToldOnce:
    def test_many_approvals_make_one_notice_with_a_count(self, stall, category, monkeypatch, admin_user):
        monkeypatch.setattr(gemini, "ask_model", _model())
        for name in ("Cucumber", "Kale", "Spinach"):
            review_product(_pending(stall, category, name=name).pk)

        notices = Notification.objects.filter(recipient=admin_user, type=NotificationType.AI_AUTO_APPROVED)
        assert notices.count() == 1
        notice = notices.get()
        assert "3 listing" in notice.title
        assert "Spinach" in notice.message
        assert notice.target_url == "/admin/approvals?tab=ai"

    def test_after_reading_it_a_new_notice_starts(self, stall, category, monkeypatch, admin_user):
        monkeypatch.setattr(gemini, "ask_model", _model())
        review_product(_pending(stall, category, name="Cucumber").pk)
        Notification.objects.filter(recipient=admin_user).update(is_read=True)

        review_product(_pending(stall, category, name="Kale").pk)

        assert Notification.objects.filter(
            recipient=admin_user, type=NotificationType.AI_AUTO_APPROVED
        ).count() == 2

    def test_the_admin_can_read_their_notifications(self, admin_client):
        assert admin_client.get(reverse("notifications-unread-count")).status_code == 200


@pytest.mark.django_db
class TestTheDecisionsList:
    def test_lists_unchecked_decisions_and_filters_by_action(self, admin_client, stall, category, monkeypatch):
        monkeypatch.setattr(gemini, "ask_model", _model())
        passed = _pending(stall, category, name="Cucumber")
        review_product(passed.pk)
        monkeypatch.setattr(gemini, "ask_model", _model([NOT_FOOD]))
        held = _pending(stall, category, name="iPhone")
        review_product(held.pk)

        url = reverse("admin-ai-decision-list")
        rows = admin_client.get(url).data["data"]["results"]
        assert {row["product"]["id"] for row in rows} == {passed.pk, held.pk}
        only_held = admin_client.get(url, {"action": "HELD"}).data["data"]["results"]
        assert [row["product"]["id"] for row in only_held] == [held.pk]
        by_name = admin_client.get(url, {"q": "cucum"}).data["data"]["results"]
        assert [row["product"]["id"] for row in by_name] == [passed.pk]

    def test_checking_one_moves_it_out_of_the_unchecked_list(
        self, admin_client, stall, category, monkeypatch, admin_user
    ):
        monkeypatch.setattr(gemini, "ask_model", _model())
        review = review_product(_pending(stall, category).pk)

        response = admin_client.post(reverse("admin-ai-decision-check", args=[review.pk]))

        assert response.status_code == 200
        assert response.data["data"]["checked_by"] == admin_user.email
        url = reverse("admin-ai-decision-list")
        assert admin_client.get(url).data["data"]["results"] == []
        assert len(admin_client.get(url, {"checked": "true"}).data["data"]["results"]) == 1

    def test_undoing_an_approval_counts_as_checked(self, admin_client, stall, category, monkeypatch):
        monkeypatch.setattr(gemini, "ask_model", _model())
        product = _pending(stall, category)
        review = review_product(product.pk)

        admin_client.post(f"/api/admin/products/{product.pk}/reject/", {"reason": "Wrong photo."}, format="json")

        review.refresh_from_db()
        product.refresh_from_db()
        assert product.review_status == ReviewStatus.REJECTED
        assert review.admin_checked_at is not None

    def test_only_admins_see_the_list(self, api_client, customer_user):
        api_client.force_authenticate(user=customer_user)
        assert api_client.get(reverse("admin-ai-decision-list")).status_code == 403
