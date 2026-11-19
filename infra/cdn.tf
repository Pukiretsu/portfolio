resource "aws_cloudfront_origin_access_control" "website" {
  name                              = "${aws_s3_bucket.website.id}-oac"
  description                       = "Signed access to the private portfolio bucket"
  origin_access_control_origin_type = "s3"
  # always signing using SigV4 and HTTPS between CloudFront and S3.
  signing_behavior = "always"
  signing_protocol = "sigv4"
}

resource "aws_cloudfront_distribution" "website" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.domain_name, "www.${var.domain_name}"]
  http_version        = "http2and3"
  price_class         = "PriceClass_100"
  comment             = "Portfolio: ${var.domain_name}"

  origin {
    # OAC requires the S3 REST endpoint, not an S3 website endpoint.
    domain_name              = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id                = "portfolio-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.website.id
  }

  default_cache_behavior {
    target_origin_id           = "portfolio-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.website.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_routes.arn
    }
  }

  # Login configuration must not remain stale after an auth infrastructure change.
  ordered_cache_behavior {
    path_pattern               = "/auth-config.json"
    target_origin_id           = "portfolio-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.no_cache.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.website.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

}

resource "aws_cloudfront_function" "spa_routes" {
  name    = "portfolio-${data.aws_caller_identity.current.account_id}-spa-routes"
  runtime = "cloudfront-js-2.0"
  comment = "Serve the Vue shell for explicit application routes"
  publish = true
  code    = file("${path.module}/functions/spa-routes.js")
}
