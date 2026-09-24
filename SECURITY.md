# Política de seguridad

Este repositorio es material de una charla y contiene código de demostración.

## Reportar una vulnerabilidad

No abras un issue público. Usa el reporte privado de GitHub:
**Security → Report a vulnerability** en este repositorio.

Incluye qué encontraste, cómo reproducirlo y el impacto. Se responde en la medida de lo posible; no hay SLA.

## Secretos

Nunca se versionan credenciales, `*.tfvars`, `*.tfstate` ni `.env` (ver `.gitignore`). El secret scanning y su push protection están activos. Si ves un secreto expuesto, repórtalo por el mismo canal.
