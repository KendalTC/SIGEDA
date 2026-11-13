"""
Servicio de restauración (RF-16, D-05, ADR-03): `restaurar_respaldo()`
reemplaza toda la base de datos con el paquete elegido, igual que hace
hoy `scripts/restore.sh` (cerrar conexiones, `dropdb`/`createdb`,
`pg_restore --single-transaction`, sin exclusiones), pero sin perder
la bitácora vigente: antes de tocar nada guarda aparte el contenido
actual de `registro_bitacora`/`registro_modificacion`/
`registro_restauracion`, deja que el `pg_restore` reemplace las 14
tablas tal cual vienen en el paquete, y reinserta lo guardado con
`ON CONFLICT DO NOTHING` (RNF-11: la bitácora queda completa y
continua, nunca se borra nada).

Parámetros de prueba (`nombre_base_datos`, `almacen_destino`): permiten
dirigir las operaciones destructivas de Postgres y del almacén de
documentos hacia una base y un directorio descartables, para poder
probar esta función de verdad sin tocar nunca la base de desarrollo
real `sigeda` ni el almacén de documentos real. El catálogo de
`Respaldo`/`CopiaRespaldo` (bitácora de la propia aplicación) sigue
viviendo siempre en la conexión Django normal (`settings.DATABASES`):
solo el paquete restaurado y su bitácora preservada van a
`nombre_base_datos`.
"""

import hashlib
import io
import tarfile
import tempfile
from pathlib import Path

import psycopg
from django.conf import settings
from django.utils import timezone

from apps.bitacora.models import AccionBitacora
from apps.documents.cifrado import ServicioCifrado

from ._postgres import (
    ComandoPostgresError,
    credenciales_postgres,
    ejecutar,
    entorno_pg,
    nombre_base_datos_real,
)
from .models import Respaldo, TipoRespaldo
from .servicio_respaldo import RespaldoError, crear_respaldo

_TABLAS_BITACORA = ("registro_bitacora", "registro_modificacion", "registro_restauracion")
_BASES_PROTEGIDAS = {"postgres", "template0", "template1"}


class RestauracionError(RuntimeError):
    pass


def _localizar_paquete(respaldo: Respaldo) -> bytes:
    destinos = (
        settings.SIGEDA_BACKUP_DISCO_EXTERNO_DIR,
        settings.SIGEDA_BACKUP_ONEDRIVE_DIR,
    )

    for directorio in destinos:
        if not directorio:
            continue

        ruta = Path(directorio) / respaldo.nombre_paquete

        if ruta.exists():
            return ruta.read_bytes()

    raise RestauracionError(
        f"No se encontró el archivo del respaldo «{respaldo.nombre_paquete}» "
        "en ningún destino configurado.",
    )


def _descifrar_paquete(datos_cifrados: bytes, clave_cifrado_b64: str) -> bytes:
    import base64

    try:
        clave = base64.b64decode(clave_cifrado_b64, validate=True)
    except Exception as exc:
        raise RestauracionError("La clave de cifrado no es correcta.") from exc

    try:
        return ServicioCifrado(clave=clave).descifrar(datos_cifrados)
    except Exception as exc:
        raise RestauracionError("La clave de cifrado no es correcta.") from exc


def _validar_nombre_base_datos(nombre_base_datos: str) -> None:
    if nombre_base_datos in _BASES_PROTEGIDAS:
        raise RestauracionError(
            f"El nombre de base «{nombre_base_datos}» no es seguro para "
            "restauración.",
        )


def _conexion_mantenimiento(creds: dict):
    return psycopg.connect(
        dbname="postgres",
        host=creds["host"],
        port=creds["port"],
        user=creds["usuario"],
        password=creds["clave"],
        autocommit=True,
    )


def _recrear_base_datos(nombre_base_datos: str) -> None:
    """Cierra conexiones y recrea la base, igual que `scripts/restore.sh`
    (ahí en dos pasos: pg_terminate_backend + dropdb/createdb). Postgres
    17 permite hacerlo en un solo DROP DATABASE ... WITH (FORCE)."""

    creds = credenciales_postgres()

    try:
        with _conexion_mantenimiento(creds) as conexion:
            with conexion.cursor() as cursor:
                identificador = psycopg.sql.Identifier(nombre_base_datos)
                cursor.execute(
                    psycopg.sql.SQL(
                        "DROP DATABASE IF EXISTS {} WITH (FORCE);",
                    ).format(identificador),
                )
                cursor.execute(
                    psycopg.sql.SQL(
                        "CREATE DATABASE {} OWNER {} ENCODING 'UTF8';",
                    ).format(identificador, psycopg.sql.Identifier(creds["usuario"])),
                )
    except psycopg.Error as exc:
        raise RestauracionError(
            f"No se pudo recrear la base de datos «{nombre_base_datos}»: {exc}",
        ) from exc


