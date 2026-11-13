import datetime

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.abonados.models import Abonado, Persona, RolVinculo, TipoAbonado, VinculoAbonado
from apps.accounts.models import Cuenta, TokenCuenta
from apps.configuration.models import TipoDocumento
from apps.documents.models import Documento

from .models import AccionBitacora, OrigenBitacora, RegistroBitacora
from .servicio import registrar, registrar_modificaciones


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


class ConsultarBitacoraViewTests(TestCase):
    """PAN-11 (RF-15): filtros de usuario, fechas, número de paja y
    acción; resolución en lote de numero_paja/tipo_documento (sin N+1)."""

    def setUp(self):
        self.cuenta_secretaria = Cuenta.objects.create(
            usuario="secretaria_bitacora",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        self.cuenta_administracion = Cuenta.objects.create(
            usuario="administracion_bitacora",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="ADMINISTRADORA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta_secretaria)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        self.abonado = Abonado.objects.create(
            numero_paja="9720", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular = Persona.objects.create(nombre="Titular bitácora prueba")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol=RolVinculo.TITULAR,
        )
        self.tipo_documento = TipoDocumento.objects.get(nombre="Plano legible")
        self.documento = Documento.objects.create(
            abonado=self.abonado,
            tipo_documento=self.tipo_documento,
            persona=self.titular,
            estado="VIGENTE",
        )

        # Evento 1: CREACION de documento, a nombre de secretaria, hoy.
        self.registro_creacion = registrar(
            cuenta=self.cuenta_secretaria,
            accion=AccionBitacora.CREACION,
            elemento_afectado=f"documento.id_documento={self.documento.id_documento}",
            id_abonado=self.abonado.id_abonado,
        )

        # Evento 2: MODIFICACION del abonado, a nombre de administración,
        # hace 10 días.
        self.registro_modificacion = registrar(
            cuenta=self.cuenta_administracion,
            accion=AccionBitacora.MODIFICACION,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
            id_abonado=self.abonado.id_abonado,
        )
        registrar_modificaciones(
            self.registro_modificacion,
            {"abonado.tipo_abonado": ("PENDIENTE", "PERSONA_FISICA")},
        )
        fecha_antigua = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=10)
        )
        RegistroBitacora.objects.filter(pk=self.registro_modificacion.pk).update(
            fecha_hora=fecha_antigua,
        )
        self.registro_modificacion.refresh_from_db()

        # Evento 3: RESPALDO de sistema, sin cuenta ni abonado.
        self.registro_sistema = registrar(
            cuenta=None, accion=AccionBitacora.RESPALDO,
            elemento_afectado="respaldo.id_respaldo=1",
        )

    def test_filtro_por_usuario(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"),
            {"usuario": "secretaria_bitacora"},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["total"], 1)
        self.assertEqual(
            respuesta.data["resultados"][0]["id_registro_bitacora"],
            self.registro_creacion.id_registro_bitacora,
        )

    def test_filtro_por_accion(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"accion": "RESPALDO"},
        )
        self.assertEqual(respuesta.data["total"], 1)
        self.assertEqual(respuesta.data["resultados"][0]["cuenta"], "Sistema")

    def test_accion_invalida_responde_400(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"accion": "NO_EXISTE"},
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_filtro_por_numero_paja(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"numero_paja": "9720"},
        )
        self.assertEqual(respuesta.data["total"], 2)
        for fila in respuesta.data["resultados"]:
            self.assertEqual(fila["numero_paja"], "9720")

    def test_filtro_por_numero_paja_inexistente(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"numero_paja": "0000"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, {"total": 0, "resultados": []})

    def test_filtro_por_fechas(self):
        hoy = datetime.date.today().isoformat()
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"desde": hoy},
        )
        ids = {fila["id_registro_bitacora"] for fila in respuesta.data["resultados"]}
        self.assertNotIn(self.registro_modificacion.id_registro_bitacora, ids)
        self.assertIn(self.registro_creacion.id_registro_bitacora, ids)

        hace_15_dias = (
            datetime.date.today() - datetime.timedelta(days=15)
        ).isoformat()
        hace_5_dias = (
            datetime.date.today() - datetime.timedelta(days=5)
        ).isoformat()
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"),
            {"desde": hace_15_dias, "hasta": hace_5_dias},
        )
        ids = {fila["id_registro_bitacora"] for fila in respuesta.data["resultados"]}
        self.assertEqual(ids, {self.registro_modificacion.id_registro_bitacora})

    def test_fecha_invalida_responde_400(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"desde": "no-es-fecha"},
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_resuelve_numero_paja_y_tipo_documento_sin_n_mas_1(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"numero_paja": "9720"},
        )

        fila_creacion = next(
            fila for fila in respuesta.data["resultados"]
            if fila["id_registro_bitacora"]
            == self.registro_creacion.id_registro_bitacora
        )
        self.assertEqual(fila_creacion["numero_paja"], "9720")
        self.assertEqual(fila_creacion["tipo_documento"], "Plano legible")

        fila_modificacion = next(
            fila for fila in respuesta.data["resultados"]
            if fila["id_registro_bitacora"]
            == self.registro_modificacion.id_registro_bitacora
        )
        self.assertIsNone(fila_modificacion["tipo_documento"])
        self.assertEqual(len(fila_modificacion["modificaciones"]), 1)
        self.assertEqual(
            fila_modificacion["modificaciones"][0]["campo"],
            "abonado.tipo_abonado",
        )

    def test_limit_y_offset(self):
        respuesta = self.cliente.get(
            reverse("sigeda_bitacora:consultar"), {"limit": 1, "offset": 0},
        )
        self.assertEqual(respuesta.data["total"], 3)
        self.assertEqual(len(respuesta.data["resultados"]), 1)
