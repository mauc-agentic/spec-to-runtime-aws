# Imagen del agente para AgentCore Runtime (linux/arm64, Python 3.14).
# Se usa contenedor porque el despliegue por zip de AgentCore solo admite Python 3.10 a 3.13.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# Dependencias primero: esta capa solo se reconstruye si cambian pyproject.toml o uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
ENV PYTHONPATH=/app/src PATH="/app/.venv/bin:$PATH"

RUN useradd --system --no-create-home agent
USER agent

# AgentCore Runtime exige el puerto 8080 con /invocations (POST) y /ping (GET).
EXPOSE 8080
# El distro de OpenTelemetry de AWS instrumenta el agente (Strands, boto3, HTTP) sin cambiar el
# código: cada consulta, llamada al modelo y herramienta aparece como un span en CloudWatch.
CMD ["opentelemetry-instrument", "python", "-m", "spec_to_runtime.agent.app"]
