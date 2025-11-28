###############################################################################
# Outputs for Simple Audit API Example
###############################################################################

output "api_gateway_url" {
  description = "URL to invoke the Audit API"
  value       = module.audit_api.api_gateway_url
}

output "api_endpoint" {
  description = "Full endpoint URL for posting audit events"
  value       = "${module.audit_api.api_gateway_url}/audit"
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.audit_api.lambda_function_name
}

output "lambda_log_group" {
  description = "CloudWatch Log Group for Lambda function"
  value       = module.audit_api.lambda_log_group_name
}

output "api_gateway_log_group" {
  description = "CloudWatch Log Group for API Gateway"
  value       = module.audit_api.api_gateway_log_group_name
}

output "curl_test_command" {
  description = "Sample curl command to test the API"
  value       = <<-EOT
    # Test the audit endpoint
    curl -X POST ${module.audit_api.api_gateway_url}/audit \
      -H "Content-Type: application/json" \
      -d '{
        "eventType": "USER_LOGIN",
        "userId": "user123",
        "action": "LOGIN",
        "resource": "/dashboard",
        "result": "SUCCESS"
      }'

    # Test the health endpoint
    curl -X GET ${module.audit_api.api_gateway_url}/health
  EOT
}
