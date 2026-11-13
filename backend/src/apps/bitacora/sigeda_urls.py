from django.urls import path

from .sigeda_views import ConsultarBitacoraView

app_name = "sigeda_bitacora"

urlpatterns = [
    path("", ConsultarBitacoraView.as_view(), name="consultar"),
]
