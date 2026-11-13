from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abonados.models import Sector
from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar, registrar_modificaciones

from .models import (
    GrupoAlternativas,
    ObligatoriedadGrupo,
    ObligatoriedadTipoDocumento,
    TipoDocumento,
)


class TiposDocumentoView(APIView):
    """RF-09: catálogo de tipos de documento, para el formulario de PAN-05."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        tipos = TipoDocumento.objects.order_by("prioridad", "nombre")

        return Response(
            [
                {
                    "id_tipo_documento": tipo.id_tipo_documento,
                    "nombre": tipo.nombre,
                    "prioridad": tipo.prioridad,
                }
                for tipo in tipos
            ],
        )


class SectoresView(APIView):
    """Catálogo de sectores, para el filtro de PAN-03."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        sectores = Sector.objects.order_by("nombre")

        return Response(
            [
                {"id_sector": sector.id_sector, "nombre": sector.nombre}
                for sector in sectores
            ],
        )


class ListarTiposDocumentoAdminView(APIView):
    """
    PAN-10 (RF-09): tabla administrativa completa, a diferencia de
    `TiposDocumentoView` (combo de PAN-05, solo id/nombre/prioridad).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        tipos = TipoDocumento.objects.select_related("grupo_alternativas").order_by(
            "prioridad", "nombre",
        )

        return Response(
            [
                {
                    "id_tipo_documento": tipo.id_tipo_documento,
                    "nombre": tipo.nombre,
                    "prioridad": tipo.prioridad,
                    "obligatoriedad": tipo.obligatoriedad,
                    "grupo_alternativas": (
                        {
                            "id_grupo_alternativas": tipo.grupo_alternativas.id_grupo_alternativas,
                            "nombre": tipo.grupo_alternativas.nombre,
                        }
                        if tipo.grupo_alternativas_id
                        else None
                    ),
                    "es_exigido_a_cotitulares": tipo.es_exigido_a_cotitulares,
                }
                for tipo in tipos
            ],
        )


def _validar_datos_tipo_documento(data, *, id_excluir=None):
    """
    Valida nombre, prioridad y modo (GRUPO/OBLIGATORIEDAD) para crear o
    editar un tipo de documento (RF-09). Lo valida la aplicación, en
    español y antes de guardar, para no depender del mensaje crudo del
    CHECK "grupo XOR obligatoriedad" de PostgreSQL.

    Devuelve (valores: dict, None) si todo está bien, o (None, Response)
    con el primer error encontrado.
    """

    nombre = (data.get("nombre") or "").strip()

    if not nombre:
        return None, Response(
            {"nombre": ["El nombre del tipo de documento es obligatorio."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    duplicados = TipoDocumento.objects.filter(nombre=nombre)

    if id_excluir is not None:
        duplicados = duplicados.exclude(pk=id_excluir)

    if duplicados.exists():
        return None, Response(
            {
                "nombre": [
                    f"Ya existe un tipo de documento llamado «{nombre}». "
                    "Elija otro nombre.",
                ],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    prioridad_bruta = data.get("prioridad")

    try:
        prioridad = int(prioridad_bruta)
    except (TypeError, ValueError):
        return None, Response(
            {"prioridad": ["La prioridad debe ser un número entero mayor que 0."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if prioridad <= 0:
        return None, Response(
            {"prioridad": ["La prioridad debe ser un número entero mayor que 0."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    modo = data.get("modo")
    id_grupo_alternativas = data.get("id_grupo_alternativas")
    obligatoriedad = data.get("obligatoriedad") or None
    grupo = None

    if modo == "GRUPO":
        if obligatoriedad:
            return None, Response(
                {
                    "modo": [
                        "Elija grupo de alternativas u obligatoriedad, no "
                        "los dos.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not id_grupo_alternativas:
            return None, Response(
                {
                    "id_grupo_alternativas": [
                        "Elija un grupo de alternativas de la lista.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            grupo = GrupoAlternativas.objects.get(pk=id_grupo_alternativas)
        except (GrupoAlternativas.DoesNotExist, ValueError, TypeError):
            return None, Response(
                {
                    "id_grupo_alternativas": [
                        "El grupo de alternativas elegido no existe.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        obligatoriedad = None
    elif modo == "OBLIGATORIEDAD":
        if id_grupo_alternativas:
            return None, Response(
                {
                    "modo": [
                        "Elija grupo de alternativas u obligatoriedad, no "
                        "los dos.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if obligatoriedad not in ObligatoriedadTipoDocumento.values:
            return None, Response(
                {
                    "obligatoriedad": [
                        f"La obligatoriedad «{obligatoriedad}» no es "
                        "válida. Elija una opción de la lista.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        return None, Response(
            {
                "modo": [
                    "Elija si este tipo tiene grupo de alternativas u "
                    "obligatoriedad propia.",
                ],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return {
        "nombre": nombre,
        "prioridad": prioridad,
        "grupo_alternativas": grupo,
        "obligatoriedad": obligatoriedad,
        "es_exigido_a_cotitulares": bool(data.get("es_exigido_a_cotitulares")),
    }, None


class CrearTipoDocumentoView(APIView):
    """PAN-10 (RF-09): crea un tipo de documento nuevo."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        valores, error = _validar_datos_tipo_documento(request.data)

        if error is not None:
            return error

        with transaction.atomic():
            tipo = TipoDocumento.objects.create(**valores)
            registrar(
                cuenta=request.user,
                accion=AccionBitacora.CREACION,
                elemento_afectado=(
                    f"tipo_documento.id_tipo_documento={tipo.id_tipo_documento}"
                ),
            )

        return Response(
            {
                "detail": f"El tipo de documento «{tipo.nombre}» quedó registrado.",
                "id_tipo_documento": tipo.id_tipo_documento,
            },
            status=status.HTTP_201_CREATED,
        )


