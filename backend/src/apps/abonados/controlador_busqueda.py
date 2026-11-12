"""
ControladorBusqueda (RF-10, consulta Q1, fachada IConsultas). Busca
abonados por número de paja, nombre del titular vigente, identificación
y sector, solos o combinados (Modelo ER v1.1, consulta Q1). No filtra
por personas fusionadas: esa columna (`persona.id_persona_fusionada_en`)
se quitó del modelo el 04/11/2026.
"""

import time
import unicodedata
from dataclasses import dataclass, field

from django.contrib.postgres.lookups import Unaccent
from django.db.models import Func
from django.db.models.functions import Lower

from .models import Abonado

LIMITE_RESULTADOS = 50


class _SoloAlfanumerico(Func):
    """REGEXP_REPLACE que quita todo lo que no sea letra o dígito, para
    comparar identificaciones sin importar guiones ni espacios."""

    function = "REGEXP_REPLACE"
    template = "%(function)s(%(expressions)s, '[^A-Za-z0-9]', '', 'g')"
    arity = 1


@dataclass
class ResultadoBusqueda:
    total: int
    resultados: list
    tiempo_segundos: float
    mostrados: int = field(init=False)

    def __post_init__(self):
        self.mostrados = len(self.resultados)


def _normalizar_identificacion(valor: str) -> str:
    return "".join(ch for ch in valor if ch.isalnum())


def _sin_tildes(valor: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(ch)
    )


def enmascarar_identificacion(identificacion: str | None) -> str | None:
    """
    Guía de estilo de SIGEDA: se oculta parcialmente en las listas
    (por ejemplo 1-••••-0123). Deja visible el primer y el último
    bloque separados por guion; si no hay guiones, deja visibles los
    primeros y los últimos 2 caracteres.
    """

    if not identificacion:
        return None

    partes = identificacion.split("-")

    if len(partes) >= 3:
        return f"{partes[0]}-{'•' * 4}-{partes[-1]}"

    if len(identificacion) <= 4:
        return identificacion

    return f"{identificacion[:2]}{'•' * 4}{identificacion[-2:]}"


def buscar(
    *,
    numero_paja: str | None = None,
    nombre: str | None = None,
    identificacion: str | None = None,
    id_sector: int | None = None,
    incluir_baja: bool = True,
) -> ResultadoBusqueda:
    inicio = time.perf_counter()

    queryset = Abonado.objects.select_related("sector")

    if not incluir_baja:
        queryset = queryset.filter(estado="ACTIVO")

    if numero_paja:
        queryset = queryset.filter(numero_paja__startswith=numero_paja.strip())

    if id_sector:
        queryset = queryset.filter(sector_id=id_sector)

    if nombre:
        nombre_normalizado = _sin_tildes(nombre.strip()).lower()
        queryset = queryset.alias(
            titular_nombre_normalizado=Lower(Unaccent("vinculos__persona__nombre")),
        ).filter(
            vinculos__rol="TITULAR",
            vinculos__fecha_fin__isnull=True,
            titular_nombre_normalizado__icontains=nombre_normalizado,
        )

    if identificacion:
        identificacion_normalizada = _normalizar_identificacion(identificacion)
        queryset = queryset.alias(
            identificacion_normalizada_db=_SoloAlfanumerico(
                "vinculos__persona__identificacion",
            ),
        ).filter(
            vinculos__rol="TITULAR",
            vinculos__fecha_fin__isnull=True,
            identificacion_normalizada_db__icontains=identificacion_normalizada,
        )

    queryset = queryset.distinct().order_by("numero_paja")

    total = queryset.count()
    pagina = list(queryset[:LIMITE_RESULTADOS])

    resultados = []

    for abonado in pagina:
        vinculo_titular = (
            abonado.vinculos
            .filter(rol="TITULAR", fecha_fin__isnull=True)
            .select_related("persona")
            .first()
        )
        titular = vinculo_titular.persona if vinculo_titular else None

        resultados.append(
            {
                "numero_paja": abonado.numero_paja,
                "titular_vigente": titular.nombre if titular else None,
                "identificacion_parcial": (
                    enmascarar_identificacion(titular.identificacion)
                    if titular else None
                ),
                "sector": abonado.sector.nombre if abonado.sector else None,
                "tipo_abonado": abonado.tipo_abonado,
                "estado": abonado.estado,
            }
        )

    tiempo_segundos = round(time.perf_counter() - inicio, 3)

    return ResultadoBusqueda(
        total=total, resultados=resultados, tiempo_segundos=tiempo_segundos,
    )
