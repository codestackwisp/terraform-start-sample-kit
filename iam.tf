###############################################################################
# Lambda IAM Role
###############################################################################

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = [var.lambda_principals_identifiers]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  description        = "IAM role for ${local.name_prefix} Lambda function"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-lambda"
    }
  )
}

###############################################################################
# Lambda Basic Execution Policy
###############################################################################

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = data.aws_iam_policy.lambda_basic.arn
}

###############################################################################
# Lambda VPC Execution Policy (conditional)
###############################################################################

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  count      = var.lambda_vpc_subnet_ids != null ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = var.aws_iam_policy_lambda_vpc_arn
}

###############################################################################
# Lambda X-Ray Policy (conditional)
###############################################################################

resource "aws_iam_role_policy_attachment" "lambda_xray" {
  count      = var.lambda_tracing_mode != null ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = var.aws_iam_policy_lambda_xray_arn
}

###############################################################################
# Lambda Custom Policies (optional)
###############################################################################

data "aws_iam_policy_document" "lambda_custom" {
  count = length(var.lambda_custom_policies) > 0 ? 1 : 0

  dynamic "statement" {
    for_each = var.lambda_custom_policies
    content {
      sid       = statement.value.sid
      effect    = statement.value.effect
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_policy" "lambda_custom" {
  count       = length(var.lambda_custom_policies) > 0 ? 1 : 0
  name        = "${local.name_prefix}-lambda-custom-policy"
  description = "Custom IAM policy for ${local.name_prefix} Lambda function"
  policy      = data.aws_iam_policy_document.lambda_custom[0].json

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-lambda-custom-policy"
    }
  )
}

resource "aws_iam_role_policy_attachment" "lambda_custom" {
  count      = length(var.lambda_custom_policies) > 0 ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_custom[0].arn
}

###############################################################################
# API Gateway CloudWatch Role
###############################################################################

data "aws_iam_policy_document" "api_gateway_assume_role" {
  count = var.enable_api_gateway_logging ? 1 : 0

  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = [var.api_gateway_principals_identifiers]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "api_gateway_cloudwatch" {
  count              = var.enable_api_gateway_logging ? 1 : 0
  name               = "${local.name_prefix}-api-gateway-cloudwatch-role"
  assume_role_policy = data.aws_iam_policy_document.api_gateway_assume_role[0].json
  description        = "IAM role for API Gateway CloudWatch logging"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-api-gateway-cloudwatch-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  count      = var.enable_api_gateway_logging ? 1 : 0
  role       = aws_iam_role.api_gateway_cloudwatch[0].name
  policy_arn = var.aws_iam_policy_apigw_cloudwatch_arn
}
