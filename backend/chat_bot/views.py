import logging

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from chat_bot import limits
from chat_bot.ai_chatbot import Asker
from chat_bot.prompts import busy_reply
from chat_bot.serializers import ChatRequestSerializer
from chat_bot.services import answer
from marketlink_core.exceptions import ServiceUnavailableError
from marketlink_core.gemini import AIUnavailable
from marketlink_core.responses import api_response

logger = logging.getLogger("marketlink")


def _latest_message(request) -> str:
    try:
        messages = request.data.get("messages") or []
        return str(messages[-1].get("content", "")) if messages else ""
    except (AttributeError, IndexError, TypeError, ValueError):
        return ""


class ChatMessagesView(APIView):
    """CH-01: one assistant reply. Open to everyone; what it can look up depends on the role.

    Every refusal (per-minute throttle, daily cap, model down, quota) answers with the same
    neutral "busy" message and 503 AI_UNAVAILABLE; only the log says which it was.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def _busy(self, request, reason: str) -> ServiceUnavailableError:
        role = Asker.from_request(request).role
        logger.warning("Assistant refused (%s) for %s", reason, role)
        return ServiceUnavailableError(busy_reply(_latest_message(request)))

    def throttled(self, request, wait):
        raise self._busy(request, "per-minute throttle")

    def post(self, request: Request) -> Response:
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asker = Asker.from_request(request)
        if limits.used_up(request, asker):
            raise self._busy(request, "daily cap")
        try:
            result = answer(serializer.validated_data["messages"], asker)
        except AIUnavailable as exc:
            raise self._busy(request, f"model unavailable: {exc}") from exc
        limits.record_answer(request, asker)
        return api_response(
            message="OK",
            data={"reply": result.reply, "tools_used": result.tools_used},
            request=request,
        )
