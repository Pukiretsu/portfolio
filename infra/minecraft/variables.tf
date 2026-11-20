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
  default     = "1.21.11"
  description = "Pinned Minecraft Java Edition release, downloaded from Mojang."
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+(\\.[0-9]+)?$", var.minecraft_version))
    error_message = "Use a stable release number, for example 1.21.11."
  }
}
variable "whitelist" {
  type        = list(string)
  default     = []
  description = "Optional Java account names. Empty means any authenticated player can join."
  validation {
    condition     = alltrue([for name in var.whitelist : can(regex("^[A-Za-z0-9_]{3,16}$", name))])
    error_message = "Whitelist entries must be Java account names of 3–16 letters, digits or underscores."
  }
}
