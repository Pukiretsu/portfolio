locals {
  tools_origins         = ["https://${var.domain_name}", "https://www.${var.domain_name}"]
  cognito_domain_prefix = "${substr(replace(var.domain_name, ".", "-"), 0, 28)}-${data.aws_caller_identity.current.account_id}-tools"
}

resource "aws_cognito_user_pool" "tools" {
  name                     = "${var.domain_name}-tools"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "ACTIVE"
  user_pool_tier           = "LITE"
  mfa_configuration        = "ON"

  username_configuration {
    case_sensitive = false
  }

  # Personal workspace: only an administrator can invite users.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 16
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cognito_user_pool_client" "tools" {
  name         = "portfolio-tools-spa"
  user_pool_id = aws_cognito_user_pool.tools.id

  # A browser cannot keep a secret; use authorization code + PKCE in the client.
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  callback_urls        = [for origin in local.tools_origins : "${origin}/auth/callback"]
  logout_urls          = [for origin in local.tools_origins : "${origin}/login"]
  default_redirect_uri = "https://${var.domain_name}/auth/callback"
}

resource "aws_cognito_user_pool_domain" "tools" {
  domain                = local.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.tools.id
  managed_login_version = 1
}

# Public configuration only: no tokens, passwords, or client secrets in S3.
resource "aws_s3_object" "auth_config" {
  bucket        = aws_s3_bucket.website.id
  key           = "auth-config.json"
  content_type  = "application/json"
  cache_control = "no-store,max-age=0"
  content = jsonencode({
    authority = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.tools.id}"
    clientId  = aws_cognito_user_pool_client.tools.id
    domain    = "https://${aws_cognito_user_pool_domain.tools.domain}.auth.${var.aws_region}.amazoncognito.com"
  })
  depends_on = [aws_s3_bucket_server_side_encryption_configuration.website]
}
