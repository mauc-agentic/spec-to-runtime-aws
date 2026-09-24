terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  # Bucket creado por infra/bootstrap. Locking nativo de S3 (use_lockfile), sin DynamoDB.
  backend "s3" {
    bucket       = "spec-to-runtime-tfstate-992382848403"
    key          = "spec-to-runtime/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = "spec-to-runtime-aws"
    }
  }
}
