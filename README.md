# Terraform API Gateway + Lambda Module

**Simple and beginner-friendly module** to create API Gateway with Lambda integration.


https://docs.aws.amazon.com/config/latest/developerguide/api-gw-associated-with-waf.html

## Structure

```
terraform-simple-module/
├── main.tf                    ← Core module resources
├── variables.tf               ← Module inputs
├── outputs.tf                 ← Module outputs
├── versions.tf                ← Requirements
├── README.md                  ← This file
└── examples/
    └── python-lambda/         ← Working example
        ├── main.tf            ← How to use module
        ├── variables.tf       ← Example inputs
        ├── outputs.tf         ← Example outputs
        ├── terraform.tfvars   ← Example values
        └── lambda/
            └── index.py       ← Python Lambda code
```

## How It Works

### Root Module (main.tf, variables.tf, outputs.tf, versions.tf)

The root module contains:
1. **Lambda**: Uses `terraform-aws-modules/lambda/aws` to create Lambda
2. **API Gateway**: Creates REST API
3. **Integration**: Connects API Gateway → Lambda
4. **Permissions**: Allows API Gateway to call Lambda
5. **Logs**: CloudWatch logging

**You provide:**
- Lambda ZIP file path (`lambda_zip_file` variable)
- API name and Lambda name
- Other configurations (runtime, memory, etc)

**You get:**
- API Gateway URL
- Lambda function name
- Test commands

### Example (examples/python-lambda/)

The example shows:
1. How to create a ZIP file from Python code
2. How to call the root module
3. How to pass variables
4. What outputs you receive

## Quick Start

### Step 1: Check Prerequisites

```bash
terraform version
aws --version
aws sts get-caller-identity
```

### Step 2: Navigate to Example

```bash
cd examples/python-lambda
```

### Step 3: Initialize

```bash
terraform init
```

### Step 4: Plan

```bash
terraform plan
```

### Step 5: Deploy

```bash
terraform apply
```

### Step 6: Get Outputs

```bash
terraform output
```

You'll see:
- `api_url` - Base API Gateway URL
- `endpoint_url` - Full URL to call
- `lambda_name` - Lambda function name
- `test_command` - Ready-to-run test
- `logs_command` - Ready-to-run logs command

### Step 7: Test the API

```bash
# Option 1: Use the test command from outputs
curl -X POST https://YOUR_URL/data -H 'Content-Type: application/json' -d '{"action": "test"}'

# Option 2: View logs
aws logs tail /aws/lambda/my-lambda-function --follow
```

### Step 8: Cleanup

```bash
terraform destroy
```

## Module Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `api_name` | string | Yes | - | API Gateway name |
| `lambda_function_name` | string | Yes | - | Lambda function name |
| `lambda_zip_file` | string | Yes | - | Path to Lambda ZIP file |
| `lambda_handler` | string | No | `index.lambda_handler` | Lambda handler |
| `lambda_runtime` | string | No | `python3.11` | Lambda runtime |
| `lambda_timeout` | number | No | `60` | Timeout in seconds |
| `lambda_memory_size` | number | No | `256` | Memory in MB |
| `endpoint_path` | string | No | `data` | API endpoint path |
| `http_method` | string | No | `POST` | HTTP method |
| `stage_name` | string | No | `dev` | API stage |
| `environment_variables` | map | No | `{}` | Lambda env vars |

## Module Outputs

| Output | Description |
|--------|-------------|
| `api_gateway_url` | Base API Gateway URL |
| `full_endpoint_url` | Complete endpoint URL |
| `lambda_function_name` | Lambda function name |
| `lambda_function_arn` | Lambda function ARN |
| `test_command` | Ready-to-run test command |
| `logs_command` | Ready-to-run logs command |

## What Gets Created

1. **Lambda Function** - Runs your Python code
2. **API Gateway REST API** - Public HTTP endpoint
3. **API Resource** - Specific path (e.g., `/data`)
4. **API Method** - HTTP method (e.g., POST)
5. **Integration** - Connects API → Lambda
6. **Lambda Permission** - Allows API to invoke Lambda
7. **CloudWatch Logs** - Logs Lambda execution

## Python Lambda Example

The example includes `lambda/index.py`:

```python
def lambda_handler(event, context):
    # event = API Gateway event
    # context = Lambda context
    
    # Get request body
    body = json.loads(event.get('body', '{}'))
    
    # Process request
    response = {
        'message': 'Success',
        'received': body
    }
    
    # Return HTTP response
    return {
        'statusCode': 200,
        'body': json.dumps(response),
        'headers': {'Content-Type': 'application/json'}
    }
```

## How to Use as a Module

In your own Terraform project:

```hcl
# Create Lambda ZIP from Python file
data "archive_file" "lambda" {
  type        = "zip"
  source_file = "path/to/lambda.py"
  output_path = "lambda.zip"
}

# Use this module
module "my_api" {
  source = "path/to/terraform-simple-module"

  api_name             = "my-api"
  lambda_function_name = "my-function"
  lambda_zip_file      = data.archive_file.lambda.output_path

  endpoint_path = "api"
  http_method   = "POST"
}

# Get the URL
output "api_url" {
  value = module.my_api.full_endpoint_url
}
```

## Troubleshooting

### Error: "Lambda invocation failed"
- Check Lambda logs: `aws logs tail /aws/lambda/FUNCTION_NAME --follow`
- Verify Lambda handler syntax
- Check Lambda permissions

### Error: "API returns 502"
- Check CloudWatch logs
- Verify integration type is AWS_PROXY
- Check Lambda handler returns correct format

### Error: "Terraform not found"
- Install Terraform from terraform.io
- Add to PATH

### Error: "AWS credentials not found"
- Run: `aws configure`
- Enter AWS credentials
