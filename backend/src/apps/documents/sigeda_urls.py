from django.urls import path

from .sigeda_views import (
    AnularDocumentoView,
    CargarDocumentosView,
    DescargarVersionDocumentoView,
    EditarDatosDocumentoView,
    ExportarDocumentosView,
    VersionesDocumentoView,
)

app_name = "sigeda_documents"

urlpatterns = [
    path("cargar/", CargarDocumentosView.as_view(), name="cargar"),
    path("exportar/", ExportarDocumentosView.as_view(), name="exportar"),
    path(
        "<int:id_documento>/anular/",
        AnularDocumentoView.as_view(),
        name="anular",
    ),
    path(
        "<int:id_documento>/editar-datos/",
        EditarDatosDocumentoView.as_view(),
        name="editar_datos",
    ),
    path(
        "<int:id_documento>/versiones/",
        VersionesDocumentoView.as_view(),
        name="versiones",
    ),
    path(
        "<int:id_documento>/versiones/<int:numero_version>/descargar/",
        DescargarVersionDocumentoView.as_view(),
        name="descargar",
    ),
]
