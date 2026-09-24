# API y orquestador

Código en `src/spec_to_runtime/{api,orchestrator,common}/`, infraestructura en `infra/api.tf`. Estado: **desplegado y probado de punta a punta con AWS real el 2026-09-24**. Los UCs siguen en `Draft`.

## Flujo

```
web ──JWT──▶ API Gateway (HTTP) ──▶ Lambda api ──▶ SQS ──▶ Lambda orquestadora ──▶ AgentCore Runtime
 ▲                                      │  reserva cuota          │ escribe texto parcial
 └─────── GET /requests/{id} (polling ~1 s) ◀──────── DynamoDB ◀───┘
```

`POST /questions` responde `202` al instante: valida, descuenta la cuota, guarda la solicitud como `Queued`, la encola y termina. La orquestadora consume la cola con como máximo 10 ejecuciones a la vez, invoca el Runtime, lee el stream y va publicando en DynamoDB el estado (En cola, Buscando, Redactando) y el texto parcial cada 0,7 s. Al terminar da el formato final (lista de fuentes con enlace y aviso de recorte).

| Ruta | Quién | UC |
|---|---|---|
| `POST /questions` | Participante y Ponente | UC-004, UC-005 |
| `GET /requests/{request_id}` | El dueño | UC-004 |
| `GET /sessions`, `GET /sessions/{session_id}` | El dueño | UC-006 |
| `POST /admin/sync`, `GET /admin/sync` | Solo el Ponente | UC-003 |

El registro no pasa por la API: la web llama a Cognito con el código del evento (UC-001).

## Decisiones

- **El usuario y el rol salen del token, nunca del cuerpo.** La clave de la tabla es `(user_id, request_id)` y `user_id` viene del JWT, así que una consulta ajena simplemente no existe (404): el aislamiento de NFR-009 no depende de un `if`.
- **`request_id` ordenable** (`<ms>-<hex>`) es a la vez la clave de ordenación: la lectura por polling es un `GetItem` directo, sin índice.
- **La sesión la crea el servidor** y debe ser del usuario: si el cliente pudiera elegir el id, dos usuarios compartirían microVM y memoria de AgentCore.
- **Cuotas con transacción** (usuario + global en una sola operación): o entran las dos o no entra ninguna. 25 por día para participantes, 100 para el Ponente, 3.000 en total. El "día" es el de Colombia (UTC-5). Las respuestas fallidas devuelven la unidad; las bloqueadas cuentan (UC-004 BR-006).
- **Sesión de 24 h (UC-005 BR-002)** la aplica la API: pasado ese tiempo abre una sesión nueva y avisa con `context_expired`.
- **SQS entrega al menos una vez:** la orquestadora solo atiende lo que sigue `Queued`, así que un reintento no cobra ni responde dos veces.
- **Techo de tráfico:** 40 de ráfaga y 20 por segundo en API Gateway, y 10 consultas simultáneas en la orquestadora (protege el presupuesto y Bedrock).
- **La etiqueta de la imagen del agente se versiona** (`infra/agent_image.auto.tfvars`, la actualiza `scripts/deploy_agent.sh`). Antes se pasaba con `-var`.

## Resultados medidos (prueba de punta a punta)

| Comprobación | Resultado |
|---|---|
| Registro con código de evento y con el registro cerrado | Correcto; cerrado rechaza la cuenta |
| Sin token | 401 |
| Pregunta con Basic y seguimiento con Technical en la misma sesión | Correcto; conserva la sesión |
| Fuera de tema / ataque de prompt | "sin fuente" en 2,0 s / bloqueada en 4,5 s |
| Historial y consulta ajena | 3 conversaciones agrupadas; consulta ajena = 404 |
| Participante intenta sincronizar | 403 |
| Ponente: estado de sincronización y top 10 | Correcto |
| Respuesta completa en caliente | 5 a 8 s; fuera de tema, 2 s |
| Primera petición a la API (arranque en frío de la Lambda) | 2,8 s hasta el `202`; las siguientes, 0,4 s |
| Primera pregunta tras un despliegue | 11,5 s (arranque del contenedor y de la Lambda) |

`scripts/smoke_test.py` repite estas 11 comprobaciones y **se limpia solo**: cierra el registro, borra usuarios, preguntas y contadores de la prueba. Sirve de ensayo y de calentamiento unos minutos antes de la charla.

### Top 10 del Ponente con volumen

30 preguntas sembradas de 7 temas con conteos conocidos: el informe dio 7, 5, 5, 4, 4, 3 y 2, **exactamente** los esperados, con porcentajes correctos. Los conteos los calcula el código; el modelo solo agrupa.

## Defectos que encontré y cómo se resolvieron

