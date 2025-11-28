# Audit API with CloudWatch Logging

This is a example that demonstrates audit event logging using CloudWatch

## Overview

This example creates:
- ✅ API Gateway REST API
- ✅ Lambda function for audit event processing
- ✅ CloudWatch log groups for Lambda and API Gateway
- ✅ Structured JSON logging for easy querying
- ✅ CORS enabled for web applications


Perfect for:
- 🎯 Simple audit logging
- 🎯 Development/testing environments
- 🎯 Learning the module basics
- 🎯 Low-cost deployments ($0-$5/month)

## Architecture

```
┌──────────┐      ┌─────────────┐      ┌────────────┐      ┌─────────────┐
│  Client  │─────▶│API Gateway  │─────▶│  Lambda    │─────▶│ CloudWatch  │
└──────────┘      └─────────────┘      └────────────┘      │    Logs     │
                         │                                   └─────────────┘
                         ▼
                  ┌─────────────┐
                  │ CloudWatch  │
                  │    Logs     │
                  └─────────────┘
```

## Features

### Audit Event Logging
- Receives audit events via POST /audit
- Logs structured JSON to CloudWatch
- Captures metadata (IP, user agent, timestamp)
- No database required

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/audit` | POST | Submit audit event |
| `/health` | GET | Health check |
| `/` | GET | API information |

### CloudWatch Integration
- Structured JSON logs for easy querying
- Retention configurable (default: 14 days)
- Use CloudWatch Insights for log analysis
- Real-time monitoring

## Quick Start

### Prerequisites
- Terraform >= 1.0
- AWS credentials configured
- AWS CLI (optional, for testing)

### Deploy

```bash
# Navigate to example
cd examples

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy
terraform apply
```

### Test the API

After deployment, Terraform outputs the API URL and a sample curl command.

```bash
# Get the API URL
API_URL=$(terraform output -raw api_gateway_url)

# Test health check
curl ${API_URL}health

# Submit audit event
curl -X POST ${API_URL}audit \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "USER_LOGIN",
    "userId": "user123",
    "action": "LOGIN",
    "resource": "/dashboard",
    "result": "SUCCESS",
    "additionalData": {
      "loginMethod": "SSO",
      "mfaUsed": true
    }
  }'
```

Expected response:
```json
{
  "message": "Audit event logged successfully",
  "timestamp": "2024-11-28T10:30:45.123Z",
  "requestId": "abc-123-def-456"
}
```

## Viewing Logs

### AWS Console

1. Go to CloudWatch → Log groups
2. Find `/aws/lambda/audit-api-dev` (or your project name)
3. View log streams

### AWS CLI

```bash
# Get Lambda function name
FUNCTION_NAME=$(terraform output -raw lambda_function_name)

# Tail Lambda logs
aws logs tail /aws/lambda/${FUNCTION_NAME} --follow

# Filter for audit events only
aws logs tail /aws/lambda/${FUNCTION_NAME} --follow --filter-pattern "AUDIT_EVENT"
```

### CloudWatch Insights

Use CloudWatch Insights for powerful log queries:

```
# Find all audit events
fields @timestamp, data.eventType, data.userId, data.action, data.result
| filter type = "AUDIT_EVENT"
| sort @timestamp desc
| limit 100

# Count events by type
fields data.eventType
| filter type = "AUDIT_EVENT"
| stats count() by data.eventType

# Failed actions
fields @timestamp, data.userId, data.action, data.resource
| filter type = "AUDIT_EVENT" and data.result = "FAILURE"
| sort @timestamp desc

# Events by specific user
fields @timestamp, data.action, data.resource, data.result
| filter type = "AUDIT_EVENT" and data.userId = "user123"
| sort @timestamp desc
```

## Audit Event Format

### Request Format

```json
{
  "eventType": "USER_ACTION",
  "userId": "user123",
  "action": "LOGIN|LOGOUT|CREATE|UPDATE|DELETE",
  "resource": "/path/to/resource",
  "result": "SUCCESS|FAILURE",
  "additionalData": {
    "key": "value"
  }
}
```

### Required Fields
- `eventType` - Type of event (string)
- `userId` - User identifier (string)
- `action` - Action performed (string)

### Optional Fields
- `resource` - Resource accessed (string)
- `result` - Result of action (string, default: "SUCCESS")
- `additionalData` - Additional metadata (object)

### Logged Format (in CloudWatch)

```json
{
  "level": "INFO",
  "type": "AUDIT_EVENT",
  "data": {
    "timestamp": "2024-11-28T10:30:45.123Z",
    "eventType": "USER_LOGIN",
    "userId": "user123",
    "action": "LOGIN",
    "resource": "/dashboard",
    "result": "SUCCESS",
    "metadata": {
      "sourceIp": "203.0.113.45",
      "userAgent": "Mozilla/5.0...",
      "requestId": "abc-123-def-456",
      "environment": "dev",
      "additionalData": {
        "loginMethod": "SSO"
      }
    }
  }
}
```

## Configuration

### Customize Deployment

Edit `variables.tf` or create `terraform.tfvars`:

```hcl
project_name = "my-audit-api"
environment  = "prod"
aws_region   = "us-west-2"
```

### Adjust Lambda Settings

Edit `main.tf`:

```hcl
module "audit_api" {
  # ... other config ...
  
