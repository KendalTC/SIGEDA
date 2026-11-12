# Prueba de terminado — RF-10 Buscar expedientes (consulta Q1)

Ejecutada de verdad el 12/11/2026 contra el stack real (Docker Compose:
PostgreSQL 17 + Django 5.2.6 + Nginx, sin mocks), con la cuenta
`secretaria` y una base con **1 015 abonados** (el abonado de prueba
0412 más 1 014 abonados ficticios de volumen, generados con
`python manage.py seed_sigeda_volumen` — nombres y cédulas inventados,
tomo 0000, regla 3 de CLAUDE.md). Resultados reales, no inventados
(CLAUDE.md, regla 1).

Dos formas de evidencia, ambas reales:

1. **Suite automática** (`apps.abonados.tests`, repetible con
   `make test`): cubre cada criterio por separado, combinados,
   `incluir_baja`, coincidencia por el inicio de la paja, sin
   resultados, el límite de 50 filas y el enmascarado de la
   identificación. **Resultado: 87/87 pruebas pasaron** (54 de antes +
   33 nuevas: 13 de restricciones CHECK que faltaban + 20 de la
   búsqueda y su endpoint).
2. **Medición real de RNF-05/EC-04**, 20 búsquedas distintas vía
   `curl` contra la API real (no la base de pruebas aislada de
   Django), con la base ya cargada a 1 015 abonados.

## 1. CHECK de dominio que faltaban (hallazgo de hoy)

**Lo que se encontró:** 13 columnas CHECK del Modelo ER v1.1 (dominios
como `abonado.tipo_abonado`, `cuenta.perfil`, `registro_bitacora.accion`,
etc.) no tenían su restricción CHECK en los modelos de Django — la
propia Prototipos v1.1 señalaba el hueco en `registro_bitacora.accion`.

**Resultado obtenido:** agregadas las 13 restricciones que faltaban
(`abonados`, `configuration`, `documents`, `accounts`, `bitacora`,
`respaldos`), con su migración y su prueba automática por cada una
(crear con un valor fuera del dominio, esperar `IntegrityError`).
Verificado con `psql \d <tabla>` que el CHECK real quedó en PostgreSQL,
no solo en Django. **13/13 restricciones nuevas, cada una con su
prueba. Pasaron todas.**

**¿Pasó?** Sí.

## 2. Buscar por cada criterio y combinados

**Datos:** abonado 0412 (titular Ana Lucía Mora Vega, cédula
1-0000-0123, sector Bodegas) más 1 014 abonados ficticios de volumen.

**Esperado:** por número de paja (coincide por el inicio), por nombre
del titular vigente (parcial, insensible a tildes y mayúsculas), por
identificación (sin importar guiones) y por sector, solos o
combinados con un Y lógico.

**Resultado obtenido (automatizado, `BuscarAbonadosTests`):**
- Por paja exacta y por el inicio de la paja: **pasó**.
- Por nombre, con tildes y mayúsculas distintas al dato guardado
  ("ANA LUCIA" encuentra "Ana Lucía"): **pasó**.
- Por identificación, escrita sin guiones ("100000123" encuentra
  "1-0000-0123"): **pasó**.
- Por sector: **pasó**.
- Combinando paja + nombre + sector a la vez (deben cumplirse los
  tres): **pasó**.
- Sin ningún criterio: la vista responde 400 con el mensaje "Escriba
  al menos un criterio de búsqueda...": **pasó**.
- `incluir_baja=false` excluye los abonados de baja (RN-08 no los
  borra, pero sí se pueden excluir de la lista): **pasó**.
- Límite de 50 resultados mostrados aunque el total sea mayor
  (`total` y `mostrados` son distintos): **pasó**.
- Identificación parcial enmascarada en cada resultado
  (`1-••••-0123`, guía de estilo): **pasó**.

**Manual, vía `curl` contra la API real:**
```
GET /api/sigeda/abonados/buscar/?numero_paja=0412
{"total":1,"mostrados":1,"tiempo_segundos":0.009,
 "resultados":[{"numero_paja":"0412","titular_vigente":"Ana Lucía Mora Vega",
 "identificacion_parcial":"1-••••-0123","sector":"Bodegas",
 "tipo_abonado":"PERSONA_FISICA","estado":"ACTIVO"}]}
```

**¿Pasó?** Sí.

## 3. Rendimiento real (RNF-05/EC-04)

