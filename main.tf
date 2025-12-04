provider "aws" {
  region = var.aws_region
}

# ============================================================================
# IMPORTANT: This module uses terraform-aws-modules/lambda/aws
# It automatically handles Lambda packaging and deployment
# ============================================================================

module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "8.1.2"

  # Lambda Configuration
  function_name = var.lambda_function_name
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  # Lambda Source Code (from ZIP file)
  filename            = var.lambda_zip_file
  source_path         = filebase64sha256(var.lambda_zip_file)

  # Environment Variables (passed to Lambda)
  environment_variables = var.environment_variables

  tags = var.tags
}

# ============================================================================
# API GATEWAY - REST API
# ============================================================================

resource "aws_api_gateway_rest_api" "main" {
  name        = var.api_name
  description = "API Gateway for ${var.lambda_function_name}"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = var.tags
}

# ============================================================================
# API GATEWAY RESOURCE (Endpoint)
# ============================================================================

resource "aws_api_gateway_resource" "endpoint" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = var.endpoint_path
}

# ============================================================================
# API GATEWAY METHOD (HTTP Method)
# ============================================================================

resource "aws_api_gateway_method" "endpoint_method" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.endpoint.id
  http_method      = var.http_method
  authorization    = "NONE"
  api_key_required = false
}

# ============================================================================
# API GATEWAY INTEGRATION (Connect to Lambda)
# ============================================================================

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.endpoint.id
  http_method             = aws_api_gateway_method.endpoint_method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_function.lambda_function_invoke_arn

  depends_on = [module.lambda_function]
}

# ============================================================================
# LAMBDA PERMISSION (Allow API Gateway to invoke Lambda)
# ============================================================================

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"

  depends_on = [module.lambda_function]
}

# ============================================================================
# API GATEWAY DEPLOYMENT
# ============================================================================

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = ""

  depends_on = [
    aws_api_gateway_integration.lambda_integration,
    aws_lambda_permission.api_gateway
  ]
}

# ============================================================================
# API GATEWAY STAGE (dev/prod/etc)
# ============================================================================

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.stage_name

  xray_tracing_enabled = true

  tags = var.tags
}

# ============================================================================
# CLOUDWATCH LOG GROUP FOR LAMBDA
# ============================================================================

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${module.lambda_function.lambda_function_name}"
  retention_in_days = 7

  tags = var.tags
}
