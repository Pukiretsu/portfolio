# This control plane persists when the independent infra/minecraft stack is destroyed.
resource "aws_dynamodb_table" "minecraft" {
  name         = "portfolio-minecraft-control"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  attribute {
    name = "pk"
    type = "S"
  }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

resource "aws_secretsmanager_secret" "minecraft_github" {
  name                    = "portfolio/minecraft/github-token"
  description             = "Repository Actions-write token used only by the Minecraft dispatcher"
  recovery_window_in_days = 7
  # The value is populated from a GitHub secret after apply, never put in TF state.
}

resource "aws_cloudwatch_log_group" "minecraft" {
  name              = "/aws/lambda/portfolio-minecraft-proxy"
  retention_in_days = 14
}

resource "aws_iam_role" "minecraft_proxy" {
  name = "portfolio-minecraft-proxy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}
resource "aws_iam_role_policy" "minecraft_proxy" {
  name = "minecraft-control"
  role = aws_iam_role.minecraft_proxy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.minecraft.arn}:*"
      },
      {
        Effect   = "Allow", Action = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.minecraft.arn
      },
      {
        Effect   = "Allow", Action = "secretsmanager:GetSecretValue"
        Resource = aws_secretsmanager_secret.minecraft_github.arn
      },
      {
        Effect = "Allow", Action = "ec2:DescribeInstances", Resource = "*"
      }
    ]
  })
}

data "archive_file" "minecraft_proxy" {
  type        = "zip"
  output_path = "${path.module}/.terraform/minecraft-proxy.zip"
  source {
    content  = file("${path.module}/../backend/minecraft_proxy/app.py")
    filename = "app.py"
  }
  source {
    content  = file("${path.module}/../backend/minecraft_proxy/protocol.py")
    filename = "protocol.py"
  }
  source {
    content  = file("${path.module}/../backend/minecraft_proxy/activity.py")
    filename = "activity.py"
  }
}
resource "aws_lambda_function" "minecraft_proxy" {
  function_name    = "portfolio-minecraft-proxy"
  role             = aws_iam_role.minecraft_proxy.arn
  runtime          = "python3.13"
  handler          = "app.handler"
  filename         = data.archive_file.minecraft_proxy.output_path
  source_code_hash = data.archive_file.minecraft_proxy.output_base64sha256
  timeout          = 20
  memory_size      = 256
  # Use the account pool: small/new AWS accounts cannot reserve concurrency below
  # AWS's unreserved minimum. The authenticated API is independently throttled.
  reserved_concurrent_executions = -1
  environment {
    variables = {
      TABLE_NAME     = aws_dynamodb_table.minecraft.name
      GITHUB_SECRET  = aws_secretsmanager_secret.minecraft_github.arn
      GITHUB_REPO    = "Pukiretsu/portfolio"
      COGNITO_CLIENT = aws_cognito_user_pool_client.tools.id
      SERVER_ADDRESS = "mc.${var.domain_name}"
      ACCEPT_EULA    = tostring(var.minecraft_accept_eula)
      IDLE_RULE_ARN  = aws_cloudwatch_event_rule.minecraft_idle.arn
    }
  }
  depends_on = [aws_iam_role_policy.minecraft_proxy, aws_cloudwatch_log_group.minecraft]
}

resource "aws_apigatewayv2_api" "minecraft" {
  name          = "portfolio-minecraft"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = local.tools_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 300
  }
}
resource "aws_apigatewayv2_authorizer" "minecraft" {
  api_id           = aws_apigatewayv2_api.minecraft.id
  name             = "tools-cognito-access-tokens"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  jwt_configuration {
    audience = [aws_cognito_user_pool_client.tools.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.tools.id}"
  }
}
resource "aws_apigatewayv2_integration" "minecraft" {
  api_id                 = aws_apigatewayv2_api.minecraft.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.minecraft_proxy.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 25000
}
resource "aws_apigatewayv2_route" "minecraft" {
  for_each           = toset(["GET /minecraft/status", "POST /minecraft/deploy", "POST /minecraft/destroy"])
  api_id             = aws_apigatewayv2_api.minecraft.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.minecraft.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.minecraft.id
  # Requiring a scope prevents ID tokens being mistaken for access tokens.
  authorization_scopes = ["openid"]
}
resource "aws_apigatewayv2_stage" "minecraft" {
  api_id      = aws_apigatewayv2_api.minecraft.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 4
    throttling_rate_limit  = 2
  }
}
resource "aws_lambda_permission" "minecraft_gateway" {
  statement_id  = "AllowMinecraftApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.minecraft_proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.minecraft.execution_arn}/*/*/minecraft/*"
}

resource "aws_cloudwatch_event_rule" "minecraft_idle" {
  name                = "portfolio-minecraft-idle"
  description         = "Dispatch Terraform cleanup after the instance's confirmed graceful idle stop"
  schedule_expression = "rate(1 minute)"
}
resource "aws_cloudwatch_event_target" "minecraft_idle" {
  rule      = aws_cloudwatch_event_rule.minecraft_idle.name
  target_id = "minecraft-idle-check"
  arn       = aws_lambda_function.minecraft_proxy.arn
}
resource "aws_lambda_permission" "minecraft_idle" {
  statement_id  = "AllowMinecraftIdleSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.minecraft_proxy.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.minecraft_idle.arn
}
