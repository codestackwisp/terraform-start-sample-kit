# ROOT MODULE - outputs.tf
# What you get back after terraform apply

output "api_gateway_url" {
  value       = aws_api_gateway_stage.main.invoke_url
  description = "API Gateway invoke URL"
}

output "full_endpoint_url" {
  value       = "${aws_api_gateway_stage.main.invoke_url}${aws_api_gateway_resource.endpoint.path_part}"
  description = "Full endpoint URL to test"
}

output "lambda_function_name" {
  value       = module.lambda_function.lambda_function_name
  description = "Lambda function name"
}

output "lambda_function_arn" {
  value       = module.lambda_function.lambda_function_arn
  description = "Lambda function ARN"
}

output "api_gateway_id" {
  value       = aws_api_gateway_rest_api.main.id
  description = "API Gateway ID"
}

output "test_command" {
  value = "curl -X ${var.http_method} ${aws_api_gateway_stage.main.invoke_url}${aws_api_gateway_resource.endpoint.path_part} -H 'Content-Type: application/json' -d '{\"action\": \"test\"}'"
  description = "Command to test the API"
}

output "logs_command" {
  value = "aws logs tail /aws/lambda/${module.lambda_function.lambda_function_name} --follow"
  description = "Command to view Lambda logs"
}
