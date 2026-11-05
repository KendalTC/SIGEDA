"""
CLAUDE.md sección 5 "Catálogos iniciales" y Fase 2 (paso 9 del prompt
de construcción): datos de prueba ficticios para comprobar el
prototipo vertical de CU-04. Solo nombres y cédulas inventados (regla
3 de CLAUDE.md): tomo 0000, no existe en el Registro Civil.

Repetible: usa get_or_create, no falla si ya se corrió antes.
"""

import datetime

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.abonados.models import Abonado, Persona, Sector, TipoAbonado, VinculoAbonado
from apps.accounts.models import Cuenta, PerfilCuenta

FECHA_FUNDACION = datetime.date(1998, 7, 1)
FECHA_CAMBIO_TITULAR = datetime.date(2026, 2, 10)


class Command(BaseCommand):
    help = "Carga datos ficticios de prueba: abonado 0412 y cuentas secretaria/administracion."

    @transaction.atomic
    def handle(self, *args, **options):
        sector_bodegas, _ = Sector.objects.get_or_create(nombre="Bodegas")

        abonado, creado = Abonado.objects.get_or_create(
            numero_paja="0412",
            defaults={
                "sector": sector_bodegas,
                "tipo_abonado": TipoAbonado.PERSONA_FISICA,
            },
        )

        if creado:
            rodrigo, _ = Persona.objects.get_or_create(
                nombre="Rodrigo Mora Castro",
                defaults={
                    "tipo_identificacion": "CEDULA_FISICA",
                    "identificacion": "1-0000-0789",
                },
            )
            ana_lucia, _ = Persona.objects.get_or_create(
                nombre="Ana Lucía Mora Vega",
                defaults={
                    "tipo_identificacion": "CEDULA_FISICA",
                    "identificacion": "1-0000-0123",
                },
            )
            esteban, _ = Persona.objects.get_or_create(
                nombre="Esteban Mora Vega",
                defaults={
                    "tipo_identificacion": "CEDULA_FISICA",
                    "identificacion": "2-0000-0456",
                },
            )

            VinculoAbonado.objects.get_or_create(
                abonado=abonado,
                persona=rodrigo,
                fecha_inicio=FECHA_FUNDACION,
                defaults={"rol": "TITULAR", "fecha_fin": FECHA_CAMBIO_TITULAR},
            )
            VinculoAbonado.objects.get_or_create(
                abonado=abonado,
                persona=ana_lucia,
                fecha_inicio=FECHA_CAMBIO_TITULAR,
                defaults={"rol": "TITULAR", "fecha_fin": None},
            )
            VinculoAbonado.objects.get_or_create(
                abonado=abonado,
                persona=esteban,
                fecha_inicio=FECHA_CAMBIO_TITULAR,
                defaults={"rol": "COTITULAR", "fecha_fin": None},
            )

            self.stdout.write(
                self.style.SUCCESS("Abonado 0412 creado con titular, cotitular y titular anterior.")
            )
        else:
            self.stdout.write("Abonado 0412 ya existía; no se tocó.")

        for usuario, perfil in [
            ("secretaria", PerfilCuenta.SECRETARIA),
            ("administracion", PerfilCuenta.ADMINISTRADORA),
        ]:
            _, creada = Cuenta.objects.get_or_create(
                usuario=usuario,
                defaults={
                    "hash_contrasena": make_password(f"{usuario.capitalize()}2026!"),
                    "perfil": perfil,
                },
            )

            if creada:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cuenta '{usuario}' creada (contraseña de prueba: "
                        f"{usuario.capitalize()}2026!)."
                    )
                )
            else:
                self.stdout.write(f"Cuenta '{usuario}' ya existía; no se tocó.")
