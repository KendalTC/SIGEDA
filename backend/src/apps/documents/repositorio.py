"""
RepositorioDocumentos (IPersistencia, DAS v1.1): consultas de lectura
sobre `documento`/`version_documento`. RN-05: el expediente se ordena
por prioridad del tipo, luego nombre del tipo, luego id_documento.
"""

from .models import Documento


class RepositorioDocumentos:
    def listar_expediente(self, abonado, *, incluir_anulados: bool = False):
        """Documentos del abonado, ordenados por RN-05 (orden por Meta del modelo)."""

        queryset = Documento.objects.select_related(
            "tipo_documento", "persona",
        ).prefetch_related("versiones").filter(abonado=abonado)

        if not incluir_anulados:
            queryset = queryset.exclude(estado="ANULADO")

        return queryset

    def obtener_version_vigente(self, documento: Documento):
        return documento.versiones.order_by("-numero_version").first()

    def listar_versiones(self, documento: Documento):
        return documento.versiones.order_by("-numero_version")