- **El modelo reescribía el informe y lo estropeó:** cerró con "ninguna de estas preguntas tiene una fuente documentada" cuando solo 2 de 30 no la tenían. Ahora `top_preguntas` corta el bucle del agente (`stop_event_loop`) y el informe se muestra tal cual. Además bajó de 6,7 s a 4,5 s.
- **Faltaba el enmascarado de datos personales (UC-007 BR-005):** la pregunta se guarda como se escribió, así que un correo o teléfono habría salido en pantalla. El informe pasa por el guardrail antes de mostrarse (`{EMAIL}`, `{PHONE}`); verificado con el guardrail real. **Limitación:** si un ejemplo contiene una clave de AWS, se bloquea el informe entero.
- **Casi degrado el agente sin darme cuenta:** al planificar pasé una etiqueta de imagen vieja y el plan proponía "actualizar el Runtime". Lo vi al leer el plan; ahora la etiqueta está versionada.
- **La prueba dejó 5 preguntas en la base,** que habrían contaminado el top 10 real. Se borraron y el script de humo ya se limpia solo.

- **El top 10 buscaba por el día equivocado (encontrado al reportar el autor "no encontré preguntas"):** las preguntas se guardan con el día local de Colombia y el análisis buscaba por fecha UTC. Por la tarde-noche colombiana, cuando en UTC ya es el día siguiente, no encontraba nada: justo la hora de la charla (a las 8 p. m. del sábado 26 se guardaban como "26" y se buscaba "27"). Pasaba desapercibido porque mis pruebas corrían de madrugada, cuando ambos días coinciden. Ahora `local_days` calcula los días en hora de Colombia, con un test de regresión que muerde. **Regla:** toda fecha que sea clave de partición se calcula en un solo lugar y con una sola zona horaria.
- **Las preguntas del ponente no cuentan en el top 10** (UC-007): por eso un ponente que prueba solo, con su propia cuenta, ve "No encontré preguntas de participantes". El mensaje ahora lo explica. Para ensayar hay que preguntar desde una cuenta de participante.

- **"¿Cuál es el usuario más activo?" no respondía nada útil (lo reportó el autor):** el agente buscaba en los documentos algo que no está, y "quién ha preguntado más" se iba por error a la herramienta del top 10 y devolvía "No encontré preguntas…". La causa: no existía ninguna herramienta de actividad y el modelo elegía la más parecida. Se añadió `actividad_participantes` (cuántas preguntas y participantes, hora pico, perfiles, sin fuente, bloqueadas y los participantes más activos), calculada por código sin llamar al modelo, y se le explicó al agente qué herramienta usar para qué. **Los participantes salen anónimos ("Participante 1: 8 preguntas")** porque UC-007 BR-005 prohíbe decir quién preguntó; si piden un correo o un nombre, se responde con el resumen anónimo. Verificado contra el Runtime con 30 preguntas de 8 usuarios: cifras exactas y ningún identificador filtrado en 6 preguntas distintas. **Regla:** cuando un agente tiene varias herramientas, una pregunta que ninguna cubre acaba en la "más parecida"; hay que decirle en el prompt qué cubre cada una y qué hacer cuando ninguna sirve.
- **Comprobación de mutaciones que no mutaba nada:** mi primer `sed` no encontró la línea (el formateador la había partido) y "98 en verde" parecía una prueba de que el test protegía. Una mutación solo vale si primero se comprueba que cambió el archivo. La segunda, hecha con Python y una aserción sobre el texto a cambiar, sí hizo fallar 2 tests.
- En `zsh` una variable con un comando no se divide en palabras (`T='env ... pytest'; $T` falla): usar una función.

## Aprendizajes / dolores

- **Los tests con `moto` valen más que los fakes:** DynamoDB simulado con transacciones y condiciones reales confirma que un rechazo no deja contadores a medias y que el tope global manda sobre el diario.
- **Comprobé que los tests muerden** rompiendo el código a propósito: quitar la liberación de cuota hizo fallar 3 tests y hacer que el rol ignore el token, 4.
- **SQS entrega como máximo 10 mensajes por lectura:** un test mío "drenaba la cola" y no lo hacía; se mide con el contador de mensajes.
- **API Gateway HTTP corta a los 30 s:** la sincronización se invoca con un límite de 25 s y, si tarda más, responde que sigue en curso y se consulta el estado.
- **La política de la etapa `$default` con CORS `*`** es provisional: se acota al dominio de CloudFront cuando exista la web.

## Pendiente

- La web (S3 y CloudFront) y acotar CORS.
- Exponer las herramientas del Ponente por AgentCore Gateway (FR-012).
- Acción de presupuesto que quita al agente el permiso de invocar modelos al 90 % (NFR-014).
- Solicitudes atascadas: si la orquestadora muriera a mitad, la solicitud quedaría en `Processing`; falta un barrido que la marque como fallida.
- Activar la etiqueta de costo del presupuesto (`activate_cost_allocation_tag`).
