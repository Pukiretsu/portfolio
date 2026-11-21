# Persistent control-plane storage: independent of infra/minecraft destroy.
resource "aws_s3_bucket" "minecraft_backups" {
  bucket = "${data.aws_caller_identity.current.account_id}-portfolio-minecraft-backups"
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_s3_bucket_public_access_block" "minecraft_backups" {
  bucket                  = aws_s3_bucket.minecraft_backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "minecraft_backups" {
  bucket = aws_s3_bucket.minecraft_backups.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "minecraft_backups" {
  bucket = aws_s3_bucket.minecraft_backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_versioning" "minecraft_backups" {
  bucket = aws_s3_bucket.minecraft_backups.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_cors_configuration" "minecraft_backups" {
  bucket = aws_s3_bucket.minecraft_backups.id
  cors_rule {
    allowed_origins = local.tools_origins
    allowed_methods = ["POST", "GET", "HEAD"]
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 300
  }
}
resource "aws_s3_bucket_lifecycle_configuration" "minecraft_backups" {
  bucket = aws_s3_bucket.minecraft_backups.id
  rule {
    id     = "expire-temporary-uploads"
    status = "Enabled"
    filter {
      prefix = "uploads/"
    }
    expiration {
      days = 1
    }
    noncurrent_version_expiration {
      noncurrent_days = 1
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
  depends_on = [aws_s3_bucket_versioning.minecraft_backups]
}
resource "aws_s3_bucket_policy" "minecraft_backups" {
  bucket = aws_s3_bucket.minecraft_backups.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireTLS", Effect = "Deny", Principal = "*", Action = "s3:*"
      Resource  = [aws_s3_bucket.minecraft_backups.arn, "${aws_s3_bucket.minecraft_backups.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.minecraft_backups]
}
output "minecraft_backup_bucket" {
  value = aws_s3_bucket.minecraft_backups.id
}