def _restaurar_dump(ruta_dump: Path, nombre_base_datos: str) -> None:
    creds = credenciales_postgres()
    comando = [
        "pg_restore",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['usuario']}",
        f"--dbname={nombre_base_datos}",
        "--exit-on-error",
        "--single-transaction",
        "--no-owner",
        "--no-privileges",
        str(ruta_dump),
    ]

    try:
        ejecutar(comando, entorno=entorno_pg(creds["clave"]))
    except ComandoPostgresError as exc:
        raise RestauracionError(str(exc)) from exc


def _volcar_bitacora_actual(nombre_base_datos: str) -> bytes:
    """pg_dump --data-only --inserts --on-conflict-do-nothing: genera
    INSERT ... ON CONFLICT DO NOTHING listos para reinsertar después
    del pg_restore, sin duplicar lo que el propio respaldo ya trae."""

    creds = credenciales_postgres()
    comando = [
        "pg_dump",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['usuario']}",
        f"--dbname={nombre_base_datos}",
        "--data-only",
        "--inserts",
        "--on-conflict-do-nothing",
        "--format=plain",
    ]

    for tabla in _TABLAS_BITACORA:
        comando.append(f"--table={tabla}")

    try:
        resultado = ejecutar(comando, entorno=entorno_pg(creds["clave"]))
    except ComandoPostgresError as exc:
        raise RestauracionError(
            f"No se pudo guardar la bitácora antes de restaurar: {exc}",
        ) from exc

    return resultado.stdout


def _reinsertar_bitacora(nombre_base_datos: str, sql_bitacora: bytes) -> None:
    if not sql_bitacora.strip():
        return

    creds = credenciales_postgres()

    with psycopg.connect(
        dbname=nombre_base_datos,
        host=creds["host"],
        port=creds["port"],
        user=creds["usuario"],
        password=creds["clave"],
    ) as conexion:
        # pg_dump 17 envuelve el texto plano con `\restrict`/
        # `\unrestrict` (meta-comandos de psql, no SQL válido) como
        # protección contra ejecutar un dump ajeno con `psql -f`. Acá
        # el SQL se ejecuta directo con psycopg, no con psql, así que
        # esas líneas sobran y rompen `cursor.execute`.
        sql_texto = "\n".join(
            linea for linea in sql_bitacora.decode("utf-8").splitlines()
            if not linea.startswith("\\")
        )

        with conexion.cursor() as cursor:
            cursor.execute(sql_texto)

            # El propio dump deja `search_path` vacío
            # (`SELECT pg_catalog.set_config('search_path', '', false)`,
            # lo pone pg_dump desde la versión 17): hay que
            # restablecerlo o la consulta de abajo no encuentra la
            # tabla sin calificar.
            cursor.execute("SET search_path TO public;")

            # El dump restaurado trae su propia secuencia de
            # id_registro_bitacora (calculada sobre SUS filas); al
            # reinsertar filas más nuevas que el respaldo hay que
            # corregirla, o el próximo INSERT del ORM podría chocar
            # con un id ya usado por una fila reinsertada.
            cursor.execute(
                "SELECT setval("
                "  pg_get_serial_sequence('public.registro_bitacora', 'id_registro_bitacora'),"
                "  COALESCE((SELECT MAX(id_registro_bitacora) FROM public.registro_bitacora), 1)"
                ");",
            )
        conexion.commit()


def _registrar_evento_restauracion(
    *, nombre_base_datos: str, respaldo: Respaldo, cuenta_que_autoriza, fecha_respaldo_restaurado,
) -> None:
    """
    Inserta el evento RESTAURACION directo en la base recién restaurada
    (`nombre_base_datos`), no vía el ORM de `apps.bitacora.servicio`:
    el evento pertenece a la bitácora de la base que efectivamente se
    restauró, que en una prueba contra una base descartable no es la
    misma que `settings.DATABASES["default"]` (a la que apunta
    siempre el ORM de Django).
    """

    creds = credenciales_postgres()
    ahora = timezone.now()
    id_cuenta = cuenta_que_autoriza.id_cuenta if cuenta_que_autoriza else None
    origen = "USUARIA" if cuenta_que_autoriza else "SISTEMA"

    with psycopg.connect(
        dbname=nombre_base_datos,
        host=creds["host"],
        port=creds["port"],
        user=creds["usuario"],
        password=creds["clave"],
    ) as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO registro_bitacora "
                "(id_cuenta, fecha_hora, accion, elemento_afectado, origen) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id_registro_bitacora;",
                (
                    id_cuenta,
                    ahora,
                    AccionBitacora.RESTAURACION,
                    f"respaldo.id_respaldo={respaldo.id_respaldo}",
                    origen,
                ),
            )
            (id_registro_bitacora,) = cursor.fetchone()
            cursor.execute(
                "INSERT INTO registro_restauracion "
                "(id_registro_bitacora, nombre_paquete, fecha_respaldo_restaurado) "
                "VALUES (%s, %s, %s);",
                (
                    id_registro_bitacora,
                    respaldo.nombre_paquete,
                    fecha_respaldo_restaurado,
                ),
            )
        conexion.commit()


