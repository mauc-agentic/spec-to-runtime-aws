# Requirements Catalog: spec-to-runtime-aws

Derivado de [`vision.md`](vision.md). Las filas con estado `Needs review` dependen de umbrales o decisiones que el autor debe confirmar.

## Functional Requirements

| ID     | Title                        | User Story                                                                                                                                                       | Priority | Status |
|--------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|--------|
| FR-001 | Documentación AIUP completa  | As a presentador, I want tener visión, requisitos, modelo de entidades, casos de uso y casos de prueba en `docs/` so that la especificación sea la fuente de verdad de la demo. | High     | Open   |
| FR-002 | Agente "Pregúntale al repo"  | As a asistente a la charla, I want ver un agente Python con Strands Agents que responda preguntas sobre el repo, implementado a partir de las especificaciones so that entienda cómo se pasa de spec a código. | High     | Open   |
| FR-003 | Despliegue en AWS por IaC    | As a presentador, I want desplegar y destruir todo el entorno de la demo en AWS con IaC so that pueda mostrar el runtime real y repetirlo sin pasos manuales. | High     | Open   |
| FR-010 | Invocación vía API           | As a asistente a la charla, I want invocar al agente mediante una API expuesta en API Gateway y Lambda so that vea el flujo de una petición hasta el agente en AgentCore. | High     | Open   |
| FR-011 | Procesamiento asíncrono      | As a presentador, I want que las peticiones largas se encolen en SQS so that la API responda sin esperar al agente. | Low      | Open   |
| FR-012 | Herramientas vía AgentCore Gateway | As a desarrollador, I want que el agente use sus herramientas a través de AgentCore Gateway (targets Lambda y servidor MCP de AWS) so that integre capacidades sin código de integración propio. | High     | Open   |
| FR-013 | Autenticación con perfil y rol | As a asistente a la charla, I want iniciar sesión y obtener un token que indique mi perfil (Estudiante, Profesional, General) y mi rol (Asistente, Presentador) so that el agente sepa quién soy y qué puedo ver. | High     | Open   |
| FR-014 | Sincronización de documentos | As a presentador, I want sincronizar los documentos de `docs/` con la base de conocimiento, etiquetando cada uno con su nivel de acceso so that el agente responda con información actual. | High     | Open   |
| FR-015 | Consulta con RAG y citas     | As a asistente a la charla, I want preguntar al agente y recibir una respuesta basada en los documentos, con citas a sus fuentes so that pueda verificar de dónde sale cada afirmación. | High     | Open   |
| FR-016 | Respuesta adaptada al perfil | As a estudiante, I want que el agente responda paso a paso y con glosario, y as a profesional, I want respuestas técnicas con trade-offs so that la misma pregunta me llegue en el nivel que necesito. | High     | Open   |
| FR-017 | Control de acceso por rol    | As a presentador, I want que los documentos internos y borradores solo los vea mi rol so that el público nunca reciba material restringido. | High     | Open   |
| FR-018 | Memoria de sesión            | As a asistente a la charla, I want hacer preguntas de seguimiento dentro de una conversación so that el agente recuerde el contexto de la sesión. | High     | Open   |
| FR-019 | Guardrails de contenido      | As a presentador, I want que la entrada y la salida del agente pasen por Bedrock Guardrails so that se bloqueen temas fuera de alcance, ataques de prompt y datos personales. | High     | Open   |
| FR-020 | Buzón de preguntas en vivo   | As a presentador, I want que la audiencia envíe preguntas durante la charla y pedir un resumen de los temas que se repiten so that pueda orientar la sesión. | Low      | Open   |
| FR-004 | Reproducción de la demo      | As a lector posterior del repo, I want reproducir una demo siguiendo solo la documentación so that no dependa de haber asistido a la charla. | High     | Open   |
| FR-005 | Registro del paso a paso     | As a presentador, I want registrar en `docs/charla/` cada paso seguido so that la charla y el repo cuenten el mismo proceso. | High     | Open   |
| FR-006 | Registro de buenas prácticas | As a asistente a la charla, I want consultar las buenas prácticas descubiertas so that pueda aplicarlas en mis propios proyectos. | Medium   | Open   |
| FR-007 | Registro de dolores vividos  | As a asistente a la charla, I want conocer los problemas encontrados y cómo se resolvieron so that evite repetirlos. | Medium   | Open   |
| FR-008 | Trazabilidad spec-código     | As a presentador, I want verificar la cobertura de cada UC y TC contra su especificación so that pueda demostrar que código, pruebas y spec no divergen. | High     | Open   |
| FR-009 | Flujo por ramas              | As a presentador, I want que cada spec, UC o TC nuevo se desarrolle en su propia rama y se mergee a `main` solo por PR tras certificarse so that `main` siempre contenga material verificado. | High     | Open   |

