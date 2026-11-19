resource "aws_acm_certificate" "website" {
  # forces terraform to deploy certs in US-east-1
  provider                  = aws.us_east_1
  domain_name               = var.domain_name
  validation_method         = "DNS"
  subject_alternative_names = ["www.${var.domain_name}"]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "website" {
  provider        = aws.us_east_1
  certificate_arn = aws_acm_certificate.website.arn
  # This dependency waits for Cloudflare records, then ACM issuance, before CloudFront.
  validation_record_fqdns = [for record in cloudflare_record.certificate_validation : record.hostname]

  timeouts {
    create = "45m"
  }
}
