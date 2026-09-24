# UC-003 Sincronizar documentos del repositorio: Lambda que copia la rama main de GitHub al
# bucket de documentos y lanza la ingesta de la Knowledge Base. El rol Ponente se comprueba
# antes, en la API (UC-003 A1); hasta que exista la API se invoca con `aws lambda invoke`.

data "archive_file" "sync" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/.build/sync.zip"
  excludes = [
    "spec_to_runtime/agent",
    "spec_to_runtime/agent/*",
    "spec_to_runtime/auth",
    "spec_to_runtime/auth/*",
    # Los .pyc dependen de la máquina y cambiarían el hash del paquete entre equipos.
    "spec_to_runtime/__pycache__",
    "spec_to_runtime/__pycache__/*",
    "spec_to_runtime/sync/__pycache__",
    "spec_to_runtime/sync/__pycache__/*",
  ]
}

resource "aws_cloudwatch_log_group" "sync" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/lambda/${local.name}-sync"
  retention_in_days = 14
}

resource "aws_iam_role" "sync" {
  name = "${local.name}-sync"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "sync" {
  name = "sync"
  role = aws_iam_role.sync.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.docs.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.docs.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs",
        ]
        Resource = aws_bedrockagent_knowledge_base.repo.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.sync.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "sync" {
  # checkov:skip=CKV_AWS_117:Fuera de VPC a propósito: una VPC exigiría NAT (costo fijo, NFR-012) y GitHub es público
  # checkov:skip=CKV_AWS_116:Sin DLQ; la invoca el Ponente y ve el error al instante
  # checkov:skip=CKV_AWS_173:Variables sin CMK; no contienen secretos
  # checkov:skip=CKV_AWS_272:Sin firma de código; el paquete lo genera Terraform desde este repo
  # checkov:skip=CKV_AWS_115:Sin límite de concurrencia; Bedrock ya impide dos ingestas a la vez (UC-003 BR-007)
  # checkov:skip=CKV_AWS_50:Sin X-Ray; los logs de CloudWatch bastan para el evento
  function_name    = "${local.name}-sync"
  role             = aws_iam_role.sync.arn
  runtime          = "python3.14"
  handler          = "spec_to_runtime.sync.handler.handler"
  filename         = data.archive_file.sync.output_path
  source_code_hash = data.archive_file.sync.output_base64sha256
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      DOCS_BUCKET       = aws_s3_bucket.docs.id
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.repo.id
      DATA_SOURCE_ID    = aws_bedrockagent_data_source.repo.data_source_id
      REPO              = var.github_repo
      BRANCH            = "main"
    }
  }

  depends_on = [aws_cloudwatch_log_group.sync]
}
