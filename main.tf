###############################################################################
# API Gateway Lambda Module - Main Configuration
###############################################################################

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "Terraform"
      Module      = "api-gateway-lambda"
    }
  )
}

###############################################################################
# Random ID for unique naming
###############################################################################

resource "random_id" "suffix" {
  byte_length = 4
}
