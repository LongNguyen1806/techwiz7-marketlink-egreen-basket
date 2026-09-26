import time

from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenBackendError, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.auth.sessions import (
    claim_refresh_token,
    keep_session_on_password_change,
    revoke_session,
    session_state,
)
from accounts.auth.tokens import PASSWORD_VERSION_CLAIM, SESSION_CLAIM, issue_tokens, password_version
from accounts.exceptions import AccountLockedError, InvalidCredentialsError, TokenInvalidError
from accounts.models import CustomUser
from marketlink_core.policies.roles import RoleCode
from notifications.services import disconnect_realtime

MARKET_PORTAL_ROLES = frozenset({RoleCode.CUSTOMER, RoleCode.FARMER})
ADMIN_PORTAL_ROLES = frozenset({RoleCode.ADMIN})

# Revocation state lives in Redis (accounts.auth.sessions). The one rule that must survive a Redis wipe,
# "a password change logs out every other device", is enforced by the pwv claim against the users table.


def account_locked_error(user: CustomUser) -> AccountLockedError:
    profile = getattr(user, "customer_profile", None)
    reason = profile.deactivation_reason if profile else None
    return AccountLockedError(errors={"reason": [reason]} if reason else None)


def _lock_user(user_id) -> CustomUser | None:
    return (
        CustomUser.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=user_id)
        .first()
    )


def authenticate_user(*, email: str, password: str, roles: frozenset[str]) -> CustomUser:
    user = CustomUser.objects.select_related("role").filter(email=email).first()
    if user is None:
        # Hash anyway so unknown emails take as long as wrong passwords (no user enumeration by timing).
        CustomUser().set_password(password)
        raise InvalidCredentialsError()
    if not user.check_password(password):
        raise InvalidCredentialsError()
    # D-027: a wrong portal looks like a wrong password, and is checked before the lock so it never leaks the reason.
    if user.role.code not in roles:
        raise InvalidCredentialsError()
    if not user.is_active:
        raise account_locked_error(user)
    return user


def _parse_refresh_token(raw: str) -> RefreshToken:
    try:
        return RefreshToken(raw)
    except TokenError as exc:
        raise TokenInvalidError() from exc


def _decode_refresh_payload(raw: str) -> dict:
    """Signature, expiry and type check only — accepts tokens that were already rotated."""
    try:
        payload = token_backend.decode(raw, verify=True)
    except TokenBackendError as exc:
        raise TokenInvalidError() from exc
    if payload.get(jwt_settings.TOKEN_TYPE_CLAIM) != "refresh":
        raise TokenInvalidError()
    return payload


def _exempt_after_own_password_change(keeper, *, session_id: str, token_version, current_version: str) -> bool:
    # Only the device that made the change, only across that exact change: any later password reset
    # (admin, manage.py, a rolled-back attempt) no longer matches "to" and ends the exemption.
    return (
        bool(keeper)
        and keeper.get("sid") == session_id
        and keeper.get("from") == token_version
        and keeper.get("to") == current_version
    )


def rotate_refresh_token(*, refresh: str) -> dict:
    token = _parse_refresh_token(refresh)
    session_id = token.get(SESSION_CLAIM)
    if not session_id:
        raise TokenInvalidError()
    user = CustomUser.objects.select_related("role").filter(pk=token[jwt_settings.USER_ID_CLAIM]).first()
    if user is None:
        raise TokenInvalidError()

    # Every revocation check runs before the lock check, so a dead token never learns the lock reason.
    revoked, keeper = session_state(user.pk, session_id)
    if revoked:
        raise TokenInvalidError()
    token_version, current_version = token.get(PASSWORD_VERSION_CLAIM), password_version(user)
    if token_version != current_version and not _exempt_after_own_password_change(
        keeper, session_id=session_id, token_version=token_version, current_version=current_version
    ):
        raise TokenInvalidError()
    if not claim_refresh_token(token["jti"], ttl_seconds=int(token["exp"] - time.time())):
        # A rotated token presented again means it leaked: end the whole session so neither copy survives.
        revoke_session(session_id)
        raise TokenInvalidError()

    if not user.is_active:
        raise account_locked_error(user)
    return issue_tokens(user, session_id=session_id)


def logout(*, user: CustomUser, session_id: str, refresh: str) -> None:
    payload = _decode_refresh_payload(refresh)
    if str(payload.get(jwt_settings.USER_ID_CLAIM)) != str(user.pk) or payload.get(SESSION_CLAIM) != session_id:
        raise TokenInvalidError()
    revoke_session(session_id)
    # Only this device's sockets close; the user's other sessions stay connected.
    disconnect_realtime(session_id=session_id)


def change_password(*, user: CustomUser, current_password: str, new_password: str, session_id: str) -> None:
    with transaction.atomic():
        locked = _lock_user(user.pk)
        if not locked.check_password(current_password):
            raise serializers.ValidationError({"current_password": ["Current password is incorrect"]})
        old_version = password_version(locked)
        locked.set_password(new_password)
        # Stored before the new password commits: if Redis is down nothing changes, and if the save rolls
        # back the exemption points at a password that never went live, so it can never match.
        keep_session_on_password_change(
            locked.pk, session_id=session_id, old_version=old_version, new_version=password_version(locked)
        )
        locked.save(update_fields=["password", "updated_at"])
