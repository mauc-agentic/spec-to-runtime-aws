# NFR-012 / NFR-014: presupuesto de 50 USD con alertas. La cuenta aloja otros proyectos,
# por eso el presupuesto se filtra por la etiqueta `project` (default_tags del provider).
#
# La etiqueta de costo solo existe en Facturación después de que haya recursos etiquetados
# (hasta 24 h). Hasta entonces `activate_cost_allocation_tag` queda en false, y el
# presupuesto existe pero no ve gasto; luego se pasa a true y se vuelve a aplicar.
resource "aws_ce_cost_allocation_tag" "project" {
  count = var.activate_cost_allocation_tag ? 1 : 0

  tag_key = "project"
  status  = "Active"
}

resource "aws_budgets_budget" "project" {
  name         = "${local.name}-${var.budget_usd}usd"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:project$spec-to-runtime-aws"]
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alert_email]
    }
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
