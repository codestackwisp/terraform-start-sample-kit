###############################################################################
# Complete Example - API Gateway with Lambda
###############################################################################

provider "aws" {
  region = var.aws_region
}

###############################################################################
# API Gateway + Lambda Module
###############################################################################

module "audit_api_lambda" {
  source = "../../"

  # Required
  project_name       = var.project_name
  environment        = var.environment
  lambda_runtime     = var.lambda_runtime
  lambda_handler     = var.lambda_handler
  lambda_source_path = "${path.module}/lambda_code"

  # Lambda Configuration
  lambda_description = "Audit API Lambda function for receiving and processing audit events"
  lambda_memory_size = 512
  lambda_timeout     = 60
  lambda_publish     = true

  lambda_environment_variables = {
    ENVIRONMENT  = var.environment
    LOG_LEVEL    = "INFO"
    TABLE_NAME   = "audit-events"
    REGION       = var.aws_region
  }

  # Enable X-Ray tracing
  lambda_tracing_mode = "Active"

  # CloudWatch Logs
  lambda_log_retention_days = 30

  # API Gateway Configuration
  api_gateway_description       = "Audit API Gateway for receiving audit events"
  api_gateway_stage_name        = var.environment
  api_gateway_endpoint_type     = "REGIONAL"
  enable_api_gateway_logging    = true
  api_gateway_logging_level     = "INFO"
  api_gateway_xray_tracing_enabled = true
  api_gateway_log_retention_days = 30

  # Enable CORS
  enable_cors         = true
  cors_allow_origins  = ["https://example.com", "https://app.example.com"]
  cors_allow_methods  = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  cors_allow_headers  = ["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"]

  # Throttling
  api_gateway_throttling_burst_limit = 5000
  api_gateway_throttling_rate_limit  = 10000

  # Custom Lambda IAM policies
  lambda_custom_policies = [
    {
      sid    = "DynamoDBAccess"
      effect = "Allow"
      actions = [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ]
      resources = [
        "arn:aws:dynamodb:${var.aws_region}:*:table/audit-events"
      ]
    },
    {
      sid    = "S3Access"
      effect = "Allow"
      actions = [
        "s3:PutObject",
        "s3:GetObject"
      ]
      resources = [
        "arn:aws:s3:::audit-logs-bucket/*"
      ]
    }
  ]

  # Tags
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "DevOps Team"
    CostCenter  = "Engineering"
  }
}

###############################################################################
# DynamoDB Table (Example)
###############################################################################

resource "aws_dynamodb_table" "audit_events" {
  name           = "audit-events"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "eventId"
  range_key      = "timestamp"

  attribute {
    name = "eventId"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "audit-events"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

###############################################################################
# S3 Bucket for Audit Logs (Example)
###############################################################################

resource "aws_s3_bucket" "audit_logs" {
  bucket = "audit-logs-bucket-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "audit-logs-bucket"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

###############################################################################
# Data Sources
###############################################################################

data "aws_caller_identity" "current" {}
