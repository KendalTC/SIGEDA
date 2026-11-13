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
from apps.bitacora.models import AccionBitacora, RegistroBitacora, RegistroModificacion
from apps.configuration.models import TipoDocumento
from apps.documents.models import Documento, VersionDocumento

from . import controlador_busqueda as cb
from .models import Abonado, Persona, RolVinculo, Sector, TipoAbonado, VinculoAbonado
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
