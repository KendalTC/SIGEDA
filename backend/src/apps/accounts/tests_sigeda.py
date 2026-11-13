"""RF-01 Autenticar usuario, RNF-09 (bloqueo y contraseña mínima), RF-20."""

from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bitacora.models import AccionBitacora, RegistroBitacora

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


class CuentaConstraintsTests(TestCase):
    def test_perfil_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cuenta.objects.create(
                    usuario="invalida",
                    hash_contrasena=make_password("Correcta2026!"),
                    perfil="INVALIDO",
                )


class LoginMensajesDinamicosTests(TestCase):
    """1a: intentos restantes y bloqueo con mensajes reales, no genéricos."""

    def setUp(self):
        self.client = APIClient()
        self.secretaria = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="SECRETARIA",
        )
        self.administracion = Cuenta.objects.create(
            usuario="administracion",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="ADMINISTRADORA",
        )
        self.url = reverse("sigeda_accounts:login")

    def _fallar(self, veces):
        respuesta = None

        for _ in range(veces):
            respuesta = self.client.post(
                self.url,
                {"usuario": "secretaria", "contrasena": "incorrecta"},
                format="json",
            )

        return respuesta

    def test_mensaje_intentos_restantes_es_plural_en_el_primer_fallo(self):
        respuesta = self._fallar(1)

        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("Le quedan 4 intentos", respuesta.data["detail"])
        self.assertNotIn("intento(s)", respuesta.data["detail"])

    def test_mensaje_intentos_restantes_es_singular_en_el_cuarto_fallo(self):
        respuesta = self._fallar(4)

        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("Le queda 1 intento ", respuesta.data["detail"])
        self.assertNotIn("1 intentos", respuesta.data["detail"])

    def test_mensaje_de_bloqueo_incluye_hora_minutos_y_otra_cuenta(self):
        respuesta = self._fallar(5)

        self.secretaria.refresh_from_db()
        self.assertEqual(respuesta.status_code, 423)

        detalle = respuesta.data["detail"]
        hora_desbloqueo = timezone.localtime(self.secretaria.bloqueada_hasta)

        self.assertIn("«secretaria»", detalle)
        self.assertIn(f"{hora_desbloqueo:%H:%M}", detalle)
        self.assertIn("5 minutos", detalle)
        self.assertIn("Administración", detalle)
        self.assertNotIn("minuto(s)", detalle)

    def test_mensaje_de_bloqueo_al_reintentar_ya_bloqueada(self):
        self._fallar(5)

        respuesta = self.client.post(
            self.url,
            {"usuario": "secretaria", "contrasena": "Correcta2026!"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 423)
        self.assertIn("está bloqueada por 5 intentos fallidos", respuesta.data["detail"])


class OtraCuentaViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.secretaria = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="SECRETARIA",
        )
        self.administracion = Cuenta.objects.create(
            usuario="administracion",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="ADMINISTRADORA",
        )
        self.token = TokenCuenta.objects.create(cuenta=self.secretaria)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.key}")

    def test_devuelve_la_cuenta_que_no_es_la_propia(self):
        respuesta = self.client.get(reverse("sigeda_accounts:otra-cuenta"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["usuario"], "administracion")
        self.assertEqual(respuesta.data["perfil_display"], "Administración")


class AsignarContrasenaTemporalTests(TestCase):
    """1c: RF-20, la mitad que faltaba."""

    def setUp(self):
        self.client = APIClient()
        self.secretaria = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="SECRETARIA",
        )
        self.administracion = Cuenta.objects.create(
            usuario="administracion",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="ADMINISTRADORA",
        )
        self.token_secretaria = TokenCuenta.objects.create(cuenta=self.secretaria)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.token_secretaria.key}",
        )
        self.url = reverse("sigeda_accounts:asignar-contrasena-temporal")

    def test_solo_afecta_a_la_otra_cuenta_nunca_a_quien_la_pide(self):
        respuesta = self.client.post(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["usuario"], "administracion")

        temporal = respuesta.data["contrasena_temporal"]
        self.administracion.refresh_from_db()
        self.secretaria.refresh_from_db()

        self.assertTrue(check_password(temporal, self.administracion.hash_contrasena))
        self.assertTrue(self.administracion.es_contrasena_temporal)

        # La que pidió el cambio no se toca.
        self.assertTrue(
            check_password("Correcta2026!", self.secretaria.hash_contrasena),
        )
        self.assertFalse(self.secretaria.es_contrasena_temporal)

    def test_borra_el_token_de_la_otra_cuenta(self):
        token_administracion = TokenCuenta.objects.create(cuenta=self.administracion)

        self.client.post(self.url)

        self.assertFalse(
            TokenCuenta.objects.filter(key=token_administracion.key).exists(),
        )
        # El token de quien la pidió sigue vivo.
        self.assertTrue(
            TokenCuenta.objects.filter(key=self.token_secretaria.key).exists(),
        )

    def test_la_contrasena_nueva_sirve_para_entrar(self):
        respuesta = self.client.post(self.url)
        temporal = respuesta.data["contrasena_temporal"]

        self.client.credentials()  # sin token: login no lleva autenticación
        respuesta_login = self.client.post(
            reverse("sigeda_accounts:login"),
            {"usuario": "administracion", "contrasena": temporal},
            format="json",
        )

        self.assertEqual(respuesta_login.status_code, 200)
        self.assertTrue(respuesta_login.data["cuenta"]["es_contrasena_temporal"])

    def test_queda_registrada_en_la_bitacora(self):
        self.client.post(self.url)

        self.assertTrue(
            RegistroBitacora.objects.filter(
                cuenta=self.secretaria,
                accion=AccionBitacora.RESTABLECIMIENTO_CONTRASENA,
                elemento_afectado=f"cuenta.id_cuenta={self.administracion.id_cuenta}",
            ).exists(),
        )


