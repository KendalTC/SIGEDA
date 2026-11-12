from django.urls import path

from .sigeda_views import SectoresView, TiposDocumentoView

app_name = "sigeda_configuration"

urlpatterns = [
    path("tipos-documento/", TiposDocumentoView.as_view(), name="tipos-documento"),
    path("sectores/", SectoresView.as_view(), name="sectores"),
]
