"""
AlmacenArchivosCifrados (IAlmacenArchivos) y ServicioCifrado, del DAS
v1.1 (sección 5, paquete "Almacén de archivos cifrados"). AES-256-GCM
vía `cryptography` (ADR-02); la clave vive fuera del repositorio
(RNF-13 parcial: para este incremento, en una variable de entorno
documentada como SUPUESTO en settings/base.py — la entrega como
secreto de Docker queda para el despliegue real, Incremento 3+).
"""

import base64
import os
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

NONCE_BYTES = 12


class ClaveCifradoNoConfiguradaError(RuntimeError):
    pass


class IntegridadArchivoError(RuntimeError):
    pass


class ServicioCifrado:
    """Cifra y descifra bytes en memoria con AES-256-GCM."""

    def __init__(self, clave: bytes | None = None):
        self._clave = clave or self._clave_desde_configuracion()

    @staticmethod
    def _clave_desde_configuracion() -> bytes:
        clave_b64 = getattr(settings, "DOCUMENT_ENCRYPTION_KEY_B64", None)

        if not clave_b64:
            raise ClaveCifradoNoConfiguradaError(
                "Falta DOCUMENT_ENCRYPTION_KEY_B64 en el entorno. Generá una "
                "con: python -c \"import secrets,base64; "
                "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
            )

        clave = base64.b64decode(clave_b64)

        if len(clave) != 32:
            raise ClaveCifradoNoConfiguradaError(
                "DOCUMENT_ENCRYPTION_KEY_B64 debe decodificar a 32 bytes "
                "(AES-256)."
            )

        return clave

    def cifrar(self, datos: bytes) -> bytes:
        aesgcm = AESGCM(self._clave)
        nonce = os.urandom(NONCE_BYTES)
        texto_cifrado = aesgcm.encrypt(nonce, datos, None)

        return nonce + texto_cifrado

    def descifrar(self, datos_cifrados: bytes) -> bytes:
        aesgcm = AESGCM(self._clave)
        nonce, texto_cifrado = (
            datos_cifrados[:NONCE_BYTES],
            datos_cifrados[NONCE_BYTES:],
        )

        return aesgcm.decrypt(nonce, texto_cifrado, None)


class AlmacenArchivosCifrados:
    """
    Implementa IAlmacenArchivos (DAS v1.1, p.24-25): guardarArchivo,
    leerArchivo, verificarIntegridad. Nombre de archivo generado
    (uuid4), no revela abonado ni persona. Escribe primero a
    `cuarentena/`: el llamador debe mover el archivo a su ubicación
    final solo después de que la transacción de base de datos
    confirme (ver `apps.documents.controlador`), para que un archivo
    sin fila asociada quede en cuarentena en vez de "huérfano".
    """

    def __init__(self, servicio_cifrado: ServicioCifrado | None = None):
        self.servicio_cifrado = servicio_cifrado or ServicioCifrado()
        self.raiz = Path(settings.DOCUMENT_STORAGE_ROOT)
        self.dir_cuarentena = self.raiz / "cuarentena"
        self.dir_definitivo = self.raiz / "documentos"
        self.dir_cuarentena.mkdir(parents=True, exist_ok=True)
        self.dir_definitivo.mkdir(parents=True, exist_ok=True)

    def guardar_en_cuarentena(self, datos_originales: bytes) -> str:
        """Cifra y escribe en cuarentena. Devuelve el nombre opaco del archivo."""

        datos_cifrados = self.servicio_cifrado.cifrar(datos_originales)
        nombre_archivo = f"{uuid.uuid4().hex}.bin"
        ruta = self.dir_cuarentena / nombre_archivo
        ruta.write_bytes(datos_cifrados)

        return nombre_archivo

    def confirmar(self, nombre_archivo: str) -> None:
        """Mueve un archivo de cuarentena a su ubicación definitiva."""

        origen = self.dir_cuarentena / nombre_archivo
        destino = self.dir_definitivo / nombre_archivo
        os.replace(origen, destino)

    def leer_archivo(self, nombre_archivo: str) -> bytes:
        """Lee y descifra un archivo ya confirmado. Devuelve los bytes originales."""

        ruta = self.dir_definitivo / nombre_archivo
        datos_cifrados = ruta.read_bytes()

        return self.servicio_cifrado.descifrar(datos_cifrados)

    def verificar_integridad(self, nombre_archivo: str, hash_esperado: str) -> bool:
        import hashlib

        try:
            datos_originales = self.leer_archivo(nombre_archivo)
        except FileNotFoundError:
            return False

        return hashlib.sha256(datos_originales).hexdigest() == hash_esperado
