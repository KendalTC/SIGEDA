# Prueba de terminado — Incremento 3b: importar SADA (PAN-09, RF-04)

Ejecutada de verdad el 13/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Next.js + Nginx, sin mocks), con la
cuenta `secretaria` y archivos ficticios de prueba (nombres y pajas
inventados, fuera del rango real de abonados). Resultados reales, no
inventados (CLAUDE.md, regla 1).

Trabajo autónomo del 13/11/2026 (Kendal fuera); con este cierre quedan
completos los Incrementos 2 y 3 enteros. Ver
`/home/tcken/.claude/plans/starry-baking-naur.md` y memoria
`sigeda-trabajo-autonomo`.

## 1. Flujo completo real (los 4 pasos de la ficha)

CSV ficticio real con 4 filas: dos pajas nuevas (9801, 9802), una paja
ya registrada (0412, el abonado de prueba) y una fila sin número de
paja. Mapeo manual de columnas real (`PAJA`→Número de paja,
`NOMBRE`→Nombre del titular, `DIRECCION`→No se usa —
`docs/evidencia/pan09_paso2_revisar_columnas.png`, confirma que el
mapeo no asume nombres de columna fijos, tal como pide ADR-04).

**Resultado real** (`docs/evidencia/pan09_paso4_resumen.png`): *"2
abonados creados"*, 1 omitido (paja 0412 ya existía), 1 rechazado
("No tiene número de paja." → "Agregue el número de paja en SADA y
vuelva a importar."). Los dos abonados nuevos quedaron con
`tipo_abonado=PENDIENTE` y su `Persona` sin `tipo_identificacion`/
`identificacion` (confirmado con `psql`) — tal como exige RF-04,
porque SADA no exporta ni el tipo de abonado ni la cédula.

**¿Pasó?** Sí.

## 2. Rechazo por paja con espacios (RN-01)

Probado por los agentes con una fila de paja `"96 03"`: rechazada tal
cual, sin quitarle los espacios automáticamente — *"Número de paja con
espacios («96 03»)."* → *"Corríjalo en SADA y vuelva a importar."*
(decisión del plan: no "corregirla sola", porque la ficha pide que se
corrija en el origen).

**¿Pasó?** Sí.

## 3. Bitácora: un evento por archivo, no uno por fila

Confirmado con `psql`: cada importación deja **una sola fila**
`registro_bitacora` (`IMPORTACION`,
`elemento_afectado=importacion_sada.nombre_archivo={archivo}`) con su
`registro_modificacion` (`importacion_sada.resumen`: "N importados, N
omitidos, N rechazados") — no una fila por cada uno de los abonados
creados.

**¿Pasó?** Sí.

## 4. Hueco real encontrado y cerrado durante la verificación de hoy

El plan de 3b decía que PAN-06 "Modificar abonado" debía mostrar el
titular con identificación **opcional** cuando el abonado está
"importado, pendiente" — pero no incluía el endpoint para guardar esa
identificación. El agente de frontend lo notó al revisar
`ModificarAbonadoView` y, correctamente, **no construyó un campo que
no iba a guardar nada** (regla 1 de CLAUDE.md: no fingir una función
que no existe). Se le encargó al agente de backend agregar ese
procesamiento (reutilizando la misma validación de formato y
detección de identificación duplicada que ya usan D-04/D-06/alta de
2c), y recién entonces se completó el campo en el frontend.

**Verificado de punta a punta** (abonado importado 9601): completar la
identificación con un formato inválido da 400 con el mensaje exacto;
con la cédula de otra persona ya existente da 409 ("Ya existe una
persona con esa identificación: {nombre}, titular de la paja
{paja}."); con una cédula nueva válida, guarda de verdad — el titular
pasa a mostrarse con su identificación y el banner de "pendiente"
desaparece. Confirmado con `psql`: una sola fila de bitácora
MODIFICACION con las 4 columnas cambiadas juntas (sector, tipo,
tipo_identificacion, identificación) — "todo o nada" por envío: un
intento fallido de identificación no deja a medio guardar el sector o
el tipo del mismo formulario.

**¿Pasó (tras el cierre del hueco)?** Sí.

## 5. Pruebas automáticas

- `make test`: **215/215, 1 omitida** (limitación ya documentada del
  Incremento 3a — usuario de Postgres superusuario en este entorno).
- `make test-sigeda`: **201/201, 1 omitida**.

## 6. Accesibilidad (axe-core 4.10.2, CDN)

0 infracciones reportadas por el agente de frontend en 6
pantallas/estados: PAN-09 paso 1 (elegir), error de archivo no válido,
paso 2 (revisar columnas), paso 3 (importando), paso 4 (resumen), y el
banner + mini-formulario de identificación de PAN-06 modificar.

## Qué se aprendió

- **El patrón de "revisar antes de actuar" del propio proyecto
  (`BuscarPersonaCombo`, "Usar esa persona", conflictos 409) se pudo
  reaplicar tal cual** en el flujo de completar identificación de un
  abonado importado — ninguna lógica de validación de identificación
  se repitió: `validar_longitud_identificacion()`/
  `buscar_persona_existente()` ya existían desde el Incremento 2c.
- **El mapeo manual de columnas (ADR-04) resultó ser la decisión de
  diseño correcta**: el archivo de prueba usó nombres de columna
  (`PAJA`/`NOMBRE`/`DIRECCION`) completamente distintos a cualquier
  cosa hardcodeada, y el flujo igual funcionó, confirmando que no hace
  falta conocer el formato real de SADA (S-05) para que esto sirva el
  día que llegue un archivo real.
- Con este cierre, **los Incrementos 2 y 3 completos de la hoja de
  ruta quedan construidos**. Sigue el Incremento 4 (tipos de
  documento, completitud a fondo, bitácora, exportar).
