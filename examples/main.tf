# EXAMPLE - main.tf
# This shows how to use the root module

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ============================================================================
# Create ZIP file from Python code
# ============================================================================

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/index.py"
  output_path = "${path.module}/lambda/function.zip"
}

# ============================================================================
# Use the root module
# ============================================================================

module "api_with_lambda" {
  # Point to the root module
  source = "../../"

  # Required inputs
  api_name             = var.api_name
  lambda_function_name = var.lambda_function_name
  lambda_zip_file      = data.archive_file.lambda_zip.output_path

  # Optional - customize as needed
  aws_region       = var.aws_region
  lambda_handler   = "index.lambda_handler"
  lambda_runtime   = "python3.11"
  lambda_timeout   = 60
  lambda_memory_size = 256

  endpoint_path = "data"
  http_method   = "POST"
  stage_name    = "dev"

  # Environment variables for Lambda
  environment_variables = {
    ENVIRONMENT = "development"
    APP_NAME    = var.api_name
  }

  tags = {
    Environment = "development"
    Project     = "api-gateway-lambda"
    ManagedBy   = "Terraform"
  }

  depends_on = [data.archive_file.lambda_zip]
}
