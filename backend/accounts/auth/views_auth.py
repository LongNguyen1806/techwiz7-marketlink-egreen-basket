from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.auth.serializers_auth import FarmerRegisterAuthSerializer
from accounts.auth.serializers_common import build_auth_payload
from accounts.services.registration import register_farmer
from marketlink_core.context import get_request_id
from marketlink_core.policies.roles import RoleCode
from marketlink_core.responses import api_response
from system.models import AuditAction
from system.services import log_security_event


class FarmerRegisterView(APIView):
    """AU-02: POST /api/auth/register/farmer/ -> { access, refresh, user: Me }, farmer_status PENDING."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request: Request) -> Response:
        serializer = FarmerRegisterAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, _ = register_farmer(**serializer.validated_data)
        log_security_event(
            action=AuditAction.ACCOUNT_REGISTERED,
            user=user,
            endpoint=request.get_full_path(),
            method=request.method,
            ip_address=None,
            user_agent=None,
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "id", None) or get_request_id(),
            details={"role": RoleCode.FARMER},
        )
        return api_response(
            message="Registration successful. Your account is awaiting administrator approval.",
            data=build_auth_payload(user, request),
            status_code=status.HTTP_201_CREATED,
            request=request,
        )
