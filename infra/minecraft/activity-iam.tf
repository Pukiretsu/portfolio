data "aws_dynamodb_table" "control" {
  name = "portfolio-minecraft-control"
}

resource "aws_iam_role" "activity" {
  name = "portfolio-minecraft-activity"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy" "activity" {
  name = "write-instance-activity-only"
  role = aws_iam_role.activity.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      # AL2023 includes SSM Agent. Enable SSH/SCP without opening inbound port 22.
      Effect = "Allow"
      Action = [
        "ssm:UpdateInstanceInformation",
        "ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel",
        "ec2messages:AcknowledgeMessage", "ec2messages:DeleteMessage",
        "ec2messages:FailMessage", "ec2messages:GetEndpoint",
        "ec2messages:GetMessages", "ec2messages:SendReply"
      ]
      Resource = "*"
      }, {
      Effect    = "Allow", Action = "dynamodb:UpdateItem", Resource = data.aws_dynamodb_table.control.arn
      Condition = { "ForAllValues:StringLike" = { "dynamodb:LeadingKeys" = ["activity#*"] } }
    }]
  })
}
resource "aws_iam_instance_profile" "activity" {
  name = "portfolio-minecraft-activity"
  role = aws_iam_role.activity.name
}
