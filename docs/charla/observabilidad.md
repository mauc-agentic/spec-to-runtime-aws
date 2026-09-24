# Observabilidad de punta a punta

Trazas y métricas de punta a punta. Terraform en `infra/observability.tf`. Estado: **desplegado y verificado con tráfico real y en la consola de CloudWatch el 2026-09-24**. El panel y las alarmas se construyeron y funcionaron, pero por decisión del autor quedan **fuera del alcance del proyecto**: ver [Opcional](#opcional-panel-y-alarmas-fuera-del-alcance).

## Qué se ve y dónde

| Qué | Dónde |
|---|---|
| El agente, sus sesiones, tokens y costo | CloudWatch → Observabilidad de GenAI → Bedrock AgentCore (agente `spec_to_runtime_agent`) |
| Una conversación completa, con todas sus trazas | Botón **"Ver sesión en CloudWatch"** bajo cada respuesta del Ponente en la web (abre `#gen-ai-observability/agent-core/session/<id de sesión>`) |
| Una pregunta de punta a punta con el tiempo de cada tramo | La traza dentro de la sesión, o `uv run python scripts/show_trace.py` |
| Métricas de negocio (resultado, latencias, tokens, cuotas) | CloudWatch → Métricas → `SpecToRuntime` |

El enlace usa el id de sesión (`sess-…`), el mismo que el agente etiqueta como `session.id`: la página de la sesión agrupa todas las preguntas de esa conversación. Solo lo ve el Ponente; el identificador se valida con un formato estricto antes de armar el enlace.

## Cómo viaja la traza

```
navegador → API Gateway → Lambda api ──SQS──▶ Lambda orquestadora ──▶ AgentCore Runtime
              (sin trazas*)   segmento X-Ray    enlace de trazas        traceparent + baggage
                                                                          └ agente Strands
                                                                             ├ rag.retrieve → Knowledge Base
                                                                             ├ Memory (ListEvents / CreateEvent)
                                                                             └ chat nova-2-lite (tokens y costo)
```

- **Lambdas:** trazado activo (X-Ray) en las cuatro, con la regla de muestreo `spec-to-runtime-all` al 100 %: se traza **cada** pregunta.
- **Agente:** el distro de OpenTelemetry de AWS (`aws-opentelemetry-distro`) instrumenta el contenedor con `opentelemetry-instrument`, sin tocar la lógica. Strands emite solo los spans de agente, modelo y herramientas.
- **Spans propios:** `rag.retrieve` (fragmentos recuperados y mejor puntuación) y atributos `app.*` (`request_id`, perfil, rol, resultado, tokens, citas) para filtrar y correlacionar con DynamoDB y los logs.
- **Sesiones:** `baggage: session.id=<conversación>` agrupa las trazas por conversación en la consola de AgentCore.
- **Transaction Search** guarda los spans en CloudWatch Logs (`aws/spans`, 30 días) y la indexación está al 100 % para poder buscar cualquier pregunta.

### Las dos trazas de una pregunta (SQS enlaza, no continúa)

Con SQS, Lambda **no continúa** la traza de quien envía el mensaje: crea una nueva y la **enlaza**, porque un lote puede mezclar mensajes de muchas trazas. Por eso cada pregunta son dos trazas: la de la Lambda `api` y la del orquestador con el agente. La consola muestra ambas juntas ("Esta traza forma parte de un conjunto de trazas vinculadas") y `show_trace.py` sigue el enlace. La traza principal (`trace_id` en DynamoDB) es la del orquestador y el agente; `api_trace_id` guarda la de la API.

El mensaje de SQS lleva la cabecera de traza en el atributo `AWSTraceHeader`, y el orquestador pasa a `invoke_agent_runtime` los argumentos `traceId`, `traceParent` y `baggage`: así los spans del agente cuelgan de la Lambda orquestadora. `common/tracing.py` traduce la cabecera de X-Ray a la W3C (`Root=1-5759e988-bd86…;Parent=…` → `00-5759e988bd86…-…-01`), con tests.

## Lo que enseña una traza real

Una pregunta técnica de 7,1 s en total:

| Tramo | Duración |
|---|---|
| Modelo `nova-2-lite` (4.448 tokens de entrada, 532 de salida) | 3,4 s |
| Búsqueda en la Knowledge Base (`rag.retrieve`, 5 fragmentos, mejor 0,79) | 0,37 s |
| Memoria de AgentCore (ListEvents y varios CreateEvent, uno tras otro) | 36 a 129 ms cada llamada |
| **Antes de que el agente empiece** (arranque de la Lambda, de la sesión del Runtime y escrituras a DynamoDB) | **2,4 s** |

La segunda pregunta de esa prueba (fuera de tema, sin llamar al modelo) tardó 2 s en total. Los 2,4 s previos al agente son el siguiente candidato a optimizar; en caliente bajan mucho.

## Métricas propias (EMF)

Las Lambdas escriben líneas JSON en formato de métricas embebidas: CloudWatch las convierte en métricas del namespace `SpecToRuntime` sin llamar a ninguna API.

| Métrica | Dimensión | Qué mide |
|---|---|---|
| `Requests` | `Outcome` (Completed, Blocked, Failed) | Preguntas por resultado |
| `TotalLatencyMs`, `FirstTextMs` | `Outcome` | Tiempo total y hasta el primer texto, medidos en el orquestador |
| `QueueWaitMs` | `Outcome` | Cuánto esperó la pregunta en la cola |
| `InputTokens`, `OutputTokens` | `Outcome` | Tokens por pregunta |
| `Submitted` | `Role` | Preguntas aceptadas |
| `Rejections` | `Reason` (daily, project) | Rechazos por cuota |

Cada línea trae además `request_id`, `profile`, `role`, `error_code` y `trace_id`: se pueden buscar en Logs Insights (el panel tiene dos tablas: las preguntas fallidas y las diez más lentas).

## Opcional: panel y alarmas (fuera del alcance)

Se construyeron, se probaron con tráfico real y funcionaron a la perfección, pero el autor decidió que **no forman parte de este proyecto**, así que se retiraron de Terraform (0 paneles, 0 alarmas y 0 temas SNS desplegados). El código completo se conserva como referencia en [`docs/charla/referencia/monitoring.tf.example`](referencia/monitoring.tf.example) (fuera de `infra/`, así que ni se aplica ni lo revisa el CI). Para recuperarlo basta con copiarlo a `infra/monitoring.tf`.

- **Panel `spec-to-runtime`:** tarjetas de preguntas por resultado, rechazos por cuota y tokens; latencia total, hasta el primer texto y espera en cola (con la línea del objetivo de NFR-011); API, cola, Lambdas, AgentCore Runtime, modelo, guardrails y memoria; y dos tablas de registros (fallidas y las diez más lentas, con su `request_id`).
- **6 alarmas por correo:** `orchestrator-errors`, `dead-letter-queue`, `api-5xx`, `runtime-system-errors`, `failed-questions` (3 o más en 5 min) y `slow-answers` (p90 por encima de 15 s en 2 de 3 periodos), sin datos = sin problema. La suscripción de correo exige confirmar el enlace que envía AWS.
- **Costo estimado (sin verificar):** 0,10 USD al mes por alarma y el panel gratis dentro de los 3 primeros de la cuenta.
- **Lo que sigue activo:** las métricas de negocio `SpecToRuntime` (líneas EMF de las Lambdas) siguen emitiéndose porque están en el código; cuestan unos 0,30 USD al mes por métrica personalizada, prorrateados. Si tampoco se quieren, se elimina la llamada a `metrics.emit` del orquestador y de la API.

## Privacidad

Los spans de Strands incluyen el contenido de los mensajes: **las preguntas y respuestas quedan en `aws/spans` 30 días y las ve quien administre la cuenta**. Es coherente con el resto (los datos ya están en DynamoDB y en AgentCore Memory), pero conviene decirlo a los participantes. El enlace "Ver sesión en CloudWatch" solo aparece en la web del Ponente; el `trace_id` que guarda la API solo se entrega al Ponente.

## Limitaciones

- API Gateway HTTP no admite X-Ray: la traza nace en la Lambda `api`. No se ve el tramo del navegador ni el de API Gateway (solo su latencia como métrica).
- Las Lambdas no crean subsegmentos para DynamoDB, SQS ni la llamada al Runtime (haría falta el SDK de X-Ray o la capa de ADOT): se ven como tiempo dentro del segmento de la función, y el trabajo del agente aparece con sus propios spans.
- Las métricas de Bedrock y Guardrails llegan con unos minutos de retraso.
- La entrega de logs de la Memory está creada pero aún sin eventos.

## Aprendizajes / dolores

- **La traza se cortaba en la cola** y el primer diseño (un solo id de punta a punta) no era posible: SQS enlaza trazas, no las continúa. Lo descubrí comparando el `trace_id` que guardó la API con el que vio el orquestador (eran distintos) y leyendo el campo `links` de los spans. Regla: antes de asumir cómo se propaga el contexto entre servicios, comprobar con datos reales.
- **Los spans de Lambda llegan dos veces:** uno en curso (sin duración) y otro completo. Al reconstruir una traza hay que quedarse con el completo.
- **`aws/spans` guarda cada span como JSON en `@message`:** los campos que Logs Insights aplana no incluyen todo (por ejemplo, `durationNano` desaparecía). Leer siempre el `@message`.
- **Transaction Search ya estaba a medias:** alguien lo activó desde la consola justo antes (destino `PENDING`, `aws/spans` vacío). La política de acceso de X-Ray la crea y protege el propio servicio ("DO-NOT-EDIT"): no se gestiona con Terraform. Con las Lambdas trazando y el destino confirmado pasó a `ACTIVE`.
- **No hicieron falta variables de OpenTelemetry en el Runtime:** con `aws-opentelemetry-distro` y `opentelemetry-instrument` los spans llegaron solos. El distro 0.20.0 instala bien con Python 3.14.
- **(Del panel opcional)** Una tarjeta de números salía siempre con `--` con `period = 3600`. Se arregló con `setPeriodToTimeRange`. Además, tras cambiar un panel hay que **recargar la página de verdad**: cambiar solo el fragmento de la URL (`#…`) no la recarga y se sigue viendo el panel viejo.
- **En `grep` sobre logs de EMF:** el JSON lleva un espacio tras los dos puntos (`"trace_id": "…"`); un patrón sin espacio no encuentra nada.
- **Un test con fixtures importadas de otros módulos** pasaba pero el linter protestaba (F811): declararlas en `__all__` las marca como usadas.

## Pendiente

- Optimizar los 2,4 s previos al agente (calentar la Lambda y la sesión del Runtime, y agrupar las escrituras a DynamoDB).
- Agrupar las llamadas a la memoria (varios `CreateEvent` seguidos).
