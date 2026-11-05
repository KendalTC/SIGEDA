from django.urls import path

from .sigeda_views import TiposDocumentoView

app_name = "sigeda_configuration"

urlpatterns = [
    path("tipos-documento/", TiposDocumentoView.as_view(), name="tipos-documento"),
]
