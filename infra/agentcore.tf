# Runtime y Memory de AgentCore para el agente (FR-002, FR-010, FR-018, UC-005).
# El Runtime se despliega como contenedor (linux/arm64, Python 3.14): el despliegue por zip solo
# admite Python 3.10 a 3.13. Despliegue en dos pasos porque el Runtime exige que la imagen exista:
#   1) terraform apply                          -> ECR, Memory y rol
#   2) scripts/deploy_agent.sh                  -> construye y sube la imagen
#   3) terraform apply -var agent_image_tag=... -> crea o actualiza el Runtime

resource "aws_ecr_repository" "agent" {
  # checkov:skip=CKV_AWS_136:Cifrado AES256 por defecto; una CMK de KMS añade costo fijo (NFR-012)
  name                 = "${local.name}-agent"
  image_tag_mutability = "IMMUTABLE" # cada imagen lleva el hash de git como etiqueta
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las 5 imágenes más recientes (costo de almacenamiento)"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# Memoria de corto plazo: solo eventos de la conversación, sin estrategias de largo plazo
# (fuera de alcance en la visión). La retención mínima de la plataforma es de 7 días; el límite
# de 24 h de UC-005 BR-002 lo aplica la lógica de sesión, no este recurso.
resource "aws_bedrockagentcore_memory" "agent" {
  # checkov:skip=CKV_AWS_338:Retención mínima de 7 días impuesta por la plataforma
  name                  = "${replace(local.name, "-", "_")}_memory"
  description           = "Memoria de corto plazo de las conversaciones (UC-005)"
  event_expiry_duration = 7
}

resource "aws_iam_role" "agent" {
  name = "${local.name}-agent-runtime"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:bedrock-agentcore:${var.region}:${data.aws_caller_identity.current.account_id}:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "agent" {
  name = "agent-runtime"
  role = aws_iam_role.agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid      = "EcrPull"
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
        Resource = aws_ecr_repository.agent.arn
      },
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = [
          "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
          "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
        ]
      },
      {
        # Nova 2 Lite por su perfil de inferencia entre regiones (us.*) y el modelo base.
        Sid    = "Model"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = [
          "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.amazon.nova-2-lite-v1:0",
          "arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0",
        ]
      },
      {
        Sid      = "Guardrail"
        Effect   = "Allow"
        Action   = ["bedrock:ApplyGuardrail"]
        Resource = aws_bedrock_guardrail.agent.guardrail_arn
      },
      {
        Sid      = "KnowledgeBase"
        Effect   = "Allow"
        Action   = ["bedrock:Retrieve"]
        Resource = aws_bedrockagent_knowledge_base.repo.arn
      },
      {
        Sid    = "Memory"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:ListEvents",
          "bedrock-agentcore:DeleteEvent",
          "bedrock-agentcore:ListSessions",
          "bedrock-agentcore:ListActors",
        ]
        Resource = aws_bedrockagentcore_memory.agent.arn
      },
      {
        # Trazas y métricas de AgentCore Observability (ADOT dentro del contenedor).
        Sid    = "XRay"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets",
        ]
        Resource = "*"
      },
      {
        Sid       = "AgentCoreMetrics"
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" } }
      },
      {
        Sid      = "DescribeLogGroups"
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:*"
      },
      {
        # FR-012: las herramientas del Ponente se ejecutan en el Gateway; el agente ya no lee DynamoDB.
        Sid      = "Gateway"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:InvokeGateway"]
        Resource = aws_bedrockagentcore_gateway.tools.gateway_arn
      },
    ]
  })
}

variable "agent_image_tag" {
  description = "Etiqueta de la imagen del agente en ECR (hash de git). Vacía: aún no se crea el Runtime"
  type        = string
  default     = ""
}

resource "aws_bedrockagentcore_agent_runtime" "agent" {
  count = var.agent_image_tag == "" ? 0 : 1

  agent_runtime_name = "${replace(local.name, "-", "_")}_agent"
  description        = "Agente Pregúntale al repo (Strands, Python 3.14)"
  role_arn           = aws_iam_role.agent.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agent.repository_url}:${var.agent_image_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  # Se invoca solo desde la Lambda orquestadora con IAM (SigV4): no hay autorizador JWT.
  environment_variables = {
    KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.repo.id
    GUARDRAIL_ID      = aws_bedrock_guardrail.agent.guardrail_id
    GUARDRAIL_VERSION = aws_bedrock_guardrail_version.agent.version
    REQUESTS_TABLE    = aws_dynamodb_table.requests.name
    MEMORY_ID         = aws_bedrockagentcore_memory.agent.id
    GATEWAY_URL       = aws_bedrockagentcore_gateway.tools.gateway_url
  }

  # Las sesiones inactivas liberan su microVM pronto: solo se paga el uso (NFR-012).
  lifecycle_configuration {
    idle_runtime_session_timeout = 300
    max_lifetime                 = 3600
  }

  depends_on = [aws_iam_role_policy.agent]
}
