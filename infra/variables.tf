variable "aws_region" {
  description = "AWS region for the S3 Bucket"
  type = string
  default = "us-east-1"
}

variable "domain_name" {
  description = "Root domain of the existing Cloudflare zone, without a trailing dot."
  type = string
  default = "example.com"
  
  validation {
    condition = can(regex("^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,}$", var.domain_name))
    error_message = "Use a lowercase domain such as yourdomain.com, without a scheme or trailing dot."
  }
}

variable "tags" {
  description = "Tags applied to supported AWS resources."
  type = map(string)
  default = {
    "Project" = "portfolio"
    "ManagedBy" = "Terraform"
  }
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with zone DNS Edit access scoped to the target zone. supply via TF_VAR_cloudflare_api_token."
  type = string
  sensitive = true
  nullable = false
}

variable "cloudflare_zone_id" {
  description = "ID of the existing Cloudflare zone for domain_name."
  type = string

  validation {
    condition = can(regex("^[a-f0-9]{32}$", var.cloudflare_zone_id))
    error_message = "Provide the 32-character hexadecimal Cloudflare zone ID."
  }
}
