"""
PAN-11 Bitácora (RF-15): consulta con filtros de usuario, fechas,
número de paja y acción. `numero_paja` y `tipo_documento` se resuelven
en lote (una consulta por lista, no una por fila) para no caer en N+1
sobre la página de resultados.
"""

import datetime

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abonados.models import Abonado
from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.documents.models import Documento

from .models import AccionBitacora, RegistroBitacora

LIMITE_DEFECTO = 50


def _parsear_fecha(valor, *, etiqueta):
    """(date, None) si `valor` viene vacío o es una fecha ISO válida;
    (None, Response) con un 400 si no se pudo interpretar."""

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


class ConsultarBitacoraView(APIView):
    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        queryset = RegistroBitacora.objects.select_related("cuenta").prefetch_related(
            "modificaciones",
        )

        usuario = request.query_params.get("usuario")

        if usuario:
            queryset = queryset.filter(cuenta__usuario=usuario)

        fecha_desde, error_desde = _parsear_fecha(
            request.query_params.get("desde"), etiqueta="desde",
        )
        if error_desde is not None:
            return error_desde
        if fecha_desde is not None:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_desde)

        fecha_hasta, error_hasta = _parsear_fecha(
            request.query_params.get("hasta"), etiqueta="hasta",
        )
        if error_hasta is not None:
            return error_hasta
        if fecha_hasta is not None:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_hasta)

        numero_paja = request.query_params.get("numero_paja")

        if numero_paja:
            try:
                abonado = Abonado.objects.get(numero_paja=numero_paja)
            except Abonado.DoesNotExist:
                # RF-15/PAN-11: sin resultados, el frontend ya sabe armar
                # el mensaje con los filtros que él mismo tiene.
                return Response({"total": 0, "resultados": []})

            queryset = queryset.filter(id_abonado=abonado.id_abonado)

        accion = request.query_params.get("accion")

        if accion:
            if accion not in AccionBitacora.values:
                return Response(
                    {
                        "detail": (
                            f"La acción «{accion}» no es válida. Elija una "
                            "opción de la lista."
                        ),
                    },
                    status=400,
                )

            queryset = queryset.filter(accion=accion)

        total = queryset.count()

        try:
            limit = int(request.query_params.get("limit", LIMITE_DEFECTO))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {
                    "detail": (
                        "El límite y el desplazamiento deben ser números "
                        "enteros."
                    ),
                },
                status=400,
            )

        # Meta.ordering de RegistroBitacora ya ordena del más reciente
        # al más antiguo.
        pagina = list(queryset[offset:offset + limit])

        ids_abonado = {
            registro.id_abonado for registro in pagina
            if registro.id_abonado is not None
        }
        pajas_por_id_abonado = dict(
            Abonado.objects.filter(pk__in=ids_abonado).values_list(
                "id_abonado", "numero_paja",
            ),
        )

        ids_documento = set()

        for registro in pagina:
            if registro.elemento_afectado.startswith("documento.id_documento="):
                try:
                    ids_documento.add(
                        int(registro.elemento_afectado.split("=", 1)[1]),
                    )
                except ValueError:
                    pass

        tipos_por_id_documento = {
            documento.id_documento: documento.tipo_documento.nombre
            for documento in Documento.objects.filter(
                pk__in=ids_documento,
            ).select_related("tipo_documento")
        }

        resultados = []

        for registro in pagina:
            tipo_documento = None

            if registro.elemento_afectado.startswith("documento.id_documento="):
                try:
                    id_documento = int(
                        registro.elemento_afectado.split("=", 1)[1],
                    )
                    tipo_documento = tipos_por_id_documento.get(id_documento)
                except ValueError:
                    pass

            resultados.append(
                {
                    "id_registro_bitacora": registro.id_registro_bitacora,
                    "fecha_hora": registro.fecha_hora,
                    "cuenta": registro.cuenta.usuario if registro.cuenta else "Sistema",
                    "accion": registro.accion,
                    "elemento_afectado": registro.elemento_afectado,
                    "numero_paja": pajas_por_id_abonado.get(registro.id_abonado),
                    "tipo_documento": tipo_documento,
                    "modificaciones": [
                        {
                            "campo": modificacion.campo_modificado,
                            "valor_anterior": modificacion.valor_anterior,
                            "valor_nuevo": modificacion.valor_nuevo,
                        }
                        for modificacion in registro.modificaciones.all()
                    ],
                },
            )

        return Response({"total": total, "resultados": resultados})
