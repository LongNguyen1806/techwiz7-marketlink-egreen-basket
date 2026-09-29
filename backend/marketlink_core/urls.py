from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from marketlink_core.views import HealthCheckView, WebSocketTicketView
from markets.farmer import urls_farmer as farmer_market_urls
from orders.farmer import urls_farmer as farmer_order_urls

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/health/", HealthCheckView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema", permission_classes=[AllowAny]),
        name="api-docs",
    ),
    path("api/auth/ws-ticket/", WebSocketTicketView.as_view(), name="ws-ticket"),
    path("api/auth/", include("accounts.auth.urls")),
    path("api/auth/", include("accounts.auth.urls_auth")),
    path("api/customer/", include("accounts.customer.urls_customer")),
    path("api/customer/", include("orders.customer.urls_customer")),
    path("api/customer/", include("reviews.customer.urls_customer")),
    path("api/customer/", include("favorites.customer.urls_customer")),
    path("api/public/", include("orders.public.urls_public")),
    path("api/farmer/profile/", include("accounts.farmer.urls_farmer")),
    path("api/farmer/markets/", include(farmer_market_urls.market_urlpatterns)),
    path("api/farmer/pickup-slots/", include(farmer_market_urls.pickup_slot_urlpatterns)),
    path("api/farmer/closures/", include(farmer_market_urls.closure_urlpatterns)),
    path("api/farmer/dashboard/", include(farmer_order_urls.dashboard_urlpatterns)),
    path("api/farmer/orders/", include("orders.farmer.urls_farmer")),
    path("api/farmer/products/", include("catalog.farmer.urls_farmer")),
    path("api/farmer/", include("reviews.farmer.urls_farmer")),
    path("api/notifications/", include("notifications.urls")),
    path("api/chat/", include("chat_bot.urls")),
    path("api/", include("accounts.admin_urls")),
    path("api/", include("accounts.public_urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("markets.urls")),
    path("api/", include("reviews.urls")),
    path("api/", include("orders.admin_portal.urls_admin")),
    path("api/", include("system.urls")),
    path("api/", include("notifications.admin_portal.urls_admin")),
    path("api/", include("notifications.public_portal.urls_public")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
