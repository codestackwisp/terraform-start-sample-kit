output "api_url" {
  value       = module.api_with_lambda.api_gateway_url
  description = "API Gateway base URL"
}

output "endpoint_url" {
  value       = module.api_with_lambda.full_endpoint_url
  description = "Full endpoint URL to test"
}

output "lambda_name" {
  value       = module.api_with_lambda.lambda_function_name
  description = "Lambda function name"
}

output "test_command" {
  value       = module.api_with_lambda.test_command
  description = "Command to test the API"
}
