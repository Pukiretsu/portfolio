output "website_url" {
  description = "HTTPS URL of the portfolio."
  value       = "https://${var.domain_name}"
}

output "www_url" {
  description = "HTTPS URL of the www alias."
  value       = "https://www.${var.domain_name}"
}

output "bucket_name" {
  description = "Private bucket to upload website files into."
  value       = aws_s3_bucket.website.id
}

output "cloudfront_distribution_id" {
  description = "Distribution ID for cache invalidations after uploads."
  value       = aws_cloudfront_distribution.website.id
}

output "cloudfront_domain_name" {
  description = "AWS hostname of the distribution"
  value       = aws_cloudfront_distribution.website.domain_name
}

output "certificate_arn" {
  description = "Validated ACM certificate in us-east-1."
  value       = aws_acm_certificate_validation.website.certificate_arn
}

output "cognito_user_pool_id" {
  description = "User pool where the administrator creates personal Tools accounts."
  value       = aws_cognito_user_pool.tools.id
}

output "cognito_client_id" {
  description = "Public browser app client ID (no client secret)."
  value       = aws_cognito_user_pool_client.tools.id
}

output "cognito_login_domain" {
  description = "Cognito-hosted login domain."
  value       = "https://${aws_cognito_user_pool_domain.tools.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "tools_url" {
  description = "Tools page; unauthenticated visitors are sent to login."
  value       = "https://${var.domain_name}/tools"
}

output "minecraft_api_url" {
  description = "Cognito-protected Minecraft control API."
  value       = aws_apigatewayv2_api.minecraft.api_endpoint
}

output "minecraft_github_secret_arn" {
  description = "Secret container to populate with the GitHub Actions-write token."
  value       = aws_secretsmanager_secret.minecraft_github.arn
}
