"""
Servicio de respaldo (RF-16, ADR-03): `crear_respaldo()` arma un
paquete completo — dump lógico de PostgreSQL (`pg_dump --format=custom`)
más el árbol del almacén de documentos cifrados (ADR-02) — calcula su
SHA-256 en claro, lo cifra con el mismo `ServicioCifrado` de
`apps.documents.cifrado` (AES-256-GCM, misma clave
`DOCUMENT_ENCRYPTION_KEY_B64`: no se inventa una clave nueva), lo
copia a cada destino configurado y aplica la retención.

El almacén ya guarda cada documento cifrado individualmente (ver
`apps.documents.cifrado.AlmacenArchivosCifrados`): este módulo
re-empaqueta ese árbol tal cual, no vuelve a cifrar archivo por
archivo — por eso el paquete nunca contiene un documento en texto
plano (RNF-10), incluso antes de cifrar el paquete completo.
"""

import hashlib
import os
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar
from apps.documents.cifrado import ServicioCifrado

from ._postgres import (
    ComandoPostgresError,
    credenciales_postgres,
    ejecutar,
    entorno_pg,
    nombre_base_datos_real,
)
from .models import (
    CopiaRespaldo,
    DestinoCopiaRespaldo,
    EstadoCopiaRespaldo,
    EstadoRespaldo,
    Respaldo,
    TipoRespaldo,
)

# Decisión del plan de hoy (Incremento 3a): 7 diarios en "disco
# externo". SUPUESTO pendiente: el modelo no distingue todavía un
# respaldo "diario" de uno "semanal" (`Respaldo.tipo` solo tiene
# AUTOMATICO/MANUAL) — agregar esa distinción es un cambio de modelo
# que requiere avisar antes (CLAUDE.md regla 2), así que la retención
# de "4 semanales" adicionales en disco externo NO está implementada
# todavía; queda como deuda técnica explícita para cuando se decida
# cómo marcar un respaldo como "semanal".
RETENCION_DISCO_EXTERNO = 7
# "La laptop" (decisión 5 del plan, "2 más recientes en la laptop"):
# el Modelo ER v1.1 no tiene un valor de `copia_respaldo.destino` para
# "la laptop" (solo DISCO_EXTERNO/ONEDRIVE) y el paquete se arma en un
# directorio temporal que se borra apenas termina `crear_respaldo` —
# no queda ningún archivo local que retener con la implementación de
# hoy. Esa parte de la decisión 5 queda sin implementar, documentada
# como deuda técnica explícita (no se inventa un tercer destino sin
# avisar, CLAUDE.md regla 2).


class RespaldoError(RuntimeError):
    pass


def _volcar_base_datos(*, ruta_dump: Path, nombre_base_datos: str) -> None:
    creds = credenciales_postgres()
    comando = [
        "pg_dump",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['usuario']}",
        f"--dbname={nombre_base_datos}",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(ruta_dump),
    ]

    try:
        ejecutar(comando, entorno=entorno_pg(creds["clave"]))
    except ComandoPostgresError as exc:
        raise RespaldoError(str(exc)) from exc

    if not ruta_dump.exists() or ruta_dump.stat().st_size == 0:
        raise RespaldoError("El volcado de la base de datos salió vacío.")


def _armar_paquete_sin_cifrar(*, ruta_dump: Path, ruta_paquete: Path) -> None:
    with tarfile.open(ruta_paquete, "w") as tar:
        tar.add(ruta_dump, arcname="database.dump")

        raiz_almacen = Path(settings.DOCUMENT_STORAGE_ROOT)

        if raiz_almacen.exists():
            tar.add(raiz_almacen, arcname="almacen")


def _destinos_configurados() -> dict:
    return {
        DestinoCopiaRespaldo.DISCO_EXTERNO: settings.SIGEDA_BACKUP_DISCO_EXTERNO_DIR,
        DestinoCopiaRespaldo.ONEDRIVE: settings.SIGEDA_BACKUP_ONEDRIVE_DIR,
    }


def _copiar_a_destino(
    *, respaldo: Respaldo, destino: str, directorio: str | None,
    nombre_paquete: str, datos_cifrados: bytes, hash_cifrado_esperado: str,
) -> CopiaRespaldo:
    ahora = timezone.now()

    if not directorio:
        return CopiaRespaldo.objects.create(
            respaldo=respaldo, destino=destino, estado=EstadoCopiaRespaldo.PENDIENTE,
        )

    try:
        directorio_destino = Path(directorio)
        directorio_destino.mkdir(parents=True, exist_ok=True)
        ruta_destino = directorio_destino / nombre_paquete
        ruta_destino.write_bytes(datos_cifrados)

        hash_en_destino = hashlib.sha256(ruta_destino.read_bytes()).hexdigest()
        estado = (
            EstadoCopiaRespaldo.VERIFICADA
            if hash_en_destino == hash_cifrado_esperado
            else EstadoCopiaRespaldo.FALLIDA
        )
    except OSError:
        estado = EstadoCopiaRespaldo.FALLIDA

    return CopiaRespaldo.objects.create(
        respaldo=respaldo,
        destino=destino,
        estado=estado,
        fecha_hora_verificacion=ahora,
    )


