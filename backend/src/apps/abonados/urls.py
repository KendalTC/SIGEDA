from django.urls import path

from .views import (
    AgregarPersonaAsociadaView,
    AltaAbonadoView,
    BuscarAbonadosView,
    BuscarPersonasView,
    CambiarRolPersonaAsociadaView,
    CambiarTitularView,
    DarDeBajaAbonadoView,
    ExpedienteView,
    ModificarAbonadoView,
    QuitarPersonaAsociadaView,
    ReactivarAbonadoView,
)

app_name = "abonados"

urlpatterns = [
    path("buscar/", BuscarAbonadosView.as_view(), name="buscar"),
    path("alta/", AltaAbonadoView.as_view(), name="alta"),
    path("personas/buscar/", BuscarPersonasView.as_view(), name="buscar_personas"),
    path(
        "<str:numero_paja>/expediente/",
        ExpedienteView.as_view(),
        name="expediente",
    ),
    path(
        "<str:numero_paja>/dar-de-baja/",
        DarDeBajaAbonadoView.as_view(),
        name="dar_de_baja",
    ),
    path(
        "<str:numero_paja>/reactivar/",
        ReactivarAbonadoView.as_view(),
        name="reactivar",
    ),
    path(
        "<str:numero_paja>/modificar/",
        ModificarAbonadoView.as_view(),
        name="modificar",
    ),
    path(
        "<str:numero_paja>/cambiar-titular/",
        CambiarTitularView.as_view(),
        name="cambiar_titular",
    ),
    path(
        "<str:numero_paja>/personas/",
        AgregarPersonaAsociadaView.as_view(),
        name="agregar_persona",
    ),
    path(
        "<str:numero_paja>/personas/<int:id_persona>/quitar/",
        QuitarPersonaAsociadaView.as_view(),
        name="quitar_persona",
    ),
    path(
        "<str:numero_paja>/personas/<int:id_persona>/cambiar-rol/",
        CambiarRolPersonaAsociadaView.as_view(),
        name="cambiar_rol_persona",
    ),
]
