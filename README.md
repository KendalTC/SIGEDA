# SIGEDA

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)
![Django REST Framework](https://img.shields.io/badge/DRF-3.16-A30000)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-000000?logo=nextdotjs&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-Proxy-009639?logo=nginx&logoColor=white)

**SIGEDA** (Sistema de Gestión Documental del Acueducto) digitaliza y organiza los expedientes de los
1015 abonados de la ASADA **Acueducto Bodegas y Pilas** (Costa Rica), sustituyendo el archivo físico
actual. No cubre facturación (queda en SADA), mantenimiento de averías ni conexiones nuevas.

Proyecto del curso **IF6100 Análisis y Diseño de Sistemas**, Universidad de Costa Rica, Sede de
Occidente (Recinto de Grecia), Grupo 02, II Ciclo 2026. Equipo: Mariangel Arias Alfaro, Alejandro
Arias Rojas, Sebastián Alfaro Arias y Kendal Trejos Cubero.

Construido sobre la base de código de **[LICS v2.5.0](https://github.com/aleariasr/laboratorio-inyeccion-castro-solis)**
(Alejandro Arias Rojas, integrante del equipo, quien autorizó su reutilización): infraestructura
Docker/Nginx/Django/Next.js, patrones de backend y componentes de frontend. Las apps de negocio de
LICS (inventario, ventas, caja, clientes) no aplican a SIGEDA y se retiraron; el detalle de qué se
reutilizó, adaptó o quitó está en [CLAUDE.md](CLAUDE.md).

---

# Índice

- [Estado del proyecto](#estado-del-proyecto)
- [Arquitectura general](#arquitectura-general)
- [Tecnologías principales](#tecnologías-principales)
- [Arquitectura del repositorio](#arquitectura-del-repositorio)
- [Entornos](#entornos)
- [Endpoints principales](#endpoints-principales)
- [Documentación](#documentación)
- [Estado de validación](#estado-de-validación)
- [Pendientes principales](#pendientes-principales)

---

# Estado del proyecto

Versión actual:

    0.1.0

Estado actual (Avance de Construcción, 06/11/2026):

    Script DDL del Modelo ER v1.1 (14 tablas) generado y verificado: db/ddl/sigeda_v1.1.sql.
    Modelos Django de las 14 tablas, con CHECK, UQ parciales, los 2 EXCLUDE de vinculo_abonado
    (RN-02) y llaves primarias compuestas (Django 5.2).
    Rebanada vertical de CU-04 Cargar documento: backend (ControladorDocumentos, cifrado
    AES-256-GCM, SHA-256, bitácora de solo inserción), API REST y frontend (PAN-05 con sus 6
    estados, PAN-04 y PAN-13 mínimos), con la guía de estilo propia de SIGEDA.
    Prueba de terminado ejecutada contra el stack real, con evidencia real (no inventada) en
    docs/evidencia/prueba_terminado_CU04.md.
    0 infracciones de accesibilidad (axe-core) en las pantallas construidas.
    Apps de negocio de LICS y su documentación histórica retiradas del repositorio.
    Resto del sistema (sesión y cuentas, expediente completo, respaldo y restauración,
    importación de SADA, tipos de documento, completitud, bitácora, exportación): sin construir
    todavía — ver Incrementos 2 a 4 en CLAUDE.md, sección 9.

---

# Arquitectura general

    Usuario
      |
      v
    Navegador
      |
      v
    http://localhost
      |
      v
    Nginx
      |
      +--> Next.js
      |
      +--> Django REST Framework
              |
              v
          PostgreSQL

Todos los componentes se ejecutan como servicios independientes mediante Docker Compose. Los
documentos cargados se cifran con AES-256-GCM antes de guardarse en un volumen aparte del de
PostgreSQL; la clave vive fuera del repositorio.

El despliegue de producción de SIGEDA (laptop local de la ASADA o una máquina virtual Linux en
Azure) sigue sin decidirse. El despliegue de LICS para Windows (Electron + WSL2 + Docker Engine) se
conserva en el repositorio como referencia — ver [Despliegue en Windows](infra/windows/README.md) —
pero todavía no aplica a SIGEDA.

Documentación relacionada:

- [Arquitectura del sistema](docs/architecture.md)
- [Despliegue en Windows de LICS (referencia, no vigente para SIGEDA)](infra/windows/README.md)

---

# Tecnologías principales

| Área | Tecnología |
|---|---|
| Contenedores | Docker Engine + Docker Compose |
| Backend | Python 3.13, Django 5.2.6, Django REST Framework 3.16.1 |
| Cifrado de documentos | AES-256-GCM (`cryptography`), SHA-256 |
| Frontend | Next.js 16, React 19, TypeScript |
| Base de datos | PostgreSQL 17 (`btree_gist`, `unaccent`, `pg_trgm`) |
| Proxy local | Nginx |
| Versionado | Git y GitHub |

---

# Arquitectura del repositorio

    backend/
        Código fuente del backend Django. Apps del Modelo ER v1.1: abonados, accounts,
        bitacora, configuration, documents, respaldos. apps/core y apps/health heredadas de
        LICS, recortadas a lo genérico.

    frontend/
        Aplicación Next.js. Las pantallas propias de SIGEDA viven en frontend/src/app/sigeda/
        y frontend/src/features/sigeda/, con su propia guía de estilo
        (frontend/src/app/sigeda/sigeda.css). El resto (login, mi cuenta, estado del sistema)
        es lo que queda de LICS tras retirar sus módulos de negocio.

    db/ddl/
        Script DDL del Modelo ER v1.1, generado desde la base migrada.

    infra/
        Configuración de Docker, Nginx y componentes de infraestructura. infra/windows/,
        infra/windows-demo/ e infra/systemd/ son el despliegue de LICS para Windows,
        conservados como referencia.

    docs/
        Documentación técnica heredada de LICS y evidencia propia de SIGEDA (docs/evidencia/).

    CLAUDE.md
        Contexto completo del proyecto SIGEDA: requerimientos, modelo de datos, arquitectura,
        reglas de trabajo.

    VERSION
        Versión actual del proyecto.

---

# Entornos

## Desarrollo

Requisitos:

- Docker Engine o Docker Desktop.
- Docker Compose.
- Git.
- Make.

Configuración inicial:

    cp infra/docker/.env.example infra/docker/.env

Editar `infra/docker/.env` y generar una clave de cifrado real:

    python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

Inicio:

    make up
    make migrate
    docker compose -f infra/docker/compose.yml exec backend python src/manage.py setup_roles
    docker compose -f infra/docker/compose.yml exec backend python src/manage.py seed_sigeda_demo

Administración:

    make ps
    make logs
    make restart
    make check
    make migrate
    make makemigrations
    make shell
    make test
    make test-sigeda

## Producción

Sin decidir todavía (CLAUDE.md, sección 6: "Despliegue: sigue abierto").

---

# Endpoints principales

## Sistema

    GET /api/health/
    GET /api/system/status/

## Cuentas de LICS (genérico, Django `auth.User`; no es el sistema de `Cuenta` de SIGEDA)

    POST /api/accounts/login/
    POST /api/accounts/logout/
    GET /api/accounts/me/
    POST /api/accounts/me/password/

## SIGEDA — autenticación de `Cuenta` (RF-01, RNF-09)

    POST /api/sigeda/auth/login/
    POST /api/sigeda/auth/logout/
    GET /api/sigeda/auth/me/
    POST /api/sigeda/auth/cambiar-contrasena/

## SIGEDA — CU-04 Cargar documento

    GET /api/sigeda/abonados/{numero_paja}/expediente/
    POST /api/sigeda/documentos/cargar/
    GET /api/sigeda/documentos/{id_documento}/versiones/
    GET /api/sigeda/documentos/{id_documento}/versiones/{numero_version}/descargar/
    GET /api/sigeda/catalogos/tipos-documento/

---

# Documentación

Índice general:

- [Índice de documentación](docs/index.md)
- [CLAUDE.md](CLAUDE.md) — contexto completo del proyecto, requerimientos y reglas de trabajo

Documentos técnicos (heredados de LICS, todavía vigentes para SIGEDA):

- [Arquitectura del sistema](docs/architecture.md)
- [Desarrollo](docs/development.md)
- [Backups y restauración (SIGEDA la adapta en el Incremento 3)](docs/backup-restore.md)
- [Seguridad](docs/security.md)
- [Sistema de diseño del frontend (de LICS; ver nota sobre la guía propia de SIGEDA)](docs/frontend-design-system.md)

Evidencia propia de SIGEDA:

- [Prueba de terminado — CU-04 Cargar documento](docs/evidencia/prueba_terminado_CU04.md)

---

# Estado de validación

    Django check: OK
    Migraciones: al día
    Tests backend: 54/54 en verde (make test)
    Tests propios de SIGEDA: 40/40 en verde (make test-sigeda)
    Accesibilidad (axe-core): 0 infracciones en las pantallas de SIGEDA construidas

---

# Pendientes principales

1. Renombrar «lics» → «sigeda» en `infra/docker/compose.prod.yml`, `scripts/` y lo que referencian
   (`LICS_VERSION`, nombres de imagen): se dejó para cuando se decida el despliegue de producción
   de SIGEDA, junto con `infra/windows/` e `infra/systemd/`.
2. Incremento 2: sesión y cuentas (PAN-01, PAN-14, RNF-09 completo, contraseña temporal) y
   expediente completo (PAN-02, PAN-04, PAN-06, PAN-13) con sus diálogos.
3. Incremento 3: respaldo y restauración (incluye cifrar los documentos del respaldo, restaurar
   desde la aplicación sin borrar la bitácora) e importación de SADA.
4. Incremento 4: tipos de documento, completitud, bitácora (pantalla) y exportación.
5. Segundo rol de PostgreSQL con permisos restringidos (solo INSERT/SELECT) para la bitácora en
   tiempo de ejecución (ADR-05, RNF-11) — por ahora documentado como pendiente, no implementado.
6. Preguntas abiertas con la administradora (CLAUDE.md, sección 9).

Ver [CLAUDE.md](CLAUDE.md) para el detalle completo de requerimientos y el plan de incrementos.
