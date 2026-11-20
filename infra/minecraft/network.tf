locals {
  tags = {
    Project   = "portfolio-minecraft"
    ManagedBy = "Terraform"
  }
  address = "mc.${var.domain_name}"
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "server" {
  cidr_block                       = "10.76.0.0/16"
  assign_generated_ipv6_cidr_block = true
  enable_dns_hostnames             = true
  enable_dns_support               = true
}
resource "aws_internet_gateway" "server" {
  vpc_id = aws_vpc.server.id
}
resource "aws_subnet" "server" {
  vpc_id                          = aws_vpc.server.id
  availability_zone               = data.aws_availability_zones.available.names[0]
  cidr_block                      = "10.76.1.0/24"
  ipv6_cidr_block                 = cidrsubnet(aws_vpc.server.ipv6_cidr_block, 8, 0)
  assign_ipv6_address_on_creation = true
  map_public_ip_on_launch         = true
}
resource "aws_route_table" "server" {
  vpc_id = aws_vpc.server.id
}
resource "aws_route" "ipv4" {
  route_table_id         = aws_route_table.server.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.server.id
}
resource "aws_route" "ipv6" {
  route_table_id              = aws_route_table.server.id
  destination_ipv6_cidr_block = "::/0"
  gateway_id                  = aws_internet_gateway.server.id
}
resource "aws_route_table_association" "server" {
  subnet_id      = aws_subnet.server.id
  route_table_id = aws_route_table.server.id
}
resource "aws_security_group" "server" {
  name_prefix = "portfolio-minecraft-"
  description = "Minecraft only; no SSH or RCON exposed"
  vpc_id      = aws_vpc.server.id
  ingress {
    description      = "Minecraft Java Edition"
    protocol         = "tcp"
    from_port        = 25565
    to_port          = 25565
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
  egress {
    description      = "OS updates, Mojang downloads, and authenticated game services"
    protocol         = "-1"
    from_port        = 0
    to_port          = 0
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}
