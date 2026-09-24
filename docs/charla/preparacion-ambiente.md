# Preparación del ambiente

## Decisiones

- **Región única:** `us-east-1` para todo (Terraform, Bedrock, AgentCore).
- **State de Terraform:** bucket S3 `spec-to-runtime-tfstate-<account-id>` con versionado, cifrado AES256 y bloqueo de acceso público. Locking nativo de S3 (`use_lockfile`, Terraform >= 1.10), sin DynamoDB.
- **Python:** proyecto `uv` (`pyproject.toml`) con `strands-agents` y `bedrock-agentcore`; dev: `pytest`, `ruff`.
- **Plugins:** `aws-agents` viene del marketplace `aws/agent-toolkit-for-aws` (`claude plugin marketplace add aws/agent-toolkit-for-aws`), instalado con scope project.

## Bootstrap del state (huevo y gallina)

El bucket del state no puede crearse con el state que aloja. `infra/bootstrap/` usa state local y se aplica una sola vez; luego `infra/` usa el backend S3. El state local del bootstrap no se versiona.

## Estado

- Bucket del state creado con `infra/bootstrap` (4 recursos, 2026-09-23) y backend S3 de `infra/` inicializado.

## Aprendizajes / dolores

- El AWS CLI instalado (2.15) es viejo: no tiene `bedrock list-inference-profiles` ni `get-foundation-model-availability`. Actualizarlo antes de depurar acceso a modelos.
- `terraform` MCP probado: `get_latest_provider_version` devolvió el provider `aws` 6.66.0.
- `claude plugin list` muestra `aiup-core` varias veces, pero no es un duplicado: es una instalación por proyecto (scope project). Este repo está en 2.5.4; solo `Perfumeria` sigue en 2.5.3.
- Falta confirmar acceso real al modelo de Bedrock que use el agente (los modelos Anthropic aparecen listados en us-east-1).
