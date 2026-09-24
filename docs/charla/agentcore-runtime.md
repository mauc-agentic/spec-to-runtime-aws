# AgentCore Runtime y Memory

Terraform en `infra/agentcore.tf`, imagen en `Dockerfile`, despliegue con `scripts/deploy_agent.sh`. Estado: **desplegado y probado con invocaciones reales el 2026-09-24**. Los UCs siguen en `Draft`.

## Qué se creó

| Recurso | Detalle |
|---|---|
| ECR `spec-to-runtime-agent` | Etiquetas inmutables (hash de git), escaneo al subir, conserva las 5 últimas imágenes |
| Memory `spec_to_runtime_memory` | Corto plazo, sin estrategias de largo plazo, retención de 7 días |
| Rol `spec-to-runtime-agent-runtime` | Solo lo que el agente usa: modelo Nova 2 Lite, guardrail, Knowledge Base, Memory, `Query` sobre `by_day` y logs |
| Runtime `spec_to_runtime_agent` | Contenedor `linux/arm64` con Python 3.14, red pública, invocación por IAM (sin JWT), sesiones inactivas liberadas a los 5 min |

## Despliegue en tres pasos

El Runtime exige que la imagen exista, así que `agent_image_tag` vacío no crea el Runtime.

```bash
terraform -chdir=infra apply                              # 1) ECR, Memory y rol
scripts/deploy_agent.sh                                   # 2) construye y sube la imagen (etiqueta = hash de git)
terraform -chdir=infra apply -var agent_image_tag=<hash>  # 3) crea o actualiza el Runtime
```

El script se niega a construir con cambios sin commit en el agente, para que la etiqueta identifique el código exacto.

## Decisiones

- **Contenedor y no zip:** el despliegue por código de AgentCore solo admite Python 3.10 a 3.13 (`PYTHON_3_13` es el máximo), y el proyecto es solo Python 3.14. Con contenedor controlamos la versión. La imagen pesa 345 MB.
- **Invocación con IAM:** solo la Lambda orquestadora invoca el Runtime; el rol y el perfil llegan en la carga y los verifica la API antes con el JWT de Cognito.
- **Retención de Memory de 7 días** es el mínimo de la plataforma; UC-005 BR-002 pide 24 h. Ese límite lo aplicará la lógica de sesión del orquestador: pasadas 24 h sin actividad se abre una sesión nueva.

## Resultados medidos (8 conversaciones de 2 preguntas)

| Métrica | Resultado |
|---|---|
| Primer estado ("Buscando") | 0,2 a 1,0 s con el contenedor caliente |
| Primer texto | 3,6 a 4,5 s |
| Respuesta completa | 5,2 a 8,8 s |
| Streaming | Incremental: 170 a 325 fragmentos repartidos en 1 a 3 s, aun con guardrails en modo síncrono |
| Primera llamada tras desplegar una imagen nueva | ~10 s hasta el primer estado y ~15 s en total |
| Fuera de tema | "sin fuente" en 0,6 s, sin llamar al modelo |
| Ataque de prompt | bloqueado en 2,1 s |
| Memoria | La conversación queda guardada en AgentCore Memory (mensajes del usuario y del asistente) |

Frente a NFR-011 (estado en ≤ 2 s y respuesta completa en ≤ 10 s): se cumple con el contenedor caliente. **La primera llamada tras un despliegue no lo cumple:** hay que calentar el Runtime unos minutos antes de la charla.

## Aprendizajes / dolores

- **El error intermitente de la segunda pregunta no era la memoria:** era `MaxTokensReachedException`. Strands lanza una excepción cuando el modelo llega al tope de tokens en vez de recortar. Fallaba según lo larga que saliera la respuesta, de ahí lo intermitente. Ahora se trata como recorte (`truncated: true`) y no como fallo.
- **Mi handler tragaba las excepciones sin registrarlas,** así que los logs no mostraban nada y perdí tiempo. Ahora `logger.exception` deja la traza en CloudWatch (NFR-007), con un test que lo fija. Regla: si se captura una excepción para devolver un error genérico, se registra.
- **Con 800 tokens, 3 de 8 respuestas salían cortadas a mitad de frase:** en español Nova gasta ~1,6 tokens por palabra e ignora el "350 palabras" del prompt. Se subió el tope a 1.000 tokens (menos de una milésima de dólar más por consulta) y no volvió a cortarse ninguna.
- **`iter_lines` de boto3 lee en bloques de 1 KB** y esconde el streaming: parecía que todo llegaba junto. Para medir el streaming real hay que leer con `_raw_stream.read1()`. La Lambda orquestadora tendrá que leer así.
- **El id de sesión de invocación exige al menos 33 caracteres.**
- **La política de Memory funcionó sin `GetMemory` ni `RetrieveMemoryRecords`:** bastan `CreateEvent`, `GetEvent`, `ListEvents`, `DeleteEvent`, `ListSessions` y `ListActors`.
- **Crear el recurso Memory tarda casi 3 minutos;** el Runtime, 22 segundos.
- **Etiquetas inmutables en ECR** obligan a una etiqueta nueva por cada despliegue: es lo que queremos (trazabilidad al commit), pero un `latest` no funciona.

## Pendiente

- Exponer las herramientas del Ponente por AgentCore Gateway (FR-012); hoy son locales.
- API Gateway con Cognito, SQS y la Lambda orquestadora (lee el stream con `read1`, escribe el texto parcial en DynamoDB y aplica el límite de sesión de 24 h).
- Acción de presupuesto que quita al rol del agente el permiso de invocar modelos al 90 % (NFR-014): el rol ya existe.
- Calentar el Runtime antes de la charla.
