"""
RF-01 Autenticar usuario, RNF-09 (bloqueo de 5 min tras 5 intentos
fallidos; contraseña mínimo 8 caracteres), RF-20 Contraseña temporal.
Endpoints nuevos y propios de `Cuenta`, separados del login de
`auth.User` que sigue usando el resto de LICS.
"""

from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cuenta, TokenCuenta
from .sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission

INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 5
MENSAJE_CREDENCIALES_INVALIDAS = "El usuario o la contraseña no son correctos."


def _serializar_cuenta(cuenta: Cuenta) -> dict:
    return {
        "id_cuenta": cuenta.id_cuenta,
        "usuario": cuenta.usuario,
        "perfil": cuenta.perfil,
        "es_contrasena_temporal": cuenta.es_contrasena_temporal,
    }


class LoginCuentaView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        usuario = (request.data.get("usuario") or "").strip()
        contrasena = request.data.get("contrasena") or ""

        try:
            cuenta = Cuenta.objects.get(usuario=usuario)
        except Cuenta.DoesNotExist:
            return Response(
                {"detail": MENSAJE_CREDENCIALES_INVALIDAS},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ahora = timezone.now()

        if cuenta.bloqueada_hasta and cuenta.bloqueada_hasta > ahora:
            minutos_restantes = max(
                1, int((cuenta.bloqueada_hasta - ahora).total_seconds() // 60) + 1,
            )

            return Response(
                {
                    "detail": (
                        "Esta cuenta se bloqueó por varios intentos "
                        f"fallidos. Intente de nuevo en {minutos_restantes} "
                        "minuto(s)."
                    ),
                },
                status=status.HTTP_423_LOCKED,
            )

        if not check_password(contrasena, cuenta.hash_contrasena):
            cuenta.intentos_fallidos += 1

            if cuenta.intentos_fallidos >= INTENTOS_MAXIMOS:
                cuenta.bloqueada_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
                cuenta.intentos_fallidos = 0

            cuenta.save(update_fields=["intentos_fallidos", "bloqueada_hasta"])

            return Response(
                {"detail": MENSAJE_CREDENCIALES_INVALIDAS},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        cuenta.intentos_fallidos = 0
        cuenta.bloqueada_hasta = None
        cuenta.save(update_fields=["intentos_fallidos", "bloqueada_hasta"])

        TokenCuenta.objects.filter(cuenta=cuenta).delete()
        token = TokenCuenta.objects.create(cuenta=cuenta)

        return Response(
            {"token": token.key, "cuenta": _serializar_cuenta(cuenta)},
        )


class LogoutCuentaView(APIView):
    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        TokenCuenta.objects.filter(cuenta=request.user).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeCuentaView(APIView):
    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        return Response(_serializar_cuenta(request.user))


class CambiarContrasenaCuentaView(APIView):
    """
    RF-20: cambio obligatorio al entrar con una contraseña temporal, o
    cambio voluntario en cualquier momento. Pide la actual salvo que
    sea temporal (coincide con el patrón de LICS en `ChangeOwnPasswordView`,
    que si exige la actual siempre; acá se SUPONE que una contraseña
    temporal no hace falta confirmarla porque ya se mostró una vez al
    asignarla).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        cuenta: Cuenta = request.user
        nueva = request.data.get("nueva_contrasena") or ""

        if len(nueva) < 8:
            return Response(
                {"nueva_contrasena": ["Debe tener al menos 8 caracteres."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not cuenta.es_contrasena_temporal:
            actual = request.data.get("contrasena_actual") or ""

            if not check_password(actual, cuenta.hash_contrasena):
                return Response(
                    {"contrasena_actual": ["La contraseña actual no es correcta."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cuenta.hash_contrasena = make_password(nueva)
        cuenta.es_contrasena_temporal = False
        cuenta.save(update_fields=["hash_contrasena", "es_contrasena_temporal"])

        TokenCuenta.objects.filter(cuenta=cuenta).delete()
        token = TokenCuenta.objects.create(cuenta=cuenta)

        return Response({"token": token.key})
