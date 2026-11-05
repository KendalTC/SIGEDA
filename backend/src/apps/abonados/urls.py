from django.urls import path

from .views import ExpedienteView

app_name = "abonados"

urlpatterns = [
    path(
        "<str:numero_paja>/expediente/",
        ExpedienteView.as_view(),
        name="expediente",
    ),
]
