# Prueba de terminado — Incremento 2a: sesión y cuentas (PAN-01, PAN-14, D-08, RF-20, RNF-09)

Ejecutada de verdad el 13/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Next.js + Nginx, sin mocks), con las dos
cuentas ficticias `secretaria` / `administracion` ya sembradas.
Resultados reales, no inventados (CLAUDE.md, regla 1).

## 1. Mensajes dinámicos de PAN-01 (RNF-09)

**Intentos restantes** (vía navegador real, `secretaria` con la
contraseña equivocada):
> Usuario o contraseña incorrectos. Revise que la tecla Bloq Mayús no
> esté activa e intente de nuevo. Le quedan 4 intentos antes de que la
> cuenta se bloquee 5 minutos.

Singular verificado también (`Le queda 1 intento...`, sin el bug de
`intento(s)` literal que hubo que corregir en el incremento anterior).

**Bloqueo real tras agotar los 5 intentos** (captura
`docs/evidencia/pan01_bloqueada.png`):
> La cuenta «secretaria» está bloqueada por 5 intentos fallidos. Podrá
> intentar de nuevo a las 18:24 (en 5 minutos). Si olvidó la
> contraseña, pida a la Administración una contraseña temporal desde
> «Mi cuenta».

Hora de desbloqueo y minutos reales (no simulados), y el nombre de la
otra cuenta calculado dinámicamente. Campos y botón deshabilitados
mientras dura el bloqueo.

**¿Pasó?** Sí.

## 2. RF-20: asignar contraseña temporal a la otra cuenta (lo que faltaba)

Flujo real, de punta a punta, vía navegador:
1. `administracion` entra a PAN-14 y genera una temporal para
   `secretaria`: **`Agua-4288-Cauce`** (formato palabra-número-palabra
   temático del acueducto, generado por el sistema — SUPUESTO del
   algoritmo exacto, documentado en el código).
2. `secretaria` entra con esa temporal → la aplicación la obliga a
   pasar por **"Cree su contraseña"** antes de dejarla continuar
   (capturas `pan01_temporal.png`, `pan14_temporal.png`).
3. Tras guardar la contraseña nueva, redirige al expediente y la
   bandera `es_contrasena_temporal` vuelve a `false`.
4. Confirmado con `psql`: quedó una fila `RESTABLECIMIENTO_CONTRASENA`
   en `registro_bitacora`, a nombre de quien la asignó
   (`administracion`), con `elemento_afectado=cuenta.id_cuenta=2`.

**Hallazgo corregido durante esta misma verificación:** el login ya
dejaba la sesión activa en `localStorage` *antes* de terminar "Cree su
contraseña", así que la barra superior ya era visible y alguien podía
hacer clic en "Mi cuenta" o escribir otra URL directamente para
saltarse el cambio obligatorio (RF-20 dice "cambio obligatorio al
entrar"). Se agregó una guardia global
(`GuardiaContrasenaTemporal`, en `frontend/src/features/sigeda/`) que
redirige de vuelta a PAN-01 desde cualquier otra ruta mientras
`es_contrasena_temporal` siga en `true`, y la barra superior ahora no
se muestra en ese estado. Verificado con un script real: navegar a
`/sigeda/expedientes/0412` a mitad del flujo redirige de inmediato de
vuelta a "Cree su contraseña", sin excepción.

**¿Pasó?** Sí (incluyendo la corrección del hallazgo).

## 3. RNF-09: cierre de sesión real por 15 minutos de inactividad

Antes de hoy esto no existía ni en el cliente ni en el servidor — un
token nunca expiraba. Verificado real, no solo en pruebas unitarias:

- Se forzó `ultima_actividad` de un token real a 20 minutos en el
  pasado (vía ORM) y se llamó a un endpoint autenticado real
  (`GET /api/sigeda/auth/me/`) con ese token: respondió
  **403** con `{"detail": "La sesión se cerró por 15 minutos de
  inactividad. Inicie sesión de nuevo."}`, y el token quedó borrado de
  la base (confirmado con una consulta posterior).
- El código de estado es **403, no 401**: es la convención ya
  existente en el proyecto para `AutenticacionCuenta` (DRF la fuerza
  así porque ese autenticador no define `authenticate_header()`, y ya
  hay una prueba aprobada en otra app que depende de ese 403). El
  frontend se ajustó a 403 explícitamente.
- D-08 (`docs/evidencia/d08_sesion_por_cerrarse.png`): diálogo nativo
  `<dialog>` con el texto y los dos botones exactos de la ficha,
  cuenta regresiva real. Verificado con los tiempos reales de 14/15
  minutos (se bajaron temporalmente solo para la captura, y se
  revirtió el cambio antes de seguir).
- Cuando el servidor ya cerró la sesión (403 con token), el frontend
  la detecta sola y redirige a `/sigeda/login`, sin esperar a que el
  vigilante del cliente lo note — verificado con un token corrompido
  a propósito.

**¿Pasó?** Sí.

## 4. Pruebas automáticas

- `make test`: **100/100** (87 del incremento anterior + 13 nuevas de
  cuentas/inactividad).
- `make test-sigeda`: **86/86**.
- `makemigrations --check --dry-run`: sin cambios pendientes.

## 5. Accesibilidad (axe-core 4.10.2, CDN, reglas wcag2a/wcag2aa/wcag21aa/wcag22aa/best-practice)

0 infracciones en: PAN-01 inicial, error de credenciales, bloqueada,
"Cree su contraseña"; PAN-14 inicial, con contraseña temporal
generada, error de validación; y D-08 con el diálogo abierto.

**¿Pasó?** Sí.

## Qué se aprendió

- **Confirmado:** el patrón "barra superior mínima" (sin el menú
  lateral completo de PAN-02) alcanza para que RF-20 y RNF-09 sean
  usables hoy, sin inventar una pantalla de inicio que todavía no
  corresponde a este incremento.
- **Hallazgo real, no anticipado por el plan:** dejar la sesión
  "activa" en el cliente desde el primer login —incluso con una
  contraseña temporal pendiente de cambiar— abre una vía para saltarse
  el cambio obligatorio si no se la bloquea explícitamente. Quedó
  corregido (ver sección 2) y es un recordatorio para el resto de
  incrementos: cualquier estado "a medias" de una sesión necesita su
  propia guardia de ruta, no alcanza con la UI de un solo formulario.
- **SUPUESTO que sigue abierto:** el algoritmo exacto de la contraseña
  temporal (lista de palabras, cantidad de dígitos) es una decisión
  libre nuestra — el documento solo confirma el patrón visual.
