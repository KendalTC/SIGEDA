from django.urls import path

from .sigeda_views import (
    CrearGrupoAlternativasView,
    CrearTipoDocumentoView,
    EditarTipoDocumentoView,
    ListarGruposAlternativasView,
    ListarTiposDocumentoAdminView,
    SectoresView,
    TiposDocumentoView,
)

app_name = "sigeda_configuration"

urlpatterns = [
    path("tipos-documento/", TiposDocumentoView.as_view(), name="tipos-documento"),
    path("sectores/", SectoresView.as_view(), name="sectores"),
    # PAN-10 (RF-09): administración de tipos de documento y grupos de
    # alternativas. "tipos-documento/" de arriba queda intacta (combo
    # de PAN-05, solo lectura).
    path(
        "tipos-documento/administracion/",
        ListarTiposDocumentoAdminView.as_view(),
        name="tipos-documento-admin",
    ),
    path(
        "tipos-documento/crear/",
        CrearTipoDocumentoView.as_view(),
        name="tipos-documento-crear",
    ),
    path(
        "tipos-documento/<int:id_tipo_documento>/editar/",
        EditarTipoDocumentoView.as_view(),
        name="tipos-documento-editar",
    ),
    path(
        "grupos-alternativas/",
        ListarGruposAlternativasView.as_view(),
        name="grupos-alternativas",
    ),
    path(
        "grupos-alternativas/crear/",
        CrearGrupoAlternativasView.as_view(),
        name="grupos-alternativas-crear",
    ),
]
