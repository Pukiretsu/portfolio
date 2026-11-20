output "instance_id" {
  value = aws_instance.server.id
}
output "ipv6_address" {
  value = one(aws_instance.server.ipv6_addresses)
}
output "ipv4_address" {
  value = aws_instance.server.public_ip
}
output "volume_ids" {
  value = [for volume in aws_instance.server.root_block_device : volume.volume_id]
}
output "connection_address" {
  value = local.address
}
