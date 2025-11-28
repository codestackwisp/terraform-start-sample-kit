###############################################################################
# Required Variables
###############################################################################

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "lambda_runtime" {
  description = "Lambda function runtime (e.g., python3.11, nodejs18.x)"
  type        = string
}

variable "lambda_handler" {
  description = "Lambda function handler (e.g., index.handler)"
  type        = string
}

variable "lambda_source_path" {
  description = "Path to Lambda function source code directory"
  type        = string
}

###############################################################################
# Lambda Configuration
###############################################################################

variable "lambda_description" {
  description = "Description of the Lambda function"
  type        = string
  default     = "Lambda function managed by Terraform"
}

variable "lambda_memory_size" {
  description = "Amount of memory in MB for Lambda function"
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_environment_variables" {
  description = "Environment variables for Lambda function"
  type        = map(string)
  default     = {}
}

variable "lambda_publish" {
  description = "Whether to publish creation/change as new Lambda Function Version"
  type        = bool
  default     = false
}

variable "lambda_layers" {
  description = "List of Lambda Layer ARNs to attach to the function"
  type        = list(string)
  default     = []
}

variable "lambda_vpc_subnet_ids" {
  description = "List of subnet IDs for Lambda VPC configuration"
  type        = list(string)
  default     = null
}

variable "lambda_vpc_security_group_ids" {
  description = "List of security group IDs for Lambda VPC configuration"
  type        = list(string)
  default     = []
}

variable "lambda_tracing_mode" {
  description = "Tracing mode for Lambda function (Active or PassThrough)"
  type        = string
  default     = null
}

variable "lambda_dead_letter_arn" {
  description = "ARN of the SNS topic or SQS queue for dead letter configuration"
  type        = string
  default     = null
}

variable "lambda_log_retention_days" {
  description = "CloudWatch log retention period in days for Lambda"
  type        = number
  default     = 14
}

variable "lambda_log_kms_key_id" {
  description = "KMS key ID for encrypting Lambda CloudWatch logs"
  type        = string
  default     = null
}

variable "lambda_tags" {
  description = "Additional tags for Lambda function"
  type        = map(string)
  default     = {}
}

variable "create_lambda_package" {
  description = "Whether to create Lambda deployment package from source"
  type        = bool
  default     = true
}

variable "lambda_existing_package_path" {
  description = "Path to existing Lambda deployment package (zip file)"
  type        = string
  default     = null
}

variable "create_lambda_alias" {
  description = "Whether to create a Lambda function alias"
  type        = bool
  default     = false
}

variable "lambda_alias_name" {
  description = "Name of the Lambda function alias"
  type        = string
  default     = "live"
}

variable "lambda_custom_policies" {
  description = "List of custom IAM policy statements for Lambda"
  type = list(object({
    sid       = string
    effect    = string
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}

###############################################################################
# API Gateway Configuration
###############################################################################

variable "api_gateway_description" {
  description = "Description of the API Gateway"
  type        = string
  default     = "API Gateway managed by Terraform"
}

variable "api_gateway_stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "dev"
}

variable "api_gateway_endpoint_type" {
  description = "API Gateway endpoint type (REGIONAL, EDGE, PRIVATE)"
  type        = string
  default     = "REGIONAL"
}

variable "api_gateway_authorization_type" {
  description = "Authorization type for API Gateway methods (NONE, AWS_IAM, CUSTOM, COGNITO_USER_POOLS)"
  type        = string
  default     = "NONE"
}

variable "api_gateway_xray_tracing_enabled" {
  description = "Enable X-Ray tracing for API Gateway"
  type        = bool
  default     = false
}

variable "enable_api_gateway_logging" {
  description = "Enable CloudWatch logging for API Gateway"
  type        = bool
  default     = true
}

variable "api_gateway_logging_level" {
  description = "API Gateway logging level (OFF, ERROR, INFO)"
  type        = string
  default     = "INFO"
}

variable "api_gateway_metrics_enabled" {
  description = "Enable detailed CloudWatch metrics for API Gateway"
  type        = bool
  default     = true
}

variable "api_gateway_data_trace_enabled" {
  description = "Enable data trace logging for API Gateway"
  type        = bool
  default     = false
}

variable "api_gateway_log_retention_days" {
  description = "CloudWatch log retention period in days for API Gateway"
  type        = number
  default     = 14
}

variable "api_gateway_log_kms_key_id" {
  description = "KMS key ID for encrypting API Gateway CloudWatch logs"
  type        = string
  default     = null
}

variable "api_gateway_throttling_burst_limit" {
  description = "API Gateway throttling burst limit"
  type        = number
  default     = 5000
}

variable "api_gateway_throttling_rate_limit" {
  description = "API Gateway throttling rate limit"
  type        = number
  default     = 10000
}

variable "api_gateway_tags" {
  description = "Additional tags for API Gateway"
  type        = map(string)
  default     = {}
}

###############################################################################
# CORS Configuration
###############################################################################

variable "enable_cors" {
  description = "Enable CORS for API Gateway"
  type        = bool
  default     = false
}

variable "cors_allow_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default     = ["*"]
}

variable "cors_allow_methods" {
  description = "List of allowed HTTP methods for CORS"
  type        = list(string)
  default     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
}

variable "cors_allow_headers" {
  description = "List of allowed headers for CORS"
  type        = list(string)
  default     = ["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token"]
}

###############################################################################
# Common Tags
###############################################################################

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}


variable "api_gateway_principals_identifiers" {
  description = "API Gateway Principals Identifiers"
  type        = string
  default     = null
}

variable "lambda_principals_identifiers" {
  description = "Lambda Principals Identifiers"
  type        = string
  default     = null
}

variable "aws_iam_role_assume_role_policy" {
  description = "aws iam role assume role policy"
  type        = string
  default     = null
}


variable "aws_iam_policy_lambda_vpc_arn" {
  description = "aws iam policy lambda vpc arn"
  type        = string
  default     = null
}

variable "aws_iam_policy_lambda_xray_arn" {
  description = "aws iam policy lambda xray arn"
  type        = string
  default     = null
}


variable "aws_iam_policy_apigw_cloudwatch_arn" {
  description = "aws iam policy apigw cloudwatch arn"
  type        = string
  default     = null
}

