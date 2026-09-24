# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito del repo

`spec-to-runtime-aws` es el repositorio de una charla: documenta paso a paso cómo llevar una especificación hasta un runtime en AWS, incluyendo temas de interés, buenas prácticas y dolores vividos, y sirve como base de las demos. Todo se hace con **AIUP (AI Unified Process, https://unifiedprocess.ai)**: la especificación es la fuente de verdad y el código se deriva de ella.

**Stack:** Python + Strands Agents (framework de agentes de AWS), ejecutado en Bedrock AgentCore, con API Gateway, Lambda, SQS, CloudWatch y Secrets Manager. Toda la infraestructura va como IaC (herramienta por decidir: CDK o Terraform). Fecha de la charla: **2026-09-26**.

Plugins de Claude Code: `aiup-core` (documentación AIUP, independiente del stack) y `aws-agents` (skills `agents-get-started`, `agents-build`, `agents-deploy`, `agents-debug`, etc. para AgentCore). `aiup-vaadin-jooq` está instalado pero **no aplica** a este stack: no uses `/implement`, `/flyway-migration` ni los skills de tests Vaadin/Hilla. El código aún no existe; no asumas nada más allá de lo que esté en el repo o en las specs aprobadas.

## Reglas obligatorias del flujo de trabajo

1. **Todo spec nuevo o UC nuevo va en una rama NUEVA** (p. ej. `uc-001-nombre`, `spec/requirements`, `tc-001-nombre`). Nunca se trabaja directo en `main`.
2. **Merge a `main` solo al final**: cuando la implementación, las pruebas y los tests estén completos y certificados (`/coverage-check` sin gaps ni drift, tests en verde, estado del UC/TC actualizado). No hagas merge ni push sin que el usuario lo pida.
3. **Todo se documenta y el spec se mantiene al día.** Si cambia el código, un test o una decisión, se actualiza en el mismo cambio el documento AIUP correspondiente (`Status` del UC/TC, entity model, diagrama, requisitos). Código y spec nunca deben divergir.
4. **Los aprendizajes de la charla se registran mientras ocurren**: pasos seguidos, buenas prácticas y dolores/problemas vividos se documentan en el momento en que se descubren, no al final. Ubicación: `docs/charla/` (crearla si no existe; un archivo por tema, en español).

## Documentos AIUP (`docs/`)

Cada skill lee los artefactos de los pasos anteriores. Los `SKILL.md` de los plugins son la referencia autoritativa.

| Artefacto | Ruta | Skill | Fase |
|---|---|---|---|
| Visión (misión, usuarios, metas, alcance, restricciones); lo mantiene el equipo | `docs/vision.md` | manual | Inception |
| Catálogo de requisitos: funcionales (user stories), no funcionales medibles, restricciones | `docs/requirements.md` | `/requirements` | Inception |
| Modelo de entidades: ER en Mermaid + tablas de atributos, tipos, validaciones | `docs/entity_model.md` | `/entity-model` | Elaboration |
| Diagrama de casos de uso (actores y UCs) en PlantUML | `docs/use_cases.puml` | `/use-case-diagram` | Elaboration |
| Especificación por caso de uso: actores, precondiciones, flujo principal, flujos alternos, postcondiciones, reglas de negocio | `docs/use_cases/UC-XXX-<nombre-kebab>.md` | `/use-case-spec` | Construction |
| Caso de prueba end-to-end: journey que encadena varios UCs (tabla Flow, datos concretos, validaciones finales) | `docs/test_cases/TC-XXX-<nombre-kebab>.md` | `/test-case` | Construction |

Flujo hacia adelante: `/requirements` → `/entity-model` → `/use-case-diagram` → `/use-case-spec` → `/test-case`. Para código ya existente: `/reverse-engineer`. Cada skill de aiup-core deriva de `docs/vision.md`, así que ese archivo debe existir antes de empezar.

### Estados

- **UC** (`Status` en Overview): Draft → Reviewed → Approved → Implemented → Tested → Done (u Obsolete si lo reemplaza otro UC).
- **TC**: tiene `Priority` y `Status` propios; usa los valores definidos en `aiup-core:test-case`.
- Solo se implementa un UC en estado `Approved`. Al terminar implementación pasa a `Implemented`; con todas las pruebas en verde y `/coverage-check` limpio, a `Tested`; con aceptación, a `Done`. Actualiza el estado en el mismo commit que el cambio que lo justifica.

## Construcción

AIUP no tiene plugin de construcción para Python + Strands, así que la implementación se hace a mano guiada por los `UC-XXX`/`TC-XXX` aprobados, apoyándose en los skills de `aws-agents` (scaffolding, deploy, debug, hardening). Reglas:

- Implementa solo UCs en estado `Approved`, en su rama, con tests que referencien el ID (`UC-XXX`) en nombre o docstring para mantener la trazabilidad.
- El modelo de entidades de `docs/entity_model.md` se implementa como modelos Python, no como migraciones Flyway.
- Ningún recurso AWS se crea a mano: todo pasa por IaC y queda documentado en `docs/charla/`.
- Para auditar cobertura de un UC/TC contra su spec usa la revisión de `uc-coverage` (`/coverage-check UC-XXX`), que es de solo lectura; hazlo antes de pedir review y antes de mergear.

## Comandos

Aún no hay build, lint ni tests. Cuando exista el proyecto, agrega aquí los comandos reales (build, test completo, ejecutar un solo test, arrancar la app, deploy a AWS) en el mismo cambio que los introduce.
