# Seguridad

Documento heredado de **LICS v2.5.0** (Alejandro Arias Rojas, con su
autorización), adaptado para **SIGEDA**. Los principios, el manejo de
secretos y la red son los mismos; la sección de control de acceso se
reescribió porque SIGEDA ya no usa el sistema de roles por módulo de
negocio de LICS (se retiró al construir SIGEDA — ver
[CLAUDE.md](../CLAUDE.md)). La sección "Seguridad en Windows" documenta
el despliegue real de producción de SIGEDA (`infra/windows/`, laptop
Windows de la ASADA, confirmado el 23/11/2026).

## Principios

- mínimo privilegio;
- separación entre usuario operador y usuario técnico;
- secretos fuera del repositorio;
- acceso remoto restringido;
- servicios internos no expuestos;
- registro de acciones administrativas;
- backups protegidos.

## Secretos

Nunca deben confirmarse en Git:

- contraseñas;
- claves de Django;
- credenciales de PostgreSQL;
- claves SSH privadas;
- archivos `.env`;
- respaldos con información real.

## Red

Solamente Nginx debe publicar un puerto hacia el anfitrión.

PostgreSQL, Django y Next.js deben permanecer dentro de la red interna de Docker.

## Control de acceso

SIGEDA tiene dos sistemas de autenticación separados en el mismo backend, que no se mezclan:

### Cuentas de SIGEDA (RF-01, RNF-09)

El modelo real de SIGEDA (`apps/accounts/models.py:Cuenta`, tabla `cuenta` del Modelo ER v1.1),
con su propia autenticación por token (`apps/accounts/sigeda_auth.py`,
`apps/accounts/sigeda_views.py`) y sus endpoints bajo `/api/sigeda/auth/`.

- **RN-09: dos cuentas con los mismos permisos** (`secretaria` y `administracion`, `cuenta.perfil`
  `SECRETARIA`/`ADMINISTRADORA`). No hay roles ni permisos diferenciados: cualquier cuenta
  autenticada puede hacer lo mismo. La única excepción propuesta y todavía sin confirmar con la
  administradora es que solo `ADMINISTRADORA` pueda autorizar una restauración de respaldo
  (Incremento 3, sin construir todavía).
- **Bloqueo tras intentos fallidos (RNF-09):** 5 intentos incorrectos bloquean la cuenta 5 minutos
  (`cuenta.intentos_fallidos`, `cuenta.bloqueada_hasta`), implementado en `LoginCuentaView`.
- **Contraseñas:** mínimo 8 caracteres. `cuenta.es_contrasena_temporal` fuerza el cambio al entrar
  (RF-20); todavía falta la pantalla que lo exige en el frontend (Incremento 2).
