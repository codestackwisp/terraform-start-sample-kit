###############################################################################
# Lambda Function
###############################################################################

# Create deployment package from source
data "archive_file" "lambda" {
  count       = var.create_lambda_package ? 1 : 0
  type        = "zip"
  source_dir  = var.lambda_source_path
  output_path = "${path.module}/.terraform/builds/${local.name_prefix}-lambda-${random_id.suffix.hex}.zip"
}

# Lambda Function
resource "aws_lambda_function" "this" {
  function_name    = local.name_prefix
  description      = var.lambda_description
  role             = aws_iam_role.lambda.arn
  handler          = var.lambda_handler
  runtime          = var.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size
  publish          = var.lambda_publish

  # Use either the created package or existing package
  filename         = var.create_lambda_package ? data.archive_file.lambda[0].output_path : var.lambda_existing_package_path
  source_code_hash = var.create_lambda_package ? data.archive_file.lambda[0].output_base64sha256 : (
    var.lambda_existing_package_path != null ? filebase64sha256(var.lambda_existing_package_path) : null
  )

  # Environment variables
  dynamic "environment" {
    for_each = length(var.lambda_environment_variables) > 0 ? [1] : []
    content {
      variables = var.lambda_environment_variables
    }
  }

  # VPC Configuration
  dynamic "vpc_config" {
    for_each = var.lambda_vpc_subnet_ids != null ? [1] : []
    content {
      subnet_ids         = var.lambda_vpc_subnet_ids
      security_group_ids = var.lambda_vpc_security_group_ids
    }
  }

  # Tracing
  dynamic "tracing_config" {
    for_each = var.lambda_tracing_mode != null ? [1] : []
    content {
      mode = var.lambda_tracing_mode
    }
  }

  # Dead Letter Config
  dynamic "dead_letter_config" {
    for_each = var.lambda_dead_letter_arn != null ? [1] : []
    content {
      target_arn = var.lambda_dead_letter_arn
    }
  }

  # Layers
  layers = var.lambda_layers

  tags = merge(
    local.common_tags,
    var.lambda_tags,
    {
      Name = "${local.name_prefix}-function"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_cloudwatch_log_group.lambda
  ]
}

# Lambda Function Alias (optional)
resource "aws_lambda_alias" "this" {
  count            = var.create_lambda_alias ? 1 : 0
  name             = var.lambda_alias_name
  description      = "Alias for ${local.name_prefix} Lambda function"
  function_name    = aws_lambda_function.this.function_name
  function_version = var.lambda_publish ? aws_lambda_function.this.version : "$LATEST"
}

###############################################################################
# CloudWatch Log Group for Lambda
###############################################################################

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}"
  retention_in_days = var.lambda_log_retention_days
  kms_key_id        = var.lambda_log_kms_key_id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-logs"
    }
  )
}

###############################################################################
# Lambda Permission for API Gateway
###############################################################################

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  
  # Grant permission to the specific API Gateway
  source_arn = "${aws_api_gateway_rest_api.this.execution_arn}/*/*"
}