def restaurar_respaldo(
    *,
    id_respaldo: int,
    clave_cifrado_b64: str,
    cuenta_que_autoriza,
    nombre_base_datos: str | None = None,
    almacen_destino: str | None = None,
) -> None:
    """
    Restaura el respaldo `id_respaldo` sobre `nombre_base_datos` (por
    defecto, la base real configurada en `settings`). Lanza
    `RestauracionError` con un mensaje ya listo para mostrar (RNF-02)
    si la clave no abre el paquete, si el SHA-256 no coincide, o si
    falla cualquier paso de Postgres.
    """

    respaldo = Respaldo.objects.get(pk=id_respaldo)
    nombre_base_datos = nombre_base_datos or nombre_base_datos_real()
    # Igual que `nombre_base_datos`: por defecto, el almacén real
    # configurado en `settings`; las pruebas pasan un directorio
    # descartable aparte para no tocar los documentos reales.
    almacen_destino = almacen_destino or str(settings.DOCUMENT_STORAGE_ROOT)
    _validar_nombre_base_datos(nombre_base_datos)

    datos_cifrados = _localizar_paquete(respaldo)
    datos_planos = _descifrar_paquete(datos_cifrados, clave_cifrado_b64)

    hash_calculado = hashlib.sha256(datos_planos).hexdigest()

    if respaldo.hash_sha256 and hash_calculado != respaldo.hash_sha256:
        raise RestauracionError(
            "El paquete descifrado no coincide con el SHA-256 registrado "
            "para este respaldo. No se restauró nada.",
        )

    # Paso 2 del plan: respaldo preventivo automático antes de tocar
    # nada (ADR-03). Va contra la misma `nombre_base_datos` que se va
    # a reemplazar.
    try:
        crear_respaldo(
            tipo=TipoRespaldo.AUTOMATICO,
            cuenta=cuenta_que_autoriza,
            nombre_base_datos=nombre_base_datos,
        )
    except RespaldoError as exc:
        raise RestauracionError(
            f"No se pudo hacer el respaldo preventivo: {exc}",
        ) from exc

    # Paso 3: guardar aparte la bitácora actual (datos), antes de
    # perder la base que está a punto de ser reemplazada.
    bitacora_guardada = _volcar_bitacora_actual(nombre_base_datos)

    with tempfile.TemporaryDirectory(prefix="sigeda_restauracion_") as directorio_str:
        directorio = Path(directorio_str)

        with tarfile.open(fileobj=io.BytesIO(datos_planos)) as tar:
            nombres = tar.getnames()

            if "database.dump" not in nombres:
                raise RestauracionError(
                    "El paquete no contiene el volcado de la base de datos.",
                )

            tar.extract("database.dump", path=directorio, filter="data")

            miembros_almacen = [
                nombre for nombre in nombres
                if nombre == "almacen" or nombre.startswith("almacen/")
            ]

            if miembros_almacen and almacen_destino:
                destino_almacen = Path(almacen_destino)
                destino_almacen.mkdir(parents=True, exist_ok=True)

                for miembro in tar.getmembers():
                    if miembro.name == "almacen" or miembro.name.startswith("almacen/"):
                        tar.extract(miembro, path=directorio, filter="data")

                origen_extraido = directorio / "almacen"

                if origen_extraido.exists():
                    for ruta in origen_extraido.rglob("*"):
                        if ruta.is_file():
                            destino_archivo = destino_almacen / ruta.relative_to(
                                origen_extraido,
                            )
                            destino_archivo.parent.mkdir(parents=True, exist_ok=True)
                            destino_archivo.write_bytes(ruta.read_bytes())

        ruta_dump = directorio / "database.dump"

        # Paso 4: restaurar el paquete completo tal cual (mismo
        # mecanismo que scripts/restore.sh: cerrar conexiones,
        # dropdb/createdb, pg_restore --single-transaction).
        _recrear_base_datos(nombre_base_datos)
        _restaurar_dump(ruta_dump, nombre_base_datos)

    # Paso 5: reinsertar la bitácora guardada (ON CONFLICT DO NOTHING).
    _reinsertar_bitacora(nombre_base_datos, bitacora_guardada)

    # Paso 6: evento RESTAURACION + registro_restauracion.
    _registrar_evento_restauracion(
        nombre_base_datos=nombre_base_datos,
        respaldo=respaldo,
        cuenta_que_autoriza=cuenta_que_autoriza,
        fecha_respaldo_restaurado=respaldo.fecha_hora,
    )
