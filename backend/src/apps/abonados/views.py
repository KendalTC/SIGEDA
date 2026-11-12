"""
RF-12 Consultar expediente / RN-05 orden del expediente — vista mínima
para comprobar la rebanada vertical de CU-04 (PAN-04).
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.documents.repositorio import RepositorioDocumentos
from apps.documents.serializers import DocumentoExpedienteSerializer

from . import controlador_busqueda
from .models import Abonado, VinculoAbonado
from .serializers import AbonadoSerializer, VinculoAbonadoSerializer


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

        documentos = RepositorioDocumentos().listar_expediente(
            abonado, incluir_anulados=incluir_anulados,
        )

        personas_vigentes = (
            VinculoAbonado.objects
            .filter(abonado=abonado, fecha_fin__isnull=True)
            .select_related("persona")
            .order_by("rol")
        )

        return Response(
            {
                "abonado": AbonadoSerializer(abonado).data,
                "personas_vigentes": VinculoAbonadoSerializer(
                    personas_vigentes, many=True,
                ).data,
                "documentos": DocumentoExpedienteSerializer(
                    documentos, many=True,
                ).data,
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
