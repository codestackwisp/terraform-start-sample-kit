# Example - Python Lambda with API Gateway

This example shows how to use the root module.

## Files

- `lambda/index.py` - Python Lambda code
- `main.tf` - How to use the module
- `variables.tf` - Input variables
- `outputs.tf` - Output values
- `terraform.tfvars` - Default values

## How to Run

### 1. Navigate here

```bash
cd examples/python-lambda
```

### 2. Initialize Terraform

```bash
terraform init
```

This downloads the AWS provider and terraform-aws-modules.

### 3. Plan deployment

```bash
terraform plan
```

Shows what will be created.

### 4. Deploy

```bash
terraform apply
```

Creates everything in AWS. Type `yes` when asked.

Takes 3-5 minutes.

### 5. Get outputs

```bash
terraform output
```

You'll see:
```
api_url = "https://abc123.execute-api.us-east-1.amazonaws.com/dev/"
endpoint_url = "https://abc123.execute-api.us-east-1.amazonaws.com/dev/data"
lambda_name = "my-lambda-function"
test_command = "curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/dev/data ..."
logs_command = "aws logs tail /aws/lambda/my-lambda-function --follow"
```

### 6. Test the API

#### Option A: Use the test command from outputs

```bash
curl -X POST https://YOUR_URL/data -H 'Content-Type: application/json' -d '{"action": "test"}'
```

Expected response:
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "message": "Request received and processed",
  "received_data": {
    "action": "test"
  },
  "http_method": "POST",
  "path": "/data",
  "status": "success"
}
```

#### Option B: View Lambda logs

```bash
aws logs tail /aws/lambda/my-lambda-function --follow
```

### 7. Cleanup

When done, destroy everything:

```bash
terraform destroy
```

Type `yes` when asked. Takes 2-3 minutes.

## Customize

### Change API name

Edit `terraform.tfvars`:
```hcl
api_name = "my-custom-api"
```

Run:
```bash
terraform apply
```

### Change endpoint path

Edit `main.tf`:
```hcl
endpoint_path = "custom-path"
```

### Change Lambda code

Edit `lambda/index.py`:
```python
def lambda_handler(event, context):
    # Your code here
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'hello'})
    }
```

Run:
```bash
terraform apply
```

Terraform automatically repackages and updates the Lambda.

### Change HTTP method

Edit `main.tf`:
```hcl
http_method = "GET"  # or PUT, DELETE, etc
```

### Add more endpoints

Create another module call in `main.tf`:
```hcl
module "api_endpoint_2" {
  source = "../../"
  
  api_name = var.api_name
  ...
  endpoint_path = "another-path"
}
```

## Environment Variables

Pass variables to Lambda:

In `main.tf`:
```hcl
environment_variables = {
  DATABASE_URL = "postgresql://..."
  LOG_LEVEL = "DEBUG"
}
```

Access in Lambda:

```python
import os

db_url = os.environ.get('DATABASE_URL')
log_level = os.environ.get('LOG_LEVEL')
```

## How the module works

1. **main.tf creates ZIP**
   - Takes `lambda/index.py`
   - Creates `lambda/function.zip`

2. **main.tf calls root module**
   - Passes ZIP file path
   - Passes configuration

3. **Root module creates**
   - Lambda function from ZIP
   - API Gateway
   - Integration
   - Permissions
   - Logs

4. **Outputs returned**
   - API URL
   - Lambda name
   - Test commands

## Testing Flow

```
You write code
   ↓
terraform apply
   ↓
Terraform creates ZIP
   ↓
Root module deployed
   ↓
API Gateway created
   ↓
You get URL
   ↓
You test API
   ↓
Lambda runs your code
   ↓
You see response
   ↓
You check logs
```

## Next Steps

1. Modify `lambda/index.py` with your logic
2. Test locally (optional)
3. Run `terraform apply`
4. Test the endpoint
5. View logs
6. Iterate

## Cost

**Free tier covers:**
- 1 million API Gateway requests
- 1 million Lambda invocations
- 400,000 GB-seconds of Lambda

This example: **FREE** (minimal usage)

## Troubleshooting

### API returns error
- Check logs: `aws logs tail /aws/lambda/my-lambda-function --follow`
- Look for error message
- Fix Python code
- Run `terraform apply`

### Lambda timeout
- Increase in main.tf: `lambda_timeout = 120`
- Run `terraform apply`

### Module not found
- Run `terraform init` again
- Check you're in correct directory

### AWS credentials error
- Run `aws configure`
- Enter credentials

## Ready to use!

Just edit `lambda/index.py` and deploy!