  lambda_memory_size = 512  # Increase memory
  lambda_timeout     = 60   # Increase timeout
  
  lambda_log_retention_days = 30  # Keep logs longer
}
```

### Enable X-Ray Tracing

```hcl
module "audit_api" {
  # ... other config ...
  
  lambda_tracing_mode              = "Active"
  api_gateway_xray_tracing_enabled = true
}
```

## Cost Estimate

For **1 million audit events per month**:

| Service | Cost |
|---------|------|
| API Gateway | ~$3.50 |
| Lambda | ~$0.20 |
| CloudWatch Logs (1 GB) | ~$0.50 |
| **Total** | **~$5/month** |

With 14-day retention (default): even lower costs!

## Testing

### Local Testing

```bash
# Test Lambda function locally
cd lambda_code
python3 -c "
import index
import json

event = {
    'httpMethod': 'POST',
    'path': '/audit',
    'body': json.dumps({
        'eventType': 'TEST',
        'userId': 'test-user',
        'action': 'TEST_ACTION'
    })
}

result = index.handler(event, None)
print(json.dumps(result, indent=2))
"
```

### Load Testing

```bash
# Simple load test with Apache Bench
API_URL=$(terraform output -raw api_gateway_url)

# 1000 requests, 10 concurrent
ab -n 1000 -c 10 -p event.json -T application/json ${API_URL}audit
```

Create `event.json`:
```json
{
  "eventType": "LOAD_TEST",
  "userId": "loadtest",
  "action": "TEST",
  "resource": "/test"
}
```

## Monitoring

### CloudWatch Metrics

Monitor these key metrics:
- Lambda: Invocations, Errors, Duration
- API Gateway: Count, 4XXError, 5XXError, Latency

### CloudWatch Alarms

Create alarms for critical issues:

```hcl
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "audit-api-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  
  dimensions = {
    FunctionName = module.audit_api.lambda_function_name
  }
}
```

## Troubleshooting

### Issue: 400 Bad Request
**Cause**: Missing required fields  
**Solution**: Ensure eventType, userId, and action are included

### Issue: 500 Internal Server Error
**Cause**: Lambda function error  
**Solution**: Check Lambda logs:
```bash
aws logs tail /aws/lambda/audit-api-dev --follow
```

### Issue: No logs appearing
**Cause**: Log retention or IAM permissions  
**Solution**: 
1. Check IAM role has CloudWatch Logs permissions
2. Verify log group exists
3. Wait a few seconds for logs to appear

### Issue: CORS errors
**Cause**: CORS not properly configured  
**Solution**: Module has CORS enabled by default, check browser console for specific error

## Customization Examples

### Add Authentication

```hcl
module "audit_api" {
  # ... other config ...
  
  api_gateway_authorization_type = "AWS_IAM"
}
```

### Add More Memory

```hcl
module "audit_api" {
  # ... other config ...
  
  lambda_memory_size = 1024
}
```

### Change Log Retention

```hcl
module "audit_api" {
  # ... other config ...
  
  lambda_log_retention_days      = 90
  api_gateway_log_retention_days = 90
}
```

## Next Steps

Once comfortable with this simple example:

1. **Explore the complete example** - See `examples/complete/` for DynamoDB and S3 integration
2. **Add authentication** - Use API keys, Cognito, or Lambda authorizers
3. **Set up monitoring** - Create CloudWatch dashboards and alarms
4. **Production deployment** - Deploy to staging/prod environments
5. **Log analysis** - Set up CloudWatch Insights queries and dashboards

## Cleanup

To remove all resources:

```bash
terraform destroy
```

## Files

```
example/
├── README.md              # This file
├── main.tf                # Main configuration
├── variables.tf           # Input variables
├── outputs.tf             # Output values
└── lambda_code/
    ├── index.py           # Lambda function code
    └── requirements.txt   # Python dependencies (empty)
```

## Related Documentation

- [Module README](../../README.md)

## Support

For issues or questions:
- Check module documentation
- Review CloudWatch logs
- Open an issue on GitLab

