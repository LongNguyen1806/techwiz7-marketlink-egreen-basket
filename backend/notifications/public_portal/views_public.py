from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from marketlink_core.responses import api_response
from notifications.public_portal.serializers_public import AnnouncementPublicSerializer
from notifications.selectors import active_announcements


class PublicAnnouncementListView(ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = AnnouncementPublicSerializer

    @extend_schema(responses={200: AnnouncementPublicSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        role_code = (
            getattr(getattr(user, "role", None), "code", None)
            if getattr(user, "is_authenticated", False)
            else None
        )
        serializer = self.get_serializer(active_announcements(role_code=role_code), many=True)
        return api_response(message="OK", request=request, data=serializer.data)
