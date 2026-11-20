resource "cloudflare_record" "server" {
  for_each = toset(["A", "AAAA"])
  zone_id  = var.cloudflare_zone_id
  name     = local.address
  type     = each.value
  value    = each.value == "AAAA" ? one(aws_instance.server.ipv6_addresses) : aws_instance.server.public_ip
  ttl      = 60
  # Raw Minecraft TCP must go directly to EC2, never CloudFront or Cloudflare proxy.
  proxied = false
}
