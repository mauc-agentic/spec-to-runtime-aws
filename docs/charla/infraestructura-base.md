# Infraestructura base (Terraform)

Primera capa de `infra/`, la que no depende del código del agente. Región `us-east-1`, state en S3. Estado: **aplicada el 2026-09-24** (25 recursos + el presupuesto). Prueba real: un registro con código falso se rechaza con `REGISTRATION_CLOSED` y no crea cuentas; la Knowledge Base queda `ACTIVE`. Pendiente: activar la etiqueta de costo (ver abajo).

## Qué crea

| Archivo | Recursos | Requisito |
|---|---|---|
| `budgets.tf` | Presupuesto de 50 USD filtrado por la etiqueta `project`, con alertas al 50 %, 80 % y 100 % y previsión al 100 %; activa la etiqueta de costo | NFR-012, NFR-014 |
| `dynamodb.tf` | Tablas `requests` (historial, texto parcial, análisis del Ponente) y `usage` (cuotas), en modo on-demand con TTL | FR-022, NFR-013 |
| `cognito.tf` | User pool con registro por código de evento (Lambda pre-sign-up), cliente web, grupo `Ponente` y secreto con el código | FR-013, UC-001 |
| `knowledge_base.tf` | Bucket de documentos, S3 Vectors (256 dimensiones), Knowledge Base con Titan Embeddings v2 y fuente de datos | FR-014, FR-015 |
| `guardrails.tf` | Bedrock Guardrail (ataque de prompt, insultos, odio, tema fuera de alcance, PII) y su versión | FR-019, NFR-010 |

Costo fijo esperado: unos 0,40 USD al mes (el secreto). Todo lo demás se paga por uso.

## Decisiones

- **Presupuesto por etiqueta:** la cuenta aloja otros proyectos, así que un presupuesto de cuenta contaría gastos ajenos. La etiqueta de costo tarda hasta 24 h en activarse, por lo que el filtro no ve gasto de las primeras horas.
- **Sin acción automática de cierre todavía:** la acción de presupuesto que quita el permiso de invocar modelos (NFR-014, al 90 %) necesita el rol del agente, que aún no existe. Queda para la capa del runtime. Hasta entonces, las alertas son solo por correo y **no bloquean el gasto**.
- **Registro cerrado por defecto:** el secreto nace con `registration_open = false`. El organizador lo abre y lo cierra con el CLI (`ignore_changes` evita que Terraform lo revierta).
- **Ponente:** se crea a mano con el CLI y se agrega al grupo `Ponente`; no hay registro que otorgue ese rol.
- **Excepciones de `checkov` (25):** cada una lleva su motivo en el código. Casi todas son claves KMS propias, VPC, replicación, logging, PITR y firma de código: controles de nivel empresarial que añaden costo fijo, contrario a NFR-012.

## Aprendizajes / dolores

- `python3.14` como runtime de Lambda ya lo acepta el provider 6.66.
- Provider 6.66: `key_schema` solo se admite dentro de los índices secundarios; a nivel de tabla se sigue usando `hash_key` y `range_key`.
- Python 3.14 en macOS ignora el `.pth` del paquete editable si tiene la bandera `hidden`. Se resolvió con `pythonpath = ["src"]` en la configuración de pytest, que además funciona igual en el CI.
- Cognito no aplica exactamente "5 intentos y 15 minutos" (UC-001 BR-005): tiene su propio bloqueo progresivo. Se acepta la diferencia o se ajusta la spec.
- Cognito envía como máximo 50 correos al día por defecto, igual que el aforo: por eso el registro no verifica el correo.
- **El CI encontró lo que mi máquina ocultaba:** la Lambda creaba los clientes de boto3 al importar el módulo y fallaba con `NoRegionError` en el runner, que no tiene región configurada; en local pasaba porque hay una región por defecto. Se corrigió creando los clientes de forma perezosa (`functools.cache`). Para reproducirlo en local: `env -u AWS_DEFAULT_REGION AWS_CONFIG_FILE=/dev/null uv run pytest`.
- **La etiqueta de costo no se puede activar el mismo día:** `aws_ce_cost_allocation_tag` falló con "Tag keys not found: project" porque la etiqueta solo aparece en Facturación cuando ya hay recursos etiquetados (hasta 24 h). El primer `apply` dejó 24 recursos y falló en los dos del presupuesto. Solución: `activate_cost_allocation_tag` (por defecto `false`) y el presupuesto sin dependencia de la etiqueta. **Hasta activarla, el presupuesto existe pero no ve gasto:** pasado un día, aplicar con `-var activate_cost_allocation_tag=true`.
- Un `apply` fallido a medias deja el state consistente: lo creado queda registrado y el siguiente `plan` solo propone lo que faltó.

## Operación durante el evento

```bash
# Ver el código del evento
aws secretsmanager get-secret-value --secret-id spec-to-runtime/event --query SecretString --output text

# Abrir (true) o cerrar (false) el registro, conservando el código
aws secretsmanager put-secret-value --secret-id spec-to-runtime/event \
  --secret-string '{"event_code":"<codigo>","registration_open":true}'
```