def _aplicar_retencion() -> None:
    """
    Decisión 5 del plan de hoy: cuenta filas, no nombres de archivo.
    Por cada destino configurado, conserva los `RETENCION_DISCO_EXTERNO`
    paquetes más recientes y borra el archivo físico + la fila
    `CopiaRespaldo` de los que sobran. La fila `Respaldo` se borra con
    ellos solo si ya no le queda ninguna copia en NINGÚN destino
    configurado (una copia PENDIENTE de un destino sin configurar, p.
    ej. ONEDRIVE cuando todavía no hay licencia confirmada, no cuenta:
    si contara, un respaldo nunca se podría limpiar mientras falte
    configurar ese destino). Nunca toca `registro_bitacora` (ya
    protegida por la migración 0003 de `apps.bitacora`).
    """

    destinos = _destinos_configurados()
    destinos_configurados = [d for d, directorio in destinos.items() if directorio]

    for destino, directorio in destinos.items():
        if not directorio:
            continue

        # Se ordena por la fecha del respaldo (siempre tiene valor),
        # no por fecha_hora_verificacion: esa queda NULL en las copias
        # PENDIENTE (destino sin configurar) y Postgres pondría esos
        # NULL primero en un ORDER BY DESC, protegiéndolos de la
        # retención por error.
        copias_viejas = list(
            CopiaRespaldo.objects.filter(destino=destino)
            .select_related("respaldo")
            .order_by("-respaldo__fecha_hora")[RETENCION_DISCO_EXTERNO:],
        )

        for copia in copias_viejas:
            respaldo = copia.respaldo

            if respaldo.nombre_paquete:
                ruta = Path(directorio) / respaldo.nombre_paquete
                ruta.unlink(missing_ok=True)

            copia.delete()

            if not respaldo.copias.filter(destino__in=destinos_configurados).exists():
                # Las que quedan son PENDIENTE de un destino sin
                # configurar (p. ej. ONEDRIVE): no cuentan para decidir
                # si se retiene el respaldo, pero la FK RESTRICT de
                # copia_respaldo.id_respaldo sí exige borrarlas antes.
                respaldo.copias.all().delete()
                respaldo.delete()


def crear_respaldo(
    *, tipo: str, cuenta=None, nombre_base_datos: str | None = None,
) -> Respaldo:
    """
    Crea un respaldo de tipo `tipo` (TipoRespaldo). `nombre_base_datos`
    permite apuntar el `pg_dump` a una base distinta de la configurada
    en `settings` — se usa para probar `restaurar_respaldo()` (que
    llama a esta función como respaldo preventivo) contra una base de
    Postgres descartable sin tocar la base real.
    """

    nombre_base_datos = nombre_base_datos or nombre_base_datos_real()
    ahora = timezone.now()
    marca_tiempo = ahora.strftime("%Y%m%dT%H%M%S")
    nombre_paquete = f"sigeda-{tipo.lower()}-{marca_tiempo}-{os.urandom(3).hex()}.pkg"

    with tempfile.TemporaryDirectory(prefix="sigeda_respaldo_") as directorio_str:
        directorio_temporal = Path(directorio_str)
        ruta_dump = directorio_temporal / "database.dump"
        _volcar_base_datos(ruta_dump=ruta_dump, nombre_base_datos=nombre_base_datos)

        ruta_paquete_sin_cifrar = directorio_temporal / "paquete.tar"
        _armar_paquete_sin_cifrar(
            ruta_dump=ruta_dump, ruta_paquete=ruta_paquete_sin_cifrar,
        )

        datos_sin_cifrar = ruta_paquete_sin_cifrar.read_bytes()
        hash_sha256 = hashlib.sha256(datos_sin_cifrar).hexdigest()

        datos_cifrados = ServicioCifrado().cifrar(datos_sin_cifrar)
        hash_cifrado = hashlib.sha256(datos_cifrados).hexdigest()
        tamano_bytes = len(datos_cifrados)

    with transaction.atomic():
        respaldo = Respaldo.objects.create(
            cuenta=cuenta,
            tipo=tipo,
            estado=EstadoRespaldo.PENDIENTE,
            nombre_paquete=nombre_paquete,
            hash_sha256=hash_sha256,
            tamano_bytes=tamano_bytes,
        )
        registrar(
            cuenta=cuenta,
            accion=AccionBitacora.RESPALDO,
            elemento_afectado=f"respaldo.id_respaldo={respaldo.id_respaldo}",
        )

    hubo_copia_verificada = False

    for destino, directorio in _destinos_configurados().items():
        copia = _copiar_a_destino(
            respaldo=respaldo,
            destino=destino,
            directorio=directorio,
            nombre_paquete=nombre_paquete,
            datos_cifrados=datos_cifrados,
            hash_cifrado_esperado=hash_cifrado,
        )

        if copia.estado == EstadoCopiaRespaldo.VERIFICADA:
            hubo_copia_verificada = True

    respaldo.estado = (
        EstadoRespaldo.COMPLETO if hubo_copia_verificada else EstadoRespaldo.FALLIDO
    )
    respaldo.save(update_fields=["estado"])

    _aplicar_retencion()

    respaldo.refresh_from_db()

    return respaldo
