"""
RF-12 Consultar expediente / RN-05 orden del expediente (PAN-04).
RF-11: filtros por tipo, nombre identificador y rango de fechas.
RF-17: baja y reactivación de abonados (D-03).
RF-02/RF-21: alta y modificación de abonado (PAN-06).
RF-13: cambiar titular (D-04, hallazgo H-02).
D-06: agregar, quitar y cambiar el rol de una persona asociada.
"""

import datetime
import unicodedata

from django.contrib.postgres.lookups import Unaccent
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.sigeda_auth import AutenticacionCuenta, CuentaAutenticadaPermission
from apps.bitacora.models import AccionBitacora
from apps.bitacora.servicio import registrar, registrar_modificaciones
from apps.documents.repositorio import RepositorioDocumentos
from apps.documents.serializers import DocumentoExpedienteSerializer

from . import controlador_busqueda
from .controlador_busqueda import _SoloAlfanumerico
from .controlador_importacion import (
    ArchivoImportacionError,
    generar_vista_previa,
    importar_lote,
)
from .controlador_personas import (
    PersonaExistenteError,
    ValidacionPersonaError,
    buscar_persona_existente,
    paja_titular_vigente,
    resolver_o_crear_persona,
    validar_longitud_identificacion,
)
from .models import (
    Abonado,
    EstadoAbonado,
    Persona,
    RolVinculo,
    Sector,
    TipoAbonado,
    TipoIdentificacion,
    VinculoAbonado,
)
from .serializers import AbonadoSerializer, VinculoAbonadoSerializer
from .servicio_completitud import (
    calcular_completitud,
    listar_incompletos,
    listar_tipo_pendiente,
    matriz_completitud,
    resumen_completitud_global,
)

LIMITE_BUSQUEDA_PERSONAS = 20


def _parsear_fecha_filtro(valor, *, etiqueta):
    """
    (date, None) si `valor` es una fecha ISO válida o viene vacío;
    (None, Response) con un 400 si no se pudo interpretar.
    """

    if not valor:
        return None, None

    try:
        return datetime.date.fromisoformat(valor), None
    except ValueError:
        return None, Response(
            {
                "detail": (
                    f"La fecha «{valor}» de {etiqueta} no es válida. Use "
                    "el formato aaaa-mm-dd."
                ),
            },
            status=400,
        )


class ExpedienteView(APIView):
    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request, numero_paja):
        try:
            abonado = Abonado.objects.select_related("sector").get(
                numero_paja=numero_paja,
            )
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=404,
            )

        incluir_anulados = (
            request.query_params.get("mostrar_anulados") == "true"
        )

        id_tipo_documento = request.query_params.get("id_tipo_documento")

        if id_tipo_documento is not None and not id_tipo_documento.isdigit():
            return Response(
                {
                    "detail": (
                        f"El tipo de documento «{id_tipo_documento}» no es "
                        "válido. Elija un tipo de la lista."
                    ),
                },
                status=400,
            )

        nombre_identificador = request.query_params.get("nombre_identificador") or None

        fecha_desde, error_desde = _parsear_fecha_filtro(
            request.query_params.get("fecha_desde"), etiqueta="fecha_desde",
        )
        if error_desde is not None:
            return error_desde

        fecha_hasta, error_hasta = _parsear_fecha_filtro(
            request.query_params.get("fecha_hasta"), etiqueta="fecha_hasta",
        )
        if error_hasta is not None:
            return error_hasta

        documentos = RepositorioDocumentos().listar_expediente(
            abonado,
            incluir_anulados=incluir_anulados,
            id_tipo_documento=int(id_tipo_documento) if id_tipo_documento else None,
            nombre_identificador=nombre_identificador,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )

        personas_vigentes = (
            VinculoAbonado.objects
            .filter(abonado=abonado, fecha_fin__isnull=True)
            .select_related("persona")
            .order_by("rol")
        )

        vinculos_titulares_cerrados = (
            VinculoAbonado.objects
            .filter(
                abonado=abonado,
                rol=RolVinculo.TITULAR,
                fecha_fin__isnull=False,
            )
            .select_related("persona")
            .order_by("fecha_inicio")
        )
        personas_titulares_anteriores = {
            v.persona_id for v in vinculos_titulares_cerrados
        }

        return Response(
            {
                "abonado": AbonadoSerializer(abonado).data,
                "personas_vigentes": VinculoAbonadoSerializer(
                    personas_vigentes, many=True,
                ).data,
                "documentos": DocumentoExpedienteSerializer(
                    documentos,
                    many=True,
                    context={
                        "personas_titulares_anteriores": personas_titulares_anteriores,
                    },
                ).data,
                "historial_titulares": VinculoAbonadoSerializer(
                    vinculos_titulares_cerrados, many=True,
                ).data,
            },
        )


