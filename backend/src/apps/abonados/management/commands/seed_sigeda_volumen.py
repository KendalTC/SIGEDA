"""
RNF-05/EC-04: para medir la búsqueda (RF-10) con un volumen realista
hay que probarla contra algo parecido a los 1 015 abonados reales de
la ASADA (CLAUDE.md sección 1), no contra un par de filas. Todos los
nombres y cédulas son ficticios (tomo 0000, regla 3 de CLAUDE.md).

Repetible: si ya hay 1015 o más abonados, no agrega nada.
"""

import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.abonados.models import Abonado, Persona, Sector, TipoAbonado, VinculoAbonado

TOTAL_OBJETIVO = 1015
NUMERO_PAJA_INICIAL = 200000
CEDULA_BASE = 9000

NOMBRES = [
    "María", "José", "Ana", "Carlos", "Luisa", "Rafael", "Marta", "Diego",
    "Sofía", "Andrés", "Gabriela", "Mario", "Paola", "Fernando", "Daniela",
]
APELLIDOS = [
    "Vega", "Castro", "Mora", "Rojas", "Araya", "Chaves", "Solís", "Alfaro",
    "Jiménez", "Rodríguez", "Cordero", "Sandí", "Quesada", "Brenes", "Zúñiga",
]


class Command(BaseCommand):
    help = (
        f"Carga abonados ficticios de volumen hasta llegar a "
        f"{TOTAL_OBJETIVO} (RNF-05/EC-04)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        existentes = Abonado.objects.count()
        faltan = TOTAL_OBJETIVO - existentes

        if faltan <= 0:
            self.stdout.write(
                f"Ya hay {existentes} abonados; no se agregó ninguno.",
            )
            return

        sectores = list(Sector.objects.all())
        rng = random.Random(2026)  # semilla fija: reproducible

        for i in range(faltan):
            numero_paja = str(NUMERO_PAJA_INICIAL + i)
            nombre = (
                f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} "
                f"{rng.choice(APELLIDOS)}"
            )
            identificacion = f"{rng.randint(1, 9)}-0000-{CEDULA_BASE + i}"

            persona = Persona.objects.create(
                nombre=nombre,
                tipo_identificacion="CEDULA_FISICA",
                identificacion=identificacion,
            )
            abonado = Abonado.objects.create(
                numero_paja=numero_paja,
                sector=rng.choice(sectores) if sectores else None,
                tipo_abonado=TipoAbonado.PERSONA_FISICA,
            )
            VinculoAbonado.objects.create(
                abonado=abonado,
                persona=persona,
                fecha_inicio=datetime.date(2010, 1, 1),
                rol="TITULAR",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Creados {faltan} abonados ficticios de volumen "
                f"(total ahora: {Abonado.objects.count()}).",
            ),
        )
