terraform {
  required_version = "~> 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.42"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  backend "s3" {
    bucket       = "mhemeryck-terraform-state-109185239364"
    key          = "goalkeepr/terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "eu-central-1"
}

provider "kubernetes" {
  config_path = pathexpand("~/.kube/config")
}

locals {
  hosts = [
    "goalkeepr.mhemeryck.xyz",
    "goalkeepr.app",
  ]
}

module "goalkeepr" {
  source = "../../../modules/goalkeepr"

  billing_alert_email = var.billing_alert_email
  hosts               = local.hosts
  image               = var.image
}

variable "billing_alert_email" {
  description = "Email address receiving Goalkeepr backup budget alerts."
  type        = string
}

variable "image" {
  description = "Goalkeepr container image."
  type        = string
  default     = "mhemeryck/goalkeepr:2026.08.22.2"
}
