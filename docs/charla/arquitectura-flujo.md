# Arquitectura del flujo y latencia percibida

Estado: **decidido el 2026-09-24** — el autor eligió la **opción C (polling con avance parcial)**. Spec de UC-004 en `docs/use_cases/UC-004-consultar-al-agente-sobre-el-repositorio.md`.

## Flujo pedido por el autor

Página web → API Gateway con autorización Cognito → SQS → Lambda → agente → respuesta. La Lambda orquesta la llamada al agente y da formato a la respuesta (Markdown, citas con enlace a GitHub).

## Dónde se va realmente el tiempo

La cola no es el problema: SQS y el disparo de Lambda suman décimas de segundo. El tiempo lo ponen el modelo, las llamadas a herramientas, los guardrails y los arranques en frío (Lambda y AgentCore Runtime). Lo que sí complica el flujo con SQS es **cómo vuelve la respuesta al navegador**, porque una cola es asíncrona y hay que entregarla por otro canal.

## Opciones para devolver la respuesta

| Opción | Cómo funciona | Pros | Contras |
|---|---|---|---|
| A. Polling | El navegador consulta `GET /respuestas/{id}` cada ~1 s; la Lambda guarda el resultado en DynamoDB | Simple, sin servicios nuevos | Añade hasta 1 s y hace muchas llamadas |
| B. WebSocket (API Gateway) | La Lambda empuja la respuesta a la conexión | Entrega inmediata | Más piezas (conexiones, rutas) y más riesgo en 3 días |
| **C. Polling con avance parcial (recomendada)** | Como A, pero la Lambda va escribiendo el texto que recibe del agente y el navegador lo muestra creciendo, con estados (En cola, Buscando, Redactando) | Se siente como streaming, funciona con Lambda en Python, sin servicios nuevos | Necesita que el agente entregue el texto por partes |

## Decisión y consecuencias

Se usa la opción C. Consecuencias que la spec de UC-004 (BR-004 y BR-007) ya recoge:

- **Texto visible solo tras pasar los guardrails.** Mostrar el texto por partes obliga a revisar la salida por partes antes de escribirla en DynamoDB; si no, el participante vería texto que después se bloquea. Es un coste de latencia y de unidades de guardrails a validar con una medición (NFR-010, NFR-012).
- **Tres estados visibles** (En cola, Buscando, Redactando) desde los primeros 2 segundos, que es lo que cubre NFR-011 incluso cuando el modelo tarda.
- **Si el participante cierra la página,** la respuesta se sigue generando y queda en el historial (A8 de UC-004; UC-006).
- **Tiempo máximo de 60 s** por solicitud; superado, se marca como fallida y no consume cuota.

## Cómo bajar la espera percibida (sin abandonar el flujo)

1. **Mostrar el estado al instante** (en cola, buscando, redactando): la primera señal llega en menos de 2 s aunque la respuesta tarde más.
2. **Texto que aparece por partes** (opción C).
3. **Una sola llamada al modelo cuando no hace falta herramienta:** el RAG puede hacerse antes de llamar al modelo, en vez de que el modelo decida buscar (evita una segunda llamada, unos 2 a 4 s menos).
4. **Recuperar pocos fragmentos** (4 a 5) y limitar la salida a 800 tokens: menos entrada y menos generación.
5. **Caché de preguntas repetidas** en DynamoDB por (pregunta normalizada, perfil): en una charla se repiten mucho las mismas preguntas y responden en milisegundos, sin costo de modelo.
6. **Calentar antes de la charla:** unas invocaciones de prueba minutos antes evitan el arranque en frío. Es gratis frente a Lambda con concurrencia aprovisionada.
7. **Guardrails:** revisar la entrada antes de encolar (rechaza rápido y barato) y la salida al final.

Con esto el objetivo de NFR-011 es: inicio visible en 2 s o menos (p95) y respuesta completa en 10 s o menos (p95). Hay que **medirlo** con la infraestructura real antes de comprometerlo.

## Dónde SQS aporta

- **Protege el presupuesto:** actúa de amortiguador y permite limitar la concurrencia de la Lambda, así 50 personas preguntando a la vez no disparan el gasto ni saturan Bedrock.
- **Desacopla la persistencia:** guardar el historial no retrasa la respuesta.

## DynamoDB: sí, y para qué

Sí hace falta. AgentCore Memory guarda solo el contexto que el agente necesita; DynamoDB guarda lo que necesita la aplicación:

- Historial de conversaciones (UC-006) y respuesta parcial en curso.
- Contadores de cuota por usuario y día (NFR-013).
- Preguntas para el análisis del ponente (UC-007).
- Caché de respuestas repetidas.

Modo on-demand: centavos para este volumen.

## Top 10 del ponente

Una herramienta `top_preguntas` detrás de AgentCore Gateway, permitida solo al grupo Ponente de Cognito. Lee las preguntas de DynamoDB (máximo 3.000 por el tope del proyecto), y el modelo las agrupa por tema y cuenta. Coste aproximado: unos 120.000 tokens de entrada, del orden de 0,04 USD por consulta.

## Riesgo de plazo

Web, Cognito, KB, Gateway, Memory, Guardrails, DynamoDB, SQS y el análisis del ponente en 3 días es mucho. Orden sugerido si hay que recortar: primero UC-001, UC-004 y UC-007 (lo que se ve en la charla); UC-002 es un selector; UC-003 puede ser un comando manual; UC-005 puede apoyarse en el historial de DynamoDB si AgentCore Memory no llega (es lo que se sacrifica primero); UC-006 se recorta primero.

## Aprendizajes / dolores

- Un repo público hace que todo su contenido sea público: los documentos no pueden tener niveles de acceso, así que el rol Ponente se distingue por **herramientas**, no por documentos (FR-017).
- El perfil de respuesta funciona mejor como elección del usuario en la interfaz que como claim del token: se puede cambiar durante la charla.
