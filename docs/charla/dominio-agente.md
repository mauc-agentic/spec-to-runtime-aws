# Dominio del agente: "Pregúntale al repo"

Decidido el 2026-09-23, a 3 días de la charla.

## Decisión

Un agente que responde con RAG sobre los documentos de este repo (visión, requisitos, specs y `docs/charla/`) y adapta la respuesta al perfil de quien pregunta: Estudiante, Profesional o General. El rol Presentador ve además material interno.

- **Por qué este dominio:** no hay que inventar datos de negocio, el agente se construye con las mismas specs que consulta (buen hilo para una charla spec-driven) y el público mixto (estudiantes, profesionales, curiosos) tiene sentido como perfiles.
- **Alternativas descartadas:** asistente de operaciones AWS (menos visual para el público), triage de incidentes y soporte de pedidos (obligaba a inventar y poblar datos).

## Decisiones técnicas

- **Almacén de vectores: S3 Vectors** en lugar de OpenSearch Serverless (costo mínimo mensual alto). Embeddings con Titan Text Embeddings v2 a 256 dimensiones.
- **Identidad:** Cognito emite el JWT con los claims `perfil` y `rol`; AgentCore Gateway valida el token. Complementa con AgentCore Workload Identity para credenciales de salida.
- **Memoria:** AgentCore Memory de corto plazo, por sesión. La memoria de largo plazo queda fuera de alcance.
- **Guardrails:** Bedrock Guardrails filtran entrada y salida (temas fuera de alcance, ataques de prompt, datos personales).
- **Terraform:** el provider `aws` 6.66 ya trae `aws_bedrockagent_knowledge_base` con `S3_VECTORS`, `aws_s3vectors_*`, `aws_bedrockagentcore_gateway`, `_gateway_target`, `_memory` y `_workload_identity` (verificado con el MCP `terraform`).

## Alcance y prioridad

UCs previstos: autenticarse con perfil y rol, sincronizar documentos, consultar con RAG adaptado al perfil, conversar con memoria de sesión, usar herramientas por Gateway y, opcional, buzón de preguntas en vivo con SQS. Con 3 días, solo se muestra como terminado lo que llegue a `Tested`; el buzón en vivo es lo primero que se recorta.

## Aprendizajes / dolores

- Ampliar el dominio obligó a ampliar la visión: Cognito, S3, S3 Vectors, Bedrock KB y Guardrails no estaban en la lista de servicios (C-003) y se agregaron en el mismo cambio.
- Los umbrales de latencia y costo (NFR-011, NFR-012) quedan `Needs review` hasta medir con la infraestructura real.