class EditarTipoDocumentoView(APIView):
    """PAN-10 (RF-09): edita un tipo de documento existente."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, id_tipo_documento):
        try:
            tipo = TipoDocumento.objects.select_related("grupo_alternativas").get(
                pk=id_tipo_documento,
            )
        except TipoDocumento.DoesNotExist:
            return Response(
                {"detail": "El tipo de documento indicado no existe."}, status=404,
            )

        valores, error = _validar_datos_tipo_documento(
            request.data, id_excluir=tipo.id_tipo_documento,
        )

        if error is not None:
            return error

        grupo_nuevo = valores["grupo_alternativas"]
        id_grupo_anterior = tipo.grupo_alternativas_id
        id_grupo_nuevo = grupo_nuevo.id_grupo_alternativas if grupo_nuevo else None

        cambios = {}

        if tipo.nombre != valores["nombre"]:
            cambios["tipo_documento.nombre"] = (tipo.nombre, valores["nombre"])

        if tipo.prioridad != valores["prioridad"]:
            cambios["tipo_documento.prioridad"] = (
                tipo.prioridad, valores["prioridad"],
            )

        if id_grupo_anterior != id_grupo_nuevo:
            cambios["tipo_documento.id_grupo_alternativas"] = (
                tipo.grupo_alternativas.nombre if tipo.grupo_alternativas else None,
                grupo_nuevo.nombre if grupo_nuevo else None,
            )

        if tipo.obligatoriedad != valores["obligatoriedad"]:
            cambios["tipo_documento.obligatoriedad"] = (
                tipo.obligatoriedad, valores["obligatoriedad"],
            )

        if tipo.es_exigido_a_cotitulares != valores["es_exigido_a_cotitulares"]:
            cambios["tipo_documento.es_exigido_a_cotitulares"] = (
                tipo.es_exigido_a_cotitulares, valores["es_exigido_a_cotitulares"],
            )

        with transaction.atomic():
            tipo.nombre = valores["nombre"]
            tipo.prioridad = valores["prioridad"]
            tipo.grupo_alternativas = grupo_nuevo
            tipo.obligatoriedad = valores["obligatoriedad"]
            tipo.es_exigido_a_cotitulares = valores["es_exigido_a_cotitulares"]
            tipo.save(
                update_fields=[
                    "nombre", "prioridad", "grupo_alternativas",
                    "obligatoriedad", "es_exigido_a_cotitulares",
                ],
            )

            if cambios:
                registro = registrar(
                    cuenta=request.user,
                    accion=AccionBitacora.MODIFICACION,
                    elemento_afectado=(
                        f"tipo_documento.id_tipo_documento={tipo.id_tipo_documento}"
                    ),
                )
                registrar_modificaciones(registro, cambios)

        return Response(
            {
                "detail": f"El tipo de documento «{tipo.nombre}» quedó actualizado.",
                "id_tipo_documento": tipo.id_tipo_documento,
            },
        )


class ListarGruposAlternativasView(APIView):
    """PAN-10 (RF-09): cada grupo con sus tipos miembros."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        grupos = GrupoAlternativas.objects.prefetch_related(
            "tipos_documento",
        ).order_by("nombre")

        return Response(
            [
                {
                    "id_grupo_alternativas": grupo.id_grupo_alternativas,
                    "nombre": grupo.nombre,
                    "obligatoriedad": grupo.obligatoriedad,
                    "tipos_documento": [
                        {
                            "id_tipo_documento": tipo.id_tipo_documento,
                            "nombre": tipo.nombre,
                        }
                        for tipo in grupo.tipos_documento.all()
                    ],
                }
                for grupo in grupos
            ],
        )


