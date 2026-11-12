"""
CU-04 Cargar documento. "Prueba de terminado" de CLAUDE.md sección 8,
automatizada: conservar la fecha original, cifrado real, rechazos,
nueva versión y bitácora. También las restricciones CHECK propias de
esta app y la regla "vínculo vigente" que programa la aplicación.
"""

import datetime
import shutil

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.abonados.models import Abonado, Persona, TipoAbonado, VinculoAbonado
from apps.accounts.models import Cuenta, TokenCuenta
from apps.bitacora.models import AccionBitacora, RegistroBitacora
from apps.configuration.models import TipoDocumento

from .cifrado import AlmacenArchivosCifrados
from .controlador import (
    ControladorDocumentos,
    ValidacionArchivoError,
    VinculoNoVigenteError,
)
from .models import Documento, VersionDocumento

PDF_MINIMO = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
PNG_MINIMO = b"\x89PNG\r\n\x1a\n" + b"0" * 20
JPG_MINIMO = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"0" * 20


def _raiz_prueba():
    return str(settings.BASE_DIR / "almacen_cifrado_test")


@override_settings(DOCUMENT_STORAGE_ROOT=_raiz_prueba())
class CargaDeDocumentoCU04Tests(TestCase):
    """Las 5 filas de la tabla "Prueba de terminado" de CLAUDE.md sección 8."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        shutil.rmtree(_raiz_prueba(), ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_raiz_prueba(), ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.abonado = Abonado.objects.create(
            numero_paja="0412", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular = Persona.objects.create(
            nombre="Ana Lucía Mora Vega",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0123",
        )
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular,
            fecha_inicio=datetime.date(2026, 2, 10),
            rol="TITULAR",
        )
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria",
            hash_contrasena=make_password("Secretaria2026!"),
            perfil="SECRETARIA",
        )
        self.tipo_documento = TipoDocumento.objects.get(
            nombre="Certificación de registro de propiedad",
        )
        self.controlador = ControladorDocumentos()

    # 1. Conservar la fecha original -----------------------------------

    def test_conserva_fecha_original_en_5_cargas(self):
        fecha_original = datetime.date(2005, 3, 15)
        resultados = []

        for indice in range(5):
            resultado = self.controlador.cargar_documento(
                abonado=self.abonado,
                tipo_documento=self.tipo_documento,
                persona=self.titular,
                nombre_identificador=f"doc-{indice}",
                fecha_documento=fecha_original,
                nombre_original=f"documento_{indice}.pdf",
                contenido=PDF_MINIMO + f" {indice}".encode(),
                cuenta=self.cuenta,
            )
            resultados.append(resultado)

        self.assertEqual(len(resultados), 5)

        for resultado in resultados:
            version = VersionDocumento.objects.get(
                documento=resultado.documento, numero_version=1,
            )
            self.assertEqual(version.fecha_documento, fecha_original)

            contenido_original = PDF_MINIMO + (
                f" {resultados.index(resultado)}".encode()
            )
            import hashlib

            self.assertEqual(
                version.hash_sha256,
                hashlib.sha256(contenido_original).hexdigest(),
            )

    # 2. Cifrado ---------------------------------------------------------

    def test_archivos_en_el_almacen_quedan_cifrados(self):
        with self.captureOnCommitCallbacks(execute=True):
            resultado = self.controlador.cargar_documento(
                abonado=self.abonado,
                tipo_documento=self.tipo_documento,
                persona=self.titular,
                nombre_identificador=None,
                fecha_documento=datetime.date(2005, 3, 15),
                nombre_original="certificacion.pdf",
                contenido=PDF_MINIMO,
                cuenta=self.cuenta,
            )

        from pathlib import Path

        ruta_en_disco = (
            Path(settings.DOCUMENT_STORAGE_ROOT)
            / "documentos"
            / resultado.version.ruta_archivo
        )
        contenido_en_disco = ruta_en_disco.read_bytes()

        self.assertFalse(contenido_en_disco.startswith(b"%PDF-"))
        self.assertNotEqual(contenido_en_disco, PDF_MINIMO)

        # Pero SIGEDA sí lo puede leer y verificar:
        almacen = AlmacenArchivosCifrados()
        self.assertTrue(
            almacen.verificar_integridad(
                resultado.version.ruta_archivo, resultado.version.hash_sha256,
            ),
        )
        self.assertEqual(
            almacen.leer_archivo(resultado.version.ruta_archivo), PDF_MINIMO,
        )

    # 3. Rechazos ----------------------------------------------------------

    def test_rechaza_jpg_y_no_guarda_nada(self):
        documentos_antes = Documento.objects.count()
        versiones_antes = VersionDocumento.objects.count()

        with self.assertRaises(ValidacionArchivoError) as contexto:
            self.controlador.cargar_documento(
                abonado=self.abonado,
                tipo_documento=self.tipo_documento,
                persona=self.titular,
                nombre_identificador=None,
                fecha_documento=datetime.date(2026, 1, 1),
                nombre_original="foto.jpg",
                contenido=JPG_MINIMO,
                cuenta=self.cuenta,
            )

        self.assertIn("JPG", str(contexto.exception))
        self.assertIn("PDF o PNG", str(contexto.exception))
        self.assertEqual(Documento.objects.count(), documentos_antes)
        self.assertEqual(VersionDocumento.objects.count(), versiones_antes)

    def test_rechaza_archivo_de_mas_de_10mb_y_no_guarda_nada(self):
        contenido_grande = PDF_MINIMO + b"0" * (11 * 1024 * 1024)
        documentos_antes = Documento.objects.count()

        with self.assertRaises(ValidacionArchivoError) as contexto:
            self.controlador.cargar_documento(
                abonado=self.abonado,
                tipo_documento=self.tipo_documento,
                persona=self.titular,
                nombre_identificador=None,
                fecha_documento=datetime.date(2026, 1, 1),
                nombre_original="plano.pdf",
                contenido=contenido_grande,
                cuenta=self.cuenta,
            )

        mensaje = str(contexto.exception)
        self.assertIn("10 MB", mensaje)
        self.assertIn(",", mensaje)  # separador decimal costarricense
        self.assertEqual(Documento.objects.count(), documentos_antes)

    def test_lote_con_un_archivo_invalido_no_guarda_ninguno(self):
        """Mientras haya errores no se guarda nada (ficha PAN-05)."""

        cliente = APIClient()
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        from django.core.files.uploadedfile import SimpleUploadedFile

        respuesta = cliente.post(
            reverse("sigeda_documents:cargar"),
            {
                "numero_paja": "0412",
                "archivos": [
                    SimpleUploadedFile("ok.pdf", PDF_MINIMO, content_type="application/pdf"),
                    SimpleUploadedFile("malo.jpg", JPG_MINIMO, content_type="image/jpeg"),
                ],
                "metadatos": (
                    f'[{{"es_nueva_version": false, '
                    f'"id_tipo_documento": {self.tipo_documento.id_tipo_documento}, '
                    f'"id_persona": {self.titular.id_persona}, '
                    f'"fecha_documento": "2026-01-01"}}, '
                    f'{{"es_nueva_version": false, '
                    f'"id_tipo_documento": {self.tipo_documento.id_tipo_documento}, '
                    f'"fecha_documento": "2026-01-01"}}]'
                ),
            },
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Documento.objects.count(), 0)

    # 4. Nueva versión -----------------------------------------------------

    def test_nueva_version_no_sobrescribe_la_anterior(self):
        primera = self.controlador.cargar_documento(
            abonado=self.abonado,
            tipo_documento=self.tipo_documento,
            persona=self.titular,
            nombre_identificador="formulario",
            fecha_documento=datetime.date(2005, 3, 15),
            nombre_original="formulario_2005.pdf",
            contenido=PDF_MINIMO,
            cuenta=self.cuenta,
        )

        segunda = self.controlador.cargar_nueva_version(
            documento=primera.documento,
            fecha_documento=datetime.date(2026, 2, 10),
            nombre_original="formulario_2026.pdf",
            contenido=PDF_MINIMO + b" v2",
            cuenta=self.cuenta,
        )

        self.assertEqual(segunda.version.numero_version, 2)

        version_1 = VersionDocumento.objects.get(
            documento=primera.documento, numero_version=1,
        )
        self.assertEqual(version_1.fecha_documento, datetime.date(2005, 3, 15))
        self.assertEqual(
            VersionDocumento.objects.filter(documento=primera.documento).count(), 2,
        )

    # 5. Bitácora ------------------------------------------------------------

    def test_una_fila_creacion_por_carga_a_nombre_de_la_cuenta(self):
        self.controlador.cargar_documento(
            abonado=self.abonado,
            tipo_documento=self.tipo_documento,
            persona=self.titular,
            nombre_identificador=None,
            fecha_documento=datetime.date(2026, 1, 1),
            nombre_original="doc.pdf",
            contenido=PDF_MINIMO,
            cuenta=self.cuenta,
        )

        registros = RegistroBitacora.objects.filter(
            accion=AccionBitacora.CREACION, cuenta=self.cuenta,
        )
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.first().id_abonado, self.abonado.id_abonado)

    # Reglas adicionales que programa la aplicación --------------------

    def test_persona_sin_vinculo_vigente_se_rechaza(self):
        persona_ajena = Persona.objects.create(nombre="Persona sin vínculo")

        with self.assertRaises(VinculoNoVigenteError):
            self.controlador.cargar_documento(
                abonado=self.abonado,
                tipo_documento=self.tipo_documento,
                persona=persona_ajena,
                nombre_identificador=None,
                fecha_documento=datetime.date(2026, 1, 1),
                nombre_original="doc.pdf",
                contenido=PDF_MINIMO,
                cuenta=self.cuenta,
            )

    def test_detecta_png_por_contenido_no_por_extension(self):
        formato = self.controlador.validar_archivo(
            nombre_original="foto_sin_extension", contenido=PNG_MINIMO,
        )
        self.assertEqual(formato, "PNG")

    def test_rechaza_pdf_falso_con_extension_correcta(self):
        """Revisa el contenido real, no solo la extensión (RF-05)."""

        with self.assertRaises(ValidacionArchivoError):
            self.controlador.validar_archivo(
                nombre_original="falso.pdf", contenido=b"esto no es un PDF",
            )


class DocumentoConstraintsTests(TestCase):
    def setUp(self):
        self.abonado = Abonado.objects.create(
            numero_paja="9200", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.tipo_documento = TipoDocumento.objects.get(nombre="Plano legible")

    def test_anulado_requiere_motivo_y_fecha(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Documento.objects.create(
                    abonado=self.abonado,
                    tipo_documento=self.tipo_documento,
                    estado="ANULADO",
                )

    def test_vigente_no_puede_tener_motivo_de_anulacion(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Documento.objects.create(
                    abonado=self.abonado,
                    tipo_documento=self.tipo_documento,
                    estado="VIGENTE",
                    motivo_anulacion="algo",
                    fecha_anulacion=datetime.datetime.now(datetime.timezone.utc),
                )

    def test_version_documento_tamano_bytes_positivo(self):
        documento = Documento.objects.create(
            abonado=self.abonado, tipo_documento=self.tipo_documento,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VersionDocumento.objects.create(
                    documento=documento,
                    numero_version=1,
                    nombre_original="x.pdf",
                    ruta_archivo="x.bin",
                    formato="PDF",
                    tamano_bytes=0,
                    fecha_documento=datetime.date(2026, 1, 1),
                    hash_sha256="0" * 64,
                )

    def test_version_documento_formato_solo_pdf_o_png(self):
        """RN-11: solo PDF o PNG (documento.estado ya probado arriba)."""

        documento = Documento.objects.create(
            abonado=self.abonado, tipo_documento=self.tipo_documento,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VersionDocumento.objects.create(
                    documento=documento,
                    numero_version=1,
                    nombre_original="x.jpg",
                    ruta_archivo="x2.bin",
                    formato="JPG",
                    tamano_bytes=100,
                    fecha_documento=datetime.date(2026, 1, 1),
                    hash_sha256="0" * 64,
                )
