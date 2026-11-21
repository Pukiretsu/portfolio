data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

resource "aws_instance" "server" {
  ami                         = data.aws_ssm_parameter.ami.value
  instance_type               = "t4g.medium"
  subnet_id                   = aws_subnet.server.id
  vpc_security_group_ids      = [aws_security_group.server.id]
  associate_public_ip_address = true
  ipv6_address_count          = 1
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user-data.sh.tftpl", {
    version                  = var.minecraft_version
    fabric_loader_version    = var.fabric_loader_version
    fabric_installer_version = var.fabric_installer_version
    fabric_api_version       = var.fabric_api_version
    installer_gzip           = base64gzip(file("${path.module}/install-server.py"))
    monitor_gzip             = base64gzip(file("${path.module}/../../backend/minecraft_proxy/activity_monitor.py"))
    activity_gzip            = base64gzip(file("${path.module}/../../backend/minecraft_proxy/activity.py"))
    protocol_gzip            = base64gzip(file("${path.module}/../../backend/minecraft_proxy/protocol.py"))
    backup_bucket            = "${data.aws_caller_identity.current.account_id}-portfolio-minecraft-backups"
    launch_config_key        = var.launch_config_key
    aws_region               = var.aws_region
  })
  iam_instance_profile = aws_iam_instance_profile.activity.name
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  credit_specification {
    cpu_credits = "standard"
  }
  # World data lives on this encrypted disk. Destroy deliberately removes it.
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = true
  }
  volume_tags = local.tags
  tags        = { Name = "portfolio-minecraft", LaunchConfig = var.launch_config_key }
  lifecycle {
    precondition {
      condition     = var.accept_eula
      error_message = "Accept the Minecraft EULA before launching: set MINECRAFT_ACCEPT_EULA=true in repository variables."
    }
  }
  depends_on = [aws_route.ipv4, aws_route.ipv6, aws_route_table_association.server, aws_iam_role_policy.activity]
}
