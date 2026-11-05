"""
CLAUDE.md paso 10: una prueba automática por cada restricción del
Modelo ER v1.1 relevante a esta app (un solo titular vigente, sin
periodos superpuestos, cédula única, CHECK de abonado de baja, etc.).
"""

import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Abonado, Persona, Sector, TipoAbonado, VinculoAbonado


class AbonadoConstraintsTests(TestCase):
    def test_de_baja_requiere_fecha_baja(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Abonado.objects.create(
                    numero_paja="9001",
                    tipo_abonado=TipoAbonado.PERSONA_FISICA,
                    estado="DE_BAJA",
                    fecha_baja=None,
                )

    def test_activo_no_puede_tener_fecha_baja(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Abonado.objects.create(
                    numero_paja="9002",
                    tipo_abonado=TipoAbonado.PERSONA_FISICA,
                    estado="ACTIVO",
                    fecha_baja=datetime.date(2026, 1, 1),
                )

    def test_numero_paja_unico(self):
        Abonado.objects.create(
            numero_paja="9003", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Abonado.objects.create(
                    numero_paja="9003", tipo_abonado=TipoAbonado.PERSONA_FISICA,
                )


class PersonaConstraintsTests(TestCase):
    def test_identificacion_unica(self):
        Persona.objects.create(
            nombre="Persona Uno",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0001",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Persona.objects.create(
                    nombre="Persona Dos (misma cédula)",
                    tipo_identificacion="CEDULA_FISICA",
                    identificacion="1-0000-0001",
                )

    def test_identificacion_se_llena_junto_con_tipo(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Persona.objects.create(
                    nombre="Persona Incompleta",
                    tipo_identificacion="CEDULA_FISICA",
                    identificacion=None,
                )

    def test_persona_sin_identificacion_es_valida(self):
        """Importación de SADA (RF-04): persona sin identificación todavía."""

        persona = Persona.objects.create(nombre="Persona Pendiente")
        self.assertIsNone(persona.tipo_identificacion)

    def test_dos_personas_sin_identificacion_no_chocan(self):
        """La UQ parcial no aplica cuando ambos campos son NULL."""

        Persona.objects.create(nombre="Persona A")
        Persona.objects.create(nombre="Persona B")  # no debe fallar


class VinculoAbonadoConstraintsTests(TestCase):
    def setUp(self):
        self.abonado = Abonado.objects.create(
            numero_paja="9100", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.persona_1 = Persona.objects.create(nombre="Titular Uno")
        self.persona_2 = Persona.objects.create(nombre="Titular Dos")

    def test_un_solo_titular_vigente(self):
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_1,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VinculoAbonado.objects.create(
                    abonado=self.abonado,
                    persona=self.persona_2,
                    fecha_inicio=datetime.date(2021, 1, 1),
                    rol="TITULAR",
                )

    def test_titular_puede_cambiar_el_mismo_dia(self):
        """Rango semiabierto '[)': un titular puede terminar el mismo
        día en que empieza el siguiente (Modelo_Relacional_SIGEDA_v1.1_Contexto.md)."""

        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_1,
            fecha_inicio=datetime.date(2020, 1, 1),
            fecha_fin=datetime.date(2026, 2, 10),
            rol="TITULAR",
        )

        # No debe lanzar: el periodo del segundo empieza justo donde
        # termina el primero.
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_2,
            fecha_inicio=datetime.date(2026, 2, 10),
            rol="TITULAR",
        )

    def test_titulares_superpuestos_se_rechazan(self):
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_1,
            fecha_inicio=datetime.date(2020, 1, 1),
            fecha_fin=datetime.date(2026, 3, 1),
            rol="TITULAR",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VinculoAbonado.objects.create(
                    abonado=self.abonado,
                    persona=self.persona_2,
                    fecha_inicio=datetime.date(2026, 2, 10),
                    rol="TITULAR",
                )

    def test_misma_pareja_sin_periodos_superpuestos(self):
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_1,
            fecha_inicio=datetime.date(2020, 1, 1),
            fecha_fin=datetime.date(2022, 1, 1),
            rol="COTITULAR",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VinculoAbonado.objects.create(
                    abonado=self.abonado,
                    persona=self.persona_1,
                    fecha_inicio=datetime.date(2021, 6, 1),
                    fecha_fin=datetime.date(2023, 1, 1),
                    rol="COTITULAR",
                )

    def test_fecha_fin_no_puede_ser_anterior_a_inicio(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VinculoAbonado.objects.create(
                    abonado=self.abonado,
                    persona=self.persona_1,
                    fecha_inicio=datetime.date(2026, 1, 1),
                    fecha_fin=datetime.date(2025, 1, 1),
                    rol="COTITULAR",
                )

    def test_dos_cotitulares_vigentes_a_la_vez_si_permitido(self):
        """RN-02 solo exige un TITULAR vigente; cotitulares sí pueden
        coexistir."""

        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_1,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="COTITULAR",
        )
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.persona_2,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="COTITULAR",
        )

        self.assertEqual(
            VinculoAbonado.objects.filter(
                abonado=self.abonado, fecha_fin__isnull=True,
            ).count(),
            2,
        )
