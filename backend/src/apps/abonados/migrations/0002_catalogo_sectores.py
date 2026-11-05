from django.db import migrations

# SUPUESTO (CLAUDE.md sección 5): lista de sectores sacada del
# prototipo; falta confirmar que esté completa con la administradora.
SECTORES = ["Bodegas", "Pilas", "Calle Cerro", "Calle Central", "Trapiche"]


def cargar_sectores(apps, schema_editor):
    Sector = apps.get_model("abonados", "Sector")

    for nombre in SECTORES:
        Sector.objects.get_or_create(nombre=nombre)


def quitar_sectores(apps, schema_editor):
    Sector = apps.get_model("abonados", "Sector")
    Sector.objects.filter(nombre__in=SECTORES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("abonados", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(cargar_sectores, quitar_sectores),
    ]
