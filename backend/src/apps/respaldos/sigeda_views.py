"""
PAN-08 (respaldo y restauración) y D-05 (restaurar). RF-16. Mismo
patrón de autenticación que el resto de SIGEDA: `AutenticacionCuenta`/
`CuentaAutenticadaPermission` (apps.accounts.sigeda_auth).
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Cuenta
from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.bitacora.servicio import registrar
from apps.bitacora.models import AccionBitacora
from apps.documents.models import VersionDocumento

from .models import (
    CopiaRespaldo,
    EstadoRespaldo,
    PruebaRestauracion,
    Respaldo,
    ResultadoPruebaRestauracion,
    TipoRespaldo,
)
from .servicio_respaldo import RespaldoError, crear_respaldo
from .servicio_restauracion import RestauracionError, restaurar_respaldo

PALABRA_CONFIRMACION = "RESTAURAR"
MENSAJE_PERFIL_ADMINISTRACION_NO_ENCONTRADO = (
    "No se encontró la cuenta de Administración. Contacte a soporte técnico."
)


def _serializar_copia(copia: CopiaRespaldo) -> dict:
    return {
        "destino": copia.destino,
        "destino_display": copia.get_destino_display(),
        "estado": copia.estado,
        "estado_display": copia.get_estado_display(),
        "fecha_hora_verificacion": copia.fecha_hora_verificacion,
    }


def _serializar_respaldo(respaldo: Respaldo) -> dict:
    return {
        "id_respaldo": respaldo.id_respaldo,
        "fecha_hora": respaldo.fecha_hora,
        "tipo": respaldo.tipo,
        "tipo_display": respaldo.get_tipo_display(),
        "estado": respaldo.estado,
        "estado_display": respaldo.get_estado_display(),
        "nombre_paquete": respaldo.nombre_paquete,
        "hash_sha256": respaldo.hash_sha256,
        "tamano_bytes": respaldo.tamano_bytes,
        "cuenta": respaldo.cuenta.usuario if respaldo.cuenta_id else None,
        "copias": [_serializar_copia(copia) for copia in respaldo.copias.all()],
    }


class RespaldosView(APIView):
    """GET: lista + resumen para la insignia global (PAN-08)."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        respaldos = list(
            Respaldo.objects.prefetch_related("copias").select_related("cuenta")[:30],
        )
        ultimo = respaldos[0] if respaldos else None

        if ultimo is None:
            resumen = {
                "estado": "VACIO",
                "mensaje": "Todavía no se ha hecho ningún respaldo.",
            }
        elif ultimo.estado == EstadoRespaldo.COMPLETO:
            resumen = {
                "estado": EstadoRespaldo.COMPLETO,
                "mensaje": f"Último respaldo completo: {ultimo.fecha_hora:%d/%m/%Y %H:%M}.",
            }
        else:
            resumen = {
                "estado": ultimo.estado,
                "mensaje": (
                    f"El último respaldo ({ultimo.fecha_hora:%d/%m/%Y %H:%M}) "
                    f"quedó {ultimo.get_estado_display().lower()}. Revise la "
                    "lista de respaldos."
                ),
            }

        return Response(
            {
                "resumen": resumen,
                "respaldos": [_serializar_respaldo(r) for r in respaldos],
            },
        )


