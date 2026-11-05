"""
Autenticación de `Cuenta` para los endpoints nuevos de SIGEDA. No usa
`rest_framework.authtoken` ni `auth.User`: es un mecanismo paralelo,
para no tocar el login de las cuentas de negocio heredadas de LICS.
"""

from rest_framework import authentication, exceptions, permissions

from .models import Cuenta, TokenCuenta

PREFIJO_TOKEN = "Bearer"


class AutenticacionCuenta(authentication.BaseAuthentication):
    def authenticate(self, request):
        encabezado = authentication.get_authorization_header(request).decode("utf-8")

        if not encabezado or not encabezado.startswith(f"{PREFIJO_TOKEN} "):
            return None

        key = encabezado[len(PREFIJO_TOKEN) + 1:].strip()

        try:
            token = TokenCuenta.objects.select_related("cuenta").get(key=key)
        except TokenCuenta.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                "La sesión no es válida o ya venció. Inicie sesión de nuevo.",
            )

        return (token.cuenta, token)


class CuentaAutenticadaPermission(permissions.BasePermission):
    message = "Inicie sesión para continuar."

    def has_permission(self, request, view):
        return isinstance(request.user, Cuenta)
