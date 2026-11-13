"""
RF-01 Autenticar usuario, RNF-09 (bloqueo de 5 min tras 5 intentos
fallidos; contraseña mínimo 8 caracteres; cierre de sesión a los 15
minutos de inactividad), RF-20 Contraseña temporal. Endpoints nuevos y
propios de `Cuenta`, separados del login de `auth.User` que sigue
usando el resto de LICS.
"""

import math
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar

from .models import Cuenta, TokenCuenta
from .sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission

INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 5
MENSAJE_CREDENCIALES_INVALIDAS = "El usuario o la contraseña no son correctos."

# SUPUESTO (decisión 1 del plan de hoy): el documento de prototipos
# confirma el patrón visual palabra-número-palabra temático del
# acueducto («Rio-7425-Agua»), pero el algoritmo exacto queda libre.
PALABRAS_CONTRASENA_TEMPORAL = [
    "Agua",
    "Rio",
    "Tuberia",
    "Pila",
    "Bodega",
    "Cauce",
    "Pozo",
    "Cerro",
    "Canal",
    "Represa",
]


def _serializar_cuenta(cuenta: Cuenta) -> dict:
    return {
        "id_cuenta": cuenta.id_cuenta,
        "usuario": cuenta.usuario,
        "perfil": cuenta.perfil,
        "es_contrasena_temporal": cuenta.es_contrasena_temporal,
    }


def _otra_cuenta(usuario_actual: str) -> Cuenta | None:
    """
    RN-09: hay exactamente dos cuentas fijas. Esta función ubica la que
    no es `usuario_actual`, tanto sin autenticar (login, con el nombre
    de usuario tecleado) como autenticada (PAN-14, con la cuenta de la
    sesión).
    """

    return Cuenta.objects.exclude(usuario=usuario_actual).order_by("usuario").first()


def _pluralizar(cantidad: int, singular: str, plural: str) -> str:
    return singular if cantidad == 1 else plural


def _mensaje_intentos_restantes(intentos_restantes: int) -> str:
    verbo = _pluralizar(intentos_restantes, "queda", "quedan")
    sustantivo = _pluralizar(intentos_restantes, "intento", "intentos")

    return (
        "Usuario o contraseña incorrectos. Revise que la tecla Bloq "
        f"Mayús no esté activa e intente de nuevo. Le {verbo} "
        f"{intentos_restantes} {sustantivo} antes de que la cuenta se "
        "bloquee 5 minutos."
    )


def _mensaje_bloqueo(cuenta: Cuenta, ahora) -> str:
    segundos_restantes = (cuenta.bloqueada_hasta - ahora).total_seconds()
    minutos_restantes = max(1, math.ceil(segundos_restantes / 60))
    hora_desbloqueo = timezone.localtime(cuenta.bloqueada_hasta)

    otra = _otra_cuenta(cuenta.usuario)
    otro_perfil_display = otra.get_perfil_display() if otra else "otra cuenta"
    sustantivo_minuto = _pluralizar(minutos_restantes, "minuto", "minutos")

    return (
        f"La cuenta «{cuenta.usuario}» está bloqueada por 5 intentos "
        f"fallidos. Podrá intentar de nuevo a las "
        f"{hora_desbloqueo:%H:%M} (en {minutos_restantes} "
        f"{sustantivo_minuto}). Si olvidó la contraseña, pida a la "
        f"{otro_perfil_display} una contraseña temporal desde «Mi "
        "cuenta»."
    )


