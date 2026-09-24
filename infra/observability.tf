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
