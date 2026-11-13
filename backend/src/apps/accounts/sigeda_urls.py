from django.urls import path

from .sigeda_views import (
    AsignarContrasenaTemporalView,
    CambiarContrasenaCuentaView,
    LoginCuentaView,
    LogoutCuentaView,
    MeCuentaView,
    OtraCuentaView,
)

app_name = "sigeda_accounts"

urlpatterns = [
    path("login/", LoginCuentaView.as_view(), name="login"),
    path("logout/", LogoutCuentaView.as_view(), name="logout"),
    path("me/", MeCuentaView.as_view(), name="me"),
    path(
        "cambiar-contrasena/",
        CambiarContrasenaCuentaView.as_view(),
        name="cambiar-contrasena",
    ),
    path("otra-cuenta/", OtraCuentaView.as_view(), name="otra-cuenta"),
    path(
        "asignar-contrasena-temporal/",
        AsignarContrasenaTemporalView.as_view(),
        name="asignar-contrasena-temporal",
    ),
]
