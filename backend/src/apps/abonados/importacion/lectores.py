"""
Lectores de archivo para RF-04 Importar listado de SADA (ADR-04:
IFuenteImportacion.leerFilas(ruta)). Dos implementaciones, una por
formato; la vista elige cuál usar según la extensión real del archivo
subido (`.xlsx` / `.csv`); cualquier otra extensión es el caso de
"archivo no válido" de la ficha de PAN-09.
"""

import csv
import io
from abc import ABC, abstractmethod

from openpyxl import load_workbook


class ArchivoImportacionError(Exception):
    """Mensaje con causa y acción (RNF-02), listo para mostrar tal cual."""


class IFuenteImportacion(ABC):
    """DAS v1.1/ADR-04: IFuenteImportacion.leerFilas(ruta)."""

    @abstractmethod
    def leer_filas(self, archivo) -> tuple[list[str], list[list[str]]]:
        """
        (columnas, filas) a partir de un archivo subido (objeto tipo
        Django `UploadedFile`, con `.read()`/`.seek()`). `columnas` es
        la fila 1 (encabezado); `filas` son las filas de datos (fila 2
        en adelante), sin las filas completamente vacías.
        """


def _texto_celda(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor.strip()
    return str(valor).strip()


class LectorArchivoExcel(IFuenteImportacion):
    """`.xlsx` (ADR-04: openpyxl). Usa la primera hoja del libro."""

    def leer_filas(self, archivo) -> tuple[list[str], list[list[str]]]:
        archivo.seek(0)

        try:
            libro = load_workbook(filename=archivo, read_only=True, data_only=True)
        except Exception as error:
            raise ArchivoImportacionError(
                "No se pudo leer el archivo de Excel: puede estar dañado o "
                "no ser un .xlsx real. Vuelva a exportarlo de SADA y elija "
                "otro archivo."
            ) from error

        try:
            hoja = libro.worksheets[0]
            filas_hoja = hoja.iter_rows(values_only=True)

            try:
                primera_fila = next(filas_hoja)
            except StopIteration:
                raise ArchivoImportacionError(
                    "El archivo está vacío: no tiene ni encabezados. Revise "
                    "el archivo exportado de SADA."
                )

            columnas = [_texto_celda(valor) for valor in primera_fila]

            filas = []
            for fila in filas_hoja:
                valores = [_texto_celda(valor) for valor in fila]
                if any(valores):
                    filas.append(valores)
        finally:
            libro.close()

        return columnas, filas


class LectorArchivoTexto(IFuenteImportacion):
    """`.csv` (ADR-04: módulo `csv` de Python). Detecta coma o punto y
    coma como separador (SADA/Excel en español suelen exportar con
    punto y coma) y admite UTF-8 o Latin-1."""

    _CODIFICACIONES = ("utf-8-sig", "latin-1")

    def leer_filas(self, archivo) -> tuple[list[str], list[list[str]]]:
        archivo.seek(0)
        contenido_bytes = archivo.read()

        texto = None
        for codificacion in self._CODIFICACIONES:
            try:
                texto = contenido_bytes.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue

        if texto is None:
            raise ArchivoImportacionError(
                "No se pudo leer el archivo de texto: la codificación no "
                "se reconoce. Vuelva a exportarlo de SADA y elija otro "
                "archivo."
            )

        try:
            dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel  # separador por coma, por defecto

        lector = csv.reader(io.StringIO(texto), dialect=dialecto)

        try:
            primera_fila = next(lector)
        except StopIteration:
            raise ArchivoImportacionError(
                "El archivo está vacío: no tiene ni encabezados. Revise el "
                "archivo exportado de SADA."
            )

        columnas = [_texto_celda(valor) for valor in primera_fila]

        filas = []
        for fila in lector:
            valores = [_texto_celda(valor) for valor in fila]
            if any(valores):
                filas.append(valores)

        return columnas, filas


def elegir_lector(nombre_archivo: str) -> IFuenteImportacion:
    """
    Elige el lector según la extensión real del archivo subido. Otra
    extensión levanta `ArchivoImportacionError` (caso de "archivo no
    válido" de la ficha de PAN-09).
    """

    extension = (
        nombre_archivo.rsplit(".", 1)[-1].lower() if "." in nombre_archivo else ""
    )

    if extension == "xlsx":
        return LectorArchivoExcel()

    if extension == "csv":
        return LectorArchivoTexto()

    raise ArchivoImportacionError(
        f"«{nombre_archivo}» no es un archivo .xlsx ni .csv. Exporte el "
        "listado de SADA en uno de esos dos formatos y elija otro archivo."
    )
