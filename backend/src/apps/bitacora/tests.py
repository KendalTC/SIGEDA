from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Cuenta

from .models import AccionBitacora, OrigenBitacora, RegistroBitacora
from .servicio import registrar


class RegistroBitacoraConstraintsTests(TestCase):
    def setUp(self):
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria_test",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )

    def test_origen_usuaria_requiere_cuenta(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroBitacora.objects.create(
                    cuenta=None,
                    accion=AccionBitacora.CREACION,
                    elemento_afectado="documento.id_documento=1",
                    origen=OrigenBitacora.USUARIA,
                )

    def test_origen_sistema_no_puede_tener_cuenta(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroBitacora.objects.create(
                    cuenta=self.cuenta,
                    accion=AccionBitacora.RESPALDO,
                    elemento_afectado="respaldo.id_respaldo=1",
                    origen=OrigenBitacora.SISTEMA,
                )

    def test_registrar_crea_fila_a_nombre_de_la_cuenta(self):
        registro = registrar(
            cuenta=self.cuenta,
            accion=AccionBitacora.CREACION,
            elemento_afectado="documento.id_documento=1",
            id_abonado=1,
        )

        self.assertEqual(registro.cuenta, self.cuenta)
        self.assertEqual(registro.origen, OrigenBitacora.USUARIA)
