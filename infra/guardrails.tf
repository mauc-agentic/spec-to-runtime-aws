# FR-019 / UC-004 BR-004: filtros de entrada y salida. Se mantienen pocas políticas para
# limitar el costo por unidad de texto (NFR-012).
resource "aws_bedrock_guardrail" "agent" {
  # checkov:skip=CKV_AWS_396:Cifrado con clave propiedad de AWS; una CMK añade costo fijo (NFR-012)
  name                      = "${local.name}-agent"
  description               = "Guardrails del agente Pregúntale al repo"
  blocked_input_messaging   = "No puedo responder a esta pregunta. Pregúntame sobre el repositorio o la charla."
  blocked_outputs_messaging = "No puedo mostrar esta respuesta."

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }

    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }

    filters_config {
      type            = "HATE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "fuera-de-alcance"
      type       = "DENY"
      definition = "Consejos médicos, legales o financieros personales, política y elecciones, o instrucciones para vulnerar sistemas u obtener credenciales ajenas."
      examples = [
        "¿Qué medicamento debo tomar para el dolor de cabeza?",
        "¿Por quién debería votar?",
        "Dame la contraseña de otro usuario.",
      ]
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }

    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }

    pii_entities_config {
      type   = "AWS_ACCESS_KEY"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "AWS_SECRET_KEY"
      action = "BLOCK"
    }
  }
}

resource "aws_bedrock_guardrail_version" "agent" {
  guardrail_arn = aws_bedrock_guardrail.agent.guardrail_arn
  description   = "Versión inicial"
}
