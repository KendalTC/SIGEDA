"""
Envoltorio fino sobre `crear_respaldo()` para que el futuro
temporizador systemd (fuera de alcance de hoy; ver CLAUDE.md sección 6,
"faltante 1") pueda disparar el respaldo diario sin tocar código
Python: `python manage.py respaldar automatico`.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.respaldos.models import EstadoRespaldo, TipoRespaldo
from apps.respaldos.servicio_respaldo import RespaldoError, crear_respaldo


class Command(BaseCommand):
    help = "RF-16/ADR-03: crea un respaldo manual o automático del sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "tipo",
            nargs="?",
            default="automatico",
            choices=["manual", "automatico"],
            help="Tipo de respaldo (por defecto: automatico).",
        )

    def handle(self, *args, **options):
        tipo = (
            TipoRespaldo.MANUAL
            if options["tipo"] == "manual"
            else TipoRespaldo.AUTOMATICO
        )

        try:
            respaldo = crear_respaldo(tipo=tipo)
        except RespaldoError as exc:
            raise CommandError(str(exc)) from exc

        if respaldo.estado == EstadoRespaldo.COMPLETO:
            estilo = self.style.SUCCESS
        else:
            estilo = self.style.WARNING

        self.stdout.write(
            estilo(
                f"Respaldo {respaldo.nombre_paquete}: {respaldo.estado} "
                f"({respaldo.tamano_bytes} bytes, SHA-256 {respaldo.hash_sha256}).",
            ),
        )
