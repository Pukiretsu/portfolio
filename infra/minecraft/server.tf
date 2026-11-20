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
    version   = var.minecraft_version
    whitelist = jsonencode(var.whitelist)
  })
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
  tags        = { Name = "portfolio-minecraft" }
  lifecycle {
    precondition {
      condition     = var.accept_eula
      error_message = "Accept the Minecraft EULA before launching: set MINECRAFT_ACCEPT_EULA=true in repository variables."
    }
  }
  depends_on = [aws_route.ipv4, aws_route.ipv6, aws_route_table_association.server]
}
