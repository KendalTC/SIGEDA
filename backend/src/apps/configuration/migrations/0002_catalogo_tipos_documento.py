from django.db import migrations

# SUPUESTO (CLAUDE.md sección 5): catálogo sacado del prototipo; la
# prioridad del 3 en adelante es provisional (pendiente con la
# administradora). El grupo "Permiso o formulario" exige a la persona
# jurídica aportar uno de los dos tipos 9 o 10 (CU-09: 2 o más tipos).
GRUPO_PERMISO_O_FORMULARIO = "Permiso o formulario"

TIPOS_DOCUMENTO = [
    # (prioridad, nombre, obligatoriedad, grupo, exigido_a_cotitulares)
    (1, "Plano legible", "AMBAS", None, False),
    (2, "Formulario de solicitud", "AMBAS", None, False),
    (3, "Copia de cédula", "PERSONA_FISICA", None, True),
    (4, "Certificación de registro de propiedad", "PERSONA_FISICA", None, False),
    (5, "Contrato de servicio", "AMBAS", None, False),
    (6, "Cédula jurídica", "PERSONA_JURIDICA", None, False),
    (7, "Personería jurídica vigente", "PERSONA_JURIDICA", None, False),
    (8, "Cédula de la persona apoderada", "PERSONA_JURIDICA", None, False),
    (9, "Permiso de construcción vigente", None, GRUPO_PERMISO_O_FORMULARIO, False),
    (10, "Formulario de construcción y uso del agua", None, GRUPO_PERMISO_O_FORMULARIO, False),
    (11, "Boletas de trabajo", "NINGUNA", None, False),
    (12, "Recibos por cobros especiales", "NINGUNA", None, False),
    (13, "Conexiones ilegales", "NINGUNA", None, False),
    (14, "Fotos del inmueble", "NINGUNA", None, False),
]


def cargar_tipos_documento(apps, schema_editor):
    GrupoAlternativas = apps.get_model("configuration", "GrupoAlternativas")
    TipoDocumento = apps.get_model("configuration", "TipoDocumento")

    grupo, _ = GrupoAlternativas.objects.get_or_create(
        nombre=GRUPO_PERMISO_O_FORMULARIO,
        defaults={"obligatoriedad": "PERSONA_JURIDICA"},
    )

    for prioridad, nombre, obligatoriedad, nombre_grupo, exigido in TIPOS_DOCUMENTO:
        TipoDocumento.objects.get_or_create(
            nombre=nombre,
            defaults={
                "prioridad": prioridad,
                "obligatoriedad": obligatoriedad,
                "grupo_alternativas": grupo if nombre_grupo else None,
                "es_exigido_a_cotitulares": exigido,
            },
        )


def quitar_tipos_documento(apps, schema_editor):
    TipoDocumento = apps.get_model("configuration", "TipoDocumento")
    GrupoAlternativas = apps.get_model("configuration", "GrupoAlternativas")

    TipoDocumento.objects.filter(
        nombre__in=[t[1] for t in TIPOS_DOCUMENTO],
    ).delete()
    GrupoAlternativas.objects.filter(nombre=GRUPO_PERMISO_O_FORMULARIO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("configuration", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(cargar_tipos_documento, quitar_tipos_documento),
    ]
