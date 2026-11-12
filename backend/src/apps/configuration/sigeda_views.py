from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abonados.models import Sector
from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission

from .models import TipoDocumento


class TiposDocumentoView(APIView):
    """RF-09: catálogo de tipos de documento, para el formulario de PAN-05."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        tipos = TipoDocumento.objects.order_by("prioridad", "nombre")

        return Response(
            [
                {
                    "id_tipo_documento": tipo.id_tipo_documento,
                    "nombre": tipo.nombre,
                    "prioridad": tipo.prioridad,
                }
                for tipo in tipos
            ],
        )


class SectoresView(APIView):
    """Catálogo de sectores, para el filtro de PAN-03."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        sectores = Sector.objects.order_by("nombre")

        return Response(
            [
                {"id_sector": sector.id_sector, "nombre": sector.nombre}
                for sector in sectores
            ],
        )
