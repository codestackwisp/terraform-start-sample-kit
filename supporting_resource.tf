# Vraiable file
variable "lambda_subnet_ids" {
  type = list(string)
}

variable "lambda_security_group_ids" {
  type = list(string)
}



# main file
module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "8.1.2"

  function_name = var.lambda_function_name
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size


  source_path = var.lambda_source_path

  environment_variables = var.environment_variables

  # VPC CONFIG
  vpc_subnet_ids         = var.lambda_subnet_ids
  vpc_security_group_ids = var.lambda_security_group_ids

  # Required for VPC Lambdas (default = true, but explicit is good)
  attach_network_policy = true

  tags = merge(local.block_tag, {
    Name = "${var.prefix}-apigateway-lambda"
  })
}


resource "aws_vpc_endpoint" "api_gateway" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.execute-api"
  vpc_endpoint_type = "Interface"

  subnet_ids         = var.endpoint_subnet_ids
  security_group_ids = var.endpoint_security_group_ids

  private_dns_enabled = true

  tags = var.tags
}


resource "aws_api_gateway_rest_api_policy" "policy" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = "*"
        Action = "execute-api:Invoke"
        Resource = "${aws_api_gateway_rest_api.main.execution_arn}/*"
        Condition = {
          StringEquals = {
            "aws:SourceVpce" = aws_vpc_endpoint.api_gateway.id
          }
        }
      }
    ]
  })
}

