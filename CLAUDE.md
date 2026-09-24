# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito del repo

`spec-to-runtime-aws` es el repositorio de una charla: documenta paso a paso cómo llevar una especificación hasta un runtime en AWS, incluyendo temas de interés, buenas prácticas y dolores vividos, y sirve como base de las demos. Todo se hace con **AIUP (AI Unified Process, https://unifiedprocess.ai)**: la especificación es la fuente de verdad y el código se deriva de ella.

**Stack:** Python 3.14 + Strands Agents (framework de agentes de AWS), ejecutado en Bedrock AgentCore con el modelo **Amazon Nova 2 Lite** (`us.amazon.nova-2-lite-v1:0`, región `us-east-1`), con API Gateway, Lambda, SQS, CloudWatch y Secrets Manager. Toda la infraestructura va como IaC con **Terraform** (además: Bedrock Knowledge Bases, S3 Vectors, Cognito y Bedrock Guardrails) (decisión en `docs/charla/iac-terraform.md`). Fecha de la charla: **2026-09-26**.

Plugins de Claude Code: `aiup-core` (documentación AIUP, independiente del stack) y `aws-agents` (skills `agents-get-started`, `agents-build`, `agents-deploy`, `agents-debug`, etc. para AgentCore). `aws-agents` (marketplace `aws/agent-toolkit-for-aws`) ya está instalado y habilitado en `.claude/settings.json`. `aiup-vaadin-jooq` **no aplica** a este stack y está deshabilitado en `.claude/settings.json`: no uses `/implement`, `/flyway-migration` ni los skills de tests Vaadin/Hilla. El código aún no existe; no asumas nada más allá de lo que esté en el repo o en las specs aprobadas.

**Estado de los specs:** la visión, los requisitos, `docs/entity_model.md` y el diagrama `docs/use_cases.puml` ya cubren el dominio **"Pregúntale al repo"**: página web → API Gateway (Cognito) → SQS → Lambda → agente con RAG (Bedrock Knowledge Base + S3 Vectors sobre todo el repo de GitHub), AgentCore Gateway y Memory, DynamoDB para historial y cuotas, Bedrock Guardrails. Los participantes eligen perfil (Básico, Técnico, General); el rol Ponente accede al top 10 de preguntas. Siete UCs (UC-001 a UC-007) están identificados; falta escribir cada spec en su rama. Los umbrales `Needs review` (NFR-004, NFR-011) están por confirmar. Ver `docs/charla/dominio-agente.md` y `docs/charla/arquitectura-flujo.md`.

**MCP del proyecto (`.mcp.json`):** `strands-agents` (`uvx strands-agents-mcp-server`, del monorepo `strands-agents/harness-sdk`) expone `search_docs` y `fetch_doc` sobre la documentación de Strands. Consúltalo antes de escribir código con la API de Strands en lugar de asumir de memoria. Requiere `uv` instalado. `terraform` (`hashicorp/terraform-mcp-server` vía Docker, solo toolset `registry`) consulta providers y módulos del Terraform Registry: úsalo antes de escribir recursos `aws_*` en lugar de asumir atributos de memoria. Requiere Docker en ejecución. Aún no se ha probado contra una invocación real: valídalo la primera vez que escribas Terraform (ver `docs/charla/iac-terraform.md`).

## Reglas obligatorias del flujo de trabajo

1. **Todo spec nuevo o UC nuevo va en una rama NUEVA** (p. ej. `uc-001-nombre`, `spec/requirements`, `tc-001-nombre`). Nunca se trabaja directo en `main`.
2. **Merge a `main` solo al final**: cuando la implementación, las pruebas y los tests estén completos y certificados (`/coverage-check` sin gaps ni drift, tests en verde, estado del UC/TC actualizado). No hagas merge ni push sin que el usuario lo pida. `main` está protegido (ruleset `protect-main`): solo entra por PR con squash merge, commits firmados y CI en verde; el dueño es el único que mergea. Detalle en `docs/charla/proteccion-repo.md`. Si apilas PRs, cambia la base del segundo a `main` antes de mergear el primero.
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
- **Presupuesto duro de 50 USD** para todo el proyecto (`docs/charla/presupuesto.md`, NFR-012 a NFR-014). No crear recursos de costo fijo (NAT Gateway, OpenSearch Serverless, throughput aprovisionado, KMS CMK, VPC endpoints); antes de agregar un servicio nuevo, estima su costo; y destruye el entorno al terminar cada sesión.
- Ningún recurso AWS se crea a mano: todo pasa por IaC y queda documentado en `docs/charla/`.
- Para auditar cobertura de un UC/TC contra su spec usa la revisión de `uc-coverage` (`/coverage-check UC-XXX`), que es de solo lectura; hazlo antes de pedir review y antes de mergear.

## Comandos

Región única: `us-east-1`. Proyecto Python con `uv`, **solo Python 3.14** (`.python-version` y `requires-python = ">=3.14,<3.15"`; no uses otra versión). Código en `src/spec_to_runtime`, tests en `tests/`.

```bash
uv sync                         # instalar dependencias
uv run pytest                   # todos los tests
uv run pytest tests/test_x.py::test_y   # un solo test
uv run ruff check . && uv run ruff format --check .   # lint / formato
```

Terraform (`infra/`, state remoto en S3; el bucket se crea una vez desde `infra/bootstrap/` con state local):

```bash
terraform -chdir=infra/bootstrap init && terraform -chdir=infra/bootstrap apply   # solo la primera vez
terraform -chdir=infra init && terraform -chdir=infra validate && terraform -chdir=infra plan
```

Agente en AgentCore Runtime (contenedor arm64, Python 3.14; el zip de AgentCore no admite 3.14):

```bash
scripts/deploy_agent.sh                                   # construye y sube la imagen a ECR (exige commit)
terraform -chdir=infra apply -var agent_image_tag=<hash>  # crea o actualiza el Runtime
```

Web (`web/`, estática, sin compilar): `cd web && node --test` corre los tests del renderizador de Markdown (protegen contra XSS). `terraform -chdir=infra apply` sube los archivos a S3 y genera `config.js`; la dirección pública sale de `terraform -chdir=infra output web_url`. Para probar en local copia `web/config.example.js` a `web/config.js` y añade tu origen a `web_origins_extra` (CORS).

Prueba de humo de punta a punta contra la API real (11 comprobaciones; se limpia sola y sirve de calentamiento): `uv run python scripts/smoke_test.py`. Tras `scripts/deploy_agent.sh`, haz commit de `infra/agent_image.auto.tfvars`: versiona la imagen desplegada.

Sincronizar el repositorio con la Knowledge Base: `aws lambda invoke --function-name spec-to-runtime-sync --payload '{}' --cli-binary-format raw-in-base64-out out.json`. Scripts sueltos: `PYTHONPATH=src uv run python ...` (el `.pth` oculto de macOS impide importar el paquete).

Aún no hay comando de arranque local del agente; agrégalos aquí en el mismo cambio que los introduce. Detalle del ambiente en `docs/charla/preparacion-ambiente.md`.
