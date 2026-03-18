# ── Terraform Configuration for MLOps Lab 4 ──
# Розгортає: S3 сховища, ECR репозиторій, CloudWatch алерти, IAM ролі

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
}
