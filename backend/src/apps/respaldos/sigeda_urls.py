from django.urls import path

from .sigeda_views import (
    CuarentenaView,
    PruebasRestauracionView,
    RespaldoManualView,
    RespaldosView,
    RestaurarRespaldoView,
)

app_name = "sigeda_respaldos"

urlpatterns = [
    path("", RespaldosView.as_view(), name="lista"),
    path("manual/", RespaldoManualView.as_view(), name="manual"),
    path(
        "<int:id_respaldo>/restaurar/",
        RestaurarRespaldoView.as_view(),
        name="restaurar",
    ),
    path("cuarentena/", CuarentenaView.as_view(), name="cuarentena"),
    path(
        "pruebas-restauracion/",
        PruebasRestauracionView.as_view(),
        name="pruebas_restauracion",
    ),
]
