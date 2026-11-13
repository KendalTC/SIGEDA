"""
RF-12 Consultar expediente / RN-05 orden del expediente (PAN-04).
RF-11: filtros por tipo, nombre identificador y rango de fechas.
RF-17: baja y reactivación de abonados (D-03).
"""

import datetime

from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar
from apps.documents.repositorio import RepositorioDocumentos
from apps.documents.serializers import DocumentoExpedienteSerializer

from . import controlador_busqueda
from .models import Abonado, EstadoAbonado, RolVinculo, VinculoAbonado
from .serializers import AbonadoSerializer, VinculoAbonadoSerializer


def _parsear_fecha_filtro(valor, *, etiqueta):
    """
    (date, None) si `valor` es una fecha ISO válida o viene vacío;
    (None, Response) con un 400 si no se pudo interpretar.
    """

    if not valor:
        return None, None

    try:
        return datetime.date.fromisoformat(valor), None
    except ValueError:
        return None, Response(
            {
                "detail": (
                    f"La fecha «{valor}» de {etiqueta} no es válida. Use "
                    "el formato aaaa-mm-dd."
                ),
            },
            status=400,
        )


class ExpedienteView(APIView):
    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request, numero_paja):
        try:
            abonado = Abonado.objects.select_related("sector").get(
                numero_paja=numero_paja,
            )
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=404,
            )

        incluir_anulados = (
            request.query_params.get("mostrar_anulados") == "true"
        )

        id_tipo_documento = request.query_params.get("id_tipo_documento")

        if id_tipo_documento is not None and not id_tipo_documento.isdigit():
            return Response(
                {
                    "detail": (
                        f"El tipo de documento «{id_tipo_documento}» no es "
                        "válido. Elija un tipo de la lista."
                    ),
                },
                status=400,
            )

        nombre_identificador = request.query_params.get("nombre_identificador") or None

        fecha_desde, error_desde = _parsear_fecha_filtro(
            request.query_params.get("fecha_desde"), etiqueta="fecha_desde",
        )
        if error_desde is not None:
            return error_desde

        fecha_hasta, error_hasta = _parsear_fecha_filtro(
            request.query_params.get("fecha_hasta"), etiqueta="fecha_hasta",
        )
        if error_hasta is not None:
            return error_hasta

        documentos = RepositorioDocumentos().listar_expediente(
            abonado,
            incluir_anulados=incluir_anulados,
            id_tipo_documento=int(id_tipo_documento) if id_tipo_documento else None,
            nombre_identificador=nombre_identificador,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )

        personas_vigentes = (
            VinculoAbonado.objects
            .filter(abonado=abonado, fecha_fin__isnull=True)
            .select_related("persona")
            .order_by("rol")
        )

        vinculos_titulares_cerrados = (
            VinculoAbonado.objects
            .filter(
                abonado=abonado,
                rol=RolVinculo.TITULAR,
                fecha_fin__isnull=False,
            )
            .select_related("persona")
            .order_by("fecha_inicio")
        )
        personas_titulares_anteriores = {
            v.persona_id for v in vinculos_titulares_cerrados
        }

        return Response(
            {
                "abonado": AbonadoSerializer(abonado).data,
                "personas_vigentes": VinculoAbonadoSerializer(
                    personas_vigentes, many=True,
                ).data,
                "documentos": DocumentoExpedienteSerializer(
                    documentos,
                    many=True,
                    context={
                        "personas_titulares_anteriores": personas_titulares_anteriores,
                    },
                ).data,
                "historial_titulares": VinculoAbonadoSerializer(
                    vinculos_titulares_cerrados, many=True,
                ).data,
            },
        )


class DarDeBajaAbonadoView(APIView):
    """D-03 Dar de baja (RF-17): no borra documentos ni el abonado."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=404,
            )

        if abonado.estado == EstadoAbonado.DE_BAJA:
            return Response(
                {"detail": "Este abonado ya está de baja."}, status=400,
            )

        fecha_baja_bruta = request.data.get("fecha_baja")

        if not fecha_baja_bruta:
            return Response(
                {"fecha_baja": ["La fecha de baja es obligatoria."]},
                status=400,
            )

        try:
            fecha_baja = datetime.date.fromisoformat(fecha_baja_bruta)
        except (ValueError, TypeError):
            return Response(
                {
                    "fecha_baja": [
                        f"La fecha «{fecha_baja_bruta}» no es válida. Use "
                        "el formato aaaa-mm-dd.",
                    ],
                },
                status=400,
            )

        with transaction.atomic():
            abonado.estado = EstadoAbonado.DE_BAJA
            abonado.fecha_baja = fecha_baja
            abonado.save(update_fields=["estado", "fecha_baja"])

            registrar(
                cuenta=request.user,
                accion=AccionBitacora.BAJA,
                elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                id_abonado=abonado.id_abonado,
            )

        return Response(
            {
                "detail": "El abonado quedó de baja.",
                "estado": abonado.estado,
                "fecha_baja": abonado.fecha_baja,
            },
        )


class ReactivarAbonadoView(APIView):
    """D-03 Reactivar (RF-17)."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=404,
            )

        if abonado.estado == EstadoAbonado.ACTIVO:
            return Response(
                {"detail": "Este abonado ya está activo."}, status=400,
            )

        with transaction.atomic():
            abonado.estado = EstadoAbonado.ACTIVO
            abonado.fecha_baja = None
            abonado.save(update_fields=["estado", "fecha_baja"])

            registrar(
                cuenta=request.user,
                accion=AccionBitacora.REACTIVACION,
                elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                id_abonado=abonado.id_abonado,
            )

        return Response(
            {
                "detail": "El abonado quedó activo de nuevo.",
                "estado": abonado.estado,
            },
        )


class BuscarAbonadosView(APIView):
    """RF-10 Buscar expedientes (consulta Q1), para PAN-03."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        numero_paja = request.query_params.get("numero_paja")
        nombre = request.query_params.get("nombre")
        identificacion = request.query_params.get("identificacion")
        id_sector = request.query_params.get("id_sector")
        incluir_baja = request.query_params.get("incluir_baja", "true") != "false"

        if not any([numero_paja, nombre, identificacion, id_sector]):
            return Response(
                {
                    "detail": (
                        "Escriba al menos un criterio de búsqueda: número "
                        "de paja, nombre, identificación o sector."
                    ),
                },
                status=400,
            )

        if id_sector is not None and not id_sector.isdigit():
            return Response(
                {
                    "detail": (
                        f"El sector «{id_sector}» no es válido. Elija un "
                        f"sector de la lista."
                    ),
                },
                status=400,
            )

        resultado = controlador_busqueda.buscar(
            numero_paja=numero_paja,
            nombre=nombre,
            identificacion=identificacion,
            id_sector=int(id_sector) if id_sector else None,
            incluir_baja=incluir_baja,
        )

        return Response(
            {
                "total": resultado.total,
                "mostrados": resultado.mostrados,
                "tiempo_segundos": resultado.tiempo_segundos,
                "resultados": resultado.resultados,
            },
        )
