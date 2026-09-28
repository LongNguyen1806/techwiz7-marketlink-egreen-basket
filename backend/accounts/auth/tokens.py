import uuid

from django.utils.crypto import salted_hmac
from rest_framework_simplejwt.tokens import RefreshToken

SESSION_CLAIM = "sid"
PASSWORD_VERSION_CLAIM = "pwv"


def password_version(user) -> str:
    return salted_hmac("accounts.auth.password_version", user.password).hexdigest()[:16]


def issue_tokens(user, *, session_id: str | None = None) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role.code
    refresh[SESSION_CLAIM] = session_id or uuid.uuid4().hex
    refresh[PASSWORD_VERSION_CLAIM] = password_version(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
