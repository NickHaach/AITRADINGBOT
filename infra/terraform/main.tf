# Terraform-ready skeleton — fill remote state + cloud provider before apply.
terraform {
  required_version = ">= 1.5"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

variable "environment" {
  type    = string
  default = "dev"
}

resource "null_resource" "platform_placeholder" {
  triggers = {
    environment = var.environment
    note        = "Replace with VPC, RDS Postgres, ElastiCache Redis, EKS/GKE, Qdrant"
  }
}

output "next_steps" {
  value = "Wire provider credentials and replace null_resource with real infra modules."
}
