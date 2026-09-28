from django.urls import include, path

urlpatterns = [
    path("", include("accounts.admin_portal.urls_admin_people")),
]
