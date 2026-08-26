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
  config_path = pathexpand(var.kubeconfig_path)
}

locals {
  hosts = [
    "goalkeepr.mhemeryck.xyz",
    "goalkeepr.app",
  ]

  image = var.image != null ? var.image : data.kubernetes_resource.goalkeepr[0].object.spec.template.spec.containers[0].image
}

data "kubernetes_resource" "goalkeepr" {
  count = var.image == null ? 1 : 0

  api_version = "apps/v1"
  kind        = "Deployment"

  metadata {
    name      = "goalkeepr"
    namespace = "goalkeepr"
  }
}

module "goalkeepr" {
  source = "../../../modules/goalkeepr"

  billing_alert_email = var.billing_alert_email
  hosts               = local.hosts
  image               = local.image
}

variable "billing_alert_email" {
  description = "Email address receiving Goalkeepr backup budget alerts."
  type        = string
}

variable "image" {
  description = "Goalkeepr container image."
  type        = string
  default     = null
  nullable    = true
}

variable "kubeconfig_path" {
  description = "Path to the kubeconfig used to manage the Goalkeepr namespace."
  type        = string
  default     = "~/.kube/config"
}
