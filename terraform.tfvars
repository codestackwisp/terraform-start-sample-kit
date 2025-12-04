aws_region           = "us-east-1"

api_name             = "project-api"
lambda_function_name = "project-lambda"

# Path to Lambda zip package
lambda_zip_file      = "lambda.zip"

lambda_handler       = "index.lambda_handler"
lambda_runtime       = "python3.11"

lambda_timeout       = 60
lambda_memory_size   = 256

endpoint_path = "data"
http_method   = "POST"
stage_name    = "dev"

# Lambda environment variables
environment_variables = {
  APP_ENV   = "dev"
  LOG_LEVEL = "info"
}

# Tags applied to all resources
tags = {
  Project = "ProjectAPI"
  Env     = "dev"
}