def generar_contrasena_temporal() -> str:
    """RF-20: contraseña temporal palabra-número-palabra, sin repetir
    la misma palabra dos veces seguidas."""

    primera = secrets.choice(PALABRAS_CONTRASENA_TEMPORAL)
    segunda = secrets.choice(PALABRAS_CONTRASENA_TEMPORAL)

    while segunda == primera:
        segunda = secrets.choice(PALABRAS_CONTRASENA_TEMPORAL)

    numero = f"{secrets.randbelow(10000):04d}"

    return f"{primera}-{numero}-{segunda}"


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
            return Response(
                {"detail": _mensaje_bloqueo(cuenta, ahora)},
                status=status.HTTP_423_LOCKED,
            )

        if not check_password(contrasena, cuenta.hash_contrasena):
            cuenta.intentos_fallidos += 1

            if cuenta.intentos_fallidos >= INTENTOS_MAXIMOS:
                cuenta.bloqueada_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
                cuenta.intentos_fallidos = 0
                cuenta.save(update_fields=["intentos_fallidos", "bloqueada_hasta"])

                return Response(
                    {"detail": _mensaje_bloqueo(cuenta, ahora)},
                    status=status.HTTP_423_LOCKED,
                )

            cuenta.save(update_fields=["intentos_fallidos", "bloqueada_hasta"])
            intentos_restantes = INTENTOS_MAXIMOS - cuenta.intentos_fallidos

            return Response(
                {"detail": _mensaje_intentos_restantes(intentos_restantes)},
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
        repetir = request.data.get("repetir_contrasena")

        if len(nueva) < 8:
            return Response(
                {"nueva_contrasena": ["Debe tener al menos 8 caracteres."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # SUPUESTO (decisión 2 del plan de hoy): el prototipo pide
        # "Repita la contraseña nueva" pero ninguna captura muestra el
        # mensaje de error; se sigue el patrón de RNF-02 (causa y
        # acción).
        if repetir is not None and repetir != nueva:
            return Response(
                {
                    "repetir_contrasena": [
                        "Las contraseñas no coinciden. Vuelva a "
                        "escribirlas iguales.",
                    ],
                },
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


class OtraCuentaView(APIView):
    """
    PAN-14: a quién pertenece "la otra cuenta" (RN-09: hay exactamente
    dos, con los mismos permisos).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        otra = _otra_cuenta(request.user.usuario)

        if otra is None:
            return Response(
                {
                    "detail": (
                        "No se encontró la otra cuenta. Contacte a "
                        "soporte técnico."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "usuario": otra.usuario,
                "perfil": otra.perfil,
                "perfil_display": otra.get_perfil_display(),
            },
        )


class AsignarContrasenaTemporalView(APIView):
    """
    RF-20, la mitad que faltaba: una cuenta le asigna una contraseña
    temporal a la otra (nunca a sí misma). Fuerza el cambio obligatorio
    al entrar (`es_contrasena_temporal=True`) y deja rastro en la
    bitácora (RF-15).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        candidatas = list(
            Cuenta.objects.exclude(id_cuenta=request.user.id_cuenta),
        )

        if len(candidatas) != 1:
            # Defensivo: con las 2 cuentas fijas de RN-09/ADR-05 esto
            # no debería pasar.
            return Response(
                {
                    "detail": (
                        "No se pudo identificar una sola otra cuenta. "
                        "Contacte a soporte técnico."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otra = candidatas[0]
        temporal = generar_contrasena_temporal()

        otra.hash_contrasena = make_password(temporal)
        otra.es_contrasena_temporal = True
        otra.intentos_fallidos = 0
        otra.bloqueada_hasta = None
        otra.save(
            update_fields=[
                "hash_contrasena",
                "es_contrasena_temporal",
                "intentos_fallidos",
                "bloqueada_hasta",
            ],
        )

        # Fuerza el cierre de la sesión que tuviera abierta: su
        # contraseña anterior ya no existe.
        TokenCuenta.objects.filter(cuenta=otra).delete()

        registrar(
            cuenta=request.user,
            accion=AccionBitacora.RESTABLECIMIENTO_CONTRASENA,
            elemento_afectado=f"cuenta.id_cuenta={otra.id_cuenta}",
        )

        return Response(
            {"usuario": otra.usuario, "contrasena_temporal": temporal},
        )
