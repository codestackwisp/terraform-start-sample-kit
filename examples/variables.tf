variable "aws_region" {
  type        = string
  description = "AWS Region"
  default     = "eu-west-2"
}

variable "api_name" {
  type        = string
  description = "Name of the API"
  default     = "my-api-gateway"
}

variable "lambda_function_name" {
  type        = string
  description = "Name of Lambda function"
  default     = "my-lambda-function"
}
