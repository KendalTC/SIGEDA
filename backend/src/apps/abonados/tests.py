"""
CLAUDE.md paso 10: una prueba automática por cada restricción del
Modelo ER v1.1 relevante a esta app (un solo titular vigente, sin
periodos superpuestos, cédula única, CHECK de abonado de baja, etc.).
También RF-10 Buscar expedientes (consulta Q1), para PAN-03.
"""

import csv
import datetime
import io

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.accounts.models import Cuenta, TokenCuenta
from apps.bitacora.models import AccionBitacora, RegistroBitacora, RegistroModificacion
from apps.configuration.models import TipoDocumento
from apps.documents.models import Documento, VersionDocumento

from . import controlador_busqueda as cb
from .importacion.lectores import (
    ArchivoImportacionError,
    LectorArchivoExcel,
    LectorArchivoTexto,
    elegir_lector,
)
from .models import (
    Abonado,
    EstadoAbonado,
    Persona,
    RolVinculo,
    Sector,
    TipoAbonado,
    VinculoAbonado,
)
from .serializers import AbonadoSerializer
from .servicio_completitud import (
    calcular_completitud,
    listar_incompletos,
    listar_tipo_pendiente,
    resumen_completitud_global,
)


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


class CompletitudAbonadoTests(TestCase):
    """
    Q3 (RF-14): servicio reutilizable de completitud. Hoy lo usa el
    indicador breve de PAN-04 ("Incompleto · faltan N"); el detalle a
    fondo (PAN-07) es del Incremento 4.
    """

    TIPOS_PERSONA_FISICA = [
        "Plano legible",
        "Formulario de solicitud",
        "Copia de cédula",
        "Certificación de registro de propiedad",
        "Contrato de servicio",
    ]

    def setUp(self):
        self.abonado = Abonado.objects.create(
            numero_paja="0601", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular = Persona.objects.create(nombre="Ana Lucía Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

    def _aportar(self, nombre_tipo, persona, **extra):
        datos = {
            "abonado": self.abonado,
            "tipo_documento": TipoDocumento.objects.get(nombre=nombre_tipo),
            "persona": persona,
            "estado": "VIGENTE",
        }
        datos.update(extra)
        return Documento.objects.create(**datos)

    def test_sin_documentos_faltan_los_5_tipos_de_persona_fisica(self):
        resultado = calcular_completitud(self.abonado)
        self.assertFalse(resultado["completo"])
        self.assertEqual(len(resultado["faltantes"]), 5)
        self.assertIn("Plano legible (titular)", resultado["faltantes"])

    def test_con_todos_los_documentos_vigentes_queda_completo(self):
        for nombre in self.TIPOS_PERSONA_FISICA:
            self._aportar(nombre, self.titular)

        resultado = calcular_completitud(self.abonado)
        self.assertTrue(resultado["completo"])
        self.assertEqual(resultado["faltantes"], [])

    def test_documento_anulado_no_cuenta(self):
        for nombre in self.TIPOS_PERSONA_FISICA:
            self._aportar(nombre, self.titular)

        plano = Documento.objects.get(
            abonado=self.abonado, tipo_documento__nombre="Plano legible",
        )
        plano.estado = "ANULADO"
        plano.motivo_anulacion = "Documento equivocado"
        plano.fecha_anulacion = datetime.datetime.now(datetime.timezone.utc)
        plano.save()

        resultado = calcular_completitud(self.abonado)
        self.assertFalse(resultado["completo"])
        self.assertIn("Plano legible (titular)", resultado["faltantes"])

    def test_copia_de_cedula_se_exige_tambien_a_cada_cotitular(self):
        cotitular = Persona.objects.create(nombre="Esteban Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=cotitular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="COTITULAR",
        )

        for nombre in self.TIPOS_PERSONA_FISICA:
            self._aportar(nombre, self.titular)

        resultado = calcular_completitud(self.abonado)
        self.assertFalse(resultado["completo"])
        self.assertIn(
            "Copia de cédula del cotitular Esteban Mora Vega",
            resultado["faltantes"],
        )

        self._aportar("Copia de cédula", cotitular)
        resultado = calcular_completitud(self.abonado)
        self.assertTrue(resultado["completo"])

    def test_grupo_de_alternativas_basta_con_uno(self):
        abonado_juridico = Abonado.objects.create(
            numero_paja="0602", tipo_abonado=TipoAbonado.PERSONA_JURIDICA,
        )
        titular_juridico = Persona.objects.create(nombre="Acueducto Ficticio S.A.")
        VinculoAbonado.objects.create(
            abonado=abonado_juridico,
            persona=titular_juridico,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

        for nombre in [
            "Plano legible",
            "Formulario de solicitud",
            "Contrato de servicio",
            "Cédula jurídica",
            "Personería jurídica vigente",
            "Cédula de la persona apoderada",
        ]:
            Documento.objects.create(
                abonado=abonado_juridico,
                tipo_documento=TipoDocumento.objects.get(nombre=nombre),
                persona=titular_juridico,
                estado="VIGENTE",
            )

        resultado = calcular_completitud(abonado_juridico)
        self.assertFalse(resultado["completo"])
        self.assertIn("Permiso o formulario (titular)", resultado["faltantes"])

        Documento.objects.create(
            abonado=abonado_juridico,
            tipo_documento=TipoDocumento.objects.get(
                nombre="Permiso de construcción vigente",
            ),
            persona=titular_juridico,
            estado="VIGENTE",
        )

        resultado = calcular_completitud(abonado_juridico)
        self.assertTrue(resultado["completo"])

    def test_documento_del_titular_anterior_no_cuenta(self):
        """RF-14: nunca cuentan los documentos de titulares anteriores."""

        titular_anterior = Persona.objects.create(nombre="Rodrigo Mora Castro")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=titular_anterior,
            fecha_inicio=datetime.date(2010, 1, 1),
            fecha_fin=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )
        Documento.objects.create(
            abonado=self.abonado,
            tipo_documento=TipoDocumento.objects.get(nombre="Plano legible"),
            persona=titular_anterior,
            estado="VIGENTE",
        )

        resultado = calcular_completitud(self.abonado)
        self.assertIn("Plano legible (titular)", resultado["faltantes"])

    def test_documento_de_la_persona_apoderada_no_cuenta_para_el_titular(self):
        """RF-14: nunca cuentan los documentos de la persona apoderada."""

        apoderada = Persona.objects.create(nombre="Mariana Apoderada Solano")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=apoderada,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="APODERADA",
        )
        Documento.objects.create(
            abonado=self.abonado,
            tipo_documento=TipoDocumento.objects.get(nombre="Plano legible"),
            persona=apoderada,
            estado="VIGENTE",
        )

        resultado = calcular_completitud(self.abonado)
        self.assertIn("Plano legible (titular)", resultado["faltantes"])


class ResumenCompletitudGlobalTests(TestCase):
    """
    PAN-07 (RF-14): tarjetas globales (`resumen_completitud_global`) y
    lista de incompletos (`listar_incompletos`). Los abonados de baja
    no cuentan en los totales (confirmado, CLAUDE.md sección 9).
    """

    TIPOS_PERSONA_FISICA = CompletitudAbonadoTests.TIPOS_PERSONA_FISICA

    def _abonado_completo(self, numero_paja, *, id_sector=None):
        abonado = Abonado.objects.create(
            numero_paja=numero_paja,
            tipo_abonado=TipoAbonado.PERSONA_FISICA,
            sector_id=id_sector,
        )
        titular = Persona.objects.create(nombre=f"Titular completo {numero_paja}")
        VinculoAbonado.objects.create(
            abonado=abonado,
            persona=titular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )
        for nombre in self.TIPOS_PERSONA_FISICA:
            Documento.objects.create(
                abonado=abonado,
                tipo_documento=TipoDocumento.objects.get(nombre=nombre),
                persona=titular,
                estado="VIGENTE",
            )
        return abonado

    def _abonado_incompleto(self, numero_paja, *, id_sector=None):
        abonado = Abonado.objects.create(
            numero_paja=numero_paja,
            tipo_abonado=TipoAbonado.PERSONA_FISICA,
            sector_id=id_sector,
        )
        titular = Persona.objects.create(nombre=f"Titular incompleto {numero_paja}")
        VinculoAbonado.objects.create(
            abonado=abonado,
            persona=titular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )
        return abonado

    def setUp(self):
        self.sector_bodegas = Sector.objects.create(nombre="Bodegas de prueba RCG")
        self.sector_pilas = Sector.objects.create(nombre="Pilas de prueba RCG")

        self.completo_1 = self._abonado_completo(
            "9701", id_sector=self.sector_bodegas.id_sector,
        )
        self.completo_2 = self._abonado_completo(
            "9702", id_sector=self.sector_pilas.id_sector,
        )
        self.incompleto_1 = self._abonado_incompleto(
            "9703", id_sector=self.sector_bodegas.id_sector,
        )

        self.pendiente = Abonado.objects.create(
            numero_paja="9704", tipo_abonado=TipoAbonado.PENDIENTE,
        )
        Persona.objects.create(nombre="Titular pendiente 9704")
        VinculoAbonado.objects.create(
            abonado=self.pendiente,
            persona=Persona.objects.get(nombre="Titular pendiente 9704"),
            fecha_inicio=datetime.date(2026, 1, 5),
            rol="TITULAR",
        )

        self.de_baja = Abonado.objects.create(
            numero_paja="9705",
            tipo_abonado=TipoAbonado.PERSONA_FISICA,
            estado=EstadoAbonado.DE_BAJA,
            fecha_baja=datetime.date(2026, 1, 1),
        )

    def test_de_baja_no_cuenta_en_los_totales(self):
        resumen = resumen_completitud_global()

        self.assertEqual(resumen["completos"], 2)
        self.assertEqual(resumen["incompletos"], 1)
        self.assertEqual(resumen["tipo_pendiente"], 1)
        self.assertEqual(resumen["total_activos"], 4)

    def test_avance_pct_se_calcula_sobre_el_total_activo(self):
        resumen = resumen_completitud_global()

        self.assertAlmostEqual(resumen["avance_pct"], 50.0)

    def test_avance_pct_cero_sin_abonados_activos(self):
        # Un sector sin abonados (en vez de borrar: todas las FK hacia
        # abonado son RESTRICT, Modelo ER v1.1).
        sector_vacio = Sector.objects.create(nombre="Sector sin abonados RCG")

        self.assertEqual(
            resumen_completitud_global({"id_sector": sector_vacio.id_sector}),
            {
                "completos": 0,
                "incompletos": 0,
                "tipo_pendiente": 0,
                "total_activos": 0,
                "avance_pct": 0.0,
            },
        )

    def test_filtro_por_sector(self):
        resumen = resumen_completitud_global(
            {"id_sector": self.sector_bodegas.id_sector},
        )

        # Bodegas: completo_1 (completo) + incompleto_1 (incompleto).
        self.assertEqual(resumen["completos"], 1)
        self.assertEqual(resumen["incompletos"], 1)
        self.assertEqual(resumen["tipo_pendiente"], 0)
        self.assertEqual(resumen["total_activos"], 2)

    def test_filtro_por_tipo_abonado(self):
        resumen = resumen_completitud_global(
            {"tipo_abonado": TipoAbonado.PENDIENTE},
        )

        self.assertEqual(resumen["tipo_pendiente"], 1)
        self.assertEqual(resumen["completos"], 0)
        self.assertEqual(resumen["incompletos"], 0)

    def test_listar_incompletos_solo_devuelve_incompletos_activos(self):
        incompletos = listar_incompletos()

        pajas = {fila["numero_paja"] for fila in incompletos}
        self.assertEqual(pajas, {"9703"})

        fila = incompletos[0]
        self.assertEqual(fila["tipo_abonado"], TipoAbonado.PERSONA_FISICA)
        self.assertIn("Plano legible (titular)", fila["faltantes"])

    def test_listar_incompletos_filtra_por_sector(self):
        incompletos = listar_incompletos({"id_sector": self.sector_pilas.id_sector})
        self.assertEqual(incompletos, [])

    def test_listar_incompletos_filtra_por_tipo_abonado(self):
        incompletos = listar_incompletos(
            {"tipo_abonado": TipoAbonado.PERSONA_JURIDICA},
        )
        self.assertEqual(incompletos, [])

    def test_listar_incompletos_filtra_por_documento_faltante(self):
        con_filtro = listar_incompletos({"documento_faltante": "Plano legible"})
        self.assertEqual({fila["numero_paja"] for fila in con_filtro}, {"9703"})

        sin_coincidencia = listar_incompletos(
            {"documento_faltante": "Cédula jurídica"},
        )
        self.assertEqual(sin_coincidencia, [])

    def test_listar_tipo_pendiente(self):
        pendientes = listar_tipo_pendiente()

        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0]["numero_paja"], "9704")
        self.assertEqual(pendientes[0]["titular_vigente"], "Titular pendiente 9704")
        self.assertEqual(pendientes[0]["fecha_inicio"], datetime.date(2026, 1, 5))


