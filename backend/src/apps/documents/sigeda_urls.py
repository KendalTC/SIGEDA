from django.urls import path

from .sigeda_views import (
    CargarDocumentosView,
    DescargarVersionDocumentoView,
    VersionesDocumentoView,
)

app_name = "sigeda_documents"

urlpatterns = [
    path("cargar/", CargarDocumentosView.as_view(), name="cargar"),
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
