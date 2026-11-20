terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.52"
    }
  }
  # Separate state: destroying Minecraft can never destroy the portfolio or login.
  backend "s3" {
    bucket       = "458302836200-terraform-state-portfolio"
    key          = "minecraft/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = local.tags
  }
}
provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
