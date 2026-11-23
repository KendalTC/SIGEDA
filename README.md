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

Estado actual (23/11/2026):

    Script DDL del Modelo ER v1.1 (14 tablas) generado y verificado: db/ddl/sigeda_v1.1.sql.
    Modelos Django de las 14 tablas, con CHECK, UQ parciales, los 2 EXCLUDE de vinculo_abonado
    (RN-02) y llaves primarias compuestas (Django 5.2).
    Incrementos 1 a 4 completos y cerrados, cada uno con prueba de terminado real contra el
    stack real (evidencia en docs/evidencia/, no inventada) y 0 infracciones de accesibilidad
    (axe-core): CU-04 cargar documento (PAN-05); sesión y cuentas (PAN-01, PAN-14, RNF-09);
    expediente completo (PAN-02, PAN-04, PAN-06, PAN-13) con sus diálogos; respaldo y
    restauración cifrados (PAN-08, D-05); importación de SADA (PAN-09); tipos de documento
    (PAN-10, CRUD real); completitud a fondo (PAN-07); bitácora (PAN-11); exportación (PAN-12).
    252 pruebas automáticas del backend en verde (1 omitida, limitación documentada de rol de
    Postgres superusuario en desarrollo).
    Apps de negocio de LICS y su documentación histórica retiradas del repositorio.
    Despliegue de producción confirmado (23/11/2026): laptop Windows de la ASADA. El
    instalador de infra/windows/ (Electron + WSL2 + Docker Engine) quedó renombrado
    lics→sigeda ese mismo día, junto con infra/systemd/, scripts/ y el workflow de
    GitHub Actions — ver Pendientes principales para lo que falta antes de instalarlo en
    hardware real.

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

El despliegue de producción de SIGEDA es la laptop Windows de la ASADA (confirmado el
23/11/2026). `infra/windows/` (Electron + WSL2 + Docker Engine), renombrado lics→sigeda ese
mismo día, es el instalador real a terminar — ver [Despliegue en Windows](infra/windows/README.md).
Falta compilarlo y probarlo contra hardware Windows real (no se puede desde un entorno
Linux/WSL2 de desarrollo) y volver a registrar el runner self-hosted de GitHub Actions con su
label nuevo.

Documentación relacionada:

- [Arquitectura del sistema](docs/architecture.md)
- [Despliegue en Windows](infra/windows/README.md)

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

Evidencia propia de SIGEDA (`docs/evidencia/`): una prueba de terminado real por incremento,
desde [CU-04 Cargar documento](docs/evidencia/prueba_terminado_CU04.md) hasta
[Incremento 4 — tipos, completitud, bitácora, exportar](docs/evidencia/prueba_terminado_incremento4.md).

---

# Estado de validación

    Django check: OK
    Migraciones: al día
    Tests backend: 252/252 en verde, 1 omitida (make test) — limitación documentada: rol de
    Postgres superusuario en desarrollo (ADR-05 sin efecto real todavía)
    Tests propios de SIGEDA: 238/238 en verde, 1 omitida (make test-sigeda)
    Accesibilidad (axe-core): 0 infracciones en las pantallas de SIGEDA construidas

---

# Pendientes principales

1. Compilar y probar el instalador de Windows (`infra/windows/`) contra hardware real: no se
   puede desde un entorno Linux/WSL2 de desarrollo. El renombrado lics→sigeda, la corrección
   del respaldo automático systemd (ahora dispara el mecanismo real de `apps/respaldos`, no el
   `pg_dump` viejo) y la limpieza del modo kiosco descartado ya quedaron hechos (23/11/2026).
2. Volver a registrar el runner self-hosted de GitHub Actions con el label `sigeda-windows`
   (antes `lics-windows`) en la máquina física — acción manual, fuera de git.
3. Segundo rol de PostgreSQL con permisos restringidos (solo INSERT/SELECT) para la bitácora en
   tiempo de ejecución (ADR-05, RNF-11) — por ahora documentado como pendiente, no implementado.
4. Preguntas abiertas con la administradora (CLAUDE.md, sección 9).
5. Retención de respaldos: falta "diario vs. semanal" y "2 copias en la laptop" (solo "7 más
   recientes por destino" implementado — ver `docs/evidencia/prueba_terminado_respaldo_restauracion.md`).

Ver [CLAUDE.md](CLAUDE.md) para el detalle completo de requerimientos y el plan de incrementos.
