# Prueba de terminado — Incremento 3a: respaldo y restauración (PAN-08, D-05, RF-16)

Ejecutada de verdad el 13/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Next.js + Nginx, sin mocks salvo donde
se indica explícitamente). Resultados reales, no inventados (CLAUDE.md,
regla 1).

Trabajo autónomo del 13/11/2026 (Kendal fuera); ver
`/home/tcken/.claude/plans/starry-baking-naur.md` y memoria
`sigeda-trabajo-autonomo`. Es el incremento con operaciones más
delicadas del día: `pg_dump`/`pg_restore`/`dropdb`/`createdb` reales.

## 1. Respaldo completo cifrado (RF-16, ADR-03)

Probado de verdad contra el stack de desarrollo, sin riesgo (es de solo
lectura): dos respaldos manuales reales desde la interfaz
(`docs/evidencia/pan08_hecho.png`), cada uno con su paquete cifrado de
verdad en `SIGEDA_BACKUP_DISCO_EXTERNO_DIR`, SHA-256 verificado contra
el disco, y `Respaldo.estado=COMPLETO` solo porque al menos una copia
(disco externo) quedó `VERIFICADA` (OneDrive queda `PENDIENTE`, S-10
sin confirmar — correcto, no falla el respaldo completo).

**Cifrado real confirmado (RNF-10)**: los primeros bytes del paquete
en disco no son un `tar` válido ni texto plano — el archivo es
ilegible fuera de SIGEDA, igual que ya pasa con cada documento
individual.

**¿Pasó?** Sí.

## 2. D-05 Restaurar un respaldo (RF-16, RF-13 por extensión)

Los 4 campos en el orden exacto de la ficha, recuadro de advertencia
literal, botón deshabilitado hasta completar clave + contraseña de
Administración + la palabra exacta "RESTAURAR"
(`docs/evidencia/d05_abierto.png`, `d05_listo_sin_enviar.png`):
confirmado por navegador real que el botón sigue deshabilitado con
"restaurar" en minúscula y se habilita solo con "RESTAURAR" exacto.
**El envío real del formulario nunca se probó contra el entorno de
desarrollo** (ver sección 3) — el diálogo se cerró con "Cancelar"
después de verificar la validación.

**¿Pasó?** Sí (validación de la interfaz).

## 3. Restauración real, preservando la bitácora — contra una base descartable

La prueba más delicada de hoy **nunca tocó la base de desarrollo**
(`sigeda`, con todo el trabajo acumulado de 2a/2b/2c). Corrió contra
una base de Postgres creada y destruida dentro de la misma prueba
automática (`sigeda_prueba_restauracion_<aleatorio>`), verificado por
mí mismo leyendo el código de la prueba
(`RestaurarRespaldoTests.test_restaura_preservando_la_bitacora_y_agrega_el_evento_restauracion`
en `backend/src/apps/respaldos/tests.py`) antes de aceptarla:

1. Se crea la base descartable con un esquema mínimo (`cuenta` + las 3
   tablas de bitácora).
2. Una fila de bitácora que ya existe ANTES del respaldo.
3. Se respalda esa base descartable.
4. Una fila de bitácora agregada DESPUÉS del respaldo y ANTES de
   restaurar (el caso central: ¿sobrevive algo que pasó después de la
   foto del respaldo?).
5. Se restaura.
6. **Las dos filas siguen ahí** — la de antes (porque venía en el
   paquete) y la de después (porque se guardó aparte y se reinsertó
   con `ON CONFLICT DO NOTHING`).
7. Aparece, encima, el nuevo evento `RESTAURACION` con su
   `registro_restauracion` (`nombre_paquete` correcto).
8. Una fila nueva se puede insertar después sin chocar con la
   secuencia de `id_registro_bitacora` (quedó resincronizada tras
   reinsertar la bitácora guardada — detalle fino que el propio
   trabajo de hoy encontró y corrigió).
9. La base descartable se borra al final con `DROP DATABASE ... WITH (FORCE)`
   dentro de un `try/finally`, pase lo que pase.

Confirmado independientemente por mí (no solo por el reporte): conté
los abonados y cuentas reales de `sigeda` antes y después de correr
toda la suite dos veces — sin cambios.

**¿Pasó?** Sí.

## 4. Restricción de privilegios sobre la bitácora (ADR-05) — limitación real, no maquillada

