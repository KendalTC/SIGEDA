from django.urls import path

from .views import (
    ChangeOwnPasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path(
        "me/password/",
        ChangeOwnPasswordView.as_view(),
        name="change-own-password",
    ),
]
