# IaC: Terraform

## Decisión

La infraestructura de este proyecto se define con **Terraform** (se descartó CDK).

## MCP de apoyo

Se registró `terraform` en `.mcp.json`: `hashicorp/terraform-mcp-server` ejecutado con Docker y solo el toolset `registry` (consulta de providers y módulos del Terraform Registry). No usa `TFE_TOKEN`, así que no toca HCP Terraform ni workspaces.

- **Por qué:** que el agente lea la documentación real de los recursos `aws_*` en lugar de inventar atributos de memoria.
- **Requisito:** Docker instalado y en ejecución.
- **Pendiente:** no se ha probado contra una invocación real; validar la primera vez que se escriba código Terraform.
