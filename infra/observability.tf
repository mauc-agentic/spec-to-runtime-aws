# Observabilidad: trazas de punta a punta (X-Ray + OpenTelemetry) visibles en CloudWatch
# (Application Signals, Transaction Search y GenAI Observability de AgentCore).
#
# Flujo de la traza:  Lambda api -> SQS (AWSTraceHeader) -> Lambda orquestadora -> AgentCore Runtime.
# Las API HTTP de API Gateway no admiten X-Ray, así que la traza nace en la Lambda api.
#
# La política de recursos que permite a X-Ray escribir en `aws/spans` la crea y protege el propio
# servicio al activar Transaction Search ("XRayToLogsIngestion_DO-NOT-EDIT"), por eso no se gestiona aquí.

# Transaction Search: los spans llegan a CloudWatch Logs (`aws/spans`) y se pueden buscar y filtrar.
resource "aws_xray_trace_segment_destination" "spans" {
  destination = "CloudWatchLogs"
}

# Por defecto solo se indexa el 1 % de las trazas. Con el volumen de la charla (unos miles de
# preguntas) se indexan todas para poder buscar cualquiera por su request_id.
resource "aws_xray_indexing_rule" "default" {
  name = "Default"

  rule {
    probabilistic {
      desired_sampling_percentage = 100
    }
  }
}

# Lambda traza por defecto 1 solicitud por segundo y el 5 % del resto: aquí se trazan todas.
resource "aws_xray_sampling_rule" "all" {
  rule_name      = "${local.name}-all"
  priority       = 1
  version        = 1
  reservoir_size = 5
  fixed_rate     = 1.0
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"
}

# Permiso de las Lambdas para enviar segmentos a X-Ray.
locals {
  traced_lambda_roles = {
    api          = aws_iam_role.api.name
    orchestrator = aws_iam_role.orchestrator.name
    sync         = aws_iam_role.sync.name
    pre_signup   = aws_iam_role.pre_signup.name
  }
}

resource "aws_iam_role_policy_attachment" "xray" {
  for_each = local.traced_lambda_roles

  role       = each.value
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# --- AgentCore Memory: logs y trazas propios del servicio ------------------------------------------
# Las llamadas a la memoria ya aparecen como spans dentro de la traza del agente; esto añade los
# registros y trazas que emite el propio servicio (pestaña "Memoria" de la consola de AgentCore).
resource "aws_cloudwatch_log_group" "memory" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/vendedlogs/bedrock-agentcore/memory/APPLICATION_LOGS/${aws_bedrockagentcore_memory.agent.id}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_delivery_source" "memory_logs" {
  name         = "${local.name}-memory-logs"
  log_type     = "APPLICATION_LOGS"
  resource_arn = aws_bedrockagentcore_memory.agent.arn
}

resource "aws_cloudwatch_log_delivery_destination" "memory_logs" {
  name = "${local.name}-memory-logs"

  delivery_destination_configuration {
    destination_resource_arn = aws_cloudwatch_log_group.memory.arn
  }
}

resource "aws_cloudwatch_log_delivery" "memory_logs" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.memory_logs.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.memory_logs.arn
}

resource "aws_cloudwatch_log_delivery_source" "memory_traces" {
  name         = "${local.name}-memory-traces"
  log_type     = "TRACES"
  resource_arn = aws_bedrockagentcore_memory.agent.arn
}

resource "aws_cloudwatch_log_delivery_destination" "memory_traces" {
  name                      = "${local.name}-memory-traces"
  delivery_destination_type = "XRAY"
}

resource "aws_cloudwatch_log_delivery" "memory_traces" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.memory_traces.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.memory_traces.arn
}
