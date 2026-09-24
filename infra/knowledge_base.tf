# FR-014 / FR-015: RAG sobre el repositorio. S3 Vectors evita el costo mínimo mensual de
# OpenSearch Serverless (NFR-012). Titan Text Embeddings v2 a 256 dimensiones.
data "aws_caller_identity" "current" {}

locals {
  embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"
  embedding_dims      = 256
}

# Copia del repositorio que carga UC-003 (rama main).
resource "aws_s3_bucket" "docs" {
  # checkov:skip=CKV_AWS_144:Sin replicación; el contenido se regenera desde GitHub
  # checkov:skip=CKV_AWS_145:SSE-S3; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_18:Sin access logging; requeriría otro bucket solo para la demo
  # checkov:skip=CKV2_AWS_61:Sin lifecycle; el volumen es mínimo y se destruye con el entorno
  # checkov:skip=CKV2_AWS_62:Sin notificaciones; la ingesta la lanza UC-003
  # checkov:skip=CKV_AWS_21:Sin versionado; el contenido es una copia regenerable del repositorio
  bucket        = "${local.name}-docs-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3vectors_vector_bucket" "kb" {
  vector_bucket_name = "${local.name}-vectors-${data.aws_caller_identity.current.account_id}"
  force_destroy      = true
}

resource "aws_s3vectors_index" "kb" {
  index_name         = "docs"
  vector_bucket_name = aws_s3vectors_vector_bucket.kb.vector_bucket_name
  data_type          = "float32"
  dimension          = local.embedding_dims
  distance_metric    = "cosine"

  # Bedrock guarda el texto del fragmento como metadato no filtrable.
  metadata_configuration {
    non_filterable_metadata_keys = ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
  }
}

resource "aws_iam_role" "kb" {
  name = "${local.name}-kb"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "kb" {
  name = "kb-access"
  role = aws_iam_role.kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = local.embedding_model_arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.docs.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.docs.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3vectors:PutVectors",
          "s3vectors:GetVectors",
          "s3vectors:DeleteVectors",
          "s3vectors:QueryVectors",
          "s3vectors:GetIndex",
        ]
        Resource = aws_s3vectors_index.kb.index_arn
      },
    ]
  })
}

resource "aws_bedrockagent_knowledge_base" "repo" {
  name     = "${local.name}-repo"
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = local.embedding_model_arn

      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = local.embedding_dims
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "S3_VECTORS"

    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.kb.index_arn
    }
  }

  depends_on = [aws_iam_role_policy.kb]
}

resource "aws_bedrockagent_data_source" "repo" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.repo.id
  name              = "repositorio-github"

  data_source_configuration {
    type = "S3"

    s3_configuration {
      bucket_arn = aws_s3_bucket.docs.arn
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"

      fixed_size_chunking_configuration {
        max_tokens         = 300
        overlap_percentage = 20
      }
    }
  }
}
