import pytest
from django.urls import reverse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.auth.authentication import SessionJWTAuthentication
from accounts.auth.sessions import revoke_session
from accounts.auth.tokens import (
    PASSWORD_VERSION_CLAIM,
    SESSION_CLAIM,
    issue_tokens,
    password_version,
)



@pytest.mark.django_db
def test_the_issued_admin_token_carries_the_session_and_password_claims(admin_user):
    access = issue_tokens(admin_user)["access"]

    claims = AccessToken(access)
    assert claims[SESSION_CLAIM]
    assert claims[PASSWORD_VERSION_CLAIM] == password_version(admin_user)


@pytest.mark.django_db
def test_session_authentication_accepts_the_issued_token(admin_user):
    access = issue_tokens(admin_user)["access"]

    authenticator = SessionJWTAuthentication()
    validated = authenticator.get_validated_token(access.encode())

    assert authenticator.get_user(validated) == admin_user


@pytest.mark.django_db
def test_a_token_without_a_session_claim_is_refused(admin_user):
    bare = str(RefreshToken.for_user(admin_user).access_token)

    with pytest.raises(AuthenticationFailed):
        SessionJWTAuthentication().get_validated_token(bare.encode())


@pytest.mark.django_db
def test_the_access_token_opens_an_admin_endpoint_over_http(api_client, admin_user):
    access = issue_tokens(admin_user)["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert api_client.get(reverse("admin-category-list")).status_code == 200
    assert api_client.get(reverse("admin-dashboard")).status_code == 200


@pytest.mark.django_db
def test_revoking_the_session_closes_the_admin_portal(admin_user):
    access = issue_tokens(admin_user)["access"]

    revoke_session(AccessToken(access)[SESSION_CLAIM])

    with pytest.raises(AuthenticationFailed):
        SessionJWTAuthentication().get_validated_token(access.encode())


@pytest.mark.django_db
def test_changing_the_password_invalidates_the_old_admin_token(admin_user):
    access = issue_tokens(admin_user)["access"]
    authenticator = SessionJWTAuthentication()
    validated = authenticator.get_validated_token(access.encode())

    admin_user.set_password("An0therStr0ngPass")
    admin_user.save(update_fields=["password"])

    with pytest.raises(AuthenticationFailed):
        authenticator.get_user(validated)


@pytest.mark.django_db
def test_a_customer_token_cannot_open_an_admin_endpoint(api_client, customer_user):
    access = issue_tokens(customer_user)["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert api_client.get(reverse("admin-category-list")).status_code == 403
