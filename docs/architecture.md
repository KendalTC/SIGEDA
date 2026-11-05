# Arquitectura del sistema

Documento heredado de **LICS v2.5.0** (Alejandro Arias Rojas, con su
autorización), la base de código de **SIGEDA**. La capa de infraestructura
que describe (Docker Compose, Nginx como único punto de entrada, Next.js,
Django/DRF, PostgreSQL) es la misma que usa SIGEDA hoy; lo que cambió al
construir SIGEDA está en la capa de aplicación (modelos del Modelo ER
v1.1, CU-04), no en esta arquitectura base — ver [CLAUDE.md](../CLAUDE.md).

## 1. Objetivo

El sistema está diseñado para operar localmente en una computadora dedicada sin depender de una conexión permanente a Internet.

> **Nota:** esta descripción de producción en Windows (WSL2 + Electron) es
> la de **LICS**, conservada en `infra/windows/` como referencia — ver
> [Despliegue en Windows](../infra/windows/README.md). SIGEDA todavía no
> tiene un despliegue de producción propio decidido. Los componentes y el
> flujo interno descritos en este documento no cambian entre plataformas;
> la única capa que varía es la de "interfaz final" (kiosco Linux vs.
> ventana Electron en Windows).

La arquitectura prioriza:

- estabilidad;
- persistencia de datos;
- recuperación ante fallos;
- facilidad de mantenimiento;
- despliegues reproducibles;
- soporte técnico controlado;
- posibilidad de reutilización para otros clientes.

## 2. Componentes

### Nginx

Es el único punto de entrada expuesto al usuario.

Responsabilidades:

- recibir solicitudes en `http://localhost`;
- enviar solicitudes de interfaz al frontend;
- enviar solicitudes `/api/` al backend;
- ocultar los puertos internos de los servicios;
- centralizar futuras políticas de seguridad y límites.

### Frontend

Aplicación Next.js responsable de la interfaz de usuario.

El frontend debe consumir la API mediante rutas relativas:

```text
/api/
```

No debe conocer ni utilizar directamente el puerto interno de Django.

### Backend

Aplicación Django con Django REST Framework.

Responsabilidades:

- reglas de negocio;
- autenticación;
- autorización;
- validación;
- persistencia;
- auditoría;
- API;
- coordinación de procesos transaccionales.

### PostgreSQL

Base de datos principal.

Los datos se almacenan en un volumen nombrado administrado por Docker. Los respaldos lógicos se realizarán mediante `pg_dump`.

## 3. Flujo de solicitudes

```text
Usuario
  |
  v
App de escritorio (Electron) o Chromium en modo kiosco
  |
  v
Nginx :80
  |
  +---- / ---------> Next.js :3000
  |
  +---- /api/ -----> Django :8000
                          |
                          v
                    PostgreSQL :5432
```

## 4. Exposición de servicios

En la configuración base solamente Nginx publica un puerto hacia el equipo anfitrión.

PostgreSQL, Django y Next.js permanecen accesibles únicamente dentro de la red interna de Docker.

## 5. Persistencia

PostgreSQL utiliza el volumen:

```text
postgres_data
```

Las dependencias de Node utilizan un volumen separado:

```text
frontend_node_modules
```

**Propio de SIGEDA:** los documentos cargados (CU-04) se cifran y se guardan en un tercer
volumen, aparte del de PostgreSQL:

```text
sigeda_documentos_cifrados
```

Los contenedores pueden eliminarse y recrearse sin perder los datos almacenados en PostgreSQL ni
en el almacén de documentos cifrados.

## 6. Entornos

El proyecto mantiene separación entre:

- desarrollo;
- staging local;
- producción.

### Desarrollo

Usa `infra/docker/compose.yml`.

Características:

- código fuente montado como volumen;
- recarga y herramientas de desarrollo;
- configuración mediante `.env`;
- comandos mediante `Makefile`.

### Producción

Usa `infra/docker/compose.prod.yml`.

Características:

- imágenes construidas y versionadas;
- Gunicorn para Django;
- Next.js compilado en modo standalone;
- `DEBUG=False`;
- secretos generados localmente;
- Nginx enlazado a `127.0.0.1`;
- healthchecks;
- backup y restore;
- instalación offline mediante paquete versionado.

## 7. Decisiones no negociables

- PostgreSQL es la base de datos de producción.
- Los secretos no se almacenan en Git.
- Nginx es el único punto de entrada.
- Toda actualización productiva debe crear un backup previo.
- Los procesos críticos deben validar su estado antes de modificar datos.
- La restauración debe probarse antes de la entrega.
- No se implementará el modelo de negocio sin requerimientos formales.
