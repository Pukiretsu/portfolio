variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "domain_name" {
  type        = string
  description = "Existing Cloudflare apex domain; Minecraft uses mc.<domain>."
  validation {
    condition     = can(regex("^[a-z0-9.-]+\\.[a-z]{2,}$", var.domain_name))
    error_message = "Use a lowercase domain without a scheme or trailing dot."
  }
}
variable "cloudflare_zone_id" {
  type = string
}
variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}
variable "accept_eula" {
  type        = bool
  default     = false
  description = "Set true only after accepting https://aka.ms/MinecraftEULA."
}
variable "minecraft_version" {
  type        = string
  default     = "26.3"
  description = "Pinned Minecraft Java Edition release, downloaded from Mojang."
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+(\\.[0-9]+)?$", var.minecraft_version))
    error_message = "Use a stable release number, for example 26.3."
  }
}
variable "fabric_loader_version" {
  type    = string
  default = "0.19.5"
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.fabric_loader_version))
    error_message = "Use a stable Fabric loader version."
  }
}
variable "fabric_installer_version" {
  type    = string
  default = "1.1.1"
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.fabric_installer_version))
    error_message = "Use a stable Fabric installer version."
  }
}

variable "fabric_api_version" {
  type        = string
  default     = "0.166.2+26.3"
  description = "Exact Fabric API version; must support minecraft_version."
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+[+][0-9.]+$", var.fabric_api_version))
    error_message = "Use a Fabric API release such as 0.166.2+26.3."
  }
}

variable "launch_config_key" {
  type    = string
  default = "settings/server.json"
  validation {
    condition     = var.launch_config_key == "settings/server.json" || can(regex("^launches/[0-9a-f-]{36}[.]json$", var.launch_config_key))
    error_message = "Use a persisted S3 launch configuration."
  }
}
