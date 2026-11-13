import hashlib
import secrets
import shutil
import tarfile
import tempfile
from pathlib import Path

import psycopg
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Cuenta, TokenCuenta
from apps.bitacora.models import AccionBitacora, OrigenBitacora, RegistroBitacora
from apps.documents.cifrado import ServicioCifrado

from ._postgres import credenciales_postgres
from .models import (
    CopiaRespaldo,
    DestinoCopiaRespaldo,
    EstadoCopiaRespaldo,
    EstadoRespaldo,
    Respaldo,
    TipoRespaldo,
)
from .servicio_respaldo import crear_respaldo
from .servicio_restauracion import restaurar_respaldo


class RespaldoConstraintsTests(TestCase):
    def test_tipo_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Respaldo.objects.create(tipo="INVALIDO", estado="PENDIENTE")

    def test_estado_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Respaldo.objects.create(tipo="AUTOMATICO", estado="INVALIDO")

    def test_tamano_bytes_debe_ser_positivo(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Respaldo.objects.create(
                    tipo="AUTOMATICO", estado="PENDIENTE", tamano_bytes=0,
                )


class CopiaRespaldoConstraintsTests(TestCase):
    def setUp(self):
        self.respaldo = Respaldo.objects.create(tipo="MANUAL", estado="PENDIENTE")

    def test_destino_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CopiaRespaldo.objects.create(
                    respaldo=self.respaldo, destino="INVALIDO", estado="PENDIENTE",
                )

    def test_estado_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CopiaRespaldo.objects.create(
                    respaldo=self.respaldo,
                    destino="DISCO_EXTERNO",
                    estado="INVALIDO",
                )


class CrearRespaldoTests(TestCase):
    """
    `crear_respaldo()` corre de verdad contra `test_sigeda` (la base de
    pruebas aislada que ya crea `TestCase`), nunca contra la base de
    desarrollo `sigeda`: `pg_dump` es de solo lectura de todas formas,
    pero además nunca se le pasa `nombre_base_datos` explícito acá, así
    que usa el valor por defecto, que durante `manage.py test` es
    `test_sigeda` (Django sustituye `settings.DATABASES["default"]["NAME"]`
    mientras corren las pruebas).
    """

    def setUp(self):
        self.directorio_disco_externo = tempfile.mkdtemp(
            prefix="sigeda_prueba_respaldo_disco_externo_",
        )
        self.addCleanup(
            shutil.rmtree, self.directorio_disco_externo, ignore_errors=True,
        )
        self.override = override_settings(
            SIGEDA_BACKUP_DISCO_EXTERNO_DIR=self.directorio_disco_externo,
            SIGEDA_BACKUP_ONEDRIVE_DIR=None,
        )
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_crea_un_paquete_real_cifrado_y_verificable(self):
        respaldo = crear_respaldo(tipo=TipoRespaldo.MANUAL)

        self.assertEqual(respaldo.estado, EstadoRespaldo.COMPLETO)
        self.assertIsNotNone(respaldo.hash_sha256)
        self.assertGreater(respaldo.tamano_bytes, 0)

        ruta_paquete = Path(self.directorio_disco_externo) / respaldo.nombre_paquete
        self.assertTrue(ruta_paquete.exists())

        contenido_en_destino = ruta_paquete.read_bytes()

        # RNF-10: el paquete en disco está cifrado, no es un tar
        # legible ni contiene texto plano reconocible.
        self.assertFalse(tarfile.is_tarfile(ruta_paquete))
        self.assertNotIn(b"database.dump", contenido_en_destino)

        datos_planos = ServicioCifrado().descifrar(contenido_en_destino)
        self.assertEqual(
            hashlib.sha256(datos_planos).hexdigest(), respaldo.hash_sha256,
        )

        with tempfile.TemporaryDirectory() as directorio:
            ruta_tar = Path(directorio) / "paquete.tar"
            ruta_tar.write_bytes(datos_planos)
            with tarfile.open(ruta_tar) as tar:
                nombres = tar.getnames()

        self.assertIn("database.dump", nombres)

        copia_disco = respaldo.copias.get(destino=DestinoCopiaRespaldo.DISCO_EXTERNO)
        self.assertEqual(copia_disco.estado, EstadoCopiaRespaldo.VERIFICADA)
        self.assertIsNotNone(copia_disco.fecha_hora_verificacion)

        copia_onedrive = respaldo.copias.get(destino=DestinoCopiaRespaldo.ONEDRIVE)
        self.assertEqual(copia_onedrive.estado, EstadoCopiaRespaldo.PENDIENTE)

        self.assertTrue(
            RegistroBitacora.objects.filter(
                accion=AccionBitacora.RESPALDO,
                elemento_afectado=f"respaldo.id_respaldo={respaldo.id_respaldo}",
            ).exists(),
        )

    def test_retencion_conserva_solo_los_7_mas_recientes_en_disco_externo(self):
        respaldos = [
            crear_respaldo(tipo=TipoRespaldo.AUTOMATICO) for _ in range(9)
        ]

        self.assertEqual(Respaldo.objects.count(), 7)

        ids_restantes = set(Respaldo.objects.values_list("id_respaldo", flat=True))
        ids_esperados = {r.id_respaldo for r in respaldos[-7:]}
        self.assertEqual(ids_restantes, ids_esperados)

        for respaldo_viejo in respaldos[:2]:
            ruta = Path(self.directorio_disco_externo) / respaldo_viejo.nombre_paquete
            self.assertFalse(ruta.exists())


_DDL_MINIMA_BASE_DESCARTABLE = """
CREATE TABLE cuenta (
    id_cuenta BIGINT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL,
    hash_contrasena VARCHAR(255) NOT NULL
);

CREATE TABLE registro_bitacora (
    id_registro_bitacora BIGSERIAL PRIMARY KEY,
    id_cuenta BIGINT REFERENCES cuenta (id_cuenta),
    id_abonado BIGINT,
    fecha_hora TIMESTAMPTZ NOT NULL,
    accion VARCHAR(30) NOT NULL,
    elemento_afectado VARCHAR(200) NOT NULL,
    origen VARCHAR(10) NOT NULL
);

CREATE TABLE registro_modificacion (
    registro_bitacora_id BIGINT REFERENCES registro_bitacora (id_registro_bitacora),
    campo_modificado VARCHAR(100) NOT NULL,
    valor_anterior TEXT,
    valor_nuevo TEXT,
    PRIMARY KEY (registro_bitacora_id, campo_modificado)
);

CREATE TABLE registro_restauracion (
    id_registro_bitacora BIGINT PRIMARY KEY REFERENCES registro_bitacora (id_registro_bitacora),
    nombre_paquete VARCHAR(200) NOT NULL,
    fecha_respaldo_restaurado TIMESTAMPTZ NOT NULL
);
"""


class RestaurarRespaldoTests(TestCase):
    """
    Caso central del plan de hoy (Incremento 3a, Paso 1e): restaurar
    preservando la bitácora. Corre ÍNTEGRAMENTE contra una base de
    Postgres descartable creada y destruida dentro de esta misma
    prueba (`nombre_base_datos` de `restaurar_respaldo`/`crear_respaldo`)
    — nunca contra `sigeda` (la base de desarrollo real) ni siquiera
    contra `test_sigeda`.

    La base descartable se maneja con `psycopg` crudo (nunca con
    `.using(<alias>)` del ORM de Django): registrar un alias nuevo a
    mitad de una prueba choca con el mecanismo de aislamiento
    multi-base de `TestCase` (que exige declarar `databases` en la
    clase, antes de que el alias exista). No hace falta el esquema
    completo de las 14 tablas para probar el mecanismo de preservar la
    bitácora: basta con `cuenta` + las 3 tablas de bitácora, con los
    mismos nombres `tabla.columna` del Modelo ER v1.1. El catálogo
    `Respaldo`/`CopiaRespaldo` de la propia aplicación sigue viviendo
    en `test_sigeda`, vía el ORM normal (que es donde `crear_respaldo`/
    `restaurar_respaldo` lo escriben siempre).
    """

    def test_restaura_preservando_la_bitacora_y_agrega_el_evento_restauracion(self):
        nombre_base_datos = f"sigeda_prueba_restauracion_{secrets.token_hex(4)}"
        creds = credenciales_postgres()
        directorio_disco_externo = tempfile.mkdtemp(
            prefix="sigeda_prueba_restauracion_disco_externo_",
        )
        # `restaurar_respaldo` usa por defecto el almacén REAL
        # (settings.DOCUMENT_STORAGE_ROOT) para restaurar los
        # documentos, igual que usa la base real por defecto: hay que
        # pasarle un directorio descartable aparte, o esta prueba
        # sobrescribiría el almacén de documentos real.
        directorio_almacen_descartable = tempfile.mkdtemp(
            prefix="sigeda_prueba_restauracion_almacen_",
        )
        base_datos_creada = False

        def _conectar_a_descartable():
            return psycopg.connect(
                dbname=nombre_base_datos, host=creds["host"], port=creds["port"],
                user=creds["usuario"], password=creds["clave"],
            )

        try:
            with override_settings(
                SIGEDA_BACKUP_DISCO_EXTERNO_DIR=directorio_disco_externo,
                SIGEDA_BACKUP_ONEDRIVE_DIR=None,
            ):
                # 1. Crear la base descartable con un esquema mínimo
                # (cuenta + las 3 tablas de bitácora, mismos nombres
                # tabla.columna del Modelo ER v1.1).
                with psycopg.connect(
                    dbname="postgres", host=creds["host"], port=creds["port"],
                    user=creds["usuario"], password=creds["clave"], autocommit=True,
                ) as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            psycopg.sql.SQL(
                                "CREATE DATABASE {} OWNER {} ENCODING 'UTF8';",
                            ).format(
                                psycopg.sql.Identifier(nombre_base_datos),
                                psycopg.sql.Identifier(creds["usuario"]),
                            ),
                        )
                base_datos_creada = True

                with _conectar_a_descartable() as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(_DDL_MINIMA_BASE_DESCARTABLE)
                    conexion.commit()

                # 2. Una cuenta "administración" real en `test_sigeda`
                # (para el catálogo de Respaldo/bitácora de la propia
                # app, por el ORM normal) y, con el MISMO id_cuenta, una
                # fila `cuenta` en la base descartable (para que la FK
                # de registro_bitacora.id_cuenta tenga a quién apuntar
                # allá).
                cuenta_administracion = Cuenta.objects.create(
                    usuario="administracion_prueba_restauracion",
                    hash_contrasena=make_password("Prueba2026!"),
                    perfil="ADMINISTRADORA",
                )

                with _conectar_a_descartable() as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO cuenta (id_cuenta, usuario, hash_contrasena) "
                            "VALUES (%s, %s, %s);",
                            (
                                cuenta_administracion.id_cuenta,
                                cuenta_administracion.usuario,
                                cuenta_administracion.hash_contrasena,
                            ),
                        )

                        # 3. Fila de bitácora que YA existe antes del
                        # respaldo.
                        cursor.execute(
                            "INSERT INTO registro_bitacora "
                            "(id_cuenta, fecha_hora, accion, elemento_afectado, origen) "
                            "VALUES (%s, now(), %s, %s, %s) "
                            "RETURNING id_registro_bitacora;",
                            (
                                cuenta_administracion.id_cuenta,
                                AccionBitacora.CREACION,
                                "documento.id_documento=1",
                                OrigenBitacora.USUARIA,
                            ),
                        )
                        (id_registro_previo,) = cursor.fetchone()
                    conexion.commit()

                respaldo = crear_respaldo(
                    tipo=TipoRespaldo.MANUAL,
                    cuenta=cuenta_administracion,
                    nombre_base_datos=nombre_base_datos,
                )

                # 4. Fila agregada DESPUÉS del respaldo y ANTES de
                # restaurar: debe sobrevivir completa a la restauración
                # (RNF-11, "caso central" del plan).
                with _conectar_a_descartable() as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO registro_bitacora "
                            "(id_cuenta, fecha_hora, accion, elemento_afectado, origen) "
                            "VALUES (%s, now(), %s, %s, %s) "
                            "RETURNING id_registro_bitacora;",
                            (
                                cuenta_administracion.id_cuenta,
                                AccionBitacora.CREACION,
                                "documento.id_documento=2",
                                OrigenBitacora.USUARIA,
                            ),
                        )
                        (id_registro_posterior,) = cursor.fetchone()
                    conexion.commit()

                clave_cifrado_b64 = settings.DOCUMENT_ENCRYPTION_KEY_B64

                # 5. Restaurar, contra la base descartable.
                restaurar_respaldo(
                    id_respaldo=respaldo.id_respaldo,
                    clave_cifrado_b64=clave_cifrado_b64,
                    cuenta_que_autoriza=cuenta_administracion,
                    nombre_base_datos=nombre_base_datos,
                    almacen_destino=directorio_almacen_descartable,
                )

                # 6. La fila previa (ya venía en el respaldo) y la
                # posterior (agregada después) siguen las dos ahí.
                with _conectar_a_descartable() as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            "SELECT id_registro_bitacora FROM registro_bitacora "
                            "WHERE id_registro_bitacora IN (%s, %s);",
                            (id_registro_previo, id_registro_posterior),
                        )
                        ids_presentes = {fila[0] for fila in cursor.fetchall()}

                self.assertIn(
                    id_registro_previo, ids_presentes,
                    "Se perdió la fila de bitácora que ya traía el respaldo.",
                )
                self.assertIn(
                    id_registro_posterior, ids_presentes,
                    "Se perdió la fila agregada después del respaldo y "
                    "antes de restaurar.",
                )

                # 7. Encima, el nuevo evento RESTAURACION.
                with _conectar_a_descartable() as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            "SELECT b.id_registro_bitacora, r.nombre_paquete "
                            "FROM registro_bitacora b "
                            "JOIN registro_restauracion r "
                            "ON r.id_registro_bitacora = b.id_registro_bitacora "
                            "WHERE b.accion = %s;",
                            (AccionBitacora.RESTAURACION,),
                        )
                        eventos_restauracion = cursor.fetchall()

                self.assertEqual(len(eventos_restauracion), 1)
                self.assertEqual(eventos_restauracion[0][1], respaldo.nombre_paquete)

                # 8. Una fila nueva sigue pudiendo insertarse sin
                # chocar con la secuencia (quedó corregida tras
                # reinsertar la bitácora guardada).
                with _conectar_a_descartable() as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO registro_bitacora "
                            "(id_cuenta, fecha_hora, accion, elemento_afectado, origen) "
                            "VALUES (%s, now(), %s, %s, %s);",
                            (
                                cuenta_administracion.id_cuenta,
                                AccionBitacora.CREACION,
                                "documento.id_documento=3",
                                OrigenBitacora.USUARIA,
                            ),
                        )
                    conexion.commit()
        finally:
            if base_datos_creada:
                with psycopg.connect(
                    dbname="postgres", host=creds["host"], port=creds["port"],
                    user=creds["usuario"], password=creds["clave"], autocommit=True,
                ) as conexion:
                    with conexion.cursor() as cursor:
                        cursor.execute(
                            psycopg.sql.SQL(
                                "DROP DATABASE IF EXISTS {} WITH (FORCE);",
                            ).format(psycopg.sql.Identifier(nombre_base_datos)),
                        )

            shutil.rmtree(directorio_disco_externo, ignore_errors=True)
            shutil.rmtree(directorio_almacen_descartable, ignore_errors=True)


