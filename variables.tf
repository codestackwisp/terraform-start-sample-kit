variable "aws_region" {
  type        = string
  description = "AWS Region"
  default     = "us-east-1"
}

variable "api_name" {
  type        = string
  description = "Name of API Gateway"
}

variable "lambda_function_name" {
  type        = string
  description = "Name of Lambda function"
}

variable "lambda_handler" {
  type        = string
  description = "Lambda handler (e.g., index.lambda_handler for Python)"
  default     = "index.lambda_handler"
}

variable "lambda_runtime" {
  type        = string
  description = "Lambda runtime (e.g., python3.11, nodejs18.x)"
  default     = "python3.11"
}

variable "lambda_timeout" {
  type        = number
  description = "Lambda timeout in seconds"
  default     = 60
}

variable "lambda_memory_size" {
  type        = number
  description = "Lambda memory in MB (128-10240)"
  default     = 256
}

variable "lambda_zip_file" {
  type        = string
  description = "Path to Lambda ZIP file"
}

variable "endpoint_path" {
  type        = string
  description = "API Gateway endpoint path (e.g., 'audit')"
  default     = "data"
}

variable "http_method" {
  type        = string
  description = "HTTP method (GET, POST, PUT, DELETE)"
  default     = "POST"
}

variable "stage_name" {
  type        = string
  description = "API stage name (dev, prod, etc)"
  default     = "dev"
}

variable "environment_variables" {
  type        = map(string)
  description = "Environment variables for Lambda"
  default     = {}
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
