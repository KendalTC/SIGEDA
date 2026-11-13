from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
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

    def test_accion_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroBitacora.objects.create(
                    cuenta=self.cuenta,
                    accion="INVALIDO",
                    elemento_afectado="documento.id_documento=1",
                    origen=OrigenBitacora.USUARIA,
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


class RevocarUpdateDeleteBitacoraTests(TestCase):
    """
    Migración 0003 (ADR-05, RNF-11): el usuario de BD de la aplicación
    solo debe tener INSERT/SELECT sobre las 3 tablas de bitácora.

    La prueba verifica dos cosas por separado:

    1. Que el `REVOKE` de la migración efectivamente se aplicó en el
       ACL de Postgres (`pg_class.relacl`) — esto es determinista y no
       depende de cómo esté configurado el rol en este entorno.
    2. Que un `UPDATE`/`DELETE` directo realmente falla con el rol de
       la aplicación — esto SÍ depende del entorno: Postgres nunca
       hace cumplir un REVOKE contra un rol superusuario (lo
       confirmamos aparte, con un rol descartable, sin tocar el rol
       real). En este entorno de desarrollo, `POSTGRES_USER` arranca
       como superusuario del clúster (así inicializa la imagen
       oficial de `postgres` cuando se define `POSTGRES_USER`), así
       que esa segunda verificación se salta con un mensaje explícito
       en vez de fallar o de fingir que pasó: separar un rol de
       aplicación no-superusuario del rol de arranque/migraciones es
       una decisión de infraestructura compartida pendiente, fuera de
       esta migración (ver comentario en la migración 0003).
    """

    def test_el_acl_de_postgres_ya_no_tiene_update_ni_delete(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relname, relacl::text FROM pg_class "
                "WHERE relname IN "
                "('registro_bitacora', 'registro_modificacion', "
                "'registro_restauracion');",
            )
            filas = dict(cursor.fetchall())

        usuario = settings.DATABASES["default"]["USER"]

        for tabla, acl in filas.items():
            self.assertIsNotNone(
                acl, f"{tabla} no tiene ACL explícito: la migración no corrió.",
            )
            # Formato típico: {usuario=arDxtm/usuario}. "w" es UPDATE,
            # "d" es DELETE: no deben aparecer en los privilegios del
            # usuario de la aplicación.
            for fragmento in acl.split(","):
                if fragmento.strip("{}").startswith(f"{usuario}="):
                    privilegios = fragmento.split("=", 1)[1].split("/", 1)[0]
                    self.assertNotIn(
                        "w", privilegios,
                        f"{tabla}: {usuario} todavía puede UPDATE.",
                    )
                    self.assertNotIn(
                        "d", privilegios,
                        f"{tabla}: {usuario} todavía puede DELETE.",
                    )
                    break
            else:
                self.fail(f"No se encontró el ACL de {usuario} en {tabla}.")

    def test_update_delete_directo_falla_si_el_rol_no_es_superusuario(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user;")
            (es_superusuario,) = cursor.fetchone()

        if es_superusuario:
            self.skipTest(
                "El usuario de BD de este entorno (POSTGRES_USER) es "
                "superusuario del clúster: Postgres no hace cumplir "
                "ningún REVOKE contra un superusuario, sin importar el "
                "ACL (confirmado aparte con un rol descartable). Separar "
                "un rol de aplicación no-superusuario queda pendiente "
                "como decisión de infraestructura compartida.",
            )

        cuenta = Cuenta.objects.create(
            usuario="administracion_test_revoke",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="ADMINISTRADORA",
        )
        registro = RegistroBitacora.objects.create(
            cuenta=cuenta,
            accion=AccionBitacora.CREACION,
            elemento_afectado="documento.id_documento=999999",
            origen=OrigenBitacora.USUARIA,
        )

        # Cada intento va en su propio SAVEPOINT (transaction.atomic()
        # anidado): si Postgres rechaza el UPDATE/DELETE, solo se
        # revierte ese SAVEPOINT y la prueba puede seguir usando la
        # conexión (igual que el resto de pruebas de CHECK de este
        # repositorio).
        with self.assertRaises(Exception) as contexto_update:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE registro_bitacora SET elemento_afectado = %s "
                        "WHERE id_registro_bitacora = %s;",
                        ["manipulado", registro.id_registro_bitacora],
                    )
        self.assertIn("permission denied", str(contexto_update.exception).lower())

        with self.assertRaises(Exception) as contexto_delete:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM registro_bitacora "
                        "WHERE id_registro_bitacora = %s;",
                        [registro.id_registro_bitacora],
                    )
        self.assertIn("permission denied", str(contexto_delete.exception).lower())
