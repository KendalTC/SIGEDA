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
from apps.bitacora.models import AccionBitacora, RegistroBitacora
from apps.configuration.models import TipoDocumento
from apps.documents.models import Documento, VersionDocumento

from . import controlador_busqueda as cb
from .models import Abonado, Persona, Sector, TipoAbonado, VinculoAbonado
from .servicio_completitud import calcular_completitud


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
