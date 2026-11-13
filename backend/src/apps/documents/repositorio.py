"""
RepositorioDocumentos (IPersistencia, DAS v1.1): consultas de lectura
sobre `documento`/`version_documento`. RN-05: el expediente se ordena
por prioridad del tipo, luego nombre del tipo, luego id_documento.
"""

from .models import Documento


class RepositorioDocumentos:
    def listar_expediente(
        self,
        abonado,
        *,
        incluir_anulados: bool = False,
        id_tipo_documento=None,
        nombre_identificador: str | None = None,
        fecha_desde=None,
        fecha_hasta=None,
    ):
        """
        Documentos del abonado, ordenados por RN-05 (orden por Meta del
        modelo). RF-11: filtros opcionales por tipo, nombre
        identificador y rango de fechas, contra la fecha_documento de
        la versión vigente de cada documento (no de cualquier
        versión).
        """

        queryset = Documento.objects.select_related(
            "tipo_documento", "persona",
        ).prefetch_related("versiones").filter(abonado=abonado)

        if not incluir_anulados:
            queryset = queryset.exclude(estado="ANULADO")

        if id_tipo_documento:
            queryset = queryset.filter(tipo_documento_id=id_tipo_documento)

        if nombre_identificador:
            queryset = queryset.filter(
                nombre_identificador__icontains=nombre_identificador,
            )

        documentos = list(queryset)

        if fecha_desde or fecha_hasta:
            documentos = [
                documento
                for documento in documentos
                if self._version_vigente_en_rango(documento, fecha_desde, fecha_hasta)
            ]

        return documentos

    @staticmethod
    def _version_vigente_en_rango(documento, fecha_desde, fecha_hasta):
        # Usa las versiones ya traídas por prefetch_related, sin
        # volver a golpear la base de datos.
        versiones = list(documento.versiones.all())

        if not versiones:
            return False

        version_vigente = max(versiones, key=lambda v: v.numero_version)
        fecha = version_vigente.fecha_documento

        if fecha_desde and fecha < fecha_desde:
            return False

        if fecha_hasta and fecha > fecha_hasta:
            return False

        return True

    def obtener_version_vigente(self, documento: Documento):
        return documento.versiones.order_by("-numero_version").first()

    def listar_versiones(self, documento: Documento):
        return documento.versiones.order_by("-numero_version")
