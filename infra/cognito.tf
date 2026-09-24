# UC-001 Autenticarse: registro con código de evento, sin verificación por correo
# (el límite por defecto de correos de Cognito es de 50 al día, igual que el aforo).

resource "random_password" "event_code" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_secretsmanager_secret" "event" {
  # checkov:skip=CKV_AWS_149:Cifrado con la clave administrada de AWS; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV2_AWS_57:Es un código de evento de un solo uso, sin rotación automática
  name                    = "${local.name}/event"
  description             = "Código del evento y apertura del registro (UC-001 BR-001 y BR-002)"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "event" {
  secret_id = aws_secretsmanager_secret.event.id
  secret_string = jsonencode({
    event_code        = random_password.event_code.result
    registration_open = false
  })

  # El organizador abre y cierra el registro con el CLI sin que Terraform lo revierta.
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "archive_file" "pre_signup" {
  type        = "zip"
  source_file = "${path.module}/../src/spec_to_runtime/auth/pre_signup.py"
  output_path = "${path.module}/.build/pre_signup.zip"
}

resource "aws_iam_role" "pre_signup" {
  name = "${local.name}-pre-signup"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "pre_signup" {
  name = "pre-signup"
  role = aws_iam_role.pre_signup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.event.arn
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:DescribeUserPool"]
        Resource = aws_cognito_user_pool.main.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.pre_signup.arn}:*"
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "pre_signup" {
  # checkov:skip=CKV_AWS_158:Logs con cifrado por defecto; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_338:Retención de 14 días: los logs solo sirven durante el evento
  name              = "/aws/lambda/${local.name}-pre-signup"
  retention_in_days = 14
}

resource "aws_lambda_function" "pre_signup" {
  # checkov:skip=CKV_AWS_117:Fuera de VPC a propósito: una VPC exigiría NAT (costo fijo, NFR-012)
  # checkov:skip=CKV_AWS_116:Sin DLQ; el trigger es síncrono y Cognito muestra el error al usuario
  # checkov:skip=CKV_AWS_173:Variables sin CMK; no contienen secretos (solo el ARN del secreto)
  # checkov:skip=CKV_AWS_272:Sin firma de código; el paquete lo genera Terraform desde este repo
  # checkov:skip=CKV_AWS_115:Sin límite de concurrencia; el máximo de cuentas ya acota el uso
  # checkov:skip=CKV_AWS_50:Sin X-Ray; los logs de CloudWatch bastan para el evento
  function_name    = "${local.name}-pre-signup"
  role             = aws_iam_role.pre_signup.arn
  runtime          = "python3.14"
  handler          = "pre_signup.handler"
  filename         = data.archive_file.pre_signup.output_path
  source_code_hash = data.archive_file.pre_signup.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      EVENT_SECRET_ARN = aws_secretsmanager_secret.event.arn
      MAX_ACCOUNTS     = tostring(var.max_accounts)
    }
  }

  depends_on = [aws_cloudwatch_log_group.pre_signup]
}

resource "aws_lambda_permission" "cognito_pre_signup" {
  statement_id  = "AllowCognito"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pre_signup.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.main.arn
}

resource "aws_cognito_user_pool" "main" {
  # checkov:skip=CKV_AWS_363:Sin MFA en la demo; el registro está acotado por código de evento y cuotas
  name                     = "${local.name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OFF"
  deletion_protection      = "INACTIVE"

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_numbers                  = true
    require_uppercase                = false
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    # UC-001 BR-006: sin recuperación de contraseña en la demo.
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  lambda_config {
    pre_sign_up = aws_lambda_function.pre_signup.arn
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${local.name}-web"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"

  # UC-001 BR-008: sesión de hasta 12 horas.
  access_token_validity  = 12
  id_token_validity      = 12
  refresh_token_validity = 1

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

# UC-001 BR-003: el rol Ponente es un grupo; solo el organizador agrega personas.
resource "aws_cognito_user_group" "ponente" {
  name         = "Ponente"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Puede ejecutar el análisis de preguntas (UC-007)"
}
