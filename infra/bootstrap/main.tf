# Bootstrap: crea el bucket S3 del state remoto. Usa state local (huevo y gallina);
# se aplica una sola vez y su state no se versiona (ver .gitignore).
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

# Excepciones de checkov: state de un repo de charla, un solo bucket y una sola región.
resource "aws_s3_bucket" "tfstate" {
  #checkov:skip=CKV_AWS_144:Sin replicación cross-region; el state es reproducible y el bucket tiene versionado
  #checkov:skip=CKV_AWS_145:SSE-S3 (AES256) es suficiente; KMS añade costo y gestión de llaves innecesarios aquí
  #checkov:skip=CKV_AWS_18:Sin access logging; requeriría otro bucket de logs solo para la demo
  #checkov:skip=CKV2_AWS_61:Sin lifecycle; el volumen del state es mínimo
  #checkov:skip=CKV2_AWS_62:Sin notificaciones de eventos; nadie consume eventos del bucket
  bucket = "spec-to-runtime-tfstate-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.id
}
