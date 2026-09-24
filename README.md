# spec-to-runtime-aws

Repositorio de la charla del **2026-09-26** que documenta paso a paso cómo llevar una especificación hasta un runtime en AWS (Python + Strands Agents en Bedrock AgentCore, infraestructura con Terraform). Se sigue [AIUP (AI Unified Process)](https://unifiedprocess.ai): la especificación es la fuente de verdad y el código se deriva de ella.

- `docs/`: artefactos AIUP (visión, requisitos, modelo de entidades, casos de uso).
- `docs/charla/`: aprendizajes, buenas prácticas y dolores de la charla.
- `docs/faq.md`: preguntas frecuentes (qué es AIUP, cuánto cuesta la demo, cómo protege las respuestas, perfiles e instalación).
- `CLAUDE.md`: guía de flujo de trabajo para Claude Code.

## Cómo instalar las dependencias y correr los tests

Requisitos: **Python 3.14** (única versión soportada), [`uv`](https://docs.astral.sh/uv/), Node.js (solo para los tests de la web), y para desplegar: Terraform 1.10 o superior, Docker y credenciales de AWS en `us-east-1`.

```bash
uv sync                                                # instala las dependencias de Python
uv run pytest                                          # todos los tests
uv run pytest tests/test_x.py::test_y                  # un solo test
uv run ruff check . && uv run ruff format --check .    # lint y formato
cd web && node --test                                  # tests de la web (renderizador de Markdown)
```

Infraestructura y despliegue (detalle en `CLAUDE.md` y `docs/charla/`):

```bash
cp infra/backend.hcl.example infra/backend.hcl          # bucket del estado (lleva el ID de tu cuenta)
cp infra/terraform.tfvars.example infra/terraform.tfvars  # correo de las alertas de presupuesto
terraform -chdir=infra init -backend-config=backend.hcl && terraform -chdir=infra plan
scripts/deploy_agent.sh                                 # construye y sube la imagen del agente
uv run python scripts/smoke_test.py                     # prueba de humo contra la API desplegada
```
