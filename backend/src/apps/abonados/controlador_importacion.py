"""
ControladorImportacion (RF-04 Importar listado de SADA, PAN-09, ADR-04).

Dos pasos, dos llamadas (decisión del 13/11/2026, ver el plan): la
vista previa parsea el archivo y muestra columnas + ejemplo, sin
guardar nada; la importación manda el archivo otra vez + el mapeo de
columnas elegido y crea todo en una sola transacción para el lote
completo. SADA no exporta identificación: la persona se crea solo con
el nombre (`tipo_identificacion`/`identificacion` quedan en NULL,
igual que permite el Modelo ER v1.1), a diferencia del alta manual
(RF-02) que sí la exige.
"""

import datetime
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar, registrar_modificaciones

from .importacion.lectores import ArchivoImportacionError, elegir_lector
from .models import Abonado, Persona, RolVinculo, TipoAbonado, VinculoAbonado

__all__ = [
    "ArchivoImportacionError",
    "FilaRechazada",
    "ResultadoImportacion",
    "ResultadoVistaPrevia",
    "generar_vista_previa",
    "importar_lote",
]


@dataclass
class ResultadoVistaPrevia:
    columnas: list[str]
    ejemplo_fila_2: list[str] | None
    total_filas: int


@dataclass
class FilaRechazada:
    fila: int
    problema: str
    que_hacer: str


@dataclass
class ResultadoImportacion:
    importados: int
    omitidos: int
    rechazados: list[FilaRechazada]
    fecha: datetime.date


def generar_vista_previa(archivo) -> ResultadoVistaPrevia:
    """Paso 2 de PAN-09 ("revisar columnas"): no guarda nada."""

    lector = elegir_lector(archivo.name)
    columnas, filas = lector.leer_filas(archivo)

    return ResultadoVistaPrevia(
        columnas=columnas,
        ejemplo_fila_2=filas[0] if filas else None,
        total_filas=len(filas),
    )


def _indice_columna(columnas: list[str], nombre_columna: str) -> int | None:
    try:
        return columnas.index(nombre_columna)
    except ValueError:
        return None


def _valor_columna(fila: list[str], indice: int) -> str:
    return fila[indice].strip() if indice < len(fila) else ""


def _validar_paja(valor_bruto: str) -> tuple[str | None, str | None, str | None]:
    """
    (paja, problema, qué_hacer). `problema` es `None` cuando la paja
    viene limpia (RN-01: solo dígitos, sin espacios).
    """

    valor = (valor_bruto or "").strip()

    if not valor:
        return (
            None,
            "No tiene número de paja.",
            "Agregue el número de paja en SADA y vuelva a importar.",
        )

    if any(ch.isspace() for ch in valor):
        return (
            None,
            f"Número de paja con espacios («{valor}»).",
            "Corríjalo en SADA y vuelva a importar.",
        )

    if not valor.isdigit():
        return (
            None,
            f"El número de paja «{valor}» no son solo números.",
            "Corríjalo en SADA y vuelva a importar.",
        )

    return valor, None, None


def importar_lote(
    *, archivo, columna_paja: str, columna_nombre: str, cuenta,
) -> ResultadoImportacion:
    """
    Paso 3 de PAN-09 ("importar"): crea un abonado (tipo PENDIENTE) +
    persona (solo nombre) + vínculo TITULAR por cada fila válida con
    paja no registrada, todo en una sola transacción para el archivo
    completo. Un solo evento IMPORTACION en la bitácora para el lote
    (no uno por fila).
    """

    lector = elegir_lector(archivo.name)
    columnas, filas = lector.leer_filas(archivo)

    indice_paja = _indice_columna(columnas, columna_paja)
    indice_nombre = _indice_columna(columnas, columna_nombre)

    if indice_paja is None:
        raise ArchivoImportacionError(
            f"La columna «{columna_paja}» elegida para el número de paja "
            "ya no está en este archivo. Revise el mapeo de columnas."
        )

    if indice_nombre is None:
        raise ArchivoImportacionError(
            f"La columna «{columna_nombre}» elegida para el nombre del "
            "titular ya no está en este archivo. Revise el mapeo de "
            "columnas."
        )

    importados = 0
    omitidos = 0
    rechazados: list[FilaRechazada] = []
    hoy = timezone.localdate()

    with transaction.atomic():
        for numero_fila, fila in enumerate(filas, start=2):
            valor_paja_bruto = _valor_columna(fila, indice_paja)
            valor_nombre = _valor_columna(fila, indice_nombre)

            paja, problema, que_hacer = _validar_paja(valor_paja_bruto)

            if problema is not None:
                rechazados.append(
                    FilaRechazada(
                        fila=numero_fila, problema=problema, que_hacer=que_hacer,
                    )
                )
                continue

            if Abonado.objects.filter(numero_paja=paja).exists():
                # RF-04: paja ya registrada (incluye duplicados dentro del
                # mismo archivo, ya visibles en esta misma transacción).
                omitidos += 1
                continue

            if not valor_nombre:
                rechazados.append(
                    FilaRechazada(
                        fila=numero_fila,
                        problema="No tiene nombre del titular.",
                        que_hacer="Agregue el nombre en SADA y vuelva a importar.",
                    )
                )
                continue

            abonado = Abonado.objects.create(
                numero_paja=paja, tipo_abonado=TipoAbonado.PENDIENTE,
            )
            # SADA no exporta identificación (CLAUDE.md sección 8/plan): se
            # crea sin tipo_identificacion/identificacion, a propósito.
            persona = Persona.objects.create(nombre=valor_nombre)
            VinculoAbonado.objects.create(
                abonado=abonado,
                persona=persona,
                fecha_inicio=hoy,
                rol=RolVinculo.TITULAR,
            )
            importados += 1

        if importados or omitidos or rechazados:
            registro = registrar(
                cuenta=cuenta,
                accion=AccionBitacora.IMPORTACION,
                elemento_afectado=f"importacion_sada.nombre_archivo={archivo.name}",
            )
            registrar_modificaciones(
                registro,
                {
                    "importacion_sada.resumen": (
                        None,
                        f"{importados} importados, {omitidos} omitidos, "
                        f"{len(rechazados)} rechazados",
                    ),
                },
            )

    return ResultadoImportacion(
        importados=importados, omitidos=omitidos, rechazados=rechazados, fecha=hoy,
    )