class RestaurarRespaldoVistaTests(TestCase):
    """1d: la vista valida la palabra de confirmación y la contraseña
    de Administración antes de llamar a `restaurar_respaldo`."""

    def setUp(self):
        self.cuenta_secretaria = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Secretaria2026!"),
            perfil="SECRETARIA",
        )
        self.cuenta_administracion = Cuenta.objects.create(
            usuario="administracion",
            hash_contrasena=make_password("Administracion2026!"),
            perfil="ADMINISTRADORA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta_secretaria)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
        self.respaldo = Respaldo.objects.create(
            tipo=TipoRespaldo.MANUAL,
            estado=EstadoRespaldo.COMPLETO,
            nombre_paquete="sigeda-manual-prueba.pkg",
            hash_sha256="0" * 64,
            tamano_bytes=10,
        )

    def test_rechaza_sin_la_palabra_de_confirmacion(self):
        respuesta = self.cliente.post(
            reverse("sigeda_respaldos:restaurar", args=[self.respaldo.id_respaldo]),
            {
                "clave_cifrado": "x",
                "contrasena_administracion": "Administracion2026!",
                "confirmacion": "restaurar",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_rechaza_con_la_contrasena_de_administracion_incorrecta(self):
        respuesta = self.cliente.post(
            reverse("sigeda_respaldos:restaurar", args=[self.respaldo.id_respaldo]),
            {
                "clave_cifrado": "x",
                "contrasena_administracion": "incorrecta",
                "confirmacion": "RESTAURAR",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_valida_la_contrasena_de_administracion_sin_importar_la_sesion_activa(self):
        # La sesión activa es la de "secretaria" (ver setUp), pero la
        # contraseña se valida contra "administracion" de todas formas.
        self.assertTrue(
            check_password(
                "Administracion2026!", self.cuenta_administracion.hash_contrasena,
            ),
        )
        respuesta = self.cliente.post(
            reverse("sigeda_respaldos:restaurar", args=[self.respaldo.id_respaldo]),
            {
                "clave_cifrado": "x",
                "contrasena_administracion": "Secretaria2026!",
                "confirmacion": "RESTAURAR",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)


class RespaldosVistaTests(TestCase):
    """PAN-08: lista + resumen, y el botón "Respaldar ahora" (RF-16)."""

    def setUp(self):
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Secretaria2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

    def test_lista_vacia_devuelve_resumen_vacio(self):
        respuesta = self.cliente.get(reverse("sigeda_respaldos:lista"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["resumen"]["estado"], "VACIO")
        self.assertEqual(respuesta.data["respaldos"], [])

    def test_rechaza_sin_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.get(reverse("sigeda_respaldos:lista"))

        # CuentaAutenticadaPermission no define authenticate_header,
        # así que DRF responde 403 (no 401) sin encabezado de sesión,
        # igual que el resto de los endpoints de SIGEDA.
        self.assertEqual(respuesta.status_code, 403)

    def test_respaldo_manual_crea_un_respaldo_real(self):
        directorio_disco_externo = tempfile.mkdtemp(
            prefix="sigeda_prueba_vista_manual_",
        )
        self.addCleanup(
            shutil.rmtree, directorio_disco_externo, ignore_errors=True,
        )

        with override_settings(
            SIGEDA_BACKUP_DISCO_EXTERNO_DIR=directorio_disco_externo,
            SIGEDA_BACKUP_ONEDRIVE_DIR=None,
        ):
            respuesta = self.cliente.post(reverse("sigeda_respaldos:manual"))

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["estado"], EstadoRespaldo.COMPLETO)
        self.assertEqual(Respaldo.objects.count(), 1)


class PruebasRestauracionVistaTests(TestCase):
    """CRUD simple de `prueba_restauracion` (tabla propuesta, SUPUESTO)."""

    def setUp(self):
        self.cuenta = Cuenta.objects.create(
            usuario="administracion",
            hash_contrasena=make_password("Administracion2026!"),
            perfil="ADMINISTRADORA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
        self.respaldo = Respaldo.objects.create(
            tipo=TipoRespaldo.MANUAL,
            estado=EstadoRespaldo.COMPLETO,
            nombre_paquete="sigeda-manual-prueba.pkg",
            hash_sha256="0" * 64,
            tamano_bytes=10,
        )

    def test_registra_una_prueba_de_restauracion(self):
        respuesta = self.cliente.post(
            reverse("sigeda_respaldos:pruebas_restauracion"),
            {
                "id_respaldo": self.respaldo.id_respaldo,
                "fecha": "2026-11-13",
                "computadora_usada": "Laptop de pruebas",
                "resultado": "EXITOSA",
                "observaciones": "Restauración de prueba trimestral.",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)

        respuesta_lista = self.cliente.get(
            reverse("sigeda_respaldos:pruebas_restauracion"),
        )
        self.assertEqual(len(respuesta_lista.data), 1)
        self.assertEqual(respuesta_lista.data[0]["resultado"], "EXITOSA")

    def test_rechaza_sin_computadora_usada(self):
        respuesta = self.cliente.post(
            reverse("sigeda_respaldos:pruebas_restauracion"),
            {
                "id_respaldo": self.respaldo.id_respaldo,
                "fecha": "2026-11-13",
                "computadora_usada": "",
                "resultado": "EXITOSA",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)


class CuarentenaVistaTests(TestCase):
    def setUp(self):
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Secretaria2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

    def test_sin_almacen_devuelve_lista_vacia(self):
        with override_settings(
            DOCUMENT_STORAGE_ROOT=tempfile.mkdtemp(prefix="sigeda_prueba_cuarentena_"),
        ):
            respuesta = self.cliente.get(reverse("sigeda_respaldos:cuarentena"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["archivos"], [])
