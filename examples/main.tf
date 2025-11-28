###############################################################################
# Audit API with CloudWatch Logging
###############################################################################

provider "aws" {
  region = var.aws_region
}

###############################################################################
# API Gateway + Lambda Module
###############################################################################

module "audit_api" {
  source = "../../"

  # Required variables
  project_name       = var.project_name
  environment        = var.environment
  lambda_runtime     = var.lambda_runtime
  lambda_handler     = var.lambda_handler
  lambda_source_path = "${path.module}/lambda_code"

  # Lambda configuration
  lambda_description = "Audit event receiver - logs to CloudWatch"
  lambda_memory_size = 256
  lambda_timeout     = 30

  # Environment variables
  lambda_environment_variables = {
    ENVIRONMENT = var.environment
    LOG_LEVEL   = "INFO"
  }

  # CloudWatch Logs retention
  lambda_log_retention_days = 14

  # API Gateway configuration
  api_gateway_description    = "Audit API - CloudWatch logging"
  api_gateway_stage_name     = var.environment
  enable_api_gateway_logging = true
  api_gateway_logging_level  = "INFO"

  # Enable CORS for web applications
  enable_cors        = true
  cors_allow_origins = ["*"]
  cors_allow_methods = ["POST", "OPTIONS"]
  cors_allow_headers = ["Content-Type", "Authorization"]

  # Tags
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "AuditLogging"
  }
}
