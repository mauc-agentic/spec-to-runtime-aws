variable "region" {
  description = "Región AWS única para todo el proyecto"
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Correo que recibe las alertas de presupuesto. Sin valor por defecto: el repositorio es público; va en infra/terraform.tfvars (local, ignorado por git; ver terraform.tfvars.example)"
  type        = string
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

variable "github_repo" {
  description = "Repositorio público cuyo contenido carga UC-003 (propietario/nombre)"
  type        = string
  default     = "mauc-agentic/spec-to-runtime-aws"
}

variable "budget_filter_by_tag" {
  description = "Acotar el presupuesto a la etiqueta `project`; solo funciona cuando la etiqueta de costo ya está activa"
  type        = bool
  default     = false
}

variable "budget_cutoff_percent" {
  description = "Porcentaje del presupuesto al que se corta la invocación de modelos (NFR-014)"
  type        = number
  default     = 90
}
