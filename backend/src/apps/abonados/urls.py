from django.urls import path

from .views import (
    BuscarAbonadosView,
    DarDeBajaAbonadoView,
    ExpedienteView,
    ReactivarAbonadoView,
)

app_name = "abonados"

urlpatterns = [
    path("buscar/", BuscarAbonadosView.as_view(), name="buscar"),
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
]
