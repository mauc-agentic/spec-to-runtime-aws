variable "region" {
  description = "Región AWS única para todo el proyecto"
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Correo que recibe las alertas de presupuesto"
  type        = string
  default     = "migueluribe.ing@gmail.com"
}

variable "budget_usd" {
  description = "Presupuesto duro del proyecto en USD (NFR-012)"
  type        = number
  default     = 50
}

variable "max_accounts" {
  description = "Máximo de cuentas de participantes (UC-001 BR-007)"
  type        = number
  default     = 100
}

variable "activate_cost_allocation_tag" {
  description = "Activar la etiqueta de costo `project`; solo funciona ~24 h después de crear recursos etiquetados"
  type        = bool
  default     = false
}
