from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Cuenta, TokenCuenta
from apps.bitacora.models import AccionBitacora, RegistroBitacora, RegistroModificacion

from .models import GrupoAlternativas, TipoDocumento


class TipoDocumentoConstraintsTests(TestCase):
    def test_tiene_grupo_o_obligatoriedad_nunca_ambos(self):
        grupo = GrupoAlternativas.objects.create(
            nombre="Grupo de prueba", obligatoriedad="PERSONA_JURIDICA",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TipoDocumento.objects.create(
                    nombre="Tipo con ambos",
                    prioridad=90,
                    obligatoriedad="AMBAS",
                    grupo_alternativas=grupo,
                )

    def test_tiene_grupo_o_obligatoriedad_nunca_ninguno(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TipoDocumento.objects.create(
                    nombre="Tipo sin ninguno", prioridad=91,
                )

    def test_prioridad_debe_ser_positiva(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TipoDocumento.objects.create(
                    nombre="Tipo con prioridad inválida",
                    prioridad=0,
                    obligatoriedad="AMBAS",
                )

    def test_catalogo_inicial_tiene_14_tipos(self):
        self.assertEqual(TipoDocumento.objects.count(), 14)

    def test_grupo_permiso_o_formulario_tiene_dos_tipos(self):
        grupo = GrupoAlternativas.objects.get(nombre="Permiso o formulario")
        self.assertEqual(grupo.tipos_documento.count(), 2)

    def test_obligatoriedad_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TipoDocumento.objects.create(
                    nombre="Tipo con obligatoriedad inválida",
                    prioridad=92,
                    obligatoriedad="INVALIDO",
                )


class GrupoAlternativasConstraintsTests(TestCase):
    def test_obligatoriedad_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GrupoAlternativas.objects.create(
                    nombre="Grupo con obligatoriedad inválida",
                    obligatoriedad="NINGUNA",  # no existe para grupos (obs. 12)
                )


class _ClienteAutenticadoMixin:
    """APIClient autenticado como una `Cuenta` SECRETARIA (mismo patrón
    que `apps.documents.tests_sigeda`)."""

    def _cliente_autenticado(self, usuario="secretaria_tipos_doc"):
        cuenta = Cuenta.objects.create(
            usuario=usuario,
            hash_contrasena=make_password("Prueba2026!"),
            perfil="SECRETARIA",
        )
        token = TokenCuenta.objects.create(cuenta=cuenta)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        return cliente, cuenta


class CrearTipoDocumentoViewTests(_ClienteAutenticadoMixin, TestCase):
    """PAN-10 (RF-09): crear tipo de documento."""

    def setUp(self):
        self.cliente, self.cuenta = self._cliente_autenticado()

    def test_crear_tipo_con_obligatoriedad_valido(self):
        respuesta = self.cliente.post(
            reverse("sigeda_configuration:tipos-documento-crear"),
            {
                "nombre": "Tipo de prueba con obligatoriedad",
                "prioridad": 90,
                "modo": "OBLIGATORIEDAD",
                "obligatoriedad": "AMBAS",
                "es_exigido_a_cotitulares": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        tipo = TipoDocumento.objects.get(
            nombre="Tipo de prueba con obligatoriedad",
        )
        self.assertEqual(tipo.obligatoriedad, "AMBAS")
        self.assertIsNone(tipo.grupo_alternativas_id)
        self.assertTrue(tipo.es_exigido_a_cotitulares)

        registro = RegistroBitacora.objects.get(
            elemento_afectado=f"tipo_documento.id_tipo_documento={tipo.id_tipo_documento}",
        )
        self.assertEqual(registro.accion, AccionBitacora.CREACION)
        self.assertEqual(registro.cuenta, self.cuenta)

    def test_crear_tipo_con_grupo_valido(self):
        grupo = GrupoAlternativas.objects.create(
            nombre="Grupo de prueba para crear", obligatoriedad="AMBAS",
        )

        respuesta = self.cliente.post(
            reverse("sigeda_configuration:tipos-documento-crear"),
            {
                "nombre": "Tipo de prueba con grupo",
                "prioridad": 91,
                "modo": "GRUPO",
                "id_grupo_alternativas": grupo.id_grupo_alternativas,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        tipo = TipoDocumento.objects.get(nombre="Tipo de prueba con grupo")
        self.assertEqual(tipo.grupo_alternativas_id, grupo.id_grupo_alternativas)
        self.assertIsNone(tipo.obligatoriedad)

    def test_nombre_duplicado_se_rechaza(self):
        TipoDocumento.objects.create(
            nombre="Tipo duplicado de prueba", prioridad=92, obligatoriedad="AMBAS",
        )

        respuesta = self.cliente.post(
            reverse("sigeda_configuration:tipos-documento-crear"),
            {
                "nombre": "Tipo duplicado de prueba",
                "prioridad": 93,
                "modo": "OBLIGATORIEDAD",
                "obligatoriedad": "AMBAS",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nombre", respuesta.data)
        self.assertEqual(
            TipoDocumento.objects.filter(nombre="Tipo duplicado de prueba").count(),
            1,
        )

    def test_prioridad_cero_o_negativa_se_rechaza(self):
        respuesta = self.cliente.post(
            reverse("sigeda_configuration:tipos-documento-crear"),
            {
                "nombre": "Tipo con prioridad inválida (vista)",
                "prioridad": 0,
                "modo": "OBLIGATORIEDAD",
                "obligatoriedad": "AMBAS",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("prioridad", respuesta.data)
        self.assertFalse(
            TipoDocumento.objects.filter(
                nombre="Tipo con prioridad inválida (vista)",
            ).exists(),
        )

    def test_grupo_y_obligatoriedad_juntos_se_rechaza(self):
        grupo = GrupoAlternativas.objects.create(
            nombre="Grupo de prueba para rechazo", obligatoriedad="AMBAS",
        )

        respuesta = self.cliente.post(
            reverse("sigeda_configuration:tipos-documento-crear"),
            {
                "nombre": "Tipo con ambos (vista)",
                "prioridad": 94,
                "modo": "GRUPO",
                "id_grupo_alternativas": grupo.id_grupo_alternativas,
                "obligatoriedad": "AMBAS",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(
            TipoDocumento.objects.filter(nombre="Tipo con ambos (vista)").exists(),
        )

    def test_sin_grupo_ni_obligatoriedad_se_rechaza(self):
        respuesta = self.cliente.post(
            reverse("sigeda_configuration:tipos-documento-crear"),
            {
                "nombre": "Tipo sin ninguno (vista)",
                "prioridad": 95,
                "modo": "OBLIGATORIEDAD",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(
            TipoDocumento.objects.filter(nombre="Tipo sin ninguno (vista)").exists(),
        )


class EditarTipoDocumentoViewTests(_ClienteAutenticadoMixin, TestCase):
    """PAN-10 (RF-09): editar tipo de documento + bitácora."""

    def setUp(self):
        self.cliente, self.cuenta = self._cliente_autenticado(
            usuario="secretaria_editar_tipo",
        )
        self.tipo = TipoDocumento.objects.create(
            nombre="Tipo editable de prueba", prioridad=96, obligatoriedad="AMBAS",
        )

    def test_editar_nombre_prioridad_y_obligatoriedad_deja_modificacion(self):
        respuesta = self.cliente.post(
            reverse(
                "sigeda_configuration:tipos-documento-editar",
                args=[self.tipo.id_tipo_documento],
            ),
            {
                "nombre": "Tipo editable de prueba (editado)",
                "prioridad": 97,
                "modo": "OBLIGATORIEDAD",
                "obligatoriedad": "PERSONA_FISICA",
                "es_exigido_a_cotitulares": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.nombre, "Tipo editable de prueba (editado)")
        self.assertEqual(self.tipo.prioridad, 97)
        self.assertEqual(self.tipo.obligatoriedad, "PERSONA_FISICA")
        self.assertTrue(self.tipo.es_exigido_a_cotitulares)

        registro = RegistroBitacora.objects.get(
            elemento_afectado=(
                f"tipo_documento.id_tipo_documento={self.tipo.id_tipo_documento}"
            ),
        )
        self.assertEqual(registro.accion, AccionBitacora.MODIFICACION)

        campos_modificados = set(
            RegistroModificacion.objects.filter(
                registro_bitacora=registro,
            ).values_list("campo_modificado", flat=True),
        )
        self.assertEqual(
            campos_modificados,
            {
                "tipo_documento.nombre",
                "tipo_documento.prioridad",
                "tipo_documento.obligatoriedad",
                "tipo_documento.es_exigido_a_cotitulares",
            },
        )

    def test_sin_cambios_no_deja_fila_de_bitacora(self):
        respuesta = self.cliente.post(
            reverse(
                "sigeda_configuration:tipos-documento-editar",
                args=[self.tipo.id_tipo_documento],
            ),
            {
                "nombre": self.tipo.nombre,
                "prioridad": self.tipo.prioridad,
                "modo": "OBLIGATORIEDAD",
                "obligatoriedad": self.tipo.obligatoriedad,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(
            RegistroBitacora.objects.filter(
                elemento_afectado=(
                    f"tipo_documento.id_tipo_documento={self.tipo.id_tipo_documento}"
                ),
            ).exists(),
        )


class CrearGrupoAlternativasViewTests(_ClienteAutenticadoMixin, TestCase):
    """PAN-10 (RF-09): crear grupo de alternativas con 2+ tipos."""

    def setUp(self):
        self.cliente, self.cuenta = self._cliente_autenticado(
            usuario="secretaria_grupos",
        )
        self.tipo_1 = TipoDocumento.objects.create(
            nombre="Tipo suelto A para grupo", prioridad=98, obligatoriedad="AMBAS",
        )
        self.tipo_2 = TipoDocumento.objects.create(
            nombre="Tipo suelto B para grupo", prioridad=99, obligatoriedad="AMBAS",
        )

    def test_crear_grupo_con_dos_tipos_los_reasigna_con_obligatoriedad_nula(self):
        respuesta = self.cliente.post(
            reverse("sigeda_configuration:grupos-alternativas-crear"),
            {
                "nombre": "Grupo de prueba con 2 tipos",
                "obligatoriedad": "AMBAS",
                "ids_tipos_documento": [
                    self.tipo_1.id_tipo_documento, self.tipo_2.id_tipo_documento,
                ],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        grupo = GrupoAlternativas.objects.get(nombre="Grupo de prueba con 2 tipos")

        self.tipo_1.refresh_from_db()
        self.tipo_2.refresh_from_db()
        self.assertEqual(self.tipo_1.grupo_alternativas_id, grupo.id_grupo_alternativas)
        self.assertEqual(self.tipo_2.grupo_alternativas_id, grupo.id_grupo_alternativas)
        self.assertIsNone(self.tipo_1.obligatoriedad)
        self.assertIsNone(self.tipo_2.obligatoriedad)

        self.assertTrue(
            RegistroBitacora.objects.filter(
                elemento_afectado=(
                    f"grupo_alternativas.id_grupo_alternativas="
                    f"{grupo.id_grupo_alternativas}"
                ),
                accion=AccionBitacora.CREACION,
            ).exists(),
        )

    def test_crear_grupo_con_un_solo_tipo_se_rechaza_con_mensaje_exacto(self):
        respuesta = self.cliente.post(
            reverse("sigeda_configuration:grupos-alternativas-crear"),
            {
                "nombre": "Grupo con un solo tipo",
                "obligatoriedad": "AMBAS",
                "ids_tipos_documento": [self.tipo_1.id_tipo_documento],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(
            respuesta.data["detail"],
            "No se puede guardar el grupo «Grupo con un solo tipo»: tiene "
            "un solo tipo. Un grupo de alternativas necesita al menos 2 "
            "tipos.",
        )
        self.assertFalse(
            GrupoAlternativas.objects.filter(nombre="Grupo con un solo tipo").exists(),
        )
        self.tipo_1.refresh_from_db()
        self.assertIsNone(self.tipo_1.grupo_alternativas_id)

    def test_crear_grupo_sin_tipos_se_rechaza(self):
        respuesta = self.cliente.post(
            reverse("sigeda_configuration:grupos-alternativas-crear"),
            {
                "nombre": "Grupo sin tipos",
                "obligatoriedad": "AMBAS",
                "ids_tipos_documento": [],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(
            GrupoAlternativas.objects.filter(nombre="Grupo sin tipos").exists(),
        )
