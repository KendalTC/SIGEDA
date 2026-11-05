from rest_framework import permissions


ROLE_ADMIN = "ADMIN"
ROLE_INVENTORY = "INVENTORY"
ROLE_SALES = "SALES"
ROLE_CUSTOMERS = "CUSTOMERS"
ROLE_READ_ONLY = "READ_ONLY"


class AdministrationPermission(permissions.BasePermission):
    message = "No tiene permisos para consultar esta información."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or user.is_staff:
            return True

        return user.groups.filter(name=ROLE_ADMIN).exists()


def is_module_admin(user):
    """
    Superusuario o rol ADMIN: el mismo atajo que ModulePermission. A
    diferencia de AdministrationPermission, is_staff no cuenta.
    """

    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name=ROLE_ADMIN).exists()
        )
    )


class ModuleAdminRequired(permissions.BasePermission):
    """Exige superusuario o rol ADMIN."""

    message = "Solo el Administrador puede realizar esta acción."

    def has_permission(self, request, view):
        return is_module_admin(request.user)
