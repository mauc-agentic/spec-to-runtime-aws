# Historial de conversaciones, análisis del Ponente y cuotas (FR-022, NFR-013).
# On-demand: se paga por uso, sin costo fijo.

# Una fila por consulta (AGENT_REQUEST + AGENT_RESULT). El texto parcial de la respuesta
# se va escribiendo aquí mientras el navegador consulta (polling con avance parcial).
resource "aws_dynamodb_table" "requests" {
  # checkov:skip=CKV_AWS_119:SSE con clave propiedad de AWS; una CMK de KMS añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_28:Sin PITR; el historial se borra al destruir el entorno (UC-006 BR-004)
  name         = "${local.name}-requests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "request_sk"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "request_sk"
    type = "S"
  }

  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "day"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  # Buscar una consulta por su identificador (polling del navegador y trazabilidad).
  global_secondary_index {
    name = "by_request_id"

    key_schema {
      attribute_name = "request_id"
      key_type       = "HASH"
    }

    projection_type = "ALL"
  }

  # Preguntas de un día en orden cronológico (top 10 del Ponente, UC-007).
  global_secondary_index {
    name = "by_day"

    key_schema {
      attribute_name = "day"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "created_at"
      key_type       = "RANGE"
    }

    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false
  }
}

# Contadores de cuota: una fila por usuario y día, más una global (UC-004 BR-005/BR-006).
resource "aws_dynamodb_table" "usage" {
  # checkov:skip=CKV_AWS_119:SSE con clave propiedad de AWS; una CMK de KMS añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_28:Sin PITR; son contadores del evento, no datos a recuperar
  name         = "${local.name}-usage"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "scope"
  range_key    = "usage_date"

  attribute {
    name = "scope"
    type = "S"
  }

  attribute {
    name = "usage_date"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false
  }
}
