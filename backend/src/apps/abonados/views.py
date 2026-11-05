"""
RF-12 Consultar expediente / RN-05 orden del expediente — vista mínima
para comprobar la rebanada vertical de CU-04 (PAN-04).
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.documents.repositorio import RepositorioDocumentos
from apps.documents.serializers import DocumentoExpedienteSerializer

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
