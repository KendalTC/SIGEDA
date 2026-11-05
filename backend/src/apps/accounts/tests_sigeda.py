"""RF-01 Autenticar usuario, RNF-09 (bloqueo y contraseña mínima), RF-20."""

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Cuenta, TokenCuenta


class LoginCuentaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="SECRETARIA",
        )
        self.url = reverse("sigeda_accounts:login")

    def test_login_exitoso_devuelve_token(self):
        respuesta = self.client.post(
            self.url,
            {"usuario": "secretaria", "contrasena": "Correcta2026!"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(TokenCuenta.objects.filter(cuenta=self.cuenta).exists())

    def test_login_fallido_incrementa_intentos(self):
        self.client.post(
            self.url,
            {"usuario": "secretaria", "contrasena": "incorrecta"},
            format="json",
        )

        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.intentos_fallidos, 1)

    def test_bloqueo_tras_cinco_intentos_fallidos(self):
        for _ in range(5):
            self.client.post(
                self.url,
                {"usuario": "secretaria", "contrasena": "incorrecta"},
                format="json",
            )

        self.cuenta.refresh_from_db()
        self.assertIsNotNone(self.cuenta.bloqueada_hasta)
        self.assertGreater(self.cuenta.bloqueada_hasta, timezone.now())

        respuesta = self.client.post(
            self.url,
            {"usuario": "secretaria", "contrasena": "Correcta2026!"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 423)

    def test_login_exitoso_resetea_intentos_fallidos(self):
        self.cuenta.intentos_fallidos = 3
        self.cuenta.save(update_fields=["intentos_fallidos"])

        self.client.post(
            self.url,
            {"usuario": "secretaria", "contrasena": "Correcta2026!"},
            format="json",
        )

        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.intentos_fallidos, 0)


class CambiarContrasenaCuentaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cuenta = Cuenta.objects.create(
            usuario="administracion",
            hash_contrasena=make_password("Temporal2026!"),
            perfil="ADMINISTRADORA",
            es_contrasena_temporal=True,
        )
        self.token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.key}")

    def test_contrasena_nueva_debe_tener_8_caracteres(self):
        respuesta = self.client.post(
            reverse("sigeda_accounts:cambiar-contrasena"),
            {"nueva_contrasena": "corta"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_cambio_exitoso_quita_bandera_temporal(self):
        respuesta = self.client.post(
            reverse("sigeda_accounts:cambiar-contrasena"),
            {"nueva_contrasena": "NuevaClave2026!"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.cuenta.refresh_from_db()
        self.assertFalse(self.cuenta.es_contrasena_temporal)
