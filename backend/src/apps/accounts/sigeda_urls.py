from django.urls import path

from .sigeda_views import (
    CambiarContrasenaCuentaView,
    LoginCuentaView,
    LogoutCuentaView,
    MeCuentaView,
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
]
