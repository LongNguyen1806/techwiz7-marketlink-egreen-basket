from django.urls import path

from accounts.auth.views_auth import FarmerRegisterView

urlpatterns = [
    path("register/farmer/", FarmerRegisterView.as_view(), name="auth-register-farmer"),
]
