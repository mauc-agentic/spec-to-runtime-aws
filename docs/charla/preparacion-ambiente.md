# Preparación del ambiente

## Decisiones

- **Región única:** `us-east-1` para todo (Terraform, Bedrock, AgentCore).
- **State de Terraform:** bucket S3 `spec-to-runtime-tfstate-<account-id>` con versionado, cifrado AES256 y bloqueo de acceso público. Locking nativo de S3 (`use_lockfile`, Terraform >= 1.10), sin DynamoDB.
- **Python:** proyecto `uv` (`pyproject.toml`) con `strands-agents` y `bedrock-agentcore`; dev: `pytest`, `ruff`.
- **Plugins:** `aws-agents` viene del marketplace `aws/agent-toolkit-for-aws` (`claude plugin marketplace add aws/agent-toolkit-for-aws`), instalado con scope project.

## Bootstrap del state (huevo y gallina)

El bucket del state no puede crearse con el state que aloja. `infra/bootstrap/` usa state local y se aplica una sola vez; luego `infra/` usa el backend S3. El state local del bootstrap no se versiona.

## Aprendizajes / dolores

- El AWS CLI instalado (2.15) es viejo: no tiene `bedrock list-inference-profiles` ni `get-foundation-model-availability`. Actualizarlo antes de depurar acceso a modelos.
- `terraform` MCP probado: `get_latest_provider_version` devolvió el provider `aws` 6.66.0.
- `claude plugin list` mostraba `aiup-core` duplicado en scope project (2.5.3 y 2.5.4).
- Falta confirmar acceso real al modelo de Bedrock que use el agente (los modelos Anthropic aparecen listados en us-east-1).