**Datos:** 20 búsquedas reales y distintas (paja exacta, prefijo de
paja que trae 1 014 filas, nombre con tildes, identificación con y sin
guiones, sector, combinadas, sin resultados), contra la API real con
1 015 abonados ya cargados. Tiempo medido con `curl -w
"%{time_total}"` (de verdad, extremo a extremo: red + Django +
PostgreSQL + Nginx), no simulado.

**Esperado (RNF-05):** 3 segundos o menos en 19 de 20 casos.

**Resultado obtenido — las 20 mediciones reales:**

| # | Consulta | Total | Mostrados | Tiempo servidor | Tiempo HTTP real |
|---|---|---|---|---|---|
| 1 | `numero_paja=0412` | 1 | 1 | 0,009 s | 0,026 s |
| 2 | `numero_paja=20` (prefijo, 1014 filas) | 1014 | 50 | 0,073 s | 0,089 s |
| 3 | `numero_paja=200500` | 1 | 1 | 0,009 s | 0,027 s |
| 4 | `nombre=Vega` | 114 | 50 | 0,082 s | 0,103 s |
| 5 | `nombre=María` | 76 | 50 | 0,082 s | 0,100 s |
| 6 | `nombre=Mora` | 131 | 50 | 0,084 s | 0,102 s |
| 7 | `nombre=Jiménez` | 158 | 50 | 0,086 s | 0,104 s |
| 8 | `nombre=ana` | 66 | 50 | 0,084 s | 0,101 s |
| 9 | `identificacion=100000123` (sin guiones) | 1 | 1 | 0,016 s | 0,033 s |
| 10 | `identificacion=1-0000-0123` (con guiones) | 1 | 1 | 0,017 s | 0,033 s |
| 11 | `identificacion=200000456` | 1 | 1 | 0,016 s | 0,033 s |
| 12 | `id_sector=1` (Bodegas) | 217 | 50 | 0,073 s | 0,090 s |
| 13 | `id_sector=2` (Pilas) | 204 | 50 | 0,073 s | 0,090 s |
| 14 | `id_sector=3` (Calle Cerro) | 212 | 50 | 0,073 s | 0,089 s |
| 15 | `numero_paja=20&nombre=Castro` | 139 | 50 | 0,090 s | 0,107 s |
| 16 | `numero_paja=0412&incluir_baja=false` | 1 | 1 | 0,010 s | 0,028 s |
| 17 | `nombre=Rodríguez&id_sector=4` | 28 | 28 | 0,059 s | 0,077 s |
| 18 | `numero_paja=999999` (sin resultados) | 0 | 0 | 0,005 s | 0,022 s |
| 19 | `nombre=Zúñiga` | 128 | 50 | 0,094 s | 0,114 s |
| 20 | `numero_paja=2005` | 100 | 50 | 0,072 s | 0,091 s |

**Resumen:** máximo 0,114 s, mínimo 0,022 s, promedio 0,073 s.
**20 de 20 casos en 3 segundos o menos** (el requisito pide 19 de 20).

**¿Pasó?** Sí, con margen amplio: la peor búsqueda real tardó 114 ms,
muy por debajo del límite de 3 000 ms.

## Qué se aprendió (confirmaciones y cambios sobre el DAS v1.1)

- **Confirmado:** el índice GIN con `pg_trgm` (ADR-06) sobre
  `persona.nombre`, junto con los B-tree normales de `numero_paja` (UQ)
  y `id_sector` (FK), alcanzan sin ningún esfuerzo extra el margen de
  RNF-05 con 1 015 filas — ni de cerca cerca del límite de 3 s. No hace
  falta ninguna optimización adicional en este volumen.
- **Hallazgo no previsto en el plan original:** el lookup encadenado
  de Django `campo__unaccent__icontains` no funciona en esta versión
  de Django (lanza `FieldError`, aunque el lookup `unaccent` sí está
  registrado) — hubo que armar la comparación como una expresión
  (`Lower(Unaccent(...))`) usada con `.alias()` en vez de encadenar el
  lookup directamente. Quedó documentado en el código
  (`controlador_busqueda.py`) para que no se repita el intento.
- **Decisión tomada hoy, no en el DAS:** la identificación se compara
  quitándole a ambos lados (la búsqueda y la columna) todo lo que no
  sea letra o dígito (`REGEXP_REPLACE`), para que buscar con o sin
  guiones dé el mismo resultado. El DAS no especificaba este detalle.
- **SUPUESTO, pendiente con la administradora:** el filtro `sector` de
  esta búsqueda usa el catálogo de sectores tal como está (Bodegas,
  Pilas, Calle Cerro, Calle Central, Trapiche); sigue sin confirmarse
  si esa lista está completa (sección 11 del documento de Prototipos).
