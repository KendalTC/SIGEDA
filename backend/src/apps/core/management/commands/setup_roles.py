from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.core.permissions import (
    ROLE_ADMIN,
    ROLE_CUSTOMERS,
    ROLE_INVENTORY,
    ROLE_READ_ONLY,
    ROLE_SALES,
)


class Command(BaseCommand):
    """
    Crea los grupos de rol base. Ya no asigna permisos de módulo:
    esos módulos (inventory, sales, cash, customers) eran de las
    apps de negocio de LICS, retiradas al construir SIGEDA. Los
    nombres de rol se conservan porque `apps.accounts` todavía los
    usa para la administración genérica de usuarios de Django.
    """

    help = "Crea los grupos de roles base."

    def handle(self, *args, **options):
        roles = [
            ROLE_ADMIN,
            ROLE_INVENTORY,
            ROLE_SALES,
            ROLE_CUSTOMERS,
            ROLE_READ_ONLY,
        ]

        created_count = 0

        for role in roles:
            _, created = Group.objects.get_or_create(name=role)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created role: {role}"))
            else:
                self.stdout.write(f"Role already exists: {role}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Roles ready. Created: {created_count}. Total: {len(roles)}."
            )
        )
