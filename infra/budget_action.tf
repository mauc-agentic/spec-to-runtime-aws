# NFR-014: al llegar al 90 % del presupuesto, AWS Budgets adjunta una política que NIEGA invocar
# modelos, guardrails, la Knowledge Base y el Runtime a los roles del agente y del orquestador.
#
# Importante: Facturación tiene un retraso de 8 a 24 horas, así que esto es la red de seguridad de
# último recurso, no una protección en tiempo real. La protección en tiempo real son las cuotas de
# la API (NFR-013): 25 preguntas por participante y día y 3.000 en total.
#
# Para levantar el corte después de revisar el gasto:
#   aws iam detach-role-policy --role-name <rol> --policy-arn <arn de spec-to-runtime-budget-cutoff>

resource "aws_iam_policy" "budget_cutoff" {
  name        = "${local.name}-budget-cutoff"
  description = "Niega lo que cuesta dinero cuando se agota el presupuesto (NFR-014)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "CutOffSpend"
      Effect = "Deny"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ApplyGuardrail",
        "bedrock:Retrieve",
        "bedrock-agentcore:InvokeAgentRuntime",
      ]
      Resource = "*"
    }]
  })
}

locals {
  cutoff_roles = [aws_iam_role.agent.name, aws_iam_role.orchestrator.name]
}

# Rol que asume AWS Budgets para adjuntar la política; solo puede adjuntar y quitar ESA política
# a ESOS dos roles.
resource "aws_iam_role" "budget_action" {
  name = "${local.name}-budget-action"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "budgets.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "budget_action" {
  name = "attach-cutoff"
  role = aws_iam_role.budget_action.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
      Resource = [aws_iam_role.agent.arn, aws_iam_role.orchestrator.arn]
      Condition = {
        StringEquals = { "iam:PolicyARN" = aws_iam_policy.budget_cutoff.arn }
      }
    }]
  })
}

resource "aws_budgets_budget_action" "cutoff" {
  budget_name        = aws_budgets_budget.project.name
  action_type        = "APPLY_IAM_POLICY"
  approval_model     = "AUTOMATIC"
  notification_type  = "ACTUAL"
  execution_role_arn = aws_iam_role.budget_action.arn

  action_threshold {
    action_threshold_type  = "PERCENTAGE"
    action_threshold_value = var.budget_cutoff_percent
  }

  definition {
    iam_action_definition {
      policy_arn = aws_iam_policy.budget_cutoff.arn
      roles      = local.cutoff_roles
    }
  }

  subscriber {
    subscription_type = "EMAIL"
    address           = var.alert_email
  }

  depends_on = [aws_iam_role_policy.budget_action]
}
