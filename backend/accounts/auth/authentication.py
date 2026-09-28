from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.auth.sessions import is_session_revoked
from accounts.auth.tokens import PASSWORD_VERSION_CLAIM, SESSION_CLAIM, password_version


class SessionJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        session_id = token.get(SESSION_CLAIM)
        if not session_id or is_session_revoked(session_id):
            raise AuthenticationFailed("Session has been revoked", code="session_revoked")
        return token

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get(PASSWORD_VERSION_CLAIM) != password_version(user):
            raise AuthenticationFailed("Password has changed", code="password_changed")
        return user
