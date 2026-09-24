# AgentCore Gateway: herramientas del Ponente (FR-012)

Estado: **desplegado y verificado el 2026-09-24** (prueba de humo 11/11, con la Lambda `spec-to-runtime-tools` invocada por el Gateway). Terraform en `infra/gateway.tf`. FR-012 sigue **Parcial**: falta el target de servidor MCP de AWS (ver el final).

## Qué cambió

Antes, `buscar_documentos`, `top_preguntas` y `actividad_participantes` eran funciones Python dentro del agente, con permiso directo a DynamoDB. Ahora:

```
Agente (rol Ponente) ──MCP + SigV4──▶ AgentCore Gateway ──▶ Lambda tools ──▶ DynamoDB / Nova / Guardrail / KB
```

- **`aws_bedrockagentcore_gateway`** con autorizador `AWS_IAM`: solo el rol del Runtime tiene `bedrock-agentcore:InvokeGateway` sobre él.
- **Target `ponente`** (Lambda). Gateway antepone el nombre del target: las herramientas se llaman `ponente___top_preguntas`, etc. Los esquemas de entrada van en Terraform (`inline_payload`).
- **Lambda `tools`** (`src/spec_to_runtime/tools/handler.py`): lee el nombre de la herramienta de `context.client_context.custom["bedrockAgentCoreToolName"]`, ejecuta `agent/toolkit.py` y responde `{"report": "..."}`.
- El agente conserva funciones `@tool` finas que reenvían la llamada (`agent/factory.py`). Hace falta porque el informe debe mostrarse **tal cual** y no reescrito por el modelo: la herramienta guarda el informe en el estado y corta el bucle (`stop_event_loop`), algo que una herramienta MCP genérica no hace.
- El rol del agente **perdió** `dynamodb:Query`; el de la Lambda lo tiene, junto con `InvokeModel`, `ApplyGuardrail` y `Retrieve`. El rol de la Lambda entra en el corte de presupuesto (NFR-014).

## Decisiones

| Decisión | Elegido | Alternativa |
|---|---|---|
| Autorizador del Gateway | `AWS_IAM` (SigV4 con el rol del Runtime) | `CUSTOM_JWT` con Cognito y una regla por grupo. Exigiría llevar el token del participante hasta el agente; hoy el Runtime se invoca por IAM y el rol Ponente lo valida la API |
| Quién restringe al Ponente | La API (Cognito) y el agente, que solo entrega las herramientas a ese rol (UC-007 BR-001) | Políticas Cedar en el Gateway (defensa en profundidad; queda como mejora) |
| Cliente MCP | `MCPClient` de Strands con un `httpx.Auth` de ~20 líneas que firma con botocore | `mcp-proxy-for-aws`: arrastra decenas de dependencias al contenedor |
| Coste | Sin costo fijo; se paga por llamada | — |

## Dolores y aprendizajes

- **El zip de las Lambdas excluía todo `agent/`.** La Lambda `tools` necesita `toolkit`, `analytics`, `retrieval` y `config` (que no importan Strands), así que `infra/api.tf` ahora excluye por nombre solo los módulos que sí lo importan. Si se añade otro módulo del agente con Strands, hay que excluirlo ahí o la Lambda fallará al importar.
- **Refactor previo:** `mask_with_guardrail` y el clasificador salieron de `factory.py` a `toolkit.py` precisamente por lo anterior.
- **Orden de despliegue desde cero:** `terraform apply` con `agent_image_tag=""` falla, porque `api.tf` necesita el ARN del Runtime. Hay que crear primero el repositorio (`-target=aws_ecr_repository.agent`), subir la imagen con `scripts/deploy_agent.sh` y después aplicar todo.
- **Cada cambio en `src/` exige commit antes de desplegar** la imagen (la etiqueta es el hash de git) y un `terraform apply` posterior para que el Runtime la use.
- **Latencia:** la primera pregunta del Ponente tras el despliegue tardó 16 s (contenedor y Lambda en frío; la Lambda tardó 2,7 s con 0,3 s de arranque). Calentar antes de la charla, como ya pide NFR-011.

## Pendiente

- **Target de servidor MCP de AWS** (lo menciona FR-012 y `docs/vision.md`): no se añadió. Sacaría datos de la consulta a un servicio externo y hay que decidir qué herramienta aportaría a la demo. O se añade, o se enmienda el requisito para dejar solo Lambda.
- Políticas Cedar por herramienta (defensa en profundidad).
- Tests contra un Gateway real: los tests unitarios cubren la firma SigV4, el despacho por nombre y el informe literal; la integración se comprobó solo con la prueba de humo.