## Non-Functional Requirements

| ID      | Title                         | Requirement                                                                                                                | Category        | Priority | Status |
|---------|-------------------------------|----------------------------------------------------------------------------------------------------------------------------|-----------------|----------|--------|
| NFR-001 | Actualidad de la documentación | Todo cambio de código, test o decisión debe incluir en el mismo commit la actualización del documento AIUP afectado (100 % de los commits con cambios de comportamiento). | Maintainability | High     | Open   |
| NFR-002 | Cobertura del spec            | Todo UC en estado `Tested` o `Done` debe tener un `/coverage-check` con 0 gaps y 0 drift.                                    | Maintainability | High     | Open   |
| NFR-003 | Estado de las pruebas en main | La suite completa de tests debe pasar al 100 % en cada merge a `main`.                                                       | Maintainability | High     | Open   |
| NFR-004 | Reproducibilidad              | Un tercero debe poder levantar una demo desde un clon limpio en un máximo de 30 minutos siguiendo solo `docs/` **(umbral por confirmar)**. | Portability     | Medium   | Needs review |
| NFR-005 | Robustez en vivo              | Cada demo debe completar su flujo principal sin intervención manual fuera de lo documentado, verificado en un ensayo previo a la charla. | Availability    | High     | Open   |
| NFR-006 | Gestión de secretos           | El repositorio no debe contener credenciales ni claves de AWS; 0 secretos detectados en el historial de git. Los secretos en runtime se leen de Secrets Manager. | Security        | High     | Open   |
| NFR-007 | Observabilidad                | Cada invocación del agente debe dejar logs y métricas en CloudWatch, con 100 % de las invocaciones de la demo trazables por ID de petición. | Maintainability | High     | Open   |
| NFR-008 | Infraestructura reproducible  | El 100 % de los recursos AWS de la demo debe estar definido en IaC; 0 recursos creados manualmente en la consola.            | Portability     | High     | Open   |
| NFR-009 | Aislamiento por rol           | En la suite de pruebas, 0 respuestas o citas del agente provienen de documentos con nivel de acceso superior al rol del token.  | Security        | High     | Open   |
| NFR-010 | Efectividad de guardrails     | En un conjunto de pruebas de al menos 10 casos (ataque de prompt, tema prohibido, dato personal), el 100 % es bloqueado o anonimizado por Bedrock Guardrails. | Security        | High     | Open   |
| NFR-011 | Latencia de consulta          | El percentil 95 de una consulta síncrona con RAG debe ser de 10 segundos o menos **(umbral por confirmar tras medir)**. | Performance     | Medium   | Needs review |
| NFR-012 | Costo de la demo              | El costo de AWS de una jornada de demo (levantar, ensayar, presentar y destruir) debe ser de 5 USD o menos **(umbral por confirmar)**; el almacén de vectores debe ser S3 Vectors. | Cost            | Medium   | Needs review |

## Constraints

| ID    | Title                   | Constraint                                                                                                  | Category    | Priority | Status       |
|-------|-------------------------|-------------------------------------------------------------------------------------------------------------|-------------|----------|--------------|
| C-001 | Metodología AIUP        | Los artefactos de especificación deben seguir AIUP con el plugin `aiup-core`.                                | Technical   | High     | Open         |
| C-002 | Stack de construcción   | La aplicación se construye en Python 3.14 con Strands Agents, el framework de agentes de AWS.                | Technical   | High     | Open         |
| C-003 | Plataforma de runtime   | El runtime de las demos es AWS, con API Gateway, Lambda, Bedrock AgentCore (Runtime, Gateway, Memory, Identity), Bedrock Knowledge Bases, S3 y S3 Vectors, Cognito, Bedrock Guardrails, CloudWatch, SQS y Secrets Manager, en la región `us-east-1`. | Technical   | High     | Open         |
| C-004 | Ramas y merge           | Todo spec, UC o TC nuevo se desarrolla en una rama nueva; el merge a `main` es solo por PR, con CI en verde y commits firmados, tras pruebas y certificación. | Operational | High     | Open         |
| C-005 | Fecha de la charla      | Las demos y la documentación deben estar listas antes del 2026-09-26.                                         | Schedule    | High     | Open         |
| C-006 | Infraestructura como código | Toda la infraestructura se define con Terraform (decisión en `docs/charla/iac-terraform.md`), con el state en S3. | Technical   | High     | Open         |
| C-007 | Modelo de lenguaje      | El agente usa Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`).                                             | Technical   | High     | Open         |
