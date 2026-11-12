"""
CLAUDE.md paso 10: una prueba automática por cada restricción del
Modelo ER v1.1 relevante a esta app (un solo titular vigente, sin
periodos superpuestos, cédula única, CHECK de abonado de baja, etc.).
También RF-10 Buscar expedientes (consulta Q1), para PAN-03.
"""

import datetime

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Cuenta, TokenCuenta

from . import controlador_busqueda as cb
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

    def test_tipo_abonado_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Abonado.objects.create(
                    numero_paja="9004", tipo_abonado="INVALIDO",
                )

    def test_numero_paja_con_letras_se_rechaza(self):
        """RN-01 y Anexo B: numero_paja es solo dígitos (CLAUDE.md sección 9)."""

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Abonado.objects.create(
                    numero_paja="04A2", tipo_abonado=TipoAbonado.PERSONA_FISICA,
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

    def test_tipo_identificacion_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Persona.objects.create(
                    nombre="Persona con tipo inválido",
                    tipo_identificacion="INVALIDO",
                    identificacion="1-0000-0002",
                )


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

    def test_rol_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VinculoAbonado.objects.create(
                    abonado=self.abonado,
                    persona=self.persona_1,
                    fecha_inicio=datetime.date(2026, 1, 1),
                    rol="INVALIDO",
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


class EnmascararIdentificacionTests(TestCase):
    def test_cedula_con_guiones(self):
        self.assertEqual(
            cb.enmascarar_identificacion("1-0000-0123"), "1-••••-0123",
        )

    def test_sin_identificacion(self):
        self.assertIsNone(cb.enmascarar_identificacion(None))

    def test_sin_guiones(self):
        self.assertEqual(cb.enmascarar_identificacion("AB123456"), "AB••••56")


class BuscarAbonadosTests(TestCase):
    """RF-10, consulta Q1: por paja, nombre, identificación y sector,
    solos o combinados."""

    def setUp(self):
        self.bodegas = Sector.objects.create(nombre="Bodegas de prueba")
        self.pilas = Sector.objects.create(nombre="Pilas de prueba")

        self.abonado_412 = Abonado.objects.create(
            numero_paja="0412",
            sector=self.bodegas,
            tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular_412 = Persona.objects.create(
            nombre="Ana Lucía Mora Vega",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0123",
        )
        VinculoAbonado.objects.create(
            abonado=self.abonado_412,
            persona=self.titular_412,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

        self.abonado_413 = Abonado.objects.create(
            numero_paja="0413",
            sector=self.pilas,
            tipo_abonado=TipoAbonado.PERSONA_FISICA,
            estado="DE_BAJA",
            fecha_baja=datetime.date(2025, 1, 1),
        )
        self.titular_413 = Persona.objects.create(
            nombre="Esteban Mora Vega",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="2-0000-0456",
        )
        VinculoAbonado.objects.create(
            abonado=self.abonado_413,
            persona=self.titular_413,
            fecha_inicio=datetime.date(2019, 1, 1),
            fecha_fin=datetime.date(2025, 1, 1),
            rol="TITULAR",
        )

    def test_por_numero_paja_exacto(self):
        resultado = cb.buscar(numero_paja="0412")
        self.assertEqual(resultado.total, 1)
        self.assertEqual(
            resultado.resultados[0]["titular_vigente"], "Ana Lucía Mora Vega",
        )

    def test_por_numero_paja_coincide_por_el_inicio(self):
        resultado = cb.buscar(numero_paja="04")
        self.assertEqual(resultado.total, 2)

    def test_por_nombre_insensible_a_tildes_y_mayusculas(self):
        resultado = cb.buscar(nombre="ANA LUCIA")
        self.assertEqual(resultado.total, 1)
        self.assertEqual(resultado.resultados[0]["numero_paja"], "0412")

    def test_por_identificacion_normaliza_guiones(self):
        resultado = cb.buscar(identificacion="100000123")
        self.assertEqual(resultado.total, 1)
        self.assertEqual(resultado.resultados[0]["numero_paja"], "0412")

    def test_por_sector(self):
        resultado = cb.buscar(id_sector=self.pilas.id_sector)
        self.assertEqual(resultado.total, 1)
        self.assertEqual(resultado.resultados[0]["numero_paja"], "0413")

    def test_criterios_combinados_son_un_y(self):
        resultado = cb.buscar(numero_paja="04", nombre="Mora Vega", id_sector=self.bodegas.id_sector)
        self.assertEqual(resultado.total, 1)
        self.assertEqual(resultado.resultados[0]["numero_paja"], "0412")

    def test_sin_coincidencias(self):
        resultado = cb.buscar(numero_paja="9999")
        self.assertEqual(resultado.total, 0)
        self.assertEqual(resultado.resultados, [])

    def test_incluir_baja_false_excluye_de_baja(self):
        """RN-08: la baja no elimina, pero se puede excluir de la lista."""

        resultado = cb.buscar(numero_paja="04", incluir_baja=False)
        self.assertEqual(resultado.total, 1)
        self.assertEqual(resultado.resultados[0]["numero_paja"], "0412")

    def test_incluir_baja_true_por_defecto(self):
        resultado = cb.buscar(numero_paja="04")
        self.assertEqual(resultado.total, 2)

    def test_identificacion_parcial_queda_enmascarada(self):
        resultado = cb.buscar(numero_paja="0412")
        self.assertEqual(
            resultado.resultados[0]["identificacion_parcial"], "1-••••-0123",
        )

    def test_limite_de_resultados(self):
        for i in range(60):
            Abonado.objects.create(
                numero_paja=f"5{i:03d}", tipo_abonado=TipoAbonado.PENDIENTE,
            )

        resultado = cb.buscar(numero_paja="5")
        self.assertEqual(resultado.total, 60)
        self.assertEqual(resultado.mostrados, cb.LIMITE_RESULTADOS)
        self.assertEqual(len(resultado.resultados), cb.LIMITE_RESULTADOS)


class BuscarAbonadosViewTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria_busqueda",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        self.abonado = Abonado.objects.create(
            numero_paja="0412", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )

    def test_requiere_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.get(
            reverse("abonados:buscar"), {"numero_paja": "0412"},
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_sin_ningun_criterio_responde_400(self):
        respuesta = self.cliente.get(reverse("abonados:buscar"))
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("criterio", respuesta.data["detail"])

    def test_con_numero_paja_responde_200_con_la_forma_esperada(self):
        respuesta = self.cliente.get(
            reverse("abonados:buscar"), {"numero_paja": "0412"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            set(respuesta.data.keys()),
            {"total", "mostrados", "tiempo_segundos", "resultados"},
        )
        self.assertEqual(respuesta.data["total"], 1)

    def test_id_sector_no_numerico_responde_400(self):
        respuesta = self.cliente.get(
            reverse("abonados:buscar"), {"id_sector": "abc"},
        )
        self.assertEqual(respuesta.status_code, 400)


class SectoresViewTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        cuenta = Cuenta.objects.create(
            usuario="secretaria_sectores",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=cuenta)
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

    def test_lista_los_sectores_del_catalogo_inicial(self):
        respuesta = self.cliente.get(reverse("sigeda_configuration:sectores"))
        self.assertEqual(respuesta.status_code, 200)
        nombres = {fila["nombre"] for fila in respuesta.data}
        self.assertIn("Bodegas", nombres)
        self.assertIn("Pilas", nombres)
