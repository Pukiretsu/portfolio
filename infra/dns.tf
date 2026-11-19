# ACM supplies the names and targets; Cloudflare publishes them in authoritative DNS.
resource "cloudflare_record" "certificate_validation" {
  for_each = {
    for option in aws_acm_certificate.website.domain_validation_options : option.domain_name => {
      name  = option.resource_record_name
      type  = option.resource_record_type
      value = option.resource_record_value
    }
  }

  zone_id = var.cloudflare_zone_id
  name    = trimsuffix(each.value.name, ".")
  type    = each.value.type
  value   = trimsuffix(each.value.value, ".")
  ttl     = 60
  # ACM must see the actual CNAME target for validation and renewals.
  proxied = false
}

resource "cloudflare_record" "website" {
  for_each = toset([var.domain_name, "www.${var.domain_name}"])

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "CNAME"
  value   = aws_cloudfront_distribution.website.domain_name
  ttl     = 300
  # Cloudflare flattens the apex CNAME; CloudFront terminates visitor TLS.
  proxied = false

  depends_on = [aws_s3_bucket_policy.website]
}