class DarDeBajaAbonadoView(APIView):
    """D-03 Dar de baja (RF-17): no borra documentos ni el abonado."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=404,
            )

        if abonado.estado == EstadoAbonado.DE_BAJA:
            return Response(
                {"detail": "Este abonado ya está de baja."}, status=400,
            )

        fecha_baja_bruta = request.data.get("fecha_baja")

        if not fecha_baja_bruta:
            return Response(
                {"fecha_baja": ["La fecha de baja es obligatoria."]},
                status=400,
            )

        try:
            fecha_baja = datetime.date.fromisoformat(fecha_baja_bruta)
        except (ValueError, TypeError):
            return Response(
                {
                    "fecha_baja": [
                        f"La fecha «{fecha_baja_bruta}» no es válida. Use "
                        "el formato aaaa-mm-dd.",
                    ],
                },
                status=400,
            )

        with transaction.atomic():
            abonado.estado = EstadoAbonado.DE_BAJA
            abonado.fecha_baja = fecha_baja
            abonado.save(update_fields=["estado", "fecha_baja"])

            registrar(
                cuenta=request.user,
                accion=AccionBitacora.BAJA,
                elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                id_abonado=abonado.id_abonado,
            )

        return Response(
            {
                "detail": "El abonado quedó de baja.",
                "estado": abonado.estado,
                "fecha_baja": abonado.fecha_baja,
            },
        )


class ReactivarAbonadoView(APIView):
    """D-03 Reactivar (RF-17)."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=404,
            )

        if abonado.estado == EstadoAbonado.ACTIVO:
            return Response(
                {"detail": "Este abonado ya está activo."}, status=400,
            )

        with transaction.atomic():
            abonado.estado = EstadoAbonado.ACTIVO
            abonado.fecha_baja = None
            abonado.save(update_fields=["estado", "fecha_baja"])

            registrar(
                cuenta=request.user,
                accion=AccionBitacora.REACTIVACION,
                elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                id_abonado=abonado.id_abonado,
            )

        return Response(
            {
                "detail": "El abonado quedó activo de nuevo.",
                "estado": abonado.estado,
            },
        )


class BuscarAbonadosView(APIView):
    """RF-10 Buscar expedientes (consulta Q1), para PAN-03."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        numero_paja = request.query_params.get("numero_paja")
        nombre = request.query_params.get("nombre")
        identificacion = request.query_params.get("identificacion")
        id_sector = request.query_params.get("id_sector")
        incluir_baja = request.query_params.get("incluir_baja", "true") != "false"

        if not any([numero_paja, nombre, identificacion, id_sector]):
            return Response(
                {
                    "detail": (
                        "Escriba al menos un criterio de búsqueda: número "
                        "de paja, nombre, identificación o sector."
                    ),
                },
                status=400,
            )

        if id_sector is not None and not id_sector.isdigit():
            return Response(
                {
                    "detail": (
                        f"El sector «{id_sector}» no es válido. Elija un "
                        f"sector de la lista."
                    ),
                },
                status=400,
            )

        resultado = controlador_busqueda.buscar(
            numero_paja=numero_paja,
            nombre=nombre,
            identificacion=identificacion,
            id_sector=int(id_sector) if id_sector else None,
            incluir_baja=incluir_baja,
        )

        return Response(
            {
                "total": resultado.total,
                "mostrados": resultado.mostrados,
                "tiempo_segundos": resultado.tiempo_segundos,
                "resultados": resultado.resultados,
            },
        )


def _sin_tildes(valor: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(ch)
    )


def _vinculos_actuales(persona: Persona) -> list[str]:
    vinculos = (
        persona.vinculos
        .filter(fecha_fin__isnull=True)
        .select_related("abonado")
        .order_by("abonado__numero_paja")
    )

    return [
        f"{vinculo.get_rol_display()} de {vinculo.abonado.numero_paja}"
        for vinculo in vinculos
    ]


class BuscarPersonasView(APIView):
    """
    Búsqueda compartida de personas (alta, D-06, D-04): por nombre o
    por identificación, con sus vínculos vigentes actuales.
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        texto = (request.query_params.get("q") or "").strip()

        if not texto:
            return Response(
                {
                    "detail": (
                        "Escriba un nombre o una identificación para buscar."
                    ),
                },
                status=400,
            )

        nombre_normalizado = _sin_tildes(texto).lower()
        identificacion_normalizada = "".join(ch for ch in texto if ch.isalnum())

        filtro = Q()

        queryset = Persona.objects.alias(
            nombre_normalizado_db=Lower(Unaccent("nombre")),
        ).filter(nombre_normalizado_db__icontains=nombre_normalizado)
        filtro |= Q(pk__in=queryset.values("pk"))

        if identificacion_normalizada:
            por_identificacion = Persona.objects.alias(
                identificacion_normalizada_db=_SoloAlfanumerico("identificacion"),
            ).filter(
                identificacion_normalizada_db__icontains=identificacion_normalizada,
            )
            filtro |= Q(pk__in=por_identificacion.values("pk"))

        personas = (
            Persona.objects.filter(filtro)
            .order_by("nombre")[:LIMITE_BUSQUEDA_PERSONAS]
        )

        return Response(
            [
                {
                    "id_persona": persona.id_persona,
                    "nombre": persona.nombre,
                    "tipo_identificacion": persona.tipo_identificacion,
                    "identificacion": persona.identificacion,
                    "vinculos_actuales": _vinculos_actuales(persona),
                }
                for persona in personas
            ],
        )


