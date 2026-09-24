# Auditoría de seguridad del repositorio (2026-09-24)

El repositorio es **público**. Se auditó el árbol actual, el historial completo (91 commits, todas las ramas y remotos), la configuración de GitHub, los buckets, CloudFront, el CORS del API y las dependencias.

## Qué se comprobó y salió limpio

- **Sin credenciales:** 0 claves de acceso de AWS, claves privadas ni JWT, ni en el árbol ni en el historial.
- **Valores reales:** el código del evento y las contraseñas de prueba (incluida la del Ponente) no aparecen en ningún commit ni archivo. Se buscaron por su valor, sin imprimirlos.
- **Archivos sensibles:** `.tfstate`, `.env`, `.pem`, `.key` y `web/config.js` nunca se añadieron al historial. `*.tfvars` está ignorado; el único `.tfvars` rastreado (`agent_image.auto.tfvars`) solo lleva la etiqueta de la imagen.
- **Identificadores del entorno** (pool y cliente de Cognito, API, CloudFront, Knowledge Base, runtime, guardrail, memoria y gateway): 0 archivos.
- **GitHub:** escaneo de secretos y *push protection* activos, Dependabot con actualizaciones de seguridad, 0 alertas, ruleset `protect-main` en vigor.
- **Dependencias:** `pip-audit` sobre `uv.lock` (128 paquetes) sin vulnerabilidades conocidas. checkov: 207 correctos y 0 fallos.
- **Buckets:** los tres (documentos, web y estado) bloquean el acceso público.
- **Web y API:** HSTS, CSP estricta (`script-src 'self'`), `X-Frame-Options: DENY`, HTTP redirige a HTTPS; el API responde 401 sin token y su CORS solo acepta el origen propio.
- **Permisos IAM con `*`:** 4, todos justificados (token de ECR, X-Ray y `PutMetricData` con condición no admiten recurso concreto, y el `Deny` del corte de presupuesto).

## Hallazgos y qué se hizo

| # | Hallazgo | Resolución |
|---|---|---|
| 1 | Un correo personal era el valor por defecto de `alert_email` en `infra/variables.tf` (público desde el commit #12) | Sin valor por defecto; va en `infra/terraform.tfvars`, local e ignorado. **Sigue en el historial**: reescribirlo exigiría un force-push a `main`, que está protegido, y no compensa. |
| 2 | El ID de la cuenta estaba en el nombre del bucket de estado, en `infra/versions.tf` | Backend parcial: el bucket se pasa con `-backend-config=backend.hcl` (local e ignorado). El historial conserva el ID (2 commits); un ID de cuenta no es un secreto según AWS. |
| 3 | Un correo personal en `pyproject.toml` y en los metadatos de los commits | `pyproject.toml` usa la dirección `noreply` de GitHub y los commits nuevos de este repo también. Los 60 commits anteriores conservan el correo original: es inevitable en git. |
| 4 | La contraseña del Ponente quedó visible en la conversación con el asistente y en un archivo temporal | Rotada: la nueva funciona, la anterior es rechazada y el archivo antiguo se borró. La nueva se entregó por un archivo local con permisos solo para el usuario, sin imprimirla. |
| 5 | La CSP permite `https://*.execute-api.us-east-1.amazonaws.com` en `connect-src`, no el host exacto del API | **No aplicado: no es posible sin rediseñar.** El CORS del API (`api.tf`) referencia el dominio de CloudFront, y fijar el host del API en la CSP (cabeceras de CloudFront) crea un ciclo de dependencias. El riesgo residual es bajo: exfiltrar con `connect-src` exige antes inyectar script, y `script-src 'self'` lo impide (sin inline ni `eval`). Rediseño posible: servir el API bajo el mismo dominio de CloudFront, con lo que desaparecen el CORS y el comodín. |

## Qué no se cubrió

- Pruebas de penetración.
- Revisión completa del IAM de la cuenta (el usuario que despliega y sus credenciales locales, que no están en el repositorio).
- DoS: no hay WAF; el control de costo son las cuotas de la API y el corte de presupuesto.
- Inyección de prompt: solo hay mitigaciones de diseño y la prueba de humo.

## Aprendizajes

- **Un control positivo es imprescindible.** Dos búsquedas devolvieron 0 en silencio (un `git grep` con 91 revisiones y otro con 132 rutas como argumentos). Solo el control con una cadena que sí existía las delató. Todo escaneo de secretos debe llevar uno.
- **Un secreto borrado sigue en el historial.** Lo que entra a un repositorio público se considera publicado.
- **Un valor por defecto en Terraform es código.** Los datos personales o de cuenta van en `*.tfvars` ignorados, con un `.example`.
