from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.auth.serializers_common import (
    ChangePasswordWriteSerializer,
    LoginWriteSerializer,
    MeReadSerializer,
    RefreshTokenWriteSerializer,
    build_auth_payload,
)
from accounts.auth.throttles import LoginEmailThrottle, RecordableThrottleViewMixin
from accounts.auth.tokens import SESSION_CLAIM
from accounts.exceptions import InvalidCredentialsError
from accounts.services.auth_service import (
    ADMIN_PORTAL_ROLES,
    MARKET_PORTAL_ROLES,
    authenticate_user,
    change_password,
    logout,
    rotate_refresh_token,
)
from marketlink_core.exceptions import DomainError
from marketlink_core.responses import api_response
from system.models import AuditAction
from system.services import log_request_event


class LoginView(RecordableThrottleViewMixin, APIView):
    """AU-03: Customer and Farmer portal (D-027)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    # Per IP (every attempt) and per email (failed attempts only, from any IP).
    throttle_classes = [ScopedRateThrottle, LoginEmailThrottle]
    throttle_scope = "login"
    portal_roles = MARKET_PORTAL_ROLES
    audit_details: dict = {}

    @extend_schema(
        request=LoginWriteSerializer,
        responses={200: OpenApiResponse(description="Envelope with data: {access, refresh, user: Me}."), 401: None, 403: None, 429: None},
        summary="Sign in to the customer and farmer portal",
    )
    def post(self, request):
        serializer = LoginWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = authenticate_user(**serializer.validated_data, roles=self.portal_roles)
        except DomainError as exc:
            if isinstance(exc, InvalidCredentialsError):
                self.record_throttle(LoginEmailThrottle)
            log_request_event(request, action=AuditAction.LOGIN_FAILED, status_code=exc.status_code,
                               details={"email": email, "error": exc.code, **self.audit_details})
            raise
        log_request_event(request, action=AuditAction.LOGIN, status_code=200, user=user,
                           details=self.audit_details or None)
        return api_response(message="Login successful", data=build_auth_payload(user), request=request)


class AdminLoginView(LoginView):
    """AU-09: separate Admin portal with its own throttle bucket (D-027)."""

    throttle_scope = "admin_login"
    portal_roles = ADMIN_PORTAL_ROLES
    audit_details = {"portal": "ADMIN"}

    @extend_schema(
        request=LoginWriteSerializer,
        responses={200: OpenApiResponse(description="Envelope with data: {access, refresh, user: Me}."), 401: None, 429: None},
        summary="Sign in to the admin portal",
    )
    def post(self, request):
        return super().post(request)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=RefreshTokenWriteSerializer,
        responses={200: OpenApiResponse(description="Envelope with data: {access, refresh}."), 401: None},
        summary="Rotate the refresh token",
    )
    def post(self, request):
        serializer = RefreshTokenWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return api_response(message="Token refreshed", data=rotate_refresh_token(**serializer.validated_data), request=request)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RefreshTokenWriteSerializer,
        responses={204: None, 401: None},
        summary="End this device session",
    )
    def post(self, request):
        serializer = RefreshTokenWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logout(user=request.user, session_id=request.auth[SESSION_CLAIM], **serializer.validated_data)
        log_request_event(request, action=AuditAction.LOGOUT, status_code=204)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeReadSerializer, 401: None}, summary="The signed-in account")
    def get(self, request):
        return api_response(message="OK", data=MeReadSerializer(request.user).data, request=request)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    # Shares the login rate (5/min), keyed per user, to stop guessing the current password with a stolen token.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=ChangePasswordWriteSerializer,
        responses={200: OpenApiResponse(description="Envelope with an empty data object."), 400: None, 401: None},
        summary="Change the current password",
    )
    def post(self, request):
        serializer = ChangePasswordWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_password(user=request.user, session_id=request.auth[SESSION_CLAIM], **serializer.validated_data)
        log_request_event(request, action=AuditAction.PASSWORD_CHANGED, status_code=200)
        return api_response(message="Password changed successfully", request=request)
