# FR-012 AgentCore Gateway: las herramientas del Ponente (buscar_documentos, top_preguntas y
# actividad_participantes) viven en una Lambda que el Gateway expone por MCP. El agente ya no toca
# DynamoDB: solo puede llamar al Gateway con su rol (autorizador AWS_IAM, sin JWT: el rol Ponente lo
# valida la API con Cognito y el agente solo entrega las herramientas a ese rol, UC-007 BR-001).
# Costo: sin recursos de costo fijo, se paga por llamada (NFR-012).

resource "aws_cloudwatch_log_group" "tools" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/lambda/${local.name}-tools"
  retention_in_days = 14
}

resource "aws_iam_role" "tools" {
  name = "${local.name}-tools"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "tools" {
  name = "tools"
  role = aws_iam_role.tools.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TopQuestions"
        Effect = "Allow"
        Action = ["dynamodb:Query"]
        Resource = [
          aws_dynamodb_table.requests.arn,
          "${aws_dynamodb_table.requests.arn}/index/by_day",
        ]
      },
      {
        # El análisis agrupa las preguntas con una llamada aparte a Nova 2 Lite.
        Sid    = "Model"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
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
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.tools.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "tools" {
  # checkov:skip=CKV_AWS_117:Fuera de VPC a propósito: una VPC exigiría NAT (costo fijo, NFR-012)
  # checkov:skip=CKV_AWS_116:Sin DLQ; la invoca el Gateway de forma síncrona y el agente ve el error
  # checkov:skip=CKV_AWS_173:Variables sin CMK; no contienen secretos
  # checkov:skip=CKV_AWS_272:Sin firma de código; el paquete lo genera Terraform desde este repo
  # checkov:skip=CKV_AWS_115:Sin límite de concurrencia; la cuota de la API (NFR-013) ya acota el uso
  function_name    = "${local.name}-tools"
  role             = aws_iam_role.tools.arn
  runtime          = "python3.14"
  handler          = "spec_to_runtime.tools.handler.handler"
  filename         = data.archive_file.app.output_path
  source_code_hash = data.archive_file.app.output_base64sha256
  timeout          = 60 # UC-004 BR-007: la solicitud completa falla a los 60 s
  memory_size      = 256

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.repo.id
      GUARDRAIL_ID      = aws_bedrock_guardrail.agent.guardrail_id
      GUARDRAIL_VERSION = aws_bedrock_guardrail_version.agent.version
      REQUESTS_TABLE    = aws_dynamodb_table.requests.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.tools, aws_iam_role_policy.tools]
}

# Rol que asume el Gateway para invocar la Lambda.
resource "aws_iam_role" "gateway" {
  name = "${local.name}-gateway"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "gateway" {
  name = "invoke-tools"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.tools.arn
    }]
  })
}

resource "aws_bedrockagentcore_gateway" "tools" {
  name        = "${local.name}-tools"
  description = "Herramientas del Ponente para el agente (FR-012)"
  role_arn    = aws_iam_role.gateway.arn

  authorizer_type = "AWS_IAM"
  protocol_type   = "MCP"

  depends_on = [aws_iam_role_policy.gateway]
}

resource "aws_bedrockagentcore_gateway_target" "speaker" {
  # El nombre del target es el prefijo de cada herramienta: `ponente___top_preguntas`.
  name               = "ponente"
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id
  description        = "Búsqueda de documentos y análisis de preguntas, solo para el Ponente"

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.tools.arn

        tool_schema {
          inline_payload {
            name        = "buscar_documentos"
            description = "Busca en los documentos del repositorio y devuelve fragmentos con su enlace"

            input_schema {
              type = "object"

              property {
                name        = "consulta"
                type        = "string"
                description = "Texto a buscar"
                required    = true
              }
            }
          }

          inline_payload {
            name        = "top_preguntas"
            description = "Top 10 de preguntas más frecuentes de los participantes, agrupadas por tema"

            input_schema {
              type = "object"

              property {
                name        = "periodo_horas"
                type        = "integer"
                description = "Horas hacia atrás a analizar; 0 significa todo el evento"
              }
            }
          }

          inline_payload {
            name        = "actividad_participantes"
            description = "Resumen anónimo de la actividad: preguntas, participantes, hora pico y perfiles"

            input_schema {
              type = "object"

              property {
                name        = "periodo_horas"
                type        = "integer"
                description = "Horas hacia atrás a analizar; 0 significa todo el evento"
              }
            }
          }
        }
      }
    }
  }
}