class RespaldoManualView(APIView):
    """POST: RF-16, botón "Respaldar ahora" de PAN-08."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        try:
            respaldo = crear_respaldo(tipo=TipoRespaldo.MANUAL, cuenta=request.user)
        except RespaldoError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            _serializar_respaldo(respaldo), status=status.HTTP_201_CREATED,
        )


class RestaurarRespaldoView(APIView):
    """
    POST: D-05. Body: `{clave_cifrado, contrasena_administracion,
    confirmacion}`. La contraseña se valida contra la cuenta
    `administracion` en concreto, sin importar qué sesión esté activa
    (igual que pide la ficha de D-05).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, id_respaldo):
        try:
            Respaldo.objects.get(pk=id_respaldo)
        except Respaldo.DoesNotExist:
            return Response(
                {"detail": "El respaldo indicado no existe."}, status=404,
            )

        confirmacion = (request.data.get("confirmacion") or "").strip()

        if confirmacion != PALABRA_CONFIRMACION:
            return Response(
                {
                    "confirmacion": [
                        f'Escriba exactamente la palabra "{PALABRA_CONFIRMACION}" '
                        "para continuar.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        clave_cifrado = request.data.get("clave_cifrado") or ""
        contrasena_administracion = request.data.get("contrasena_administracion") or ""

        if not clave_cifrado:
            return Response(
                {"clave_cifrado": ["Escriba la clave de cifrado del respaldo."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cuenta_administracion = Cuenta.objects.get(perfil="ADMINISTRADORA")
        except Cuenta.DoesNotExist:
            return Response(
                {"detail": MENSAJE_PERFIL_ADMINISTRACION_NO_ENCONTRADO}, status=404,
            )

        if not check_password(
            contrasena_administracion, cuenta_administracion.hash_contrasena,
        ):
            return Response(
                {
                    "contrasena_administracion": [
                        "La contraseña de la cuenta de Administración no es "
                        "correcta.",
                    ],
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            restaurar_respaldo(
                id_respaldo=id_respaldo,
                clave_cifrado_b64=clave_cifrado,
                cuenta_que_autoriza=cuenta_administracion,
            )
        except RestauracionError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "La restauración terminó correctamente."},
        )


class CuarentenaView(APIView):
    """
    GET: compara los archivos físicos del almacén cifrado contra los
    `version_documento.ruta_archivo` reales; lo que sobra es
    "cuarentena" (archivos sin fila asociada en la base, ver
    `apps.documents.cifrado.AlmacenArchivosCifrados`).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        raiz = Path(settings.DOCUMENT_STORAGE_ROOT) / "documentos"

        if not raiz.exists():
            return Response({"archivos": []})

        rutas_registradas = set(
            VersionDocumento.objects.values_list("ruta_archivo", flat=True),
        )
        archivos_en_cuarentena = []

        for ruta in sorted(raiz.iterdir()):
            if ruta.is_file() and ruta.name not in rutas_registradas:
                estadisticas = ruta.stat()
                archivos_en_cuarentena.append(
                    {
                        "nombre_archivo": ruta.name,
                        "tamano_bytes": estadisticas.st_size,
                    },
                )

        return Response({"archivos": archivos_en_cuarentena})


class PruebasRestauracionView(APIView):
    """
    GET/POST: registro manual de la prueba trimestral de restauración
    (tabla propuesta `prueba_restauracion`, SUPUESTO; ver CLAUDE.md
    sección 9).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        pruebas = PruebaRestauracion.objects.select_related("respaldo")[:50]

        return Response(
            [
                {
                    "id_prueba_restauracion": prueba.id_prueba_restauracion,
                    "fecha": prueba.fecha,
                    "respaldo": prueba.respaldo.nombre_paquete,
                    "computadora_usada": prueba.computadora_usada,
                    "resultado": prueba.resultado,
                    "resultado_display": prueba.get_resultado_display(),
                    "observaciones": prueba.observaciones,
                }
                for prueba in pruebas
            ],
        )

    def post(self, request):
        id_respaldo = request.data.get("id_respaldo")
        fecha = request.data.get("fecha")
        computadora_usada = (request.data.get("computadora_usada") or "").strip()
        resultado = request.data.get("resultado")
        observaciones = request.data.get("observaciones") or None

        errores = {}

        try:
            respaldo = Respaldo.objects.get(pk=id_respaldo)
        except (Respaldo.DoesNotExist, ValueError, TypeError):
            errores["id_respaldo"] = ["El respaldo indicado no existe."]
            respaldo = None

        if not fecha:
            errores["fecha"] = ["La fecha de la prueba es obligatoria."]

        if not computadora_usada:
            errores["computadora_usada"] = [
                "Escriba qué computadora se usó para la prueba.",
            ]

        if resultado not in ResultadoPruebaRestauracion.values:
            errores["resultado"] = ["Elija si la prueba fue exitosa o fallida."]

        if errores:
            return Response(errores, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            prueba = PruebaRestauracion.objects.create(
                respaldo=respaldo,
                fecha=fecha,
                computadora_usada=computadora_usada,
                resultado=resultado,
                observaciones=observaciones,
            )
            registrar(
                cuenta=request.user,
                accion=AccionBitacora.CREACION,
                elemento_afectado=(
                    f"prueba_restauracion.id_prueba_restauracion="
                    f"{prueba.id_prueba_restauracion}"
                ),
            )

        return Response(
            {"id_prueba_restauracion": prueba.id_prueba_restauracion},
            status=status.HTTP_201_CREATED,
        )
