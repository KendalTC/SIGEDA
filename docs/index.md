# Índice de documentación

Este directorio contiene documentación técnica heredada de **LICS v2.5.0**
(la base de código de la que parte SIGEDA, con autorización de su autor,
Alejandro Arias Rojas) más la evidencia propia de SIGEDA.

La documentación de negocio e histórica de LICS que no aplica a SIGEDA
(auditorías, roadmap, backlog de cliente, migración DBF, cierres de
etapa, modelo de datos de inventario/ventas, capturas de pantalla de
módulos de negocio, etc.) se retiró de este repositorio el 05/11/2026
al construir SIGEDA; sigue disponible en el repositorio original de
LICS en GitHub.

---

# Lectura recomendada

1. [README principal](../README.md)
2. [CLAUDE.md](../CLAUDE.md) — contexto del proyecto SIGEDA
3. [Arquitectura del sistema](architecture.md) — capas Nginx/Next.js/Django/PostgreSQL, heredadas de LICS
4. [Desarrollo](development.md)
5. [Despliegue (histórico, plan Linux/kiosco; no vigente para SIGEDA)](deployment.md)
6. [Backups y restauración (estrategia heredada de LICS; SIGEDA la adapta en el Incremento 3)](backup-restore.md)
7. [Seguridad](security.md)
8. [Sistema de diseño del frontend (de LICS; SIGEDA ajusta la paleta y la tipografía, ver `frontend/src/app/sigeda/sigeda.css`)](frontend-design-system.md)
9. [Evidencia de SIGEDA](evidencia/)

El despliegue en Windows/Electron de LICS (`infra/windows/`,
`infra/windows-demo/`, `.github/workflows/build-windows-installer.yml`)
se conserva tal cual en el repositorio, como referencia para cuando se
decida el despliegue de SIGEDA (CLAUDE.md: "sigue abierto"): no está
documentado en este índice porque todavía no aplica.
