# Prueba de terminado — Incremento 4: tipos de documento, completitud, bitácora, exportar

Ejecutada de verdad el 13/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Next.js + Nginx, sin mocks), con la
cuenta `secretaria` y datos ficticios (pajas y nombres inventados).
Resultados reales, no inventados (CLAUDE.md, regla 1).

Trabajo autónomo del 13/11/2026 (Kendal fuera; pidió explícitamente
seguir con este incremento tras cerrar los Incrementos 2 y 3). Con
este cierre queda completa toda la hoja de ruta de
`sigeda-hoja-de-ruta` salvo el "Cierre final" (renombrado lics→sigeda,
pendiente de la decisión de despliegue).

## 1. PAN-10 — Tipos de documento (RF-09)

CRUD real, no catálogo de solo lectura: se creó el tipo "Croquis de
ubicacion prueba cierre" (`docs/evidencia/pan10_tipo_creado.png`), se
intentó crear un grupo de alternativas con 1 solo tipo y se rechazó
con el mensaje exacto de la ficha: *"No se puede guardar el grupo
«Grupo prueba cierre incompleto»: tiene un solo tipo. Un grupo de
alternativas necesita al menos 2 tipos."* (`pan10_grupo_error.png`),
y se creó un grupo válido con 2 tipos, que reasignó su obligatoriedad
a NULL como corresponde al CHECK "grupo XOR obligatoriedad"
(`pan10_grupo_exito.png`).

**¿Pasó?** Sí.

## 2. PAN-07 — Completitud a fondo (RF-14)

Reutiliza `calcular_completitud` (Q3, del Incremento 2b) tal cual para
el detalle por persona; las consultas masivas (tarjetas, lista de
incompletos, tipo pendiente) son nuevas.

**Hallazgo real durante la verificación — bug de rendimiento (N+1),
encontrado y corregido hoy, no documentado como deuda:** al abrir
PAN-07 por primera vez en el navegador, la pantalla se quedó en
"Cargando…" sin resolver. Medido directamente contra el endpoint real
(`/api/sigeda/abonados/completitud/`, con los ~1032 abonados activos
reales de la base de prueba): **9.73 segundos**. La causa: las tres
funciones de resumen llamaban `calcular_completitud` abonado por
abonado, y cada llamada hacía entre 4 y 5 consultas a la base
(vínculos, documentos aportados, catálogo de tipos, catálogo de
grupos) — más de 9000 consultas para una sola carga de pantalla.

Se corrigió en `apps/abonados/servicio_completitud.py` sin tocar la
regla de negocio (la lógica de qué falta y por qué es exactamente la
misma, movida a `_calcular_faltantes`, probada con las mismas 141
pruebas de la app `abonados`): se agregó `_contexto_lote()` (2
consultas para TODOS los abonados en vez de 2 por abonado) y
`_todo_el_catalogo()` (el catálogo completo, chico, cacheado una sola
vez por request en vez de refiltrado desde la base por cada abonado).
`calcular_completitud(abonado)` —la función pública que ya usa
PAN-04— no cambió su firma ni su contrato.

**Resultado tras la corrección:** el mismo endpoint, con los mismos
1032 abonados, responde en **0.127 segundos** (76 veces más rápido),
con los mismos números exactos (`completos: 0, incompletos: 1027,
tipo_pendiente: 5, avance_pct: 0.0`). Confirmado en el navegador real:
la pantalla ya carga (`pan07_viewport.png`) y el detalle por persona
(clic en "Ver detalle") muestra la matriz Documento obligatorio ×
Titular × Cotitular con ✓/✗/"No aplica" correctos
(`pan07_detalle.png`).

**¿Pasó (tras la corrección)?** Sí.

## 3. PAN-11 — Bitácora (RF-15)

`pan11_detalle.png`: la bitácora muestra en orden cronológico
descendente los eventos reales de hoy y de incrementos anteriores
(creación del tipo y el grupo de la prueba de PAN-10, importaciones de
SADA, cambios de titular, respaldos, creaciones de abonados), con el
número de paja resuelto correctamente para los eventos que lo tienen
(referencia lógica sin FK, resuelta por la vista con una consulta en
lote) y "Ver cambios" expandiendo el detalle campo por campo.

**¿Pasó?** Sí.

## 4. PAN-12 — Exportar documentos (RF-18, RN-10)

