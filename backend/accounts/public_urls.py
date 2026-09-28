from django.urls import include, path

urlpatterns = [
    path("", include("accounts.public_portal.urls_public")),
]