class CambiarContrasenaRepetirTests(TestCase):
    """1d: confirmación por duplicado."""

    def setUp(self):
        self.client = APIClient()
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="SECRETARIA",
        )
        self.token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.key}")
        self.url = reverse("sigeda_accounts:cambiar-contrasena")

    def test_rechaza_si_no_coinciden(self):
        respuesta = self.client.post(
            self.url,
            {
                "contrasena_actual": "Correcta2026!",
                "nueva_contrasena": "NuevaClave2026!",
                "repetir_contrasena": "OtraDistinta2026!",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("repetir_contrasena", respuesta.data)

        self.cuenta.refresh_from_db()
        self.assertTrue(check_password("Correcta2026!", self.cuenta.hash_contrasena))

    def test_acepta_si_coinciden(self):
        respuesta = self.client.post(
            self.url,
            {
                "contrasena_actual": "Correcta2026!",
                "nueva_contrasena": "NuevaClave2026!",
                "repetir_contrasena": "NuevaClave2026!",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)


class InactividadTokenTests(TestCase):
    """1e: RNF-09, cierre de sesión real en el servidor tras 15 min."""

    def setUp(self):
        self.client = APIClient()
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Correcta2026!"),
            perfil="SECRETARIA",
        )
        self.token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.key}")
        self.url = reverse("sigeda_accounts:me")

    def _forzar_ultima_actividad(self, hace):
        # `.update()` no dispara `auto_now`, a diferencia de `.save()`:
        # así se puede simular una marca vieja de verdad.
        TokenCuenta.objects.filter(key=self.token.key).update(
            ultima_actividad=timezone.now() - hace,
        )

    def test_token_con_mas_de_15_minutos_de_inactividad_expira(self):
        # NOTA: `AutenticacionCuenta` no define `authenticate_header`,
        # igual que ya pasaba antes de este cambio (ver
        # `apps.abonados.tests.BuscarAbonadosViewTests.test_requiere_autenticacion`,
        # que ya asumía 403 para una sesión no autenticada) — DRF
        # devuelve 403 en vez de 401 para cualquier `AuthenticationFailed`
        # de este backend. Se documenta así para no romper esa
        # convención ya establecida en el resto del proyecto.
        self._forzar_ultima_actividad(timedelta(minutes=16))

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("inactividad", respuesta.data["detail"])
        self.assertFalse(TokenCuenta.objects.filter(key=self.token.key).exists())

    def test_token_todavia_vigente_se_refresca_en_vez_de_expirar(self):
        self._forzar_ultima_actividad(timedelta(minutes=5))

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        token = TokenCuenta.objects.get(key=self.token.key)
        self.assertLess(
            timezone.now() - token.ultima_actividad, timedelta(seconds=10),
        )