Exportado real del documento vigente del abonado de prueba 0412
("Copia de cédula") a la carpeta montada en
`/app/exportaciones/0412_20261113/` (`pan12_resultado.png`). Confirmado
con Python dentro del contenedor que el archivo resultante en disco
empieza con los bytes mágicos reales de un PDF (`%PDF-1.6`), es decir
**ya no está cifrado** — cumple el mensaje de la ficha ("Los archivos
exportados ya no están cifrados: entréguelos solo a quien
corresponda."). Confirmado con `psql`: un solo evento `EXPORTACION`
(`exportacion.numero_paja=0412`) con un solo
`registro_modificacion` (`exportacion.resumen` = "1 documento(s)
exportado(s) a /app/exportaciones/0412_20261113").

**¿Pasó?** Sí.

## 5. Pruebas automáticas

- `make test`: **252/252, 1 omitida** (limitación ya documentada del
  Incremento 3a — usuario de Postgres superusuario en este entorno).
- `make test-sigeda`: **238/238, 1 omitida**.
- Corridas de nuevo después de la corrección de rendimiento de PAN-07
  (incluida la app `abonados` completa, 141/141) para confirmar que el
  resultado de completitud no cambió, solo la velocidad.

## 6. Accesibilidad (axe-core 4.10.2, CDN)

0 infracciones reportadas por el agente de frontend en 16
combinaciones pantalla/estado de las 4 pantallas nuevas. Verificado
de forma independiente por mí sobre PAN-07 después de la corrección
de rendimiento (por ser la pantalla que modifiqué): 0 infracciones.

## Decisiones y discrepancias encontradas durante la construcción (para el Anexo B)

- **Rutas reales distintas a las del plan inicial**: tipos de
  documento y grupos de alternativas viven bajo
  `/api/sigeda/catalogos/tipos-documento/administracion/` y
  `.../grupos-alternativas/` (junto al catálogo liviano de PAN-05, no
  en una raíz nueva); completitud vive bajo
  `/api/sigeda/abonados/completitud/` (no en una raíz propia). El
  agente de frontend las confirmó contra el backend real antes de
  escribir el código, así que no hay deuda, solo la nota para
  documentación.
- **PAN-07, filtro "Completos"**: el backend no expone la lista de
  abonados completos (solo el conteo en la tarjeta) — el filtro de
  estado en "Completos" muestra un aviso en vez de fingir una lista
  que no existe.
- **PAN-12, "Imprimir" con varios documentos**: abre una pestaña por
  documento en secuencia; con 1-2 documentos funciona, pero el
  navegador puede bloquear las pestañas después de la primera si hay
  varias (comportamiento normal de bloqueador de popups). Pendiente de
  decidir si vale la pena ajustar la UX (por ejemplo, una descarga a
  la vez con confirmación) — no es un defecto de los datos, solo de la
  experiencia con varios documentos a la vez.
- **PAN-10**: no se construyó "eliminar" tipo ni "editar" grupo — la
  ficha solo describe alta/edición de tipos y alta de grupos; borrar
  un tipo usado además rompería RESTRICT con `documento`. No es una
  omisión, es el alcance real de RF-09.
- **PAN-07, tabla de incompletos sin paginar**: con los ~1027
  abonados incompletos de la base de prueba, la tabla completa se
  renderiza de una vez (sin paginación ni virtualización). Funciona y
  pasó axe-core, pero es una página larga — queda anotado como posible
  mejora de UX para cuando haya datos reales a esa escala, no como un
  defecto bloqueante.

## Qué se aprendió

- **El mayor riesgo real de este incremento no fue una regla de
  negocio mal entendida, sino rendimiento**: la lógica de completitud
  (ya construida y probada desde el Incremento 2b) era correcta desde
  el primer día; lo que faltaba era no repetirla fila por fila contra
  la base para ~1000 abonados. Esto confirma que "reutilizar la lógica
  tal cual" (decisión del plan) fue la decisión correcta — el error
  no estaba en la regla, estaba en cuántas veces se consultaba la
  base para aplicarla — y que verificar con los datos reales de la
  base de prueba (no con 2-3 abonados de juguete) fue lo que hizo
  visible el problema.
- El patrón de "un evento de bitácora por operación, no por fila"
  (ya usado en el Incremento 3b para importar) se reaplicó igual para
  exportar, sin inventar un formato nuevo.
- Con este cierre, **toda la hoja de ruta de los Incrementos 2, 3 y 4
  queda construida**. Sigue solo el "Cierre final" (renombrado
  lics→sigeda del resto de `infra/`/`scripts/`/`.github`, pendiente de
  la decisión de despliegue, y regresión general).