class CrearGrupoAlternativasView(APIView):
    """
    PAN-10 (RF-09): crea un grupo de alternativas y reasigna los tipos
    elegidos a él, en una transacción. Regla de la aplicación, no de
    la base de datos: un grupo necesita al menos 2 tipos (CLAUDE.md
    sección 5, "Grupo de alternativas").
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        nombre = (request.data.get("nombre") or "").strip()

        if not nombre:
            return Response(
                {"nombre": ["El nombre del grupo de alternativas es obligatorio."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if GrupoAlternativas.objects.filter(nombre=nombre).exists():
            return Response(
                {
                    "nombre": [
                        f"Ya existe un grupo de alternativas llamado "
                        f"«{nombre}». Elija otro nombre.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        obligatoriedad = request.data.get("obligatoriedad")

        if obligatoriedad not in ObligatoriedadGrupo.values:
            return Response(
                {
                    "obligatoriedad": [
                        f"La obligatoriedad «{obligatoriedad}» no es "
                        "válida. Elija una opción de la lista.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids_tipos_bruto = request.data.get("ids_tipos_documento") or []

        if not isinstance(ids_tipos_bruto, list):
            return Response(
                {
                    "ids_tipos_documento": [
                        "La lista de tipos de documento no es válida.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ids_tipos = [int(valor) for valor in ids_tipos_bruto]
        except (TypeError, ValueError):
            return Response(
                {
                    "ids_tipos_documento": [
                        "Hay un tipo de documento inválido en la lista.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(ids_tipos) == 0:
            return Response(
                {
                    "detail": (
                        f"No se puede guardar el grupo «{nombre}»: no tiene "
                        "ningún tipo. Un grupo de alternativas necesita al "
                        "menos 2 tipos."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(ids_tipos) < 2:
            return Response(
                {
                    "detail": (
                        f"No se puede guardar el grupo «{nombre}»: tiene un "
                        "solo tipo. Un grupo de alternativas necesita al "
                        "menos 2 tipos."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids_tipos_unicos = set(ids_tipos)
        tipos = list(TipoDocumento.objects.filter(pk__in=ids_tipos_unicos))

        if len(tipos) != len(ids_tipos_unicos):
            return Response(
                {
                    "ids_tipos_documento": [
                        "Alguno de los tipos de documento elegidos no existe.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            grupo = GrupoAlternativas.objects.create(
                nombre=nombre, obligatoriedad=obligatoriedad,
            )
            # Un tipo que entra a este grupo nuevo debe quedar con
            # obligatoriedad NULL en la misma operación: el CHECK
            # "grupo XOR obligatoriedad" no permite las dos a la vez.
            TipoDocumento.objects.filter(pk__in=ids_tipos_unicos).update(
                grupo_alternativas=grupo, obligatoriedad=None,
            )
            registrar(
                cuenta=request.user,
                accion=AccionBitacora.CREACION,
                elemento_afectado=(
                    f"grupo_alternativas.id_grupo_alternativas="
                    f"{grupo.id_grupo_alternativas}"
                ),
            )

        return Response(
            {
                "detail": (
                    f"El grupo «{grupo.nombre}» quedó registrado con "
                    f"{len(tipos)} tipos."
                ),
                "id_grupo_alternativas": grupo.id_grupo_alternativas,
            },
            status=status.HTTP_201_CREATED,
        )
