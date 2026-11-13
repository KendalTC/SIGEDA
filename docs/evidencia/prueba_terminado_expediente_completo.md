# Prueba de terminado — Incremento 2b: expediente completo (PAN-04, D-01/02/03/07, PAN-13)

Ejecutada de verdad el 13/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Next.js + Nginx, sin mocks), con la
cuenta `secretaria` y el abonado de prueba 0412 (titular ficticio Ana
Lucía Mora Vega, cotitular Esteban Mora Vega, tomo 0000). Resultados
reales, no inventados (CLAUDE.md, regla 1).

Trabajo autónomo del 13/11/2026 (Kendal fuera, con permiso de planear y
decidir por su cuenta); ver `/home/tcken/.claude/plans/starry-baking-naur.md`
para el detalle completo del plan aprobado.

## 1. Completitud (Q3), servicio nuevo reutilizable

**Regla implementada**: tipos de documento sueltos y grupos de
alternativas, por `obligatoriedad` del tipo de abonado, exigencia a
cotitulares, solo documentos VIGENTE del titular/cotitulares vigentes
(nunca apoderada ni titulares anteriores ni anulados).

**Resultado real visto en pantalla** (`docs/evidencia/pan04_inicial.png`):
con solo 2 documentos vigentes de 6 tipos obligatorios, el abonado
0412 muestra *"Incompleto · faltan 4"* con la lista exacta:
*"Formulario de solicitud (titular) · Copia de cédula del cotitular
Esteban Mora Vega · Certificación de registro de propiedad (titular)
· Contrato de servicio (titular)"*. Al anular un documento vigente más
(`docs/evidencia/d01_anular_documento.png` → `pan04_de_baja.png`), el
contador sube a *"faltan 5"* en tiempo real — confirma que el cálculo
es real, no un valor fijo.

**¿Pasó?** Sí. 7 pruebas unitarias (`CompletitudAbonadoTests`) cubren
tipos sueltos, grupos con una alternativa satisfecha, cotitular
exigido, documentos anulados/de apoderada/de titular anterior que no
cuentan.

## 2. Filtros RF-11 en PAN-04

Tipo, nombre identificador, fecha desde/hasta y "Mostrar anulados",
todos **en vivo** (sin botón aparte, mismo patrón ya usado hoy con el
sector de PAN-03): verificado con filtro por tipo real
(`docs/evidencia/pan04_filtro_tipo.png`, redujo de 2 a 1 fila al
elegir "Copia de cédula"). El orden RN-05 (prioridad del tipo, luego
nombre, luego id) no cambia con los filtros — solo reduce filas.

**¿Pasó?** Sí.

## 3. D-01 Anular documento (RF-19)

Motivo obligatorio, documento real anulado vía la interfaz
(`docs/evidencia/d01_anular_documento.png`), confirmado con `psql`:

```
accion: ANULACION · elemento_afectado: documento.id_documento=3
registro_modificacion: documento.estado  VIGENTE → ANULADO
```

El documento anulado deja de contar para la completitud y de verse
por defecto; con "Mostrar anulados" reaparece en gris con motivo y
fecha (`docs/evidencia/pan04_anulados.png`). No hay forma de
deshacerlo desde la interfaz (confirmado por el propio prototipo).

**¿Pasó?** Sí.

## 4. D-02 Editar datos del documento (RF-22)

Tipo y nombre identificador editables; archivo, fecha del documento y
versiones anteriores intactos. Confirmado con `psql`:

```
accion: MODIFICACION · elemento_afectado: documento.id_documento=3
registro_modificacion: documento.nombre_identificador  (vacío) → "Evidencia 2b"
```

**¿Pasó?** Sí.

## 5. D-03 Baja y reactivación de abonado (RF-17)

Fecha de la baja prellenada con hoy (13/11/2026) y editable
(`docs/evidencia/d03_baja_reactivacion.png`). Tras confirmar: estado
`De baja`, documentos conservados y consultables, botón cambia a
"Reactivar" (`docs/evidencia/pan04_de_baja.png`). Reactivado
después para dejar el abonado de prueba en su estado normal.
Confirmado con `psql`:

```
accion: BAJA · elemento_afectado: abonado.id_abonado=1
accion: REACTIVACION · elemento_afectado: abonado.id_abonado=1
```

(Sin filas en `registro_modificacion`: el Modelo ER limita esa tabla a
MODIFICACION y ANULACION — decisión documentada del backend.)

**¿Pasó?** Sí.

## 6. D-07 Salir sin guardar (en PAN-05)

No existía todavía pese a estar en CLAUDE.md. Se agregó al botón
"Cancelar": si hay archivos elegidos o un documento de nueva versión
ya seleccionado, muestra el diálogo con el conteo real de archivos
antes de salir. Singular/plural correcto ("1 archivo" / "N archivos",
mismo cuidado que el bug ya corregido en el Incremento 1).

**¿Pasó?** Sí (verificado por el agente de frontend contra la app
real; no repetido en esta verificación por no requerir datos nuevos).

## 7. PAN-13: quién cargó cada versión

`version_documento` no tiene columna de usuario: se deriva emparejando
por posición con los eventos CREACION de `registro_bitacora` del mismo
documento (invariante: una fila de bitácora por versión, en el mismo
orden, dentro de la misma transacción). Columna "Por" agregada a la
tabla, más botones "Volver al expediente" y "Cargar nueva versión".

**¿Pasó?** Sí, 2 pruebas (`VersionesDocumentoCargadaPorTests`) con
2 versiones de 2 cuentas distintas.

## 8. Pruebas automáticas

- `make test`: **131/131**.
- `make test-sigeda`: **117/117**.

## 9. Accesibilidad (axe-core 4.10.2, CDN)

0 infracciones reportadas por el agente de frontend en 8
pantallas/estados (PAN-04 en varios estados, D-01/D-02/D-03, D-07,
PAN-13) — mismo patrón y reglas que los incrementos anteriores.

## Qué se aprendió

- **Decisión de alcance confirmada como correcta:** adelantar el
  cálculo real de Q3 (completitud) desde hoy, en vez de esperar al
  Incremento 4, fue necesario porque la propia ficha de PAN-04 ya lo
  muestra — y además deja ese trabajo listo para cuando se construya
  PAN-07.
- **Hallazgo real durante la verificación de hoy:** `fecha-input.tsx`
  no avisaba al padre cuando el campo se vaciaba, dejando un filtro de
  fecha fantasma activo en PAN-04. Lo corrigió el agente de frontend
  dentro del mismo incremento.
- **SUPUESTO que sigue abierto:** el texto exacto de "Reactivar" en
  D-03 y del "faltante" cuando el tipo faltante es un grupo de
  alternativas (no un tipo suelto) no tienen captura real en el
  Prototipos v1.1 — quedaron con un texto razonable, marcados en el
  código.
