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
