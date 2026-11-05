from django.db import IntegrityError, transaction
from django.test import TestCase

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
