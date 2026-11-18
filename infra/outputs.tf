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
