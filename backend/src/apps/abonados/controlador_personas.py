"""
Funciones compartidas por el alta de abonado (RF-02, PAN-06), agregar
persona asociada (D-06) y cambiar titular (D-04, RF-13): resolver si
una persona ya existe o hay que crearla, validar la longitud de la
identificación por tipo y detectar duplicados por cédula (mismo
patrón de normalización que `controlador_busqueda.buscar()`).
"""

import re

from .controlador_busqueda import _SoloAlfanumerico
from .models import Persona, RolVinculo, TipoIdentificacion

# RN y Anexo B (CLAUDE.md sección 9): cédula física 9 dígitos, cédula
# jurídica 10 (SUPUESTO: se asumen 10, pendiente con la administradora),
# DIMEX 11 o 12. Pasaporte no tiene longitud fija (alfanumérico).
_LONGITUDES_IDENTIFICACION = {
    TipoIdentificacion.CEDULA_FISICA: (9, 9),
    TipoIdentificacion.CEDULA_JURIDICA: (10, 10),
    TipoIdentificacion.DIMEX: (11, 12),
}

_EJEMPLOS_IDENTIFICACION = {
    TipoIdentificacion.CEDULA_FISICA: "1-0000-0123",
    TipoIdentificacion.CEDULA_JURIDICA: "3-101-000000",
}

_NOMBRES_TIPO_IDENTIFICACION = {
    TipoIdentificacion.CEDULA_FISICA: "La cédula física",
    TipoIdentificacion.CEDULA_JURIDICA: "La cédula jurídica",
    TipoIdentificacion.DIMEX: "El DIMEX",
}


class ValidacionPersonaError(Exception):
    """Mensaje con causa y acción (RNF-02), listo para mostrar tal cual."""


class PersonaExistenteError(Exception):
    """Ya existe una persona con esa cédula. No se crea nada: quien
    llama responde 409 y le ofrece a la usuaria reutilizarla."""

    def __init__(self, persona: Persona):
        self.persona = persona
        super().__init__(f"Ya existe una persona con esa cédula: {persona.nombre}.")


def _contar_digitos(identificacion: str) -> int:
    return len(re.sub(r"[^0-9]", "", identificacion))


def validar_longitud_identificacion(tipo_identificacion: str, identificacion: str) -> None:
    """Lanza ValidacionPersonaError si la cantidad de dígitos no corresponde
    al tipo. PASAPORTE no tiene longitud fija y no se valida acá."""

    rango = _LONGITUDES_IDENTIFICACION.get(tipo_identificacion)

    if rango is None:
        return

    minimo, maximo = rango
    cantidad = _contar_digitos(identificacion)

    if minimo <= cantidad <= maximo:
        return

    nombre_tipo = _NOMBRES_TIPO_IDENTIFICACION[tipo_identificacion]
    descripcion_longitud = (
        f"{minimo} dígitos" if minimo == maximo else f"{minimo} o {maximo} dígitos"
    )
    ejemplo = _EJEMPLOS_IDENTIFICACION.get(tipo_identificacion)
    texto_ejemplo = f" (ejemplo {ejemplo})" if ejemplo else ""

    raise ValidacionPersonaError(
        f"⚠ {nombre_tipo} tiene {descripcion_longitud}{texto_ejemplo} y aquí "
        f"hay {cantidad}. Revise el número."
    )


def buscar_persona_existente(tipo_identificacion: str, identificacion: str) -> Persona | None:
    """Busca una persona con la misma cédula, ignorando guiones y
    espacios (mismo patrón que `controlador_busqueda._SoloAlfanumerico`)."""

    identificacion_normalizada = "".join(
        ch for ch in identificacion if ch.isalnum()
    )

    if not identificacion_normalizada:
        return None

    return (
        Persona.objects
        .alias(identificacion_normalizada_db=_SoloAlfanumerico("identificacion"))
        .filter(
            tipo_identificacion=tipo_identificacion,
            identificacion_normalizada_db__iexact=identificacion_normalizada,
        )
        .first()
    )


def paja_titular_vigente(persona: Persona) -> str | None:
    """Para el aviso de persona existente (409): la paja del abonado del
    que esta persona es titular vigente, si tiene uno."""

    vinculo = (
        persona.vinculos
        .filter(rol=RolVinculo.TITULAR, fecha_fin__isnull=True)
        .select_related("abonado")
        .first()
    )

    return vinculo.abonado.numero_paja if vinculo else None


def resolver_o_crear_persona(
    *,
    id_persona=None,
    nombre: str | None = None,
    tipo_identificacion: str | None = None,
    identificacion: str | None = None,
) -> Persona:
    """
    Devuelve la `Persona` elegida (`id_persona`) o valida y crea una
    nueva. Debe llamarse dentro de la transacción de quien invoca (no
    hace commit por sí misma). Lanza `ValidacionPersonaError` (400) o
    `PersonaExistenteError` (409: no crea nada).
    """

    if id_persona:
        try:
            return Persona.objects.get(pk=id_persona)
        except (Persona.DoesNotExist, ValueError, TypeError):
            raise ValidacionPersonaError("La persona elegida no existe.")

    nombre = (nombre or "").strip()

    if not nombre:
        raise ValidacionPersonaError("El nombre de la persona es obligatorio.")

    tipo_identificacion = (tipo_identificacion or "").strip() or None
    identificacion = (identificacion or "").strip() or None

    if bool(tipo_identificacion) != bool(identificacion):
        raise ValidacionPersonaError(
            "El tipo y el número de identificación se deben completar juntos."
        )

    if tipo_identificacion is None:
        raise ValidacionPersonaError(
            "El tipo y el número de identificación son obligatorios."
        )

    if tipo_identificacion not in TipoIdentificacion.values:
        raise ValidacionPersonaError(
            f"El tipo de identificación «{tipo_identificacion}» no es válido."
        )

    validar_longitud_identificacion(tipo_identificacion, identificacion)

    existente = buscar_persona_existente(tipo_identificacion, identificacion)

    if existente is not None:
        raise PersonaExistenteError(existente)

    return Persona.objects.create(
        nombre=nombre,
        tipo_identificacion=tipo_identificacion,
        identificacion=identificacion,
    )
