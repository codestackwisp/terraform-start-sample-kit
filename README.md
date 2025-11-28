# terraform-start-sample-kit

## API Gateway Lambda Terraform Module

This Terraform module creates an AWS API Gateway (REST API) with proxy integration to a Lambda function. The module follows AWS best practices and creates all necessary resources including IAM roles, permissions, and CloudWatch log groups.

## Features

- ✅ AWS API Gateway (REST API) with proxy integration
- ✅ Lambda Function with configurable runtime
- ✅ Automatic IAM role and policy creation
- ✅ CloudWatch logging for both API Gateway and Lambda
- ✅ Support for environment variables
- ✅ Configurable CORS settings
- ✅ API Gateway deployment and stage management
- ✅ Lambda function versioning support

## Usage

```hcl
module "audit_api_lambda" {
  source = "git::https://gitlab.com/your-org/api-gateway-lambda-module.git?ref=v1.0.0"

  # Required variables
  project_name    = "audit-api"
  environment     = "dev"
  lambda_runtime  = "python3.11"
  lambda_handler  = "index.handler"

  # Lambda source code (deployment package will be created separately)
  lambda_source_path = "${path.module}/lambda_code"

  # Optional: Environment variables for Lambda
  lambda_environment_variables = {
    ENVIRONMENT = "dev"
    LOG_LEVEL   = "INFO"
  }

  # Optional: CORS configuration
  enable_cors = true
  cors_allow_origins = ["*"]
  cors_allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  cors_allow_headers = ["Content-Type", "Authorization"]

  # Optional: API Gateway settings
  api_gateway_stage_name = "dev"
  enable_api_gateway_logging = true

  # Tags
  tags = {
    Project     = "AuditAPI"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | >= 5.0 |

## Providers

| Name | Version |
|------|---------|
| aws | >= 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | n/a | yes |
| lambda_runtime | Lambda function runtime | `string` | n/a | yes |
| lambda_handler | Lambda function handler | `string` | n/a | yes |
| lambda_source_path | Path to Lambda function source code | `string` | n/a | yes |
| lambda_memory_size | Amount of memory in MB for Lambda | `number` | `256` | no |
| lambda_timeout | Lambda function timeout in seconds | `number` | `30` | no |
| lambda_environment_variables | Environment variables for Lambda | `map(string)` | `{}` | no |
| enable_cors | Enable CORS for API Gateway | `bool` | `false` | no |
| cors_allow_origins | CORS allowed origins | `list(string)` | `["*"]` | no |
| cors_allow_methods | CORS allowed methods | `list(string)` | `["GET", "POST", "OPTIONS"]` | no |
| cors_allow_headers | CORS allowed headers | `list(string)` | `["Content-Type"]` | no |
| api_gateway_stage_name | API Gateway stage name | `string` | `"dev"` | no |
| enable_api_gateway_logging | Enable API Gateway logging | `bool` | `true` | no |
| tags | Tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| api_gateway_url | The URL of the API Gateway |
| api_gateway_id | The ID of the API Gateway |
| api_gateway_execution_arn | The execution ARN of the API Gateway |
| lambda_function_name | The name of the Lambda function |
| lambda_function_arn | The ARN of the Lambda function |
| lambda_role_arn | The ARN of the Lambda IAM role |

## Examples

See the [examples](./examples) directory for complete examples.

## Module Structure

```
.
├── README.md
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── lambda.tf
├── api_gateway.tf
├── iam.tf
├── examples/
└── .gitlab-ci.yml
```

## CI/CD Pipeline

This module includes a GitLab CI/CD pipeline that:
- Validates Terraform code
- Runs security scans
- Publishes the module to GitLab registry
- Creates release tags

## License

Apache 2.0 Licensed. See LICENSE for full details.
