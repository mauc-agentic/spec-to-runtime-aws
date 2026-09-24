# Vision: spec-to-runtime-aws

> Borrador derivado del contexto del repo y de la charla. Los puntos marcados **(por confirmar)** deben ser validados por el autor antes de pasar a `Reviewed`. El dominio del agente quedó definido el 2026-09-23 (ver `docs/charla/dominio-agente.md`).

## Mission

Mostrar, con un ejemplo real y reproducible, cómo llevar una especificación hasta un sistema corriendo en AWS usando AIUP (AI Unified Process): visión, requisitos, modelo de entidades, casos de uso y casos de prueba son la fuente de verdad, y el código, las pruebas y el despliegue se derivan y se mantienen alineados con ellos. El repositorio sirve como material de una charla: documenta el paso a paso, los temas de interés, las buenas prácticas y los dolores vividos, y aloja las demos.

## Demo application: "Pregúntale al repo"

La aplicación de demostración es un agente que responde preguntas sobre este mismo repositorio (visión, requisitos, especificaciones y aprendizajes de `docs/charla/`) usando RAG, y adapta la respuesta al perfil de quien pregunta. Tiene sentido para la charla porque el agente se construye a partir de las mismas especificaciones que consulta.

- **RAG económico:** Amazon Bedrock Knowledge Base con Amazon S3 Vectors como almacén de vectores y Titan Text Embeddings v2 (256 dimensiones). Se evita OpenSearch Serverless por su costo mínimo mensual.
- **Modelo:** Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`) en `us-east-1`.
- **Identidad:** Amazon Cognito emite el JWT; AgentCore Gateway lo valida. El token trae el **perfil** (Estudiante, Profesional, General) y el **rol** (Asistente, Presentador).
- **Respuesta adaptada al perfil:** el mismo agente y la misma base de conocimiento responden distinto (didáctico para estudiantes, técnico para profesionales, resumido para el público general).
- **Herramientas:** expuestas por AgentCore Gateway (targets Lambda y servidor MCP de AWS).
- **Memoria:** AgentCore Memory de corto plazo, por sesión de conversación.
- **Seguridad de contenido:** Amazon Bedrock Guardrails filtran la entrada y la salida del agente.
- **Opcional:** buzón de preguntas en vivo durante la charla, con procesamiento asíncrono por SQS.

## Target users

- **Estudiantes:** quieren entender el flujo spec-driven desde cero, con explicaciones paso a paso y glosario.
- **Profesionales (desarrolladores y arquitectos):** quieren ver un flujo spec-driven de punta a punta, con detalle técnico y decisiones, y poder repetirlo en sus propios proyectos.
- **Público general:** quiere una idea clara y breve de qué se hizo y por qué, sin jerga.
- **Presentador (autor):** necesita un repositorio ordenado, con demos que funcionen y documentación al día para mostrar en vivo; tiene acceso a material interno y borradores que el resto no ve.
- **Lectores posteriores del repo:** llegan sin haber asistido y necesitan entender los pasos y las decisiones leyendo solo `docs/`.

## Goals

- Cada demo se puede reproducir desde cero siguiendo únicamente la documentación del repo, y su infraestructura se levanta y destruye con IaC. Hay una sola aplicación de demostración.
- Todo caso de uso o caso de prueba implementado tiene su especificación en `docs/` con estado actualizado y cobertura verificada (`/coverage-check` sin gaps ni drift).
- Los aprendizajes (pasos, buenas prácticas, dolores) quedan registrados en `docs/charla/` en el momento en que ocurren.
- El agente responde según el perfil del usuario y nunca expone documentos de un nivel de acceso superior a su rol.

## Scope

### In scope

- Documentación AIUP completa: visión, requisitos, modelo de entidades, diagrama y especificaciones de casos de uso, casos de prueba.
- La aplicación "Pregúntale al repo": un agente en Python con Strands Agents, ejecutado en Amazon Bedrock AgentCore.
- Controles de costo como parte de la solución: cuotas por usuario, tope global, AWS Budgets con acción de cierre y destrucción del entorno tras cada sesión.
- Infraestructura en AWS definida 100 % como código con Terraform: API Gateway, Lambda, Bedrock AgentCore (Runtime, Gateway, Memory, Identity), Bedrock Knowledge Bases, S3 y S3 Vectors, Cognito, Bedrock Guardrails, CloudWatch, SQS y Secrets Manager.
- Uso del servidor MCP de AWS para integrar herramientas de los servicios con el agente.
- Registro de buenas prácticas y problemas encontrados durante el proceso.
- Flujo de trabajo por ramas y PRs: cada spec, UC o TC nuevo en su rama, con merge a `main` solo tras pruebas, CI en verde y certificación.

### Out of scope

- Ser una plataforma o producto de uso productivo.
- Cubrir servicios de AWS distintos de los listados en Constraints, o stacks distintos de Python + Strands.
- Memoria de largo plazo, personalización persistente entre sesiones o registro de usuarios propio (los usuarios de la demo se crean en Cognito).
- Material de la charla en otros formatos (diapositivas, video) dentro de este repo.

## Constraints

- La metodología es AIUP; `aiup-core` genera la documentación. El plugin `aiup-vaadin-jooq` no aplica porque el stack no es Vaadin/jOOQ.
- Stack: Python 3.14 + Strands Agents. Se eligió porque es el framework de agentes de AWS, integra con más facilidad las herramientas de los servicios AWS y ofrece un servidor MCP.
- Servicios AWS: API Gateway, Lambda, Bedrock AgentCore, Bedrock Knowledge Bases, S3 y S3 Vectors, Cognito, Bedrock Guardrails, CloudWatch, SQS y Secrets Manager, todos aprovisionados por Terraform. Región única `us-east-1`.
- Modelo de lenguaje: Amazon Nova 2 Lite.
- **Presupuesto: 50 USD en total** para todo el proyecto, con un aforo esperado de 50 participantes. Es un límite duro que se aplica con cuotas en runtime, alertas y destrucción del entorno tras cada sesión.
- Nada se mergea a `main` sin PR, CI en verde, commits firmados, pruebas en verde y cobertura del spec certificada.
- Fecha de la charla: **2026-09-26**. Condiciona el alcance: los UCs se implementan por prioridad y solo se muestra como terminado lo que llegó a `Tested`.

## Success measures

- Un tercero puede clonar el repo y reproducir una demo siguiendo solo `docs/`.
- El 100 % de los UC en estado `Implemented` o superior tienen cobertura verificada sin drift entre spec, código y tests.
- Las demos se ejecutan en vivo durante la charla sin intervención manual fuera de lo documentado.
- El gasto total de AWS no supera 50 USD, con 50 participantes en la charla.
- Una misma pregunta produce respuestas diferenciadas para los tres perfiles, y ninguna respuesta cita documentos de un nivel de acceso mayor al del rol del usuario.
