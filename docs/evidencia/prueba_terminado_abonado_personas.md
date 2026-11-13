# Prueba de terminado — Incremento 2c: abonado y personas (PAN-06, D-04, D-06)

Ejecutada de verdad el 13/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Next.js + Nginx, sin mocks), con la
cuenta `secretaria` y abonados ficticios (tomo 0000 y pajas de prueba
fuera del rango real). Resultados reales, no inventados (CLAUDE.md,
regla 1).

Trabajo autónomo del 13/11/2026 (Kendal fuera); ver
`/home/tcken/.claude/plans/starry-baking-naur.md` para el plan completo
y memoria `sigeda-trabajo-autonomo`.

## 1. Alta de abonado (PAN-06, RF-02)

Flujo real por navegador: alta exitosa de un abonado nuevo ficticio
(`docs/evidencia/pan06_alta_exito.png`), paja duplicada rechazada con
el mensaje exacto de la ficha (`pan06_alta_error.png`), y detección de
persona ya existente por cédula con el recuadro ámbar y el botón "Usar
esa persona" (`pan06_alta_persona_existente.png`) — reenviar con
`id_persona` crea el abonado reutilizando la persona, sin duplicarla.

**¿Pasó?** Sí.

## 2. Modificar abonado (PAN-06, RF-21)

Sector y tipo editables; paja y estado de solo lectura con las notas
fijas (`pan06_modificar.png`). Confirmado con `psql` que solo cambian
los campos editados, con `registro_modificacion` real.

**¿Pasó?** Sí.

## 3. D-06 Agregar persona asociada

Buscador compartido (por nombre o cédula, con los vínculos actuales de
cada resultado) + alta de persona nueva si no aparece
(`d06_agregar_persona.png`). Probado agregando una cotitular nueva a
un abonado real por la interfaz; quedó en `personas_vigentes` y se
reflejó de inmediato en el indicador de completitud (construido en el
Incremento 2b).

**¿Pasó?** Sí.

## 4. D-04 Cambiar titular (RF-13, hallazgo H-02)

Se abre directo desde PAN-04 ("Cambiar titular…"), sin pasar por
"Modificar abonado" — confirmado por la interfaz real
(`d04_cambiar_titular.png`, que muestra el combo con "Vínculos
actuales: Cotitular de 0412" para ayudar a no duplicar personas). El
titular anterior pasa al historial con la fecha del cambio como fecha
fin; sus documentos se conservan con la etiqueta "titular anterior" ya
construida en 2b; el tipo de abonado no cambia.

**¿Pasó?** Sí.

## 5. Bug real encontrado y corregido durante esta verificación

**Hallazgo** (reportado primero por el agente de frontend, confirmado
y corregido por mí): cambiar el titular hacia una persona cuyo vínculo
vigente (cotitular, por ejemplo) **empezó el mismo día** que la fecha
del cambio fallaba con un error interno.

**Causa real** (confirmada reproduciendo el error directo contra
PostgreSQL, no por inspección de código): `vinculo_abonado` usa
`(id_abonado, id_persona, fecha_inicio)` como **llave primaria
compuesta**. Cerrar ese vínculo y crear uno nuevo con la misma fecha de
inicio produce dos filas con la misma llave primaria — un
`duplicate key value violates unique constraint "vinculo_abonado_pkey"`,
no un problema de rangos de fechas como se sospechaba al principio.

**Corrección**: cuando el vínculo vigente de la persona elegida empezó
el mismo día que la fecha del cambio, se **reutiliza esa misma fila**
(solo se le cambia el rol a `TITULAR`, sin tocar fechas) en vez de
cerrarla y crear una nueva — y se cierra primero al titular anterior,
antes de reasignar el rol, para no toparse tampoco con
`vinculo_abonado_un_titular_vigente` (un solo titular vigente por
abonado, que PostgreSQL comprueba por sentencia dentro de la misma
transacción, no solo al final). Agregada una prueba de regresión real
(`CambiarTitularViewTests.test_cambiar_titular_el_mismo_dia_que_el_vinculo_previo_reutiliza_la_fila`)
y reverificado el caso completo por la interfaz real: agregar una
persona hoy mismo con D-06 y ascenderla a titular hoy mismo con D-04
funciona y dejó la base en el estado correcto (un solo titular
vigente, historial íntegro).

**¿Pasó (tras la corrección)?** Sí.

## 6. Pruebas automáticas

- `make test`: **176/176**.
- `make test-sigeda`: **162/162**.

## 7. Accesibilidad (axe-core 4.10.2, CDN)

0 infracciones reportadas por el agente de frontend en 7
pantallas/estados: PAN-06 alta (inicial, error, persona-existente,
éxito), PAN-06 modificar, D-04 y D-06 abiertos.

## Qué se aprendió

- **El caso límite que el prototipo no cubría** (sección de Contexto
  del plan) resultó más sutil de lo previsto: no era un problema de
  solapamiento de rangos de fechas (`ExclusionConstraint`), sino de la
  llave primaria compuesta de `vinculo_abonado`. Confirma el valor de
  reproducir el error real contra PostgreSQL antes de "arreglarlo a
  ciegas" — el primer intento de corrección (cerrar y crear en el
  orden original) seguía fallando, esta vez contra
  `vinculo_abonado_un_titular_vigente`, hasta ajustar también el orden
  de las operaciones dentro de la transacción.
- Con 2c cerrado, el Incremento 2 completo queda construido: sesión y
  cuentas, expediente completo, y abonado y personas.
