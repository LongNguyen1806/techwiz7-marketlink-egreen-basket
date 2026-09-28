from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from simple_history.admin import SimpleHistoryAdmin

from accounts.models import CustomerProfile, CustomUser, FarmerProfile, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


class CustomUserCreationForm(BaseUserCreationForm):
    usable_password = None

    class Meta:
        model = CustomUser
        fields = ("email", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ("email", "role", "is_active", "is_staff", "is_superuser")


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    list_display = ("email", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email",)
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions & Roles", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Timestamps", {"fields": ("date_joined", "last_login", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),
    )
    readonly_fields = ("date_joined", "last_login", "updated_at")
    filter_horizontal = ()


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "phone", "created_at")
    search_fields = ("user__email", "full_name", "phone")


@admin.register(FarmerProfile)
class FarmerProfileAdmin(SimpleHistoryAdmin):
    list_display = (
        "user",
        "stall_name",
        "contact_person",
        "phone",
        "status",
        "order_cutoff_hours",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("user__email", "stall_name", "contact_person", "phone")
