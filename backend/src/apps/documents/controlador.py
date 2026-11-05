"""
ControladorDocumentos: validarArchivo(), cargarDocumento() y
cargarNuevaVersion() (CU-04, ficha del prototipo vertical en
CLAUDE.md sección 8; Modelos UML, diagrama de secuencia de CU-04).

Reglas que programa la aplicación (Modelo_Relacional_SIGEDA_v1.1_Contexto.md,
sección 2.7): documento + version_documento(numero_version=1) + evento
de bitácora en una sola transacción; la persona que aporta el
documento debe tener un vínculo vigente con el abonado.
"""

import hashlib
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Max

from apps.abonados.models import VinculoAbonado
from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar

from .cifrado import AlmacenArchivosCifrados
from .models import Documento, FormatoVersionDocumento, VersionDocumento

TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024

_FIRMAS_FORMATO = {
    FormatoVersionDocumento.PDF: (b"%PDF-",),
    FormatoVersionDocumento.PNG: (b"\x89PNG\r\n\x1a\n",),
}


class ValidacionArchivoError(Exception):
    """Mensaje ya redactado tal como lo muestra PAN-05 (RNF-02: causa + acción)."""


class VinculoNoVigenteError(Exception):
    pass


@dataclass
class ResultadoCarga:
    documento: Documento
    version: VersionDocumento


def _detectar_formato(contenido: bytes) -> str | None:
    """Revisa el contenido real del archivo, no la extensión (RF-05)."""

    for formato, firmas in _FIRMAS_FORMATO.items():
        if any(contenido.startswith(firma) for firma in firmas):
            return formato

    return None


def _extension(nombre_original: str) -> str:
    if "." not in nombre_original:
        return "?"

    return nombre_original.rsplit(".", 1)[-1].upper()


class ControladorDocumentos:
    """Fachada de CU-04. Ver también `IDocumentos` en `fachada.py`."""

    def __init__(self, almacen: AlmacenArchivosCifrados | None = None):
        self.almacen = almacen or AlmacenArchivosCifrados()

    def validar_archivo(self, *, nombre_original: str, contenido: bytes) -> str:
        """Devuelve el formato detectado (PDF/PNG) o lanza ValidacionArchivoError."""

        if len(contenido) > TAMANO_MAXIMO_BYTES:
            tamano_mb = len(contenido) / (1024 * 1024)
            tamano_mb_cr = f"{tamano_mb:.1f}".replace(".", ",")

            raise ValidacionArchivoError(
                f"Pesa {tamano_mb_cr} MB y el máximo es 10 MB. Escanéelo a "
                "menor resolución o divídalo en dos archivos."
            )

        formato = _detectar_formato(contenido)

        if formato is None:
            raise ValidacionArchivoError(
                f"Es un archivo {_extension(nombre_original)}. Solo se "
                "aceptan PDF o PNG: conviértalo con la fotocopiadora o "
                "elija otro archivo."
            )

        return formato

    def _validar_vinculo_vigente(self, *, abonado, persona):
        existe = VinculoAbonado.objects.filter(
            abonado=abonado,
            persona=persona,
            fecha_fin__isnull=True,
        ).exists()

        if not existe:
            raise VinculoNoVigenteError(
                "La persona que aporta el documento no tiene un vínculo "
                "vigente con este abonado."
            )

    @transaction.atomic
    def cargar_documento(
        self,
        *,
        abonado,
        tipo_documento,
        persona,
        nombre_identificador: str | None,
        fecha_documento,
        nombre_original: str,
        contenido: bytes,
        cuenta,
    ) -> ResultadoCarga:
        formato = self.validar_archivo(
            nombre_original=nombre_original, contenido=contenido,
        )

        if persona is not None:
            self._validar_vinculo_vigente(abonado=abonado, persona=persona)

        hash_sha256 = hashlib.sha256(contenido).hexdigest()
        nombre_cuarentena = self.almacen.guardar_en_cuarentena(contenido)

        documento = Documento.objects.create(
            abonado=abonado,
            tipo_documento=tipo_documento,
            persona=persona,
            nombre_identificador=nombre_identificador or None,
        )
        version = VersionDocumento.objects.create(
            documento=documento,
            numero_version=1,
            nombre_original=nombre_original,
            ruta_archivo=nombre_cuarentena,
            formato=formato,
            tamano_bytes=len(contenido),
            fecha_documento=fecha_documento,
            hash_sha256=hash_sha256,
        )
        registrar(
            cuenta=cuenta,
            accion=AccionBitacora.CREACION,
            elemento_afectado=f"documento.id_documento={documento.id_documento}",
            id_abonado=abonado.id_abonado,
        )

        transaction.on_commit(
            lambda: self.almacen.confirmar(nombre_cuarentena)
        )

        return ResultadoCarga(documento=documento, version=version)

    @transaction.atomic
    def cargar_nueva_version(
        self,
        *,
        documento,
        fecha_documento,
        nombre_original: str,
        contenido: bytes,
        cuenta,
    ) -> ResultadoCarga:
        formato = self.validar_archivo(
            nombre_original=nombre_original, contenido=contenido,
        )

        hash_sha256 = hashlib.sha256(contenido).hexdigest()
        nombre_cuarentena = self.almacen.guardar_en_cuarentena(contenido)

        numero_anterior = documento.versiones.aggregate(
            maximo=Max("numero_version"),
        )["maximo"] or 0

        version = VersionDocumento.objects.create(
            documento=documento,
            numero_version=numero_anterior + 1,
            nombre_original=nombre_original,
            ruta_archivo=nombre_cuarentena,
            formato=formato,
            tamano_bytes=len(contenido),
            fecha_documento=fecha_documento,
            hash_sha256=hash_sha256,
        )
        registrar(
            cuenta=cuenta,
            accion=AccionBitacora.CREACION,
            elemento_afectado=f"documento.id_documento={documento.id_documento}",
            id_abonado=documento.abonado_id,
        )

        transaction.on_commit(
            lambda: self.almacen.confirmar(nombre_cuarentena)
        )

        return ResultadoCarga(documento=documento, version=version)
