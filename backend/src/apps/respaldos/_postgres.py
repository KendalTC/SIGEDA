"""
Credenciales y ejecución de `pg_dump`/`pg_restore` compartidas entre
`servicio_respaldo.py` y `servicio_restauracion.py`. Módulo interno de
`apps.respaldos` (el guión bajo es solo para dejar claro que no es
parte del contrato público de la app).
"""

import os
import subprocess
from pathlib import Path

from django.conf import settings


class ComandoPostgresError(RuntimeError):
    pass


def nombre_base_datos_real() -> str:
    return settings.DATABASES["default"]["NAME"]


def credenciales_postgres() -> dict:
    configuracion = settings.DATABASES["default"]
    return {
        "host": configuracion.get("HOST") or "postgres",
        "port": str(configuracion.get("PORT") or 5432),
        "usuario": configuracion["USER"],
        "clave": configuracion["PASSWORD"],
    }


def entorno_pg(clave: str) -> dict:
    entorno = os.environ.copy()
    entorno["PGPASSWORD"] = clave

    return entorno


def ejecutar(comando: list, *, entorno: dict, entrada: bytes | None = None) -> subprocess.CompletedProcess:
    resultado = subprocess.run(
        comando,
        env=entorno,
        input=entrada,
        capture_output=True,
        check=False,
    )

    if resultado.returncode != 0:
        detalle = (resultado.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ComandoPostgresError(
            f"Falló «{' '.join(comando)}»: {detalle or 'sin detalle de error'}",
        )

    return resultado