class AltaAbonadoView(APIView):
    """RF-02 Registrar abonado (PAN-06): abonado + persona + vínculo
    TITULAR, en una sola transacción."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request):
        numero_paja = (request.data.get("numero_paja") or "").strip()

        if not numero_paja:
            return Response(
                {"numero_paja": ["El número de paja es obligatorio."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not numero_paja.isdigit():
            return Response(
                {
                    "numero_paja": [
                        "⚠ El número de paja solo puede tener dígitos "
                        "(RN-01). Revise el número.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        abonado_existente = Abonado.objects.filter(numero_paja=numero_paja).first()

        if abonado_existente is not None:
            vinculo_titular = (
                VinculoAbonado.objects
                .filter(
                    abonado=abonado_existente, rol=RolVinculo.TITULAR,
                    fecha_fin__isnull=True,
                )
                .select_related("persona")
                .first()
            )
            nombre_titular = (
                vinculo_titular.persona.nombre if vinculo_titular
                else "sin titular registrado"
            )

            return Response(
                {
                    "numero_paja": [
                        f"⚠ El número de paja {numero_paja} ya está "
                        f"registrado ({nombre_titular}). Revise el número "
                        "o abra ese expediente.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo_abonado = request.data.get("tipo_abonado")

        if tipo_abonado not in TipoAbonado.values:
            return Response(
                {
                    "tipo_abonado": [
                        f"El tipo de abonado «{tipo_abonado}» no es válido. "
                        "Elija una opción de la lista.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        id_sector = request.data.get("id_sector") or None
        sector = None

        if id_sector is not None:
            try:
                sector = Sector.objects.get(pk=id_sector)
            except (Sector.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"id_sector": ["El sector elegido no existe."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                persona = resolver_o_crear_persona(
                    id_persona=request.data.get("id_persona"),
                    nombre=request.data.get("nombre"),
                    tipo_identificacion=request.data.get("tipo_identificacion"),
                    identificacion=request.data.get("identificacion"),
                )

                abonado = Abonado.objects.create(
                    numero_paja=numero_paja,
                    sector=sector,
                    tipo_abonado=tipo_abonado,
                )
                VinculoAbonado.objects.create(
                    abonado=abonado,
                    persona=persona,
                    fecha_inicio=timezone.localdate(),
                    rol=RolVinculo.TITULAR,
                )
                registrar(
                    cuenta=request.user,
                    accion=AccionBitacora.CREACION,
                    elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                    id_abonado=abonado.id_abonado,
                )
        except ValidacionPersonaError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except PersonaExistenteError as error:
            return Response(
                {
                    "persona_existente": {
                        "id_persona": error.persona.id_persona,
                        "nombre": error.persona.nombre,
                        "numero_paja_titular": paja_titular_vigente(error.persona),
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "No se pudo registrar el abonado: revise los datos "
                        "e intente de nuevo."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": "El abonado quedó registrado.",
                "numero_paja": abonado.numero_paja,
                "id_abonado": abonado.id_abonado,
                "titular_vigente": persona.nombre,
            },
            status=status.HTTP_201_CREATED,
        )


class ModificarAbonadoView(APIView):
    """
    RF-21 Modificar abonado (PAN-06): sector y tipo. La paja y el
    estado no se tocan acá (el estado lo maneja D-03).

    RF-04/banner de "importado, pendiente": si el titular vigente de
    este abonado todavía NO tiene identificación (el caso de un
    abonado creado por la importación de SADA), esta misma pantalla
    puede completársela con `tipo_identificacion_titular` +
    `identificacion_titular` (decisión del 13/11/2026, ficha PAN-06
    "importado"). Si el titular YA tenía identificación, estos dos
    campos se ignoran sin error: ese no es el flujo para cambiarle la
    identificación a alguien que ya la tenía.
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        tipo_abonado = request.data.get("tipo_abonado")

        if tipo_abonado not in TipoAbonado.values:
            return Response(
                {
                    "tipo_abonado": [
                        f"El tipo de abonado «{tipo_abonado}» no es válido. "
                        "Elija una opción de la lista.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        id_sector = request.data.get("id_sector") or None
        sector = None

        if id_sector is not None:
            try:
                sector = Sector.objects.get(pk=id_sector)
            except (Sector.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"id_sector": ["El sector elegido no existe."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        tipo_identificacion_titular = (
            request.data.get("tipo_identificacion_titular") or ""
        ).strip() or None
        identificacion_titular = (
            request.data.get("identificacion_titular") or ""
        ).strip() or None

        if bool(tipo_identificacion_titular) != bool(identificacion_titular):
            return Response(
                {
                    "detail": (
                        "El tipo y el número de identificación del titular "
                        "se deben completar juntos."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cambios = {}

        if abonado.sector_id != (sector.id_sector if sector else None):
            cambios["abonado.id_sector"] = (
                abonado.sector_id, sector.id_sector if sector else None,
            )

        if abonado.tipo_abonado != tipo_abonado:
            cambios["abonado.tipo_abonado"] = (abonado.tipo_abonado, tipo_abonado)

        try:
            with transaction.atomic():
                abonado.sector = sector
                abonado.tipo_abonado = tipo_abonado
                abonado.save(update_fields=["sector", "tipo_abonado"])

                if tipo_identificacion_titular is not None:
                    vinculo_titular = (
                        VinculoAbonado.objects
                        .filter(
                            abonado=abonado, rol=RolVinculo.TITULAR,
                            fecha_fin__isnull=True,
                        )
                        .select_related("persona")
                        .first()
                    )

                    # Solo se completa la identificación del titular
                    # "pendiente" (todavía sin identificación, RF-04). Si
                    # ya la tenía, se ignora: hoy no es el flujo para
                    # cambiársela a alguien que ya la tenía.
                    if (
                        vinculo_titular is not None
                        and vinculo_titular.persona.identificacion is None
                    ):
                        if (
                            tipo_identificacion_titular
                            not in TipoIdentificacion.values
                        ):
                            raise ValidacionPersonaError(
                                "El tipo de identificación "
                                f"«{tipo_identificacion_titular}» no es "
                                "válido."
                            )

                        validar_longitud_identificacion(
                            tipo_identificacion_titular, identificacion_titular,
                        )

                        existente = buscar_persona_existente(
                            tipo_identificacion_titular, identificacion_titular,
                        )

                        if existente is not None:
                            raise PersonaExistenteError(existente)

                        persona = vinculo_titular.persona
                        cambios["persona.tipo_identificacion"] = (
                            persona.tipo_identificacion,
                            tipo_identificacion_titular,
                        )
                        cambios["persona.identificacion"] = (
                            persona.identificacion, identificacion_titular,
                        )
                        persona.tipo_identificacion = tipo_identificacion_titular
                        persona.identificacion = identificacion_titular
                        persona.save(
                            update_fields=["tipo_identificacion", "identificacion"],
                        )

                if cambios:
                    registro = registrar(
                        cuenta=request.user,
                        accion=AccionBitacora.MODIFICACION,
                        elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                        id_abonado=abonado.id_abonado,
                    )
                    registrar_modificaciones(registro, cambios)
        except ValidacionPersonaError as error:
            return Response(
                {"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST,
            )
        except PersonaExistenteError as error:
            return Response(
                {
                    "persona_existente": {
                        "id_persona": error.persona.id_persona,
                        "nombre": error.persona.nombre,
                        "numero_paja_titular": paja_titular_vigente(error.persona),
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "detail": "Los datos del abonado quedaron actualizados.",
                "numero_paja": abonado.numero_paja,
                "id_sector": abonado.sector_id,
                "tipo_abonado": abonado.tipo_abonado,
            },
        )


class AgregarPersonaAsociadaView(APIView):
    """D-06 Agregar persona asociada: cotitular o persona apoderada
    (nunca titular; eso es D-04/`CambiarTitularView`)."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        rol = request.data.get("rol")

        if rol not in (RolVinculo.COTITULAR, RolVinculo.APODERADA):
            return Response(
                {
                    "rol": [
                        "El rol debe ser cotitular o persona apoderada. "
                        "El titular se cambia con «Cambiar titular».",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha_inicio_bruta = request.data.get("fecha_inicio")

        if not fecha_inicio_bruta:
            return Response(
                {"fecha_inicio": ["La fecha de inicio es obligatoria."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fecha_inicio = datetime.date.fromisoformat(fecha_inicio_bruta)
        except (ValueError, TypeError):
            return Response(
                {
                    "fecha_inicio": [
                        f"La fecha «{fecha_inicio_bruta}» no es válida. Use "
                        "el formato aaaa-mm-dd.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                persona = resolver_o_crear_persona(
                    id_persona=request.data.get("id_persona"),
                    nombre=request.data.get("nombre"),
                    tipo_identificacion=request.data.get("tipo_identificacion"),
                    identificacion=request.data.get("identificacion"),
                )

                if VinculoAbonado.objects.filter(
                    abonado=abonado, persona=persona, fecha_fin__isnull=True,
                ).exists():
                    raise ValidacionPersonaError(
                        f"{persona.nombre} ya tiene un vínculo vigente con "
                        "este expediente. Para cambiarle el rol, use "
                        "«Cambiar rol»."
                    )

                VinculoAbonado.objects.create(
                    abonado=abonado,
                    persona=persona,
                    fecha_inicio=fecha_inicio,
                    rol=rol,
                )
                registro = registrar(
                    cuenta=request.user,
                    accion=AccionBitacora.MODIFICACION,
                    elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                    id_abonado=abonado.id_abonado,
                )
                registrar_modificaciones(
                    registro,
                    {
                        "vinculo_abonado.rol": (
                            None,
                            f"{persona.nombre} como "
                            f"{RolVinculo(rol).label.lower()}",
                        ),
                    },
                )
        except ValidacionPersonaError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except PersonaExistenteError as error:
            return Response(
                {
                    "persona_existente": {
                        "id_persona": error.persona.id_persona,
                        "nombre": error.persona.nombre,
                        "numero_paja_titular": paja_titular_vigente(error.persona),
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "No se pudo agregar la persona: revise los datos e "
                        "intente de nuevo."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": f"{persona.nombre} quedó agregada al expediente.",
                "id_persona": persona.id_persona,
                "nombre": persona.nombre,
                "rol": rol,
                "fecha_inicio": fecha_inicio,
            },
            status=status.HTTP_201_CREATED,
        )


class QuitarPersonaAsociadaView(APIView):
    """D-06 / tabla de PAN-06: cierra el vínculo de una cotitular o
    persona apoderada. No borra los documentos que aportó."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja, id_persona):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        vinculo = (
            VinculoAbonado.objects
            .filter(abonado=abonado, persona_id=id_persona, fecha_fin__isnull=True)
            .select_related("persona")
            .first()
        )

        if vinculo is None:
            return Response(
                {
                    "detail": (
                        "Esta persona no tiene un vínculo vigente con este "
                        "expediente."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if vinculo.rol == RolVinculo.TITULAR:
            return Response(
                {
                    "detail": (
                        "No se puede quitar al titular aquí. Use «Cambiar "
                        "titular»."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha_fin = timezone.localdate()

        if fecha_fin < vinculo.fecha_inicio:
            return Response(
                {
                    "detail": (
                        "La fecha de hoy es anterior al inicio de este "
                        f"vínculo ({vinculo.fecha_inicio}). Revise la fecha "
                        "del sistema."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            vinculo.fecha_fin = fecha_fin
            vinculo.save(update_fields=["fecha_fin"])

            registro = registrar(
                cuenta=request.user,
                accion=AccionBitacora.MODIFICACION,
                elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                id_abonado=abonado.id_abonado,
            )
            registrar_modificaciones(
                registro,
                {
                    "vinculo_abonado.fecha_fin": (
                        None,
                        f"{vinculo.persona.nombre} dejó de ser "
                        f"{vinculo.get_rol_display().lower()} el {fecha_fin}",
                    ),
                },
            )

        return Response(
            {
                "detail": f"{vinculo.persona.nombre} quedó quitada del expediente.",
                "fecha_fin": fecha_fin,
            },
        )


class CambiarRolPersonaAsociadaView(APIView):
    """D-06 / tabla de PAN-06: cambia el rol en el mismo vínculo abierto
    (no se abre una fila nueva; la fecha de inicio no cambia)."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja, id_persona):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        vinculo = (
            VinculoAbonado.objects
            .filter(abonado=abonado, persona_id=id_persona, fecha_fin__isnull=True)
            .select_related("persona")
            .first()
        )

        if vinculo is None:
            return Response(
                {
                    "detail": (
                        "Esta persona no tiene un vínculo vigente con este "
                        "expediente."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if vinculo.rol == RolVinculo.TITULAR:
            return Response(
                {
                    "detail": (
                        "El rol del titular no se cambia aquí. Use "
                        "«Cambiar titular»."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        rol_nuevo = request.data.get("rol")

        if rol_nuevo not in (RolVinculo.COTITULAR, RolVinculo.APODERADA):
            return Response(
                {
                    "rol": [
                        "El rol debe ser cotitular o persona apoderada.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        rol_anterior = vinculo.rol

        with transaction.atomic():
            if rol_nuevo != rol_anterior:
                vinculo.rol = rol_nuevo
                vinculo.save(update_fields=["rol"])

                registro = registrar(
                    cuenta=request.user,
                    accion=AccionBitacora.MODIFICACION,
                    elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                    id_abonado=abonado.id_abonado,
                )
                registrar_modificaciones(
                    registro,
                    {"vinculo_abonado.rol": (rol_anterior, rol_nuevo)},
                )

        return Response(
            {
                "detail": f"{vinculo.persona.nombre} quedó como "
                f"{RolVinculo(rol_nuevo).label.lower()}.",
                "rol": rol_nuevo,
            },
        )


class CambiarTitularView(APIView):
    """
    D-04 Cambiar titular (RF-13). Hallazgo H-02: se abre directo desde
    el expediente (PAN-04), no pasa por «Modificar abonado». Si la
    persona elegida ya tiene un vínculo vigente con este abonado
    (cotitular o apoderada), se cierra automáticamente antes de abrir
    el de titular (decisión del 13/11/2026, ver el plan): es la única
    forma de que la operación no choque con las restricciones reales
    de `vinculo_abonado` y preserva la intención obvia de la usuaria.
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def post(self, request, numero_paja):
        try:
            abonado = Abonado.objects.get(numero_paja=numero_paja)
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        vinculo_titular_actual = (
            VinculoAbonado.objects
            .filter(abonado=abonado, rol=RolVinculo.TITULAR, fecha_fin__isnull=True)
            .select_related("persona")
            .first()
        )

        if vinculo_titular_actual is None:
            return Response(
                {
                    "detail": (
                        "Este abonado no tiene un titular vigente que "
                        "cambiar."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha_cambio_bruta = request.data.get("fecha_cambio")

        if not fecha_cambio_bruta:
            return Response(
                {"fecha_cambio": ["La fecha del cambio es obligatoria."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fecha_cambio = datetime.date.fromisoformat(fecha_cambio_bruta)
        except (ValueError, TypeError):
            return Response(
                {
                    "fecha_cambio": [
                        f"La fecha «{fecha_cambio_bruta}» no es válida. Use "
                        "el formato aaaa-mm-dd.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fecha_cambio < vinculo_titular_actual.fecha_inicio:
            return Response(
                {
                    "fecha_cambio": [
                        "La fecha del cambio no puede ser anterior al "
                        "inicio del titular actual "
                        f"({vinculo_titular_actual.fecha_inicio}).",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                persona_nueva = resolver_o_crear_persona(
                    id_persona=request.data.get("id_persona"),
                    nombre=request.data.get("nombre"),
                    tipo_identificacion=request.data.get("tipo_identificacion"),
                    identificacion=request.data.get("identificacion"),
                )

                if persona_nueva.pk == vinculo_titular_actual.persona_id:
                    raise ValidacionPersonaError(
                        f"{persona_nueva.nombre} ya es la titular vigente "
                        "de este abonado."
                    )

                # Hallazgo H-02 / decisión del 13/11/2026: si la persona
                # elegida ya tiene un vínculo vigente (p. ej. cotitular),
                # hay que cerrarlo antes de abrir el de titular o la base
                # rechaza la operación (UniqueConstraint/ExclusionConstraint
                # de vinculo_abonado).
                vinculo_previo_persona_nueva = (
                    VinculoAbonado.objects
                    .filter(abonado=abonado, persona=persona_nueva, fecha_fin__isnull=True)
                    .first()
                )

                if (
                    vinculo_previo_persona_nueva is not None
                    and fecha_cambio < vinculo_previo_persona_nueva.fecha_inicio
                ):
                    raise ValidacionPersonaError(
                        "La fecha del cambio no puede ser anterior al "
                        "inicio del vínculo actual de "
                        f"{persona_nueva.nombre} "
                        f"({vinculo_previo_persona_nueva.fecha_inicio})."
                    )

                rol_anterior_persona_nueva = None
                # `VinculoAbonado` usa (abonado, persona, fecha_inicio) como
                # llave primaria compuesta. Si el vínculo vigente de la
                # persona elegida empezó el mismo día que `fecha_cambio`,
                # cerrarlo y crear uno nuevo chocaría con esa misma llave
                # (mismo abonado+persona+fecha_inicio) — en ese caso se
                # reutiliza la fila: solo cambia el rol a TITULAR, sin
                # tocar fechas. Si empezó antes, sí se cierra y se abre
                # una fila nueva (fechas distintas, sin conflicto de PK).
                reutiliza_misma_fila = (
                    vinculo_previo_persona_nueva is not None
                    and vinculo_previo_persona_nueva.fecha_inicio == fecha_cambio
                )

                if vinculo_previo_persona_nueva is not None:
                    rol_anterior_persona_nueva = vinculo_previo_persona_nueva.rol

                    if not reutiliza_misma_fila:
                        vinculo_previo_persona_nueva.fecha_fin = fecha_cambio
                        vinculo_previo_persona_nueva.save(update_fields=["fecha_fin"])

                # Cerrar primero al titular actual: si se reutiliza la
                # fila de la persona elegida, cambiarle el rol a TITULAR
                # antes de cerrar al titular actual dejaría, por un
                # instante dentro de la misma transacción, dos vínculos
                # TITULAR vigentes a la vez para este abonado — choca con
                # `vinculo_abonado_un_titular_vigente` (se comprueba por
                # sentencia, no al final de la transacción).
                vinculo_titular_actual.fecha_fin = fecha_cambio
                vinculo_titular_actual.save(update_fields=["fecha_fin"])

                if reutiliza_misma_fila:
                    vinculo_previo_persona_nueva.rol = RolVinculo.TITULAR
                    vinculo_previo_persona_nueva.save(update_fields=["rol"])

                if not reutiliza_misma_fila:
                    VinculoAbonado.objects.create(
                        abonado=abonado,
                        persona=persona_nueva,
                        fecha_inicio=fecha_cambio,
                        rol=RolVinculo.TITULAR,
                    )

                registro = registrar(
                    cuenta=request.user,
                    accion=AccionBitacora.CAMBIO_TITULAR,
                    elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
                    id_abonado=abonado.id_abonado,
                )
                cambios = {
                    "vinculo_abonado.id_persona": (
                        vinculo_titular_actual.persona.nombre,
                        persona_nueva.nombre,
                    ),
                }
                if rol_anterior_persona_nueva is not None:
                    cambios["vinculo_abonado.rol"] = (
                        f"{persona_nueva.nombre} era "
                        f"{RolVinculo(rol_anterior_persona_nueva).label.lower()}",
                        f"{persona_nueva.nombre} es titular",
                    )
                registrar_modificaciones(registro, cambios)
        except ValidacionPersonaError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except PersonaExistenteError as error:
            return Response(
                {
                    "persona_existente": {
                        "id_persona": error.persona.id_persona,
                        "nombre": error.persona.nombre,
                        "numero_paja_titular": paja_titular_vigente(error.persona),
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "No se pudo cambiar el titular: revise los datos e "
                        "intente de nuevo."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": f"{persona_nueva.nombre} quedó como titular.",
                "numero_paja": abonado.numero_paja,
                "titular_vigente": persona_nueva.nombre,
                "fecha_cambio": fecha_cambio,
            },
        )


class VistaPreviaImportacionAbonadosView(APIView):
    """
    RF-04 Importar listado de SADA (PAN-09, paso 2 "revisar columnas"):
    parsea el archivo y devuelve sus columnas + la fila de ejemplo (fila
    2) + el total de filas, sin guardar nada.
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        archivo = request.FILES.get("archivo")

        if archivo is None:
            return Response(
                {"archivo": ["Debe elegir un archivo."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = generar_vista_previa(archivo)
        except ArchivoImportacionError as error:
            return Response(
                {"archivo": [str(error)]}, status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "columnas": resultado.columnas,
                "ejemplo_fila_2": resultado.ejemplo_fila_2,
                "total_filas": resultado.total_filas,
            },
        )


class ImportarAbonadosView(APIView):
    """
    RF-04 Importar listado de SADA (PAN-09, paso 3 "importar"): manda
    el archivo otra vez + el mapeo de columnas elegido; crea un abonado
    por cada paja no registrada, en una sola transacción para todo el
    archivo (ADR-04).
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        archivo = request.FILES.get("archivo")

        if archivo is None:
            return Response(
                {"archivo": ["Debe elegir un archivo."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        columna_paja = (request.data.get("columna_paja") or "").strip()
        columna_nombre = (request.data.get("columna_nombre") or "").strip()

        if not columna_paja:
            return Response(
                {"columna_paja": ["Elija la columna del número de paja."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not columna_nombre:
            return Response(
                {
                    "columna_nombre": [
                        "Elija la columna del nombre del titular.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = importar_lote(
                archivo=archivo,
                columna_paja=columna_paja,
                columna_nombre=columna_nombre,
                cuenta=request.user,
            )
        except ArchivoImportacionError as error:
            return Response(
                {"archivo": [str(error)]}, status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "importados": resultado.importados,
                "omitidos": resultado.omitidos,
                "rechazados": [
                    {
                        "fila": fila.fila,
                        "problema": fila.problema,
                        "que_hacer": fila.que_hacer,
                    }
                    for fila in resultado.rechazados
                ],
                "fecha": resultado.fecha,
            },
        )


class PanelCompletitudView(APIView):
    """
    PAN-07 Completitud (RF-14): tarjetas globales + lista de
    incompletos + lista de tipo pendiente, en una sola respuesta.
    Los abonados de baja no cuentan en los totales (confirmado); con
    `mostrar_de_baja=true` se informa aparte cuántos son, sin tocar el
    cálculo global.
    """

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request):
        id_sector = request.query_params.get("id_sector")

        if id_sector is not None and not id_sector.isdigit():
            return Response(
                {
                    "detail": (
                        f"El sector «{id_sector}» no es válido. Elija un "
                        "sector de la lista."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo_abonado = request.query_params.get("tipo_abonado") or None

        if tipo_abonado is not None and tipo_abonado not in TipoAbonado.values:
            return Response(
                {
                    "detail": (
                        f"El tipo de abonado «{tipo_abonado}» no es válido. "
                        "Elija una opción de la lista."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        documento_faltante = request.query_params.get("documento_faltante") or None
        mostrar_de_baja = request.query_params.get("mostrar_de_baja") == "true"

        filtros = {
            "id_sector": int(id_sector) if id_sector else None,
            "tipo_abonado": tipo_abonado,
        }

        respuesta = {
            "tarjetas": resumen_completitud_global(filtros),
            "incompletos": listar_incompletos(
                {**filtros, "documento_faltante": documento_faltante},
            ),
            "tipo_pendiente": listar_tipo_pendiente(filtros),
        }

        if mostrar_de_baja:
            queryset_baja = Abonado.objects.filter(estado=EstadoAbonado.DE_BAJA)

            if filtros["id_sector"]:
                queryset_baja = queryset_baja.filter(sector_id=filtros["id_sector"])

            if filtros["tipo_abonado"]:
                queryset_baja = queryset_baja.filter(
                    tipo_abonado=filtros["tipo_abonado"],
                )

            respuesta["de_baja"] = {"cantidad": queryset_baja.count()}

        return Response(respuesta)


class DetalleCompletitudAbonadoView(APIView):
    """PAN-07 (vista detalle): completitud de un abonado + matriz
    "documento obligatorio × titular × cotitular"."""

    authentication_classes = [AutenticacionCuenta]
    permission_classes = [CuentaAutenticadaPermission]

    def get(self, request, numero_paja):
        try:
            abonado = Abonado.objects.select_related("sector").get(
                numero_paja=numero_paja,
            )
        except Abonado.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"No existe un expediente con el número de paja "
                        f"{numero_paja}."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        resultado = calcular_completitud(abonado)

        return Response(
            {
                "numero_paja": abonado.numero_paja,
                "tipo_abonado": abonado.tipo_abonado,
                "completo": resultado["completo"],
                "faltantes": resultado["faltantes"],
                "matriz": matriz_completitud(abonado),
            },
        )
