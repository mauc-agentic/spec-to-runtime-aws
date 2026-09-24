# API y orquestador (FR-010, FR-011, UC-004): web -> API Gateway (JWT de Cognito) -> Lambda api
# -> SQS -> Lambda orquestadora -> AgentCore Runtime. El navegador consulta el resultado cada ~1 s.

# Un solo paquete con el código de las tres Lambdas (sync, api y orquestador). Sin el agente
# (va en el contenedor) ni el trigger de Cognito (tiene su propio paquete).
data "archive_file" "app" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/.build/app.zip"
  excludes = [
    "spec_to_runtime/agent/**",
    "spec_to_runtime/auth/**",
    # Los .pyc dependen de la máquina y cambiarían el hash del paquete entre equipos.
    "**/__pycache__/**",
  ]
}

variable "web_origins" {
  description = "Orígenes web permitidos por CORS; se ajusta al dominio de CloudFront cuando exista"
  type        = list(string)
  default     = ["*"]
}

variable "project_cap" {
  description = "Tope de consultas del proyecto (NFR-013)"
  type        = number
  default     = 3000
}

locals {
  agent_runtime_arn = try(one(aws_bedrockagentcore_agent_runtime.agent[*].agent_runtime_arn), "")
}

# --- Cola -------------------------------------------------------------------------------------

resource "aws_sqs_queue" "requests_dlq" {
  name                      = "${local.name}-requests-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "requests" {
  name = "${local.name}-requests"
  # AWS recomienda al menos 6 veces el timeout de la Lambda consumidora (90 s).
  visibility_timeout_seconds = 540
  message_retention_seconds  = 3600
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.requests_dlq.arn
    maxReceiveCount     = 3
  })
}

# --- Lambda api -------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 14
}

resource "aws_iam_role" "api" {
  name = "${local.name}-api"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api" {
  name = "api"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
        Resource = aws_dynamodb_table.requests.arn
      },
      {
        # Las transacciones de cuota actualizan contadores; no hace falta leer ni borrar.
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.usage.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.requests.arn
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.sync.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "api" {
  # checkov:skip=CKV_AWS_117:Fuera de VPC a propósito: una VPC exigiría NAT (costo fijo, NFR-012)
  # checkov:skip=CKV_AWS_116:Sin DLQ; la invoca API Gateway de forma síncrona y el cliente ve el error
  # checkov:skip=CKV_AWS_173:Variables sin CMK; no contienen secretos
  # checkov:skip=CKV_AWS_272:Sin firma de código; el paquete lo genera Terraform desde este repo
  # checkov:skip=CKV_AWS_115:Sin límite de concurrencia; el throttling de API Gateway y las cuotas ya acotan el uso
  # checkov:skip=CKV_AWS_50:Sin X-Ray; los logs de CloudWatch bastan para el evento
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.14"
  handler          = "spec_to_runtime.api.handler.handler"
  filename         = data.archive_file.app.output_path
  source_code_hash = data.archive_file.app.output_base64sha256
  timeout          = 29 # API Gateway corta a los 30 s
  memory_size      = 256

  environment {
    variables = {
      REQUESTS_TABLE = aws_dynamodb_table.requests.name
      USAGE_TABLE    = aws_dynamodb_table.usage.name
      QUEUE_URL      = aws_sqs_queue.requests.url
      SYNC_FUNCTION  = aws_lambda_function.sync.function_name
      PROJECT_CAP    = tostring(var.project_cap)
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

# --- Lambda orquestadora ----------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "orchestrator" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/lambda/${local.name}-orchestrator"
  retention_in_days = 14
}

resource "aws_iam_role" "orchestrator" {
  name = "${local.name}-orchestrator"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "orchestrator" {
  name = "orchestrator"
  role = aws_iam_role.orchestrator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.requests.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.usage.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.requests.arn
      },
      {
        Effect = "Allow"
        Action = ["bedrock-agentcore:InvokeAgentRuntime"]
        Resource = [
          local.agent_runtime_arn,
          "${local.agent_runtime_arn}/runtime-endpoint/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.orchestrator.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "orchestrator" {
  # checkov:skip=CKV_AWS_117:Fuera de VPC a propósito: una VPC exigiría NAT (costo fijo, NFR-012)
  # checkov:skip=CKV_AWS_116:La cola tiene su propia DLQ con reintentos; la Lambda no necesita otra
  # checkov:skip=CKV_AWS_173:Variables sin CMK; no contienen secretos
  # checkov:skip=CKV_AWS_272:Sin firma de código; el paquete lo genera Terraform desde este repo
  # checkov:skip=CKV_AWS_115:La concurrencia se limita en el mapeo de eventos (maximum_concurrency), que protege el presupuesto
  # checkov:skip=CKV_AWS_50:Sin X-Ray; los logs de CloudWatch bastan para el evento
  function_name    = "${local.name}-orchestrator"
  role             = aws_iam_role.orchestrator.arn
  runtime          = "python3.14"
  handler          = "spec_to_runtime.orchestrator.handler.handler"
  filename         = data.archive_file.app.output_path
  source_code_hash = data.archive_file.app.output_base64sha256
  timeout          = 90 # UC-004 BR-007: la solicitud falla a los 60 s; el resto es margen para cerrar
  memory_size      = 256

  environment {
    variables = {
      REQUESTS_TABLE    = aws_dynamodb_table.requests.name
      USAGE_TABLE       = aws_dynamodb_table.usage.name
      AGENT_RUNTIME_ARN = local.agent_runtime_arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.orchestrator]
}

resource "aws_lambda_event_source_mapping" "orchestrator" {
  event_source_arn        = aws_sqs_queue.requests.arn
  function_name           = aws_lambda_function.orchestrator.arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]

  # Como mucho 10 consultas a la vez: acota el gasto y evita saturar Bedrock (NFR-012).
  scaling_config {
    maximum_concurrency = 10
  }
}

# --- API Gateway ------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api_access" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = 14
}

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.web_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  name             = "cognito"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "routes" {
  for_each = toset([
    "POST /questions",
    "GET /requests/{request_id}",
    "GET /sessions",
    "GET /sessions/{session_id}",
    "POST /admin/sync",
    "GET /admin/sync",
  ])

  api_id             = aws_apigatewayv2_api.main.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  # Techo de tráfico: 50 personas preguntando a la vez con margen, y protección del presupuesto.
  default_route_settings {
    throttling_burst_limit = 40
    throttling_rate_limit  = 20
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId = "$context.requestId"
      routeKey  = "$context.routeKey"
      status    = "$context.status"
      latencyMs = "$context.responseLatency"
      error     = "$context.error.message"
    })
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