class PanelCompletitudViewTests(TestCase):
    """PAN-07 (RF-14): vistas HTTP del panel y del detalle."""

    def setUp(self):
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria_completitud",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        self.abonado = Abonado.objects.create(
            numero_paja="9710", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular = Persona.objects.create(nombre="Titular panel completitud")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

    def test_panel_completitud_responde_las_tres_secciones(self):
        respuesta = self.cliente.get(reverse("abonados:completitud"))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertIn("tarjetas", respuesta.data)
        self.assertIn("incompletos", respuesta.data)
        self.assertIn("tipo_pendiente", respuesta.data)
        self.assertIn("9710", {fila["numero_paja"] for fila in respuesta.data["incompletos"]})

    def test_detalle_completitud_abonado_trae_matriz(self):
        respuesta = self.cliente.get(
            reverse("abonados:completitud_detalle", args=["9710"]),
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(respuesta.data["completo"])
        self.assertIsInstance(respuesta.data["matriz"], list)
        self.assertTrue(len(respuesta.data["matriz"]) > 0)

        fila_plano = next(
            fila for fila in respuesta.data["matriz"] if fila["nombre"] == "Plano legible"
        )
        self.assertEqual(len(fila_plano["columnas"]), 1)
        self.assertEqual(fila_plano["columnas"][0]["rol"], "titular")
        self.assertFalse(fila_plano["columnas"][0]["tiene_documento"])

    def test_detalle_completitud_abonado_inexistente(self):
        respuesta = self.cliente.get(
            reverse("abonados:completitud_detalle", args=["0000"]),
        )
        self.assertEqual(respuesta.status_code, 404)


class ExpedienteExtendidoViewTests(TestCase):
    """
    1b: filtros RF-11, completitud (Q3) en `abonado`, marca de
    `aportante_titular_anterior`, `motivo_anulacion`/`fecha_anulacion`
    y `historial_titulares`.
    """

    def setUp(self):
        self.cliente = APIClient()
        cuenta = Cuenta.objects.create(
            usuario="secretaria_expediente",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=cuenta)
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        self.abonado = Abonado.objects.create(
            numero_paja="0710", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular_anterior = Persona.objects.create(nombre="Rodrigo Mora Castro")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular_anterior,
            fecha_inicio=datetime.date(2010, 1, 1),
            fecha_fin=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )
        self.titular = Persona.objects.create(nombre="Ana Lucía Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

        self.tipo_plano = TipoDocumento.objects.get(nombre="Plano legible")
        self.tipo_formulario = TipoDocumento.objects.get(nombre="Formulario de solicitud")

        self.documento_titular_anterior = Documento.objects.create(
            abonado=self.abonado,
            tipo_documento=self.tipo_plano,
            persona=self.titular_anterior,
            nombre_identificador="plano viejo",
        )
        VersionDocumento.objects.create(
            documento=self.documento_titular_anterior,
            numero_version=1,
            nombre_original="plano.pdf",
            ruta_archivo="plano-viejo.bin",
            formato="PDF",
            tamano_bytes=100,
            fecha_documento=datetime.date(2015, 6, 1),
            hash_sha256="0" * 64,
        )

        self.documento_vigente = Documento.objects.create(
            abonado=self.abonado,
            tipo_documento=self.tipo_formulario,
            persona=self.titular,
            nombre_identificador="formulario nuevo",
        )
        VersionDocumento.objects.create(
            documento=self.documento_vigente,
            numero_version=1,
            nombre_original="formulario.pdf",
            ruta_archivo="formulario-nuevo.bin",
            formato="PDF",
            tamano_bytes=100,
            fecha_documento=datetime.date(2026, 2, 1),
            hash_sha256="1" * 64,
        )

        self.documento_anulado = Documento.objects.create(
            abonado=self.abonado,
            tipo_documento=self.tipo_plano,
            persona=self.titular,
            estado="ANULADO",
            motivo_anulacion="Duplicado",
            fecha_anulacion=datetime.datetime(
                2026, 3, 1, tzinfo=datetime.timezone.utc,
            ),
        )
        VersionDocumento.objects.create(
            documento=self.documento_anulado,
            numero_version=1,
            nombre_original="plano_dup.pdf",
            ruta_archivo="plano-dup.bin",
            formato="PDF",
            tamano_bytes=100,
            fecha_documento=datetime.date(2026, 3, 1),
            hash_sha256="2" * 64,
        )

    def _get(self, **parametros):
        return self.cliente.get(
            reverse("abonados:expediente", args=["0710"]), parametros,
        )

    def test_incluye_completitud_del_abonado(self):
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("completitud", respuesta.data["abonado"])
        self.assertIn("faltantes", respuesta.data["abonado"]["completitud"])

    def test_documento_aportado_por_titular_anterior_queda_marcado(self):
        respuesta = self._get()
        documentos = {d["id_documento"]: d for d in respuesta.data["documentos"]}

        self.assertTrue(
            documentos[self.documento_titular_anterior.id_documento][
                "aportante_titular_anterior"
            ],
        )
        self.assertFalse(
            documentos[self.documento_vigente.id_documento][
                "aportante_titular_anterior"
            ],
        )

    def test_historial_de_titulares_cerrados(self):
        respuesta = self._get()
        nombres = [
            h["persona"]["nombre"] for h in respuesta.data["historial_titulares"]
        ]
        self.assertEqual(nombres, ["Rodrigo Mora Castro"])

    def test_anulados_ocultos_por_defecto_y_visibles_con_el_filtro(self):
        respuesta = self._get()
        ids = {d["id_documento"] for d in respuesta.data["documentos"]}
        self.assertNotIn(self.documento_anulado.id_documento, ids)

        respuesta = self._get(mostrar_anulados="true")
        documentos = {d["id_documento"]: d for d in respuesta.data["documentos"]}
        anulado = documentos[self.documento_anulado.id_documento]
        self.assertEqual(anulado["motivo_anulacion"], "Duplicado")
        self.assertIsNotNone(anulado["fecha_anulacion"])

    def test_filtro_por_tipo_de_documento(self):
        respuesta = self._get(
            id_tipo_documento=self.tipo_formulario.id_tipo_documento,
        )
        ids = {d["id_documento"] for d in respuesta.data["documentos"]}
        self.assertEqual(ids, {self.documento_vigente.id_documento})

    def test_filtro_por_nombre_identificador(self):
        respuesta = self._get(nombre_identificador="nuevo")
        ids = {d["id_documento"] for d in respuesta.data["documentos"]}
        self.assertEqual(ids, {self.documento_vigente.id_documento})

    def test_filtro_por_rango_de_fechas_usa_la_version_vigente(self):
        respuesta = self._get(fecha_desde="2026-01-01", fecha_hasta="2026-12-31")
        ids = {d["id_documento"] for d in respuesta.data["documentos"]}
        self.assertEqual(ids, {self.documento_vigente.id_documento})

    def test_fecha_invalida_responde_400(self):
        respuesta = self._get(fecha_desde="no-es-fecha")
        self.assertEqual(respuesta.status_code, 400)

    def test_id_tipo_documento_no_numerico_responde_400(self):
        respuesta = self._get(id_tipo_documento="abc")
        self.assertEqual(respuesta.status_code, 400)


class DarDeBajaYReactivarAbonadoTests(TestCase):
    """D-03 (RF-17): no borra documentos ni el abonado; deja bitácora."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = Cuenta.objects.create(
            usuario="secretaria_baja",
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=self.cuenta)
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        self.abonado = Abonado.objects.create(
            numero_paja="0810", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )

    def test_dar_de_baja_exige_fecha(self):
        respuesta = self.cliente.post(
            reverse("abonados:dar_de_baja", args=["0810"]), {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_dar_de_baja_cambia_estado_y_deja_bitacora(self):
        respuesta = self.cliente.post(
            reverse("abonados:dar_de_baja", args=["0810"]),
            {"fecha_baja": "2026-11-13"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

        self.abonado.refresh_from_db()
        self.assertEqual(self.abonado.estado, "DE_BAJA")
        self.assertEqual(self.abonado.fecha_baja, datetime.date(2026, 11, 13))

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.BAJA,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        self.assertEqual(registro.cuenta, self.cuenta)

    def test_no_se_puede_dar_de_baja_dos_veces(self):
        self.cliente.post(
            reverse("abonados:dar_de_baja", args=["0810"]),
            {"fecha_baja": "2026-11-13"},
            format="json",
        )
        respuesta = self.cliente.post(
            reverse("abonados:dar_de_baja", args=["0810"]),
            {"fecha_baja": "2026-11-14"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_reactivar_requiere_estar_de_baja(self):
        respuesta = self.cliente.post(
            reverse("abonados:reactivar", args=["0810"]), {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_reactivar_cambia_estado_y_deja_bitacora(self):
        self.cliente.post(
            reverse("abonados:dar_de_baja", args=["0810"]),
            {"fecha_baja": "2026-11-13"},
            format="json",
        )

        respuesta = self.cliente.post(
            reverse("abonados:reactivar", args=["0810"]), {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

        self.abonado.refresh_from_db()
        self.assertEqual(self.abonado.estado, "ACTIVO")
        self.assertIsNone(self.abonado.fecha_baja)

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.REACTIVACION,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        self.assertEqual(registro.cuenta, self.cuenta)

    def test_no_borra_documentos_al_dar_de_baja(self):
        tipo = TipoDocumento.objects.get(nombre="Plano legible")
        Documento.objects.create(abonado=self.abonado, tipo_documento=tipo)

        self.cliente.post(
            reverse("abonados:dar_de_baja", args=["0810"]),
            {"fecha_baja": "2026-11-13"},
            format="json",
        )

        self.assertEqual(
            Documento.objects.filter(abonado=self.abonado).count(), 1,
        )


def _crear_cuenta_autenticada(cliente, usuario):
    cuenta = Cuenta.objects.create(
        usuario=usuario,
        hash_contrasena=make_password("Prueba2026!"),
        perfil="SECRETARIA",
    )
    token = TokenCuenta.objects.create(cuenta=cuenta)
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return cuenta


class BuscarPersonasViewTests(TestCase):
    """1a: búsqueda compartida de personas (alta, D-06, D-04)."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_buscar_personas")

        self.abonado = Abonado.objects.create(
            numero_paja="0910", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.ana = Persona.objects.create(
            nombre="Ana Lucía Mora Vega",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0123",
        )
        self.esteban = Persona.objects.create(
            nombre="Esteban Mora Vega",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0456",
        )
        self.rodrigo = Persona.objects.create(nombre="Rodrigo Mora Castro")

        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=self.ana,
            fecha_inicio=datetime.date(2020, 1, 1), rol="TITULAR",
        )
        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=self.esteban,
            fecha_inicio=datetime.date(2021, 1, 1), rol="COTITULAR",
        )

    def test_requiere_texto(self):
        respuesta = self.cliente.get(reverse("abonados:buscar_personas"))
        self.assertEqual(respuesta.status_code, 400)

    def test_requiere_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.get(
            reverse("abonados:buscar_personas"), {"q": "Ana"},
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_por_nombre_insensible_a_tildes_y_mayusculas(self):
        respuesta = self.cliente.get(
            reverse("abonados:buscar_personas"), {"q": "ana lucia"},
        )
        self.assertEqual(respuesta.status_code, 200)
        nombres = {fila["nombre"] for fila in respuesta.data}
        self.assertIn("Ana Lucía Mora Vega", nombres)

        fila_ana = next(
            f for f in respuesta.data if f["id_persona"] == self.ana.id_persona
        )
        self.assertEqual(fila_ana["vinculos_actuales"], ["Titular de 0910"])

    def test_por_identificacion_normaliza_guiones(self):
        respuesta = self.cliente.get(
            reverse("abonados:buscar_personas"), {"q": "100000456"},
        )
        self.assertEqual(respuesta.status_code, 200)
        ids = {fila["id_persona"] for fila in respuesta.data}
        self.assertIn(self.esteban.id_persona, ids)

        fila_esteban = next(
            f for f in respuesta.data if f["id_persona"] == self.esteban.id_persona
        )
        self.assertEqual(fila_esteban["vinculos_actuales"], ["Cotitular de 0910"])

    def test_persona_sin_vinculos_aparece_con_lista_vacia(self):
        respuesta = self.cliente.get(
            reverse("abonados:buscar_personas"), {"q": "Rodrigo"},
        )
        self.assertEqual(respuesta.status_code, 200)
        fila_rodrigo = next(
            f for f in respuesta.data if f["id_persona"] == self.rodrigo.id_persona
        )
        self.assertEqual(fila_rodrigo["vinculos_actuales"], [])

    def test_limite_de_resultados(self):
        for n in range(25):
            Persona.objects.create(nombre=f"Persona de Prueba {n:02d}")

        respuesta = self.cliente.get(
            reverse("abonados:buscar_personas"), {"q": "Persona de Prueba"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 20)


class AltaAbonadoViewTests(TestCase):
    """1b: RF-02 Registrar abonado (PAN-06)."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_alta")
        self.sector = Sector.objects.get(nombre="Bodegas")

    def test_requiere_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.post(reverse("abonados:alta"), {}, format="json")
        self.assertEqual(respuesta.status_code, 403)

    def test_alta_exitosa_crea_abonado_persona_y_vinculo_titular(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0920",
                "id_sector": self.sector.pk,
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Ana Lucía Mora Vega",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "1-0000-0123",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)

        abonado = Abonado.objects.get(numero_paja="0920")
        self.assertEqual(abonado.sector, self.sector)
        self.assertEqual(abonado.tipo_abonado, "PERSONA_FISICA")

        vinculo = VinculoAbonado.objects.get(abonado=abonado, rol="TITULAR")
        self.assertIsNone(vinculo.fecha_fin)
        self.assertEqual(vinculo.fecha_inicio, datetime.date.today())
        self.assertEqual(vinculo.persona.nombre, "Ana Lucía Mora Vega")
        self.assertEqual(vinculo.persona.identificacion, "1-0000-0123")

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.CREACION,
            elemento_afectado=f"abonado.id_abonado={abonado.id_abonado}",
        )
        self.assertEqual(registro.cuenta, self.cuenta)

    def test_paja_duplicada_responde_400_y_no_crea_nada(self):
        abonado_previo = Abonado.objects.create(
            numero_paja="0921", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        titular_previo = Persona.objects.create(nombre="Esteban Mora Vega")
        VinculoAbonado.objects.create(
            abonado=abonado_previo, persona=titular_previo,
            fecha_inicio=datetime.date(2020, 1, 1), rol="TITULAR",
        )

        total_abonados_antes = Abonado.objects.count()
        total_personas_antes = Persona.objects.count()

        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0921",
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Otra Persona",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "1-0000-0999",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("0921", respuesta.data["numero_paja"][0])
        self.assertIn("Esteban Mora Vega", respuesta.data["numero_paja"][0])

        self.assertEqual(Abonado.objects.count(), total_abonados_antes)
        self.assertEqual(Persona.objects.count(), total_personas_antes)

    def test_numero_paja_no_numerico_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "04A2",
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Ana Lucía Mora Vega",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "1-0000-0123",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_tipo_abonado_invalido_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {"numero_paja": "0922", "tipo_abonado": "INVALIDO"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_cedula_fisica_con_menos_de_9_digitos_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0923",
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Ana Lucía Mora Vega",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "1-0000-012",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("9 dígitos", respuesta.data["detail"])

    def test_cedula_juridica_con_10_digitos_es_valida(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0924",
                "tipo_abonado": "PERSONA_JURIDICA",
                "nombre": "Acueducto Ficticio S.A.",
                "tipo_identificacion": "CEDULA_JURIDICA",
                "identificacion": "3-101-000000",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)

    def test_cedula_juridica_con_9_digitos_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0925",
                "tipo_abonado": "PERSONA_JURIDICA",
                "nombre": "Acueducto Ficticio S.A.",
                "tipo_identificacion": "CEDULA_JURIDICA",
                "identificacion": "3-101-00000",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("10 dígitos", respuesta.data["detail"])

    def test_dimex_con_11_o_12_digitos_es_valido(self):
        for sufijo, identificacion in [("0926", "123456789012"), ("0927", "12345678901")]:
            respuesta = self.cliente.post(
                reverse("abonados:alta"),
                {
                    "numero_paja": sufijo,
                    "tipo_abonado": "PERSONA_FISICA",
                    "nombre": "Persona DIMEX",
                    "tipo_identificacion": "DIMEX",
                    "identificacion": identificacion,
                },
                format="json",
            )
            self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_dimex_con_10_digitos_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0928",
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Persona DIMEX",
                "tipo_identificacion": "DIMEX",
                "identificacion": "1234567890",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("11 o 12 dígitos", respuesta.data["detail"])

    def test_pasaporte_sin_longitud_fija_es_valido(self):
        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0929",
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Persona con Pasaporte",
                "tipo_identificacion": "PASAPORTE",
                "identificacion": "AB123",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)

    def test_persona_existente_por_cedula_responde_409_y_no_crea_nada(self):
        persona_existente = Persona.objects.create(
            nombre="Persona Ya Registrada",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0654",
        )
        total_personas_antes = Persona.objects.count()

        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0931",
                "tipo_abonado": "PERSONA_FISICA",
                "nombre": "Nombre Distinto Pero Misma Cédula",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "100000654",  # sin guiones, misma cédula
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.data["persona_existente"]["id_persona"],
            persona_existente.id_persona,
        )
        self.assertEqual(
            respuesta.data["persona_existente"]["nombre"], "Persona Ya Registrada",
        )
        self.assertIsNone(respuesta.data["persona_existente"]["numero_paja_titular"])

        self.assertEqual(Persona.objects.count(), total_personas_antes)
        self.assertFalse(Abonado.objects.filter(numero_paja="0931").exists())

    def test_reenviar_con_id_persona_reutiliza_la_existente(self):
        persona_existente = Persona.objects.create(
            nombre="Persona Ya Registrada",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0654",
        )
        total_personas_antes = Persona.objects.count()

        respuesta = self.cliente.post(
            reverse("abonados:alta"),
            {
                "numero_paja": "0932",
                "tipo_abonado": "PERSONA_FISICA",
                "id_persona": persona_existente.id_persona,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["titular_vigente"], "Persona Ya Registrada")
        self.assertEqual(Persona.objects.count(), total_personas_antes)


class ModificarAbonadoViewTests(TestCase):
    """1c: RF-21 Modificar abonado (sector y tipo; paja y estado intactos)."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_modificar")
        self.abonado = Abonado.objects.create(
            numero_paja="0930", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.sector_pilas = Sector.objects.get(nombre="Pilas")

    def test_modifica_sector_y_tipo_y_deja_bitacora(self):
        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0930"]),
            {"id_sector": self.sector_pilas.pk, "tipo_abonado": "PERSONA_JURIDICA"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

        self.abonado.refresh_from_db()
        self.assertEqual(self.abonado.sector, self.sector_pilas)
        self.assertEqual(self.abonado.tipo_abonado, "PERSONA_JURIDICA")

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.MODIFICACION,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        campos = set(
            RegistroModificacion.objects
            .filter(registro_bitacora=registro)
            .values_list("campo_modificado", flat=True)
        )
        self.assertEqual(campos, {"abonado.id_sector", "abonado.tipo_abonado"})

    def test_numero_paja_y_estado_no_cambian(self):
        self.cliente.post(
            reverse("abonados:modificar", args=["0930"]),
            {"id_sector": self.sector_pilas.pk, "tipo_abonado": "PERSONA_JURIDICA"},
            format="json",
        )
        self.abonado.refresh_from_db()
        self.assertEqual(self.abonado.numero_paja, "0930")
        self.assertEqual(self.abonado.estado, "ACTIVO")

    def test_sin_cambios_no_deja_bitacora_nueva(self):
        total_antes = RegistroBitacora.objects.count()

        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0930"]),
            {"id_sector": "", "tipo_abonado": "PERSONA_FISICA"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(RegistroBitacora.objects.count(), total_antes)

    def test_tipo_invalido_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0930"]),
            {"tipo_abonado": "INVALIDO"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_abonado_inexistente_responde_404(self):
        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["9999"]),
            {"tipo_abonado": "PERSONA_FISICA"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 404)


class ModificarAbonadoCompletarIdentificacionTests(TestCase):
    """
    RF-04/RF-21: desde "Modificar abonado" (PAN-06) se completa la
    identificación del titular de un abonado "importado, pendiente"
    (decisión del 13/11/2026). La persona importada se actualiza en el
    lugar, nunca se crea una nueva.
    """

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(
            self.cliente, "secretaria_completar_identificacion",
        )
        self.abonado = Abonado.objects.create(
            numero_paja="0990", tipo_abonado=TipoAbonado.PENDIENTE,
        )
        self.titular = Persona.objects.create(nombre="Persona Importada de SADA")
        self.vinculo = VinculoAbonado.objects.create(
            abonado=self.abonado,
            persona=self.titular,
            fecha_inicio=datetime.date(2026, 11, 13),
            rol="TITULAR",
        )

    def test_completa_identificacion_del_titular_pendiente_con_exito(self):
        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0990"]),
            {
                "tipo_abonado": "PERSONA_FISICA",
                "tipo_identificacion_titular": "CEDULA_FISICA",
                "identificacion_titular": "1-0000-0789",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.titular.refresh_from_db()
        self.assertEqual(self.titular.tipo_identificacion, "CEDULA_FISICA")
        self.assertEqual(self.titular.identificacion, "1-0000-0789")

        # Es la misma persona (misma paja de titular, no se creó otra).
        self.assertEqual(
            VinculoAbonado.objects.filter(
                abonado=self.abonado, rol="TITULAR", fecha_fin__isnull=True,
            ).get().persona_id,
            self.titular.id_persona,
        )

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.MODIFICACION,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        campos = set(
            RegistroModificacion.objects
            .filter(registro_bitacora=registro)
            .values_list("campo_modificado", flat=True)
        )
        self.assertIn("persona.tipo_identificacion", campos)
        self.assertIn("persona.identificacion", campos)

    def test_formato_invalido_responde_400_y_no_cambia_nada(self):
        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0990"]),
            {
                "tipo_abonado": "PERSONA_FISICA",
                "tipo_identificacion_titular": "CEDULA_FISICA",
                "identificacion_titular": "1-0000-07",  # 7 dígitos, faltan 2
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("9 dígitos", respuesta.data["detail"])

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.identificacion)
        # Tampoco se guardó el cambio de tipo_abonado: todo o nada.
        self.abonado.refresh_from_db()
        self.assertEqual(self.abonado.tipo_abonado, TipoAbonado.PENDIENTE)

    def test_identificacion_duplicada_responde_409_y_no_cambia_nada(self):
        Persona.objects.create(
            nombre="Otra Persona Ya Registrada",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0654",
        )

        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0990"]),
            {
                "tipo_abonado": "PERSONA_FISICA",
                "tipo_identificacion_titular": "CEDULA_FISICA",
                "identificacion_titular": "100000654",  # misma cédula, sin guiones
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.data["persona_existente"]["nombre"],
            "Otra Persona Ya Registrada",
        )

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.identificacion)
        self.abonado.refresh_from_db()
        self.assertEqual(self.abonado.tipo_abonado, TipoAbonado.PENDIENTE)

    def test_titular_con_identificacion_ya_completa_ignora_los_campos(self):
        self.titular.tipo_identificacion = "CEDULA_FISICA"
        self.titular.identificacion = "1-0000-0111"
        self.titular.save(update_fields=["tipo_identificacion", "identificacion"])

        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0990"]),
            {
                "tipo_abonado": "PERSONA_FISICA",
                "tipo_identificacion_titular": "DIMEX",
                "identificacion_titular": "123456789012",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.titular.refresh_from_db()
        # No se tocó: ya tenía identificación, ese no es el flujo de hoy.
        self.assertEqual(self.titular.tipo_identificacion, "CEDULA_FISICA")
        self.assertEqual(self.titular.identificacion, "1-0000-0111")

    def test_solo_un_campo_de_identificacion_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:modificar", args=["0990"]),
            {
                "tipo_abonado": "PERSONA_FISICA",
                "tipo_identificacion_titular": "CEDULA_FISICA",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.identificacion)


class PersonaAsociadaViewsTests(TestCase):
    """1d: agregar/quitar/cambiar rol de persona asociada (D-06)."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_personas")
        self.abonado = Abonado.objects.create(
            numero_paja="0940", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular = Persona.objects.create(nombre="Ana Lucía Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=self.titular,
            fecha_inicio=datetime.date(2020, 1, 1), rol="TITULAR",
        )

    def test_agregar_cotitular_nueva_persona_y_bitacora(self):
        respuesta = self.cliente.post(
            reverse("abonados:agregar_persona", args=["0940"]),
            {
                "nombre": "Esteban Mora Vega",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "1-0000-0789",
                "rol": "COTITULAR",
                "fecha_inicio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)

        vinculo = VinculoAbonado.objects.get(
            abonado=self.abonado, persona__nombre="Esteban Mora Vega",
        )
        self.assertEqual(vinculo.rol, "COTITULAR")
        self.assertIsNone(vinculo.fecha_fin)
        self.assertEqual(vinculo.fecha_inicio, datetime.date(2026, 11, 13))

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.MODIFICACION,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        self.assertTrue(
            RegistroModificacion.objects.filter(registro_bitacora=registro).exists(),
        )

    def test_agregar_persona_existente_por_id_no_la_duplica(self):
        persona = Persona.objects.create(nombre="Esteban Mora Vega")
        total_antes = Persona.objects.count()

        respuesta = self.cliente.post(
            reverse("abonados:agregar_persona", args=["0940"]),
            {
                "id_persona": persona.id_persona,
                "rol": "APODERADA",
                "fecha_inicio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Persona.objects.count(), total_antes)

    def test_rol_titular_rechazado(self):
        respuesta = self.cliente.post(
            reverse("abonados:agregar_persona", args=["0940"]),
            {
                "nombre": "Esteban Mora Vega",
                "rol": "TITULAR",
                "fecha_inicio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_fecha_inicio_obligatoria(self):
        respuesta = self.cliente.post(
            reverse("abonados:agregar_persona", args=["0940"]),
            {"nombre": "Esteban Mora Vega", "rol": "COTITULAR"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_persona_ya_vinculada_responde_400(self):
        persona = Persona.objects.create(nombre="Esteban Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=persona,
            fecha_inicio=datetime.date(2021, 1, 1), rol="COTITULAR",
        )

        respuesta = self.cliente.post(
            reverse("abonados:agregar_persona", args=["0940"]),
            {
                "id_persona": persona.id_persona,
                "rol": "APODERADA",
                "fecha_inicio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_quitar_persona_cierra_vinculo_y_no_borra_documentos(self):
        persona = Persona.objects.create(nombre="Esteban Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=persona,
            fecha_inicio=datetime.date(2021, 1, 1), rol="COTITULAR",
        )
        tipo = TipoDocumento.objects.get(nombre="Plano legible")
        documento = Documento.objects.create(
            abonado=self.abonado, tipo_documento=tipo, persona=persona,
        )

        respuesta = self.cliente.post(
            reverse("abonados:quitar_persona", args=["0940", persona.id_persona]),
            {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

        vinculo = VinculoAbonado.objects.get(abonado=self.abonado, persona=persona)
        self.assertIsNotNone(vinculo.fecha_fin)

        self.assertTrue(Documento.objects.filter(pk=documento.pk).exists())
        documento.refresh_from_db()
        self.assertEqual(documento.persona_id, persona.id_persona)

    def test_quitar_titular_rechazado(self):
        respuesta = self.cliente.post(
            reverse(
                "abonados:quitar_persona", args=["0940", self.titular.id_persona],
            ),
            {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_quitar_persona_sin_vinculo_vigente_responde_404(self):
        persona_ajena = Persona.objects.create(nombre="Persona Sin Vínculo")
        respuesta = self.cliente.post(
            reverse(
                "abonados:quitar_persona", args=["0940", persona_ajena.id_persona],
            ),
            {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_cambiar_rol_cotitular_a_apoderada_y_bitacora(self):
        persona = Persona.objects.create(nombre="Esteban Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=persona,
            fecha_inicio=datetime.date(2021, 1, 1), rol="COTITULAR",
        )

        respuesta = self.cliente.post(
            reverse(
                "abonados:cambiar_rol_persona", args=["0940", persona.id_persona],
            ),
            {"rol": "APODERADA"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

        vinculo = VinculoAbonado.objects.get(abonado=self.abonado, persona=persona)
        self.assertEqual(vinculo.rol, "APODERADA")
        self.assertEqual(vinculo.fecha_inicio, datetime.date(2021, 1, 1))

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.MODIFICACION,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        detalle = RegistroModificacion.objects.get(registro_bitacora=registro)
        self.assertEqual(detalle.campo_modificado, "vinculo_abonado.rol")
        self.assertEqual(detalle.valor_anterior, "COTITULAR")
        self.assertEqual(detalle.valor_nuevo, "APODERADA")

    def test_cambiar_al_mismo_rol_no_deja_bitacora_nueva(self):
        persona = Persona.objects.create(nombre="Esteban Mora Vega")
        VinculoAbonado.objects.create(
            abonado=self.abonado, persona=persona,
            fecha_inicio=datetime.date(2021, 1, 1), rol="COTITULAR",
        )
        total_antes = RegistroBitacora.objects.count()

        respuesta = self.cliente.post(
            reverse(
                "abonados:cambiar_rol_persona", args=["0940", persona.id_persona],
            ),
            {"rol": "COTITULAR"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(RegistroBitacora.objects.count(), total_antes)

    def test_cambiar_rol_del_titular_rechazado(self):
        respuesta = self.cliente.post(
            reverse(
                "abonados:cambiar_rol_persona",
                args=["0940", self.titular.id_persona],
            ),
            {"rol": "COTITULAR"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)


class CambiarTitularViewTests(TestCase):
    """
    1e: D-04 Cambiar titular (RF-13). Incluye el caso del hallazgo H-02
    (decisión del 13/11/2026): el nuevo titular ya era cotitular
    vigente del mismo abonado, y hay que cerrar ese vínculo antes de
    abrir el de titular para no chocar con las restricciones reales de
    `vinculo_abonado` (UniqueConstraint/ExclusionConstraint).
    """

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_titular")
        self.abonado = Abonado.objects.create(
            numero_paja="0950", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        self.titular_anterior = Persona.objects.create(nombre="Rodrigo Mora Castro")
        self.vinculo_titular_anterior = VinculoAbonado.objects.create(
            abonado=self.abonado, persona=self.titular_anterior,
            fecha_inicio=datetime.date(2020, 1, 1), rol="TITULAR",
        )

    def test_requiere_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.post(
            reverse("abonados:cambiar_titular", args=["0950"]), {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_cambiar_titular_a_persona_nueva(self):
        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {
                "nombre": "Ana Lucía Mora Vega",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "1-0000-0321",
                "fecha_cambio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

        self.vinculo_titular_anterior.refresh_from_db()
        self.assertEqual(
            self.vinculo_titular_anterior.fecha_fin, datetime.date(2026, 11, 13),
        )

        nuevo_vinculo = VinculoAbonado.objects.get(
            abonado=self.abonado, rol="TITULAR", fecha_fin__isnull=True,
        )
        self.assertEqual(nuevo_vinculo.persona.nombre, "Ana Lucía Mora Vega")
        self.assertEqual(nuevo_vinculo.fecha_inicio, datetime.date(2026, 11, 13))

        registro = RegistroBitacora.objects.get(
            accion=AccionBitacora.CAMBIO_TITULAR,
            elemento_afectado=f"abonado.id_abonado={self.abonado.id_abonado}",
        )
        self.assertTrue(
            RegistroModificacion.objects.filter(registro_bitacora=registro).exists(),
        )

    def test_cambiar_titular_hacia_un_cotitular_vigente_cierra_el_vinculo_anterior(self):
        """Caso H-02, sin captura del prototipo: el nuevo titular ya es
        cotitular vigente. No debe romper ningún UniqueConstraint ni
        ExclusionConstraint de `vinculo_abonado` (si los rompiera, esta
        prueba fallaría con un IntegrityError/500 en vez de 200)."""

        cotitular = Persona.objects.create(nombre="Esteban Mora Vega")
        vinculo_cotitular = VinculoAbonado.objects.create(
            abonado=self.abonado, persona=cotitular,
            fecha_inicio=datetime.date(2021, 6, 1), rol="COTITULAR",
        )

        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {"id_persona": cotitular.id_persona, "fecha_cambio": "2026-11-13"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        # El vínculo de cotitular (misma fila) quedó cerrado el día del cambio...
        vinculo_cotitular.refresh_from_db()
        self.assertEqual(vinculo_cotitular.fecha_fin, datetime.date(2026, 11, 13))
        self.assertEqual(vinculo_cotitular.rol, "COTITULAR")

        # ...y se abrió un vínculo TITULAR nuevo para la misma persona.
        vinculo_titular_nuevo = VinculoAbonado.objects.get(
            abonado=self.abonado, persona=cotitular, rol="TITULAR",
        )
        self.assertIsNone(vinculo_titular_nuevo.fecha_fin)
        self.assertEqual(
            vinculo_titular_nuevo.fecha_inicio, datetime.date(2026, 11, 13),
        )

        # El titular anterior quedó cerrado.
        self.vinculo_titular_anterior.refresh_from_db()
        self.assertEqual(
            self.vinculo_titular_anterior.fecha_fin, datetime.date(2026, 11, 13),
        )

        # Un solo titular vigente para este abonado (RN-02), de verdad
        # consultado contra la base, no solo contra la respuesta HTTP.
        titulares_vigentes = VinculoAbonado.objects.filter(
            abonado=self.abonado, rol="TITULAR", fecha_fin__isnull=True,
        )
        self.assertEqual(titulares_vigentes.count(), 1)
        self.assertEqual(titulares_vigentes.first().persona_id, cotitular.id_persona)

        # Esta persona no tiene dos vínculos vigentes a la vez.
        vigentes_de_cotitular = VinculoAbonado.objects.filter(
            abonado=self.abonado, persona=cotitular, fecha_fin__isnull=True,
        )
        self.assertEqual(vigentes_de_cotitular.count(), 1)

    def test_cambiar_titular_el_mismo_dia_que_el_vinculo_previo_reutiliza_la_fila(self):
        """Caso límite encontrado el 13/11/2026 (reportado por el agente
        de frontend, sin captura del prototipo): el nuevo titular tiene
        un vínculo vigente que empezó el MISMO día que `fecha_cambio`.
        `VinculoAbonado` usa (abonado, persona, fecha_inicio) como llave
        primaria compuesta: cerrar ese vínculo y crear uno nuevo con la
        misma fecha de inicio chocaría con esa llave (duplicate key). La
        corrección reutiliza la fila: le cambia el rol a TITULAR sin
        tocar las fechas, y cierra primero al titular anterior para no
        chocar tampoco con `vinculo_abonado_un_titular_vigente` (un solo
        TITULAR vigente por abonado, comprobado por sentencia dentro de
        la misma transacción, no solo al final)."""

        cotitular = Persona.objects.create(nombre="Esteban Mora Vega Hoy")
        vinculo_cotitular = VinculoAbonado.objects.create(
            abonado=self.abonado, persona=cotitular,
            fecha_inicio=datetime.date(2026, 11, 13), rol="COTITULAR",
        )

        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {"id_persona": cotitular.id_persona, "fecha_cambio": "2026-11-13"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        # Misma fila reutilizada: sigue con fecha_inicio=2026-11-13, pero
        # ahora es TITULAR y vigente (no se creó una fila nueva).
        vinculo_cotitular.refresh_from_db()
        self.assertEqual(vinculo_cotitular.rol, "TITULAR")
        self.assertIsNone(vinculo_cotitular.fecha_fin)
        self.assertEqual(vinculo_cotitular.fecha_inicio, datetime.date(2026, 11, 13))

        self.vinculo_titular_anterior.refresh_from_db()
        self.assertEqual(
            self.vinculo_titular_anterior.fecha_fin, datetime.date(2026, 11, 13),
        )

        titulares_vigentes = VinculoAbonado.objects.filter(
            abonado=self.abonado, rol="TITULAR", fecha_fin__isnull=True,
        )
        self.assertEqual(titulares_vigentes.count(), 1)
        self.assertEqual(titulares_vigentes.first().persona_id, cotitular.id_persona)

    def test_persona_elegida_ya_es_titular_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {
                "id_persona": self.titular_anterior.id_persona,
                "fecha_cambio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_sin_titular_vigente_responde_400(self):
        abonado_sin_titular = Abonado.objects.create(
            numero_paja="0951", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0951"]),
            {"nombre": "Ana Lucía Mora Vega", "fecha_cambio": "2026-11-13"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_persona_existente_por_cedula_responde_409_y_no_cambia_nada(self):
        persona_existente = Persona.objects.create(
            nombre="Persona Ya Registrada",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0654",
        )

        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {
                "nombre": "Nombre Distinto Pero Misma Cédula",
                "tipo_identificacion": "CEDULA_FISICA",
                "identificacion": "100000654",
                "fecha_cambio": "2026-11-13",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.data["persona_existente"]["id_persona"],
            persona_existente.id_persona,
        )

        self.vinculo_titular_anterior.refresh_from_db()
        self.assertIsNone(self.vinculo_titular_anterior.fecha_fin)

    def test_fecha_cambio_obligatoria(self):
        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {"nombre": "Ana Lucía Mora Vega", "tipo_identificacion": "CEDULA_FISICA",
             "identificacion": "1-0000-0321"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_fecha_anterior_al_inicio_del_titular_actual_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {"nombre": "Ana Lucía Mora Vega", "fecha_cambio": "2019-01-01"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_documentos_del_titular_anterior_se_conservan(self):
        tipo = TipoDocumento.objects.get(nombre="Plano legible")
        documento = Documento.objects.create(
            abonado=self.abonado, tipo_documento=tipo, persona=self.titular_anterior,
        )

        self.cliente.post(
            reverse("abonados:cambiar_titular", args=["0950"]),
            {"nombre": "Ana Lucía Mora Vega", "fecha_cambio": "2026-11-13"},
            format="json",
        )

        self.assertTrue(Documento.objects.filter(pk=documento.pk).exists())
        documento.refresh_from_db()
        self.assertEqual(documento.persona_id, self.titular_anterior.id_persona)


def _excel_sada(filas: list[list[str]]) -> bytes:
    """Arma un .xlsx real en memoria, como lo exportaría SADA."""

    libro = Workbook()
    hoja = libro.active

    for fila in filas:
        hoja.append(fila)

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _csv_sada(filas: list[list[str]], *, separador: str = ",") -> bytes:
    """Arma un .csv real en memoria, como lo exportaría SADA."""

    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=separador)

    for fila in filas:
        escritor.writerow(fila)

    return buffer.getvalue().encode("utf-8")


class LectoresImportacionTests(TestCase):
    """1a: lectores de archivo (ADR-04)."""

    FILAS = [
        ["PAJA", "NOMBRE", "OTRO"],
        ["0412", "Ana Lucía Mora Vega", "x"],
        ["0413", "Esteban Mora Vega", "y"],
    ]

    def test_lector_excel_lee_columnas_y_filas(self):
        archivo = SimpleUploadedFile(
            "sada.xlsx",
            _excel_sada(self.FILAS),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

        columnas, filas = LectorArchivoExcel().leer_filas(archivo)

        self.assertEqual(columnas, ["PAJA", "NOMBRE", "OTRO"])
        self.assertEqual(filas, [
            ["0412", "Ana Lucía Mora Vega", "x"],
            ["0413", "Esteban Mora Vega", "y"],
        ])

    def test_lector_excel_archivo_dañado_lanza_error_con_causa(self):
        archivo = SimpleUploadedFile(
            "sada.xlsx", b"esto no es un xlsx real",
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

        with self.assertRaises(ArchivoImportacionError):
            LectorArchivoExcel().leer_filas(archivo)

    def test_lector_csv_con_coma_lee_columnas_y_filas(self):
        archivo = SimpleUploadedFile(
            "sada.csv", _csv_sada(self.FILAS, separador=","),
            content_type="text/csv",
        )

        columnas, filas = LectorArchivoTexto().leer_filas(archivo)

        self.assertEqual(columnas, ["PAJA", "NOMBRE", "OTRO"])
        self.assertEqual(filas, [
            ["0412", "Ana Lucía Mora Vega", "x"],
            ["0413", "Esteban Mora Vega", "y"],
        ])

    def test_lector_csv_con_punto_y_coma_lee_columnas_y_filas(self):
        archivo = SimpleUploadedFile(
            "sada.csv", _csv_sada(self.FILAS, separador=";"),
            content_type="text/csv",
        )

        columnas, filas = LectorArchivoTexto().leer_filas(archivo)

        self.assertEqual(columnas, ["PAJA", "NOMBRE", "OTRO"])
        self.assertEqual(len(filas), 2)

    def test_elegir_lector_por_extension(self):
        self.assertIsInstance(elegir_lector("sada.xlsx"), LectorArchivoExcel)
        self.assertIsInstance(elegir_lector("sada.csv"), LectorArchivoTexto)

    def test_elegir_lector_extension_invalida_lanza_error(self):
        with self.assertRaises(ArchivoImportacionError):
            elegir_lector("sada.jpg")


class VistaPreviaImportacionViewTests(TestCase):
    """1b: vista previa (PAN-09, paso 2), no guarda nada."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_vista_previa")

    def test_requiere_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.post(
            reverse("abonados:importar_vista_previa"), {}, format="multipart",
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_devuelve_columnas_ejemplo_y_total(self):
        archivo = SimpleUploadedFile(
            "sada.xlsx",
            _excel_sada([
                ["PAJA", "NOMBRE"],
                ["0940", "Ana Lucía Mora Vega"],
                ["0941", "Esteban Mora Vega"],
            ]),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

        total_abonados_antes = Abonado.objects.count()

        respuesta = self.cliente.post(
            reverse("abonados:importar_vista_previa"),
            {"archivo": archivo},
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["columnas"], ["PAJA", "NOMBRE"])
        self.assertEqual(
            respuesta.data["ejemplo_fila_2"], ["0940", "Ana Lucía Mora Vega"],
        )
        self.assertEqual(respuesta.data["total_filas"], 2)
        # No guarda nada (paso 2 "revisar columnas"):
        self.assertEqual(Abonado.objects.count(), total_abonados_antes)

    def test_sin_archivo_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:importar_vista_previa"), {}, format="multipart",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_extension_invalida_responde_400_con_causa(self):
        archivo = SimpleUploadedFile(
            "sada.jpg", b"contenido cualquiera", content_type="image/jpeg",
        )

        respuesta = self.cliente.post(
            reverse("abonados:importar_vista_previa"),
            {"archivo": archivo},
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(".xlsx", respuesta.data["archivo"][0])


class ImportarAbonadosViewTests(TestCase):
    """1c: importar de verdad (RF-04), una transacción para todo el lote."""

    def setUp(self):
        self.cliente = APIClient()
        self.cuenta = _crear_cuenta_autenticada(self.cliente, "secretaria_importar")
        # Paja ya registrada, para probar que se omite.
        self.abonado_existente = Abonado.objects.create(
            numero_paja="0412", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        titular_existente = Persona.objects.create(
            nombre="Rodrigo Mora Castro",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0001",
        )
        VinculoAbonado.objects.create(
            abonado=self.abonado_existente,
            persona=titular_existente,
            fecha_inicio=datetime.date(2020, 1, 1),
            rol="TITULAR",
        )

    def _archivo(self, filas):
        return SimpleUploadedFile(
            "sada.xlsx",
            _excel_sada(filas),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

    def test_requiere_autenticacion(self):
        cliente_anonimo = APIClient()
        respuesta = cliente_anonimo.post(
            reverse("abonados:importar"), {}, format="multipart",
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_importa_filas_validas_omite_duplicadas_y_rechaza_malas(self):
        filas = [
            ["PAJA", "NOMBRE"],
            ["0950", "Ana Lucía Mora Vega"],   # nueva: se importa
            ["0412", "Otro Nombre Cualquiera"],  # ya registrada: se omite
            ["", "Sin Paja"],                   # paja vacía: se rechaza
            ["04 88", "Con Espacios"],           # paja con espacios: se rechaza
            ["04X8", "No Numerica"],             # paja no numérica: se rechaza
        ]

        respuesta = self.cliente.post(
            reverse("abonados:importar"),
            {
                "archivo": self._archivo(filas),
                "columna_paja": "PAJA",
                "columna_nombre": "NOMBRE",
            },
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["importados"], 1)
        self.assertEqual(respuesta.data["omitidos"], 1)
        self.assertEqual(len(respuesta.data["rechazados"]), 3)

        rechazados_por_fila = {
            r["fila"]: r for r in respuesta.data["rechazados"]
        }
        self.assertIn("No tiene número de paja", rechazados_por_fila[4]["problema"])
        self.assertIn("espacios", rechazados_por_fila[5]["problema"])
        self.assertIn(
            "no son solo números", rechazados_por_fila[6]["problema"],
        )

        abonado_nuevo = Abonado.objects.get(numero_paja="0950")
        self.assertEqual(abonado_nuevo.tipo_abonado, TipoAbonado.PENDIENTE)

        vinculo = VinculoAbonado.objects.get(
            abonado=abonado_nuevo, rol="TITULAR", fecha_fin__isnull=True,
        )
        self.assertEqual(vinculo.persona.nombre, "Ana Lucía Mora Vega")
        self.assertIsNone(vinculo.persona.tipo_identificacion)
        self.assertIsNone(vinculo.persona.identificacion)
        self.assertEqual(vinculo.fecha_inicio, datetime.date.today())

        # La paja duplicada no creó una segunda persona ni un segundo abonado.
        self.assertFalse(
            Persona.objects.filter(nombre="Otro Nombre Cualquiera").exists(),
        )

        # No se le quitaron los espacios automáticamente (RN-01, decisión
        # del plan): no existe un abonado "0488".
        self.assertFalse(Abonado.objects.filter(numero_paja="0488").exists())

    def test_una_sola_fila_bitacora_por_archivo_no_una_por_fila(self):
        filas = [
            ["PAJA", "NOMBRE"],
            ["0960", "Persona Uno"],
            ["0961", "Persona Dos"],
            ["0962", "Persona Tres"],
        ]

        self.cliente.post(
            reverse("abonados:importar"),
            {
                "archivo": self._archivo(filas),
                "columna_paja": "PAJA",
                "columna_nombre": "NOMBRE",
            },
            format="multipart",
        )

        registros = RegistroBitacora.objects.filter(accion=AccionBitacora.IMPORTACION)
        self.assertEqual(registros.count(), 1)

        registro = registros.first()
        self.assertEqual(registro.cuenta, self.cuenta)
        self.assertTrue(
            registro.elemento_afectado.startswith("importacion_sada.nombre_archivo="),
        )

        modificaciones = RegistroModificacion.objects.filter(
            registro_bitacora=registro,
        )
        self.assertEqual(modificaciones.count(), 1)
        self.assertIn("3 importados", modificaciones.first().valor_nuevo)

    def test_archivo_sin_filas_de_datos_no_crea_evento_de_bitacora(self):
        """Solo encabezado, sin ninguna fila de datos: nada que resumir."""

        filas = [["PAJA", "NOMBRE"]]

        respuesta = self.cliente.post(
            reverse("abonados:importar"),
            {
                "archivo": self._archivo(filas),
                "columna_paja": "PAJA",
                "columna_nombre": "NOMBRE",
            },
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["importados"], 0)
        self.assertEqual(respuesta.data["omitidos"], 0)
        self.assertEqual(respuesta.data["rechazados"], [])
        self.assertFalse(
            RegistroBitacora.objects.filter(
                accion=AccionBitacora.IMPORTACION,
            ).exists(),
        )

    def test_paja_omitida_por_duplicada_tambien_deja_bitacora(self):
        """Aunque todo el lote se omita, sigue siendo un intento real de
        importación: queda un evento con el resumen (0 importados)."""

        filas = [["PAJA", "NOMBRE"], ["0412", "Ya Existe"]]

        self.cliente.post(
            reverse("abonados:importar"),
            {
                "archivo": self._archivo(filas),
                "columna_paja": "PAJA",
                "columna_nombre": "NOMBRE",
            },
            format="multipart",
        )

        registro = RegistroBitacora.objects.get(accion=AccionBitacora.IMPORTACION)
        modificacion = RegistroModificacion.objects.get(registro_bitacora=registro)
        self.assertIn("0 importados", modificacion.valor_nuevo)
        self.assertIn("1 omitidos", modificacion.valor_nuevo)

    def test_columna_elegida_inexistente_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:importar"),
            {
                "archivo": self._archivo([["PAJA", "NOMBRE"], ["0970", "Alguien"]]),
                "columna_paja": "NO_EXISTE",
                "columna_nombre": "NOMBRE",
            },
            format="multipart",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_sin_mapeo_de_columnas_responde_400(self):
        respuesta = self.cliente.post(
            reverse("abonados:importar"),
            {"archivo": self._archivo([["PAJA", "NOMBRE"]])},
            format="multipart",
        )
        self.assertEqual(respuesta.status_code, 400)


class AbonadoSerializerImportacionTests(TestCase):
    """1d: banner de "abonado importado, pendiente" en PAN-06 modificar."""

    def test_abonado_importado_sin_identificacion_es_pendiente(self):
        abonado = Abonado.objects.create(
            numero_paja="0980", tipo_abonado=TipoAbonado.PENDIENTE,
        )
        persona = Persona.objects.create(nombre="Persona Importada de SADA")
        VinculoAbonado.objects.create(
            abonado=abonado,
            persona=persona,
            fecha_inicio=datetime.date(2026, 11, 13),
            rol="TITULAR",
        )

        datos = AbonadoSerializer(abonado).data

        self.assertTrue(datos["es_importado_pendiente"])
        self.assertEqual(
            str(datos["fecha_importacion"]), "2026-11-13",
        )

    def test_abonado_normal_no_es_importado_pendiente(self):
        abonado = Abonado.objects.create(
            numero_paja="0981", tipo_abonado=TipoAbonado.PERSONA_FISICA,
        )
        persona = Persona.objects.create(
            nombre="Ana Lucía Mora Vega",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0123",
        )
        VinculoAbonado.objects.create(
            abonado=abonado,
            persona=persona,
            fecha_inicio=datetime.date.today(),
            rol="TITULAR",
        )

        datos = AbonadoSerializer(abonado).data

        self.assertFalse(datos["es_importado_pendiente"])
        self.assertIsNone(datos["fecha_importacion"])

    def test_abonado_pendiente_con_identificacion_ya_completa_no_es_banner(self):
        """RF-21 ya corrió: le completaron tipo e identificación al
        titular, pero no le cambiaron tipo_abonado todavía."""

        abonado = Abonado.objects.create(
            numero_paja="0982", tipo_abonado=TipoAbonado.PENDIENTE,
        )
        persona = Persona.objects.create(
            nombre="Persona Ya Completada",
            tipo_identificacion="CEDULA_FISICA",
            identificacion="1-0000-0456",
        )
        VinculoAbonado.objects.create(
            abonado=abonado,
            persona=persona,
            fecha_inicio=datetime.date.today(),
            rol="TITULAR",
        )

        datos = AbonadoSerializer(abonado).data

        self.assertFalse(datos["es_importado_pendiente"])
        self.assertIsNone(datos["fecha_importacion"])
