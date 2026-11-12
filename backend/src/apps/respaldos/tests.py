from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import CopiaRespaldo, Respaldo


class RespaldoConstraintsTests(TestCase):
    def test_tipo_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Respaldo.objects.create(tipo="INVALIDO", estado="PENDIENTE")

    def test_estado_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Respaldo.objects.create(tipo="AUTOMATICO", estado="INVALIDO")

    def test_tamano_bytes_debe_ser_positivo(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Respaldo.objects.create(
                    tipo="AUTOMATICO", estado="PENDIENTE", tamano_bytes=0,
                )


class CopiaRespaldoConstraintsTests(TestCase):
    def setUp(self):
        self.respaldo = Respaldo.objects.create(tipo="MANUAL", estado="PENDIENTE")

    def test_destino_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CopiaRespaldo.objects.create(
                    respaldo=self.respaldo, destino="INVALIDO", estado="PENDIENTE",
                )

    def test_estado_fuera_de_dominio_se_rechaza(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CopiaRespaldo.objects.create(
                    respaldo=self.respaldo,
                    destino="DISCO_EXTERNO",
                    estado="INVALIDO",
                )