**Lo que se construyó**: una migración (`apps/bitacora/migrations/0003`)
que le revoca `UPDATE`/`DELETE` al usuario de base de datos de la
aplicación sobre `registro_bitacora`, `registro_modificacion` y
`registro_restauracion`. Confirmado con `psql \dp registro_bitacora`
(yo mismo, de forma independiente) que el ACL real de PostgreSQL ya no
incluye esos dos permisos para el usuario `sigeda`.

**Limitación real, encontrada hoy y NO resuelta** (siguiendo la regla
1 de CLAUDE.md: no maquillar un resultado): el usuario `sigeda` de
este entorno de desarrollo **es superusuario del clúster de Postgres**
(confirmado con `SELECT rolsuper FROM pg_roles WHERE rolname='sigeda'`
→ `t`). Un superusuario de PostgreSQL **ignora cualquier ACL**,
incluida la de sus propias tablas — por diseño de PostgreSQL, no es un
error de la migración. Esto significa que, **en este entorno**, la
restricción queda correcta a nivel de ACL pero sin efecto real todavía:
un `UPDATE`/`DELETE` directo sobre `registro_bitacora` con el usuario
actual **sí funcionaría**, pese a la migración.

La prueba automática (`RevocarUpdateDeleteBitacoraTests`) separa
honestamente las dos cosas: confirma el ACL (siempre pasa) y, para el
comportamiento real de bloqueo, detecta que el rol es superusuario y
hace `skipTest(...)` con el motivo completo en vez de fingir que pasó.

**Pendiente explícito para el despliegue real** (no para hoy): separar
un rol de aplicación sin privilegio de superusuario del rol usado para
migrar/arrancar el contenedor. Es un cambio de infraestructura
compartida (afecta a todo el stack), fuera del alcance seguro de
"Paso 1 backend" de un solo incremento.

**¿Pasó?** Parcialmente — correcto en diseño y en el ACL, sin
aplicación real todavía en este entorno. Documentado, no maquillado.

## 5. Retención (decisión 5 del plan) — parcialmente implementada, con la parte faltante anotada

Implementado: 7 copias más recientes por destino configurado,
contando filas reales de `CopiaRespaldo`/`Respaldo` (no nombres de
archivo). **No implementado, documentado como deuda técnica explícita**
(CLAUDE.md regla 2, no inventar columnas sin avisar): la distinción
"diario" vs. "semanal" (el modelo `Respaldo.tipo` solo tiene
AUTOMATICO/MANUAL) y "2 más recientes en la laptop" (no hay un
`destino` para "la laptop" en el dominio real de `copia_respaldo`, y
el paquete sin cifrar se arma en un directorio temporal que se borra
solo).

## 6. Pruebas automáticas

- `make test`: **190/190, 1 omitida** (la limitación de la sección 4).
- `make test-sigeda`: **176/176, 1 omitida**.

## 7. Accesibilidad (axe-core 4.10.2, CDN)

0 infracciones reportadas por el agente de frontend en 9
verificaciones: PAN-08 en sus 4 estados (hecho/pendiente/fallido/
vacío, con la respuesta de red simulada porque el backend corría en
paralelo), D-05 abierto, y las 3 sub-pantallas (cuarentena, configurar
OneDrive, registrar prueba de restauración).

## Qué se aprendió

- **El mecanismo de preservar la bitácora resultó más simple y más
  robusto de lo que el plan original imaginaba**: no hace falta
  excluir tablas de `pg_restore` (que arriesgaba romper la FK de
  `cuenta`) — guardar aparte, restaurar todo normal, reinsertar con
  `ON CONFLICT DO NOTHING` es más seguro y usa el mismo mecanismo ya
  probado de `scripts/restore.sh`.
- **pg_dump 17 cambió su formato de salida** (metacomandos
  `\restrict`/`\unrestrict`, `search_path` vacío) de una forma que no
  estaba documentada en ningún lado del proyecto — encontrado y
  corregido hoy.
- **El ACL de Postgres por sí solo no basta mientras el usuario de la
  aplicación sea superusuario** — hallazgo real de infraestructura,
  con la corrección completa (separar roles) marcada para el
  despliegue real, no para hoy.
- `backend/Dockerfile` necesitaba `postgresql-client` — no estaba.
