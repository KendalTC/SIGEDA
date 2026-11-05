"""
API REST de CU-04 (PAN-05): carga de varios archivos con sus datos,
descarga del documento descifrado, historial de versiones (PAN-13).
Vistas nuevas; no tocan `views.py`/`urls.py` (generación de PDF
heredada de LICS, intacta).
"""

import json

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abonados.models import Abonado, Persona
from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.configuration.models import TipoDocumento

from .cifrado import AlmacenArchivosCifrados, IntegridadArchivoError
from .controlador import ControladorDocumentos, ValidacionArchivoError
from .models import Documento, VersionDocumento
from .repositorio import RepositorioDocumentos
from .serializers import VersionDocumentoSerializer


def _leer_metadatos(valor_bruto: str | None) -> list | None:
    if not valor_bruto:
        return None

    try:
        metadatos = json.loads(valor_bruto)
    except (TypeError, json.JSONDecodeError):
        return None

    return metadatos if isinstance(metadatos, list) else None


class CargarDocumentosView(APIView):
    """
    POST multipart: `numero_paja`, `archivos` (uno o más), `metadatos`
    (JSON, un objeto por archivo en el mismo orden). Cada objeto:
    `{"es_nueva_version": bool, "id_tipo_documento"?, "id_documento"?,
    "id_persona"?, "nombre_identificador"?, "fecha_documento"}`.

    Valida TODO antes de guardar nada (mientras haya errores no se
    guarda nada, como pide la ficha de PAN-05); si todo está bien,
    guarda todos los archivos en una sola transacción.
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        numero_paja = (request.data.get("numero_paja") or "").strip()

        if not numero_paja:
            return Response(
                {"numero_paja": ["El número de paja es obligatorio."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "numero_paja": [
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}.",
                    ],
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        archivos = request.FILES.getlist("archivos")

        if not archivos:
            return Response(
                {"archivos": ["Debe elegir al menos un archivo."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metadatos = _leer_metadatos(request.data.get("metadatos"))

        if metadatos is None or len(metadatos) != len(archivos):
            return Response(
                {
                    "metadatos": [
                        "Debe venir un dato por cada archivo elegido.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        controlador = ControladorDocumentos()
        errores_por_archivo = []
        planes = []

        for indice, (archivo, datos) in enumerate(zip(archivos, metadatos)):
            contenido = archivo.read()
            errores_fila = {}

            try:
                controlador.validar_archivo(
                    nombre_original=archivo.name, contenido=contenido,
                )
            except ValidacionArchivoError as exc:
                errores_fila["archivo"] = str(exc)

            es_nueva_version = bool(datos.get("es_nueva_version"))
            documento_existente = None
            tipo_documento = None

            if es_nueva_version:
                try:
                    documento_existente = Documento.objects.get(
                        pk=datos.get("id_documento"), abonado=abonado,
                    )
                except (Documento.DoesNotExist, ValueError, TypeError):
                    errores_fila["documento"] = (
                        "El documento del que es nueva versión no existe "
                        "en este expediente."
                    )
            else:
                id_tipo_documento = datos.get("id_tipo_documento")

                if not id_tipo_documento:
                    errores_fila["tipo_documento"] = (
                        "Falta el tipo de documento. Elíjalo en la lista."
                    )
                else:
                    try:
                        tipo_documento = TipoDocumento.objects.get(
                            pk=id_tipo_documento,
                        )
                    except (TipoDocumento.DoesNotExist, ValueError, TypeError):
                        errores_fila["tipo_documento"] = (
                            "El tipo de documento elegido no existe."
                        )

            if not datos.get("fecha_documento"):
                errores_fila["fecha_documento"] = (
                    "La fecha del documento es obligatoria."
                )

            persona = None

            if datos.get("id_persona"):
                try:
                    persona = Persona.objects.get(pk=datos["id_persona"])
                except (Persona.DoesNotExist, ValueError, TypeError):
                    errores_fila["persona"] = (
                        "La persona que aporta el documento no existe."
                    )

            if errores_fila:
                errores_por_archivo.append(
                    {
                        "indice": indice,
                        "archivo": archivo.name,
                        "errores": errores_fila,
                    },
                )
            else:
                planes.append(
                    {
                        "es_nueva_version": es_nueva_version,
                        "documento_existente": documento_existente,
                        "tipo_documento": tipo_documento,
                        "persona": persona,
                        "nombre_identificador": datos.get("nombre_identificador") or None,
                        "fecha_documento": datos["fecha_documento"],
                        "nombre_original": archivo.name,
                        "contenido": contenido,
                    },
                )

        if errores_por_archivo:
            return Response(
                {
                    "detail": (
                        f"Hay {len(errores_por_archivo)} archivo(s) con "
                        "problemas. No se guardó ninguno todavía."
                    ),
                    "errores": errores_por_archivo,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        documentos_creados = []

        with transaction.atomic():
            for plan in planes:
                if plan["es_nueva_version"]:
                    resultado = controlador.cargar_nueva_version(
                        documento=plan["documento_existente"],
                        fecha_documento=plan["fecha_documento"],
                        nombre_original=plan["nombre_original"],
                        contenido=plan["contenido"],
                        cuenta=request.user,
                    )
                else:
                    resultado = controlador.cargar_documento(
                        abonado=abonado,
                        tipo_documento=plan["tipo_documento"],
                        persona=plan["persona"],
                        nombre_identificador=plan["nombre_identificador"],
                        fecha_documento=plan["fecha_documento"],
                        nombre_original=plan["nombre_original"],
                        contenido=plan["contenido"],
                        cuenta=request.user,
                    )

                documentos_creados.append(resultado)

        return Response(
            {
                "detail": (
                    f"Se cargaron {len(documentos_creados)} documento(s) "
                    f"al expediente {numero_paja}."
                ),
                "documentos": [
                    {
                        "id_documento": r.documento.id_documento,
                        "tipo_documento": r.documento.tipo_documento.nombre,
                        "numero_version": r.version.numero_version,
                        "fecha_documento": r.version.fecha_documento,
                    }
                    for r in documentos_creados
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class VersionesDocumentoView(APIView):
    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request, id_documento):
        try:
            documento = Documento.objects.select_related("tipo_documento").get(
                pk=id_documento,
            )
        except Documento.DoesNotExist:
            return Response(
                {"detail": "El documento indicado no existe."}, status=404,
            )

        versiones = RepositorioDocumentos().listar_versiones(documento)

        return Response(
            {
                "tipo_documento": documento.tipo_documento.nombre,
                "versiones": VersionDocumentoSerializer(versiones, many=True).data,
            },
        )


class DescargarVersionDocumentoView(APIView):
    """Descifra en memoria y entrega el archivo para el visor (PAN-04)."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request, id_documento, numero_version):
        try:
            version = VersionDocumento.objects.select_related("documento").get(
                documento_id=id_documento, numero_version=numero_version,
            )
        except VersionDocumento.DoesNotExist:
            return Response(
                {"detail": "La versión indicada no existe."}, status=404,
            )

        almacen = AlmacenArchivosCifrados()

        if not almacen.verificar_integridad(version.ruta_archivo, version.hash_sha256):
            raise IntegridadArchivoError(
                f"El archivo de la versión {numero_version} no coincide "
                "con su SHA-256 registrado.",
            )

        contenido = almacen.leer_archivo(version.ruta_archivo)
        tipo_contenido = (
            "application/pdf" if version.formato == "PDF" else "image/png"
        )

        respuesta = HttpResponse(contenido, content_type=tipo_contenido)
        respuesta["Content-Disposition"] = (
            f'inline; filename="{version.nombre_original}"'
        )

        return respuesta
