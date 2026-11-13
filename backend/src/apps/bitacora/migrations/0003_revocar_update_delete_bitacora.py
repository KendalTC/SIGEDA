"""
ADR-05 / RNF-11: el usuario de base de datos de la aplicación
(`settings.DATABASES["default"]["USER"]`) solo debe poder INSERT y
SELECT sobre las 3 tablas de bitácora. Se implementa con un REVOKE
directo (no con un rol de Postgres nuevo), reversible con el GRANT
inverso.

NOTA IMPORTANTE para quien despliegue esto (ver también
docs/evidencia u el informe del Incremento 3a): este REVOKE solo tiene
efecto real si el usuario de la aplicación NO es superusuario de
Postgres. Se confirmó empíricamente (con un rol descartable, nunca
alterando el rol real) que:
  - Postgres SÍ hace cumplir un REVOKE de UPDATE/DELETE contra el
    propio dueño de la tabla, siempre que ese dueño no sea
    superusuario.
  - Un rol superusuario ignora cualquier ACL, incluida la de sus
    propias tablas: ningún REVOKE lo restringe.
En este entorno de desarrollo, el usuario configurado en
POSTGRES_USER se crea como superusuario del clúster (así arranca la
imagen oficial de `postgres` cuando se define POSTGRES_USER), así que
esta migración no alcanza a restringirlo de verdad todavía. Dejar esa
decisión (separar un rol de aplicación no-superusuario del rol de
arranque/migraciones) para quien cierre el Incremento 3a: es un
cambio de infraestructura compartida, no algo para decidir a mitad de
una migración de Django.
"""

from django.conf import settings
from django.db import migrations


def _usuario_aplicacion() -> str:
    return settings.DATABASES["default"]["USER"]


def _identificador_postgres(nombre: str) -> str:
    """Escapa un identificador de Postgres entre comillas dobles."""

    return '"' + nombre.replace('"', '""') + '"'


_TABLAS_BITACORA = ("registro_bitacora", "registro_modificacion", "registro_restauracion")

_USUARIO_SQL = _identificador_postgres(_usuario_aplicacion())
_TABLAS_SQL = ", ".join(_TABLAS_BITACORA)


class Migration(migrations.Migration):

    dependencies = [
        ("bitacora", "0002_registrobitacora_registro_bitacora_accion_dominio"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                f"REVOKE UPDATE, DELETE ON {_TABLAS_SQL} FROM {_USUARIO_SQL};"
            ),
            reverse_sql=(
                f"GRANT UPDATE, DELETE ON {_TABLAS_SQL} TO {_USUARIO_SQL};"
            ),
        ),
    ]