- **Cierre de sesión por inactividad (15 min, RNF-09):** sin construir todavía; queda para el
  Incremento 2, como control de frontend (la tabla `cuenta` no tiene una columna de "última
  actividad": ver CLAUDE.md, sección 5).

### Administración genérica heredada de LICS

Lo que queda de LICS tras retirar sus apps de negocio (`/login`, `/account`,
`/system/status`, autenticación por `django.contrib.auth.User` y
`rest_framework.authtoken`, endpoints bajo `/api/accounts/`): sirve para administrar el
Django de base (por ejemplo, crear un superusuario con `createsuperuser` y usar `/admin/`
o `/api/system/status/`), no para el dominio de SIGEDA.

- `AdministrationPermission` (`backend/src/apps/core/permissions.py`): permite el acceso a
  superusuarios, usuarios `is_staff` o miembros del grupo `ADMIN`.
- **El sistema de permisos por módulo de negocio de LICS (`ModulePermission` y sus
  subclases, `ModulePermissions`, la administración de usuarios con permisos
  individuales) se retiró por completo al construir SIGEDA**, porque dependía de módulos
  que ya no existen (inventario, ventas, caja, clientes). `is_staff` solo controla el
  acceso al panel `/admin/` de Django; ya no hay permisos de módulo que otorgar.
- `setup_roles` sigue creando los 5 grupos de Django que traía LICS (`ADMIN`, `INVENTORY`,
  `SALES`, `CUSTOMERS`, `READ_ONLY`) porque el código genérico de administración de usuarios
  los sigue nombrando, pero ya no tienen ningún permiso de módulo asociado.

Las secciones «SSH» y «Operadores» que siguen describen el modelo de seguridad a nivel de sistema operativo pensado originalmente para Linux, heredado de LICS sin cambios. La sección [Seguridad en Windows](#seguridad-en-windows), más abajo, documenta el despliegue real de producción de SIGEDA en Windows (`infra/windows/`, ver [infra/windows/README.md](../infra/windows/README.md)).

## SSH

En producción:

- acceso exclusivo para soporte autorizado;
- autenticación mediante llave;
- contraseña deshabilitada cuando sea posible;
- acceso root directo deshabilitado;
- firewall limitado a la red de mantenimiento.

## Django

Producción deberá usar:

```text
DEBUG=False
```

También deberá configurar:

- `ALLOWED_HOSTS`;
- cookies seguras cuando aplique;
- protección CSRF;
- encabezados de seguridad;
- límites de sesión;
- bloqueo o control de intentos;
- auditoría de accesos.

## Operadores

El usuario que utiliza el sistema no debe tener permisos administrativos sobre Linux ni Docker.

## Cifrado de documentos (propio de SIGEDA, RNF-10, RNF-13)

Sección nueva: LICS no maneja archivos, así que esto no tiene equivalente en el documento
original.

- Los documentos cargados (CU-04) se cifran con **AES-256-GCM**
  (`apps/documents/cifrado.py`, librería `cryptography`) antes de guardarse en un volumen
  Docker aparte del de PostgreSQL (`sigeda_documentos_cifrados`). El SHA-256 se calcula
  sobre el archivo original, antes de cifrar.
- **SUPUESTO de este incremento:** la clave de cifrado (32 bytes) vive en
  `infra/docker/.env` (fuera de Git, en `.gitignore`), no en el repositorio. La entrega
  como secreto de Docker y la custodia física + digital de la clave que exige RNF-13 son
  trabajo de despliegue real, todavía sin hacer (Incremento 3, cuando se decida el
  despliegue de producción de SIGEDA).
- La base de datos **no está cifrada en reposo**: solo los documentos y (cuando se
  construya el respaldo de SIGEDA) los paquetes de respaldo. Nombres, cédulas y demás
  datos personales de `persona`/`abonado` quedan legibles si alguien copia el volumen de
  PostgreSQL directamente.

## Seguridad en Windows

> Esta sección describe el despliegue de **SIGEDA** en Windows
> (`infra/windows/`), confirmado como el despliegue real de producción
> (laptop Windows de la ASADA) el 23/11/2026. La infraestructura venía de
> LICS v2.5.0 y se renombró lics→sigeda ese mismo día — ver
> [Pendientes principales](../README.md#pendientes-principales).

Esta sección toma cada medida de las secciones anteriores (pensadas para
Linux) y documenta su equivalente real en la arquitectura de producción
vigente de SIGEDA: WSL2 (Ubuntu 24.04, distro `sigeda-wsl`) + Docker Engine
dentro de esa distro + app de escritorio Electron en Windows (ver
[`infra/windows/README.md`](../infra/windows/README.md), la referencia
real y validada contra hardware; el documento de cierre de etapa que se
citaba aquí antes no se conservó en el repositorio). Cada punto está
verificado contra el código real, no asumido; donde no se encontró un
equivalente implementado se marca explícitamente como brecha.

### Red

Sin cambios de fondo, y con un endurecimiento adicional confirmado en el
código: en `infra/docker/compose.prod.yml`, Nginx es el único servicio con
`ports:` — y publica `127.0.0.1:${HTTP_PORT:-80}:80`, es decir, **solo en
loopback**, no en todas las interfaces (a diferencia de `infra/docker/compose.yml`,
de desarrollo, que publica `"80:80"` sin restringir la interfaz).
PostgreSQL, backend (Django) y frontend (Next.js) no tienen ninguna
sección `ports:` en `compose.prod.yml`: siguen alcanzables solo por la red
interna de Docker (`networks: application`), exactamente igual que en
Linux — este `compose.prod.yml` corre sin ningún cambio dentro de la distro
WSL2. La propia app Electron (`infra/windows/electron/main.js`) tampoco se
desvía de esto: `APP_URL` y `HEALTH_URL` (en `main.js` y
`infra/windows/electron/lib/backend.js`) apuntan únicamente a
`http://127.0.0.1/...`.

### Acceso remoto (equivalente de SSH)

No hay ningún servidor SSH ni ningún otro puerto de administración remota
en todo el flujo Windows/WSL2/Electron — se revisó explícitamente
(`infra/windows/`) y la única mención a "SSH" en esos archivos es una
comparación de prosa con el modelo Linux anterior
(`infra/windows/README.md`, sección "Actualizar la aplicación"), no un
mecanismo real.

Todo el control de la distro se hace exclusivamente invocando `wsl.exe -d
sigeda-wsl -- ...` **desde el propio proceso Electron corriendo en esa misma
máquina Windows** (`spawnInDistro()` en
`infra/windows/electron/lib/backend.js`), o por una persona físicamente
frente a esa Windows corriendo `wsl -d sigeda-wsl` a mano. No existe ninguna
vía de red para llegar a ese control — es una mejora real sobre SSH: SSH,
aun con llaves y firewall (como pide la sección "SSH" de arriba), sigue
siendo un demonio expuesto a la red que hay que mantener parcheado y
acotado; acá no hay nada escuchando en la red para administración remota,
punto.

**Actualizaciones**: el menú **SIGEDA > Actualizar aplicación (Django/Next)…**
(`main.js`) es la única forma de llevar cambios de Django/Next a una
instalación existente, y exige una confirmación explícita
(diálogo Cancelar/Actualizar) de alguien sentado frente a esa máquina antes
de llamar a `backend.updateApplication()` →
`resources/windows/update-application.sh` dentro de la distro. No existe
disparo remoto ni automático de ningún tipo. Esto es una mejora concreta
sobre un flujo de actualización por SSH: ahí, en principio, alguien con
acceso de red y la llave correcta podría disparar una actualización sin
estar presente; acá hace falta estar físicamente en la máquina y confirmar
el diálogo.

**La restauración real del archivo documental (RF-16) no es un script: es
una funcionalidad de la propia aplicación web de SIGEDA** (PAN-08/D-05,
`apps/respaldos`), detrás de sesión iniciada, con confirmación escrita y
exigiendo la contraseña de la cuenta Administración en concreto (ver
`backend/src/apps/respaldos/sigeda_views.py`), nunca desde el menú de
Electron ni por una vía de red fuera de la propia app. `rollback.sh`
(revertir una actualización de código fallida — un procedimiento distinto,
no un respaldo del archivo documental) sigue sin exponerse en el menú de
Electron, a propósito, igual que en Linux: sigue siendo manual, con
confirmación escrita, corriendo dentro de WSL2. La diferencia con el
modelo Linux es que ahora se invoca localmente (`wsl -d sigeda-wsl --
sudo bash /opt/sigeda/scripts/rollback.sh`) en vez de por SSH: al no
existir SSH en absoluto, esto es al menos equivalente y, en la práctica,
más restrictivo — exige presencia local en la máquina de producción, no
solo credenciales de red.

### Separación de usuarios (equivalente de "Operadores")

**Brecha identificada: no hay separación de usuarios, ni en WSL2 ni en
Windows.** Verificado en el código, no es un supuesto:

- `infra/windows/wsl/provision-golden-image.sh` lo dice explícitamente en
  un comentario: la distro "corre como root (no crea un usuario operativo
  separado: esta distro es un 'appliance' de un solo propósito, no una
  estación de trabajo interactiva)".
- `infra/windows/wsl/build-golden-image.ps1` configura `wsl.conf` con
  `[user]` / `default=root` — el usuario por defecto de toda la distro
  `sigeda-wsl` es root.
- Del lado Windows, las dos tareas programadas que registra
  `register-scheduled-task.ps1` corren con principal `RunLevel Limited`
  (SID `S-1-5-32-545`, `BUILTIN\Users`) disparadas al inicio de sesión de
  **cualquier** usuario de esa Windows — no hay una cuenta Windows
  dedicada y separada para operar SIGEDA; corre bajo la sesión de quien
  inicie sesión en esa computadora.

Esto no es peor que el modelo Linux: era exactamente el mismo pendiente
documentado más abajo, en "Controles pendientes" ("Usuario operativo del
sistema operativo", "Usuario técnico separado"), y sigue sin resolverse acá
tampoco. La migración a Windows no lo empeoró ni lo arregló — lo dejó
igual de pendiente. Queda como decisión del negocio si vale la pena
resolverlo dado que SIGEDA sigue siendo una computadora dedicada de un
solo propósito.

### systemd (unidades productivas): sigue siendo la base, no fue reemplazado

`sigeda.service`, `sigeda-backup.service`/`.timer` y
`sigeda-watchdog.service`/`.timer` **siguen corriendo, sin modificar,
dentro de la distro WSL2** — no fueron reemplazados por la tarea
programada de Windows. `provision-golden-image.sh` los instala al
construir la imagen dorada (`install_systemd_units()`, que llama a
`install-systemd.sh`, `install-backup-timer.sh` e
`install-watchdog-timer.sh`), y funcionan porque WSL2 corre un systemd
real dentro de la distro (`systemd=true` en `wsl.conf`, confirmado en
`build-golden-image.ps1`). El respaldo diario (`sigeda-backup.timer`,
`OnCalendar=*-*-* 03:00:00`, `Persistent=true`) dispara
`python src/manage.py respaldar automatico` dentro del contenedor backend
(RF-16/ADR-03: base + almacén de documentos, cifrado, verificado con
SHA-256 — corregido el 23/11/2026: antes llamaba a un `scripts/backup.sh`
retirado, que solo hacía `pg_dump` sin cifrar y sin los documentos) y el
watchdog de autocuración (`sigeda-watchdog.timer`, cada 2 minutos) son
exactamente los mismos que en Linux, corriendo por la misma vía.

La tarea programada de Windows (`register-scheduled-task.ps1`) **no
sustituye** a systemd — resuelve un problema distinto y específico de
WSL2: por sí sola, WSL2 apaga toda la distro (systemd incluido) segundos
después de arrancar si ningún proceso `wsl.exe` queda conectado como
cliente (ver el comentario de "SEGUNDA RONDA" en
`register-scheduled-task.ps1` y la sección "Problema conocido" de
`infra/windows/README.md`). La tarea "SIGEDA - Iniciar backend" solo
dispara `start.sh` al iniciar sesión en Windows, y "SIGEDA - Mantener
sesion WSL activa" mantiene un cliente `wsl.exe` conectado de forma
indefinida para que WSL2 no apague la distro; el trabajo real (arrancar
servicios, respaldar, vigilar) lo sigue haciendo systemd adentro, sin
cambios.

El modo kiosco de Chromium (pensado para el plan original de Ubuntu
Desktop/Linux Mint) se descartó y se retiró del repositorio el
23/11/2026 (`infra/systemd/lics-kiosk.service` y los scripts
`start-kiosk.sh`/`install-kiosk.sh`/`install-autologin-gdm.sh`/
`install-workstation.sh`/`install-desktop-user.sh`): nunca se instaló en
el flujo Windows (`install_systemd_units()` no lo incluía) y era
vestigial en esta arquitectura — la app Electron reemplaza
funcionalmente al modo kiosco (ventana nativa normal, sin Chromium en
pantalla completa, ver `infra/windows/README.md`, "Decisión de
arquitectura").

### Backups y restauración

El timer y el servicio de respaldo automático corren dentro de WSL2 sin
modificarse (ver arriba), y desde el 23/11/2026 disparan el mecanismo
real de SIGEDA (`apps/respaldos`, cifrado AES-256-GCM, verificado con
SHA-256) en vez del `pg_dump` sin cifrar que usaban antes. La
restauración del archivo documental (RF-16) es una funcionalidad de la
propia aplicación web (PAN-08/D-05), detrás de sesión iniciada y
contraseña de la cuenta Administración — nunca un script, nunca desde la
interfaz de Electron, nunca por una vía de red fuera de la propia app.
`rollback.sh` (revertir una actualización de código fallida, procedimiento
distinto) sigue siendo manual, con confirmación escrita, y se dispara
localmente vía `wsl -d sigeda-wsl` en vez de por SSH — nunca desde la
interfaz de Electron, nunca por una vía de red. Quien puede ejecutarlo es
exactamente quien tiene acceso físico/local a esa computadora Windows; al
no existir SSH en este modelo, no hay una superficie de red adicional que
asegurar para este punto en particular.

## Controles implementados actualmente

- Secretos excluidos de Git.
- `.env.prod` generado durante instalación.
- `.env.prod` con permisos restringidos.
- Nginx como único punto de entrada.
- Servicios internos sin exposición directa.
- Backend y frontend ejecutados como usuarios no root dentro de sus contenedores.
- `no-new-privileges` configurado en producción.
- `DEBUG=False` en producción.
- Encabezados básicos de seguridad configurados en Nginx.
- Backups con permisos restrictivos.
- Restauración productiva con confirmación explícita y backup preventivo.

## Controles pendientes

- Usuario operativo del sistema operativo.
- Usuario técnico separado.
- SSH con llaves.
- Firewall.
- Hardening del sistema operativo.
- Política de recuperación de credenciales administrativas.