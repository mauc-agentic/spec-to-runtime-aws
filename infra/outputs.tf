output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "event_secret_arn" {
  description = "Secreto con el código del evento; léelo con `aws secretsmanager get-secret-value`"
  value       = aws_secretsmanager_secret.event.arn
}

output "requests_table" {
  value = aws_dynamodb_table.requests.name
}

output "usage_table" {
  value = aws_dynamodb_table.usage.name
}

output "knowledge_base_id" {
  value = aws_bedrockagent_knowledge_base.repo.id
}

output "data_source_id" {
  value = aws_bedrockagent_data_source.repo.data_source_id
}

output "docs_bucket" {
  value = aws_s3_bucket.docs.id
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.agent.guardrail_id
}

output "guardrail_version" {
  value = aws_bedrock_guardrail_version.agent.version
}

output "sync_function" {
  description = "Lambda de UC-003; invócala con `aws lambda invoke` hasta que exista la API"
  value       = aws_lambda_function.sync.function_name
}

output "agent_ecr_repository" {
  value = aws_ecr_repository.agent.repository_url
}

output "memory_id" {
  value = aws_bedrockagentcore_memory.agent.id
}

output "agent_runtime_arn" {
  description = "Vacío hasta que se despliegue la imagen (agent_image_tag)"
  value       = one(aws_bedrockagentcore_agent_runtime.agent[*].agent_runtime_arn)
}
