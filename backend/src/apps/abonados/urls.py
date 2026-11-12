from django.urls import path

from .views import BuscarAbonadosView, ExpedienteView

app_name = "abonados"

urlpatterns = [
    path("buscar/", BuscarAbonadosView.as_view(), name="buscar"),
    path(
        "<str:numero_paja>/expediente/",
        ExpedienteView.as_view(),
        name="expediente",
    ),
]
