"""
Autenticación de `Cuenta` para los endpoints nuevos de SIGEDA. No usa
`rest_framework.authtoken` ni `auth.User`: es un mecanismo paralelo,
para no tocar el login de las cuentas de negocio heredadas de LICS.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import authentication, exceptions, permissions

from .models import Cuenta, TokenCuenta

PREFIJO_TOKEN = "Bearer"
MINUTOS_INACTIVIDAD = 15
MENSAJE_INACTIVIDAD = (
    "La sesión se cerró por 15 minutos de inactividad. Inicie sesión "
    "de nuevo."
)


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

        # RNF-09: cualquier llamada autenticada real cuenta como
        # actividad. Si ya pasaron 15 minutos desde la última, la
        # sesión se cierra de verdad en el servidor (no solo en el
        # cliente).
        if timezone.now() - token.ultima_actividad > timedelta(
            minutes=MINUTOS_INACTIVIDAD,
        ):
            token.delete()

            raise exceptions.AuthenticationFailed(MENSAJE_INACTIVIDAD)

        token.save(update_fields=["ultima_actividad"])

        return (token.cuenta, token)


class CuentaAutenticadaPermission(permissions.BasePermission):
    message = "Inicie sesión para continuar."

    def has_permission(self, request, view):
        return isinstance(request.user, Cuenta)
