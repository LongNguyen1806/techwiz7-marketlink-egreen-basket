from rest_framework.permissions import BasePermission

from marketlink_core.policies.roles import RoleCode


class _RolePermission(BasePermission):
    roles: tuple[str, ...] = ()
    message = "You do not have permission to access this resource."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        role = getattr(user, "role", None)
        return role is not None and role.code in self.roles


class IsCustomer(_RolePermission):
    roles = (RoleCode.CUSTOMER,)


class IsFarmer(_RolePermission):
    roles = (RoleCode.FARMER,)


class IsAdmin(_RolePermission):
    roles = (RoleCode.ADMIN,)


class IsCustomerOrFarmer(_RolePermission):
    roles = (RoleCode.CUSTOMER, RoleCode.FARMER)


class IsAnyRole(_RolePermission):
    roles = (RoleCode.CUSTOMER, RoleCode.FARMER, RoleCode.ADMIN)
