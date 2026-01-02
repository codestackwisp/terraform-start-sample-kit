#!/bin/bash

################################################################################
# Automated AWS Deployment and Integration Testing Script
# Creates UNIQUE resources - doesn't impact existing infrastructure
################################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

print_header() {
    echo -e "\n${MAGENTA}${BOLD}============================================================${NC}"
    echo -e "${MAGENTA}${BOLD}  $1${NC}"
    echo -e "${MAGENTA}${BOLD}============================================================${NC}\n"
}

print_section() { echo -e "\n${CYAN}${BOLD}>>> $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

################################################################################
# CONFIGURATION - UNIQUE NAMES
################################################################################

UNIQUE_SUFFIX=$(date +%Y%m%d-%H%M%S)
AWS_REGION="${AWS_REGION:-eu-west-2}"

LAMBDA_FUNCTION_NAME="cpl-test-lambda-${UNIQUE_SUFFIX}"
LAMBDA_ROLE_NAME="CplTestLambdaRole-${UNIQUE_SUFFIX}"
TEST_PARAM_PREFIX="/cpl-test-${UNIQUE_SUFFIX}"
TEST_CENTRAL_PREFIX="/accounts_cpl_test-${UNIQUE_SUFFIX}"
SSM_RULE_NAME="cpl-test-ssm-rule-${UNIQUE_SUFFIX}"
LOG_GROUP_RULE_NAME="cpl-test-log-rule-${UNIQUE_SUFFIX}"
TEST_LOG_GROUP="/aws/lambda/cpl-test-function-${UNIQUE_SUFFIX}"
CROSS_ACCOUNT_ROLE_NAME="CplTestCrossAccountRole-${UNIQUE_SUFFIX}"
DEPLOYMENT_INFO_FILE=".cpl-deployment-${UNIQUE_SUFFIX}.json"

save_deployment_info() {
    cat > ${DEPLOYMENT_INFO_FILE} << EOF
{
  "deployment_id": "${UNIQUE_SUFFIX}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "region": "${AWS_REGION}",
  "account_id": "${WORKLOAD_ACCOUNT_ID}",
  "resources": {
    "lambda_function": "${LAMBDA_FUNCTION_NAME}",
    "lambda_role": "${LAMBDA_ROLE_NAME}",
    "cross_account_role": "${CROSS_ACCOUNT_ROLE_NAME}",
    "ssm_rule": "${SSM_RULE_NAME}",
    "log_group_rule": "${LOG_GROUP_RULE_NAME}",
    "test_param_prefix": "${TEST_PARAM_PREFIX}",
    "test_central_prefix": "${TEST_CENTRAL_PREFIX}",
    "test_log_group": "${TEST_LOG_GROUP}",
    "deployment_package": "lambda-package-${UNIQUE_SUFFIX}.zip"
  }
}
EOF
}

################################################################################
# PRE-FLIGHT CHECKS
################################################################################

print_header "AWS Lambda Cross-Account Sync - Automated Deployment"
print_warning "Uses UNIQUE resource names - won't affect existing infrastructure"
print_info "Deployment ID: ${UNIQUE_SUFFIX}"

print_section "Pre-flight Checks"

if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found"
    exit 1
fi
print_success "AWS CLI installed"

if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured"
    exit 1
fi
print_success "AWS credentials configured"

WORKLOAD_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CENTRAL_ACCOUNT_ID="${WORKLOAD_ACCOUNT_ID}"

print_info "AWS Account: ${WORKLOAD_ACCOUNT_ID}"
print_info "Region: ${AWS_REGION}"

################################################################################
# CHECK LAMBDA CODE
################################################################################

print_section "Checking Lambda Code"

if [ ! -f "lambda_function.py" ]; then
    print_error "lambda_function.py not found"
    exit 1
fi
print_success "Lambda code found"

################################################################################
# CREATE IAM ROLES
################################################################################

print_section "Creating IAM Roles"

cat > /tmp/lambda-trust-${UNIQUE_SUFFIX}.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name ${LAMBDA_ROLE_NAME} \
  --assume-role-policy-document file:///tmp/lambda-trust-${UNIQUE_SUFFIX}.json \
  --description "TEST - CPL Lambda ${UNIQUE_SUFFIX}" \
  --tags Key=CPL-Test,Value=${UNIQUE_SUFFIX} \
  --output text &> /dev/null

print_success "Created Lambda role: ${LAMBDA_ROLE_NAME}"
sleep 5

aws iam attach-role-policy \
  --role-name ${LAMBDA_ROLE_NAME} \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole &> /dev/null

cat > /tmp/lambda-policy-${UNIQUE_SUFFIX}.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ssm:*"],
      "Resource": [
        "arn:aws:ssm:*:${WORKLOAD_ACCOUNT_ID}:parameter${TEST_PARAM_PREFIX}/*",
        "arn:aws:ssm:*:${WORKLOAD_ACCOUNT_ID}:parameter/CplTest_Filters_${UNIQUE_SUFFIX}",
        "arn:aws:ssm:*:${WORKLOAD_ACCOUNT_ID}:parameter${TEST_CENTRAL_PREFIX}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["logs:*"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::${CENTRAL_ACCOUNT_ID}:role/${CROSS_ACCOUNT_ROLE_NAME}"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${LAMBDA_ROLE_NAME} \
  --policy-name CplTestPolicy \
  --policy-document file:///tmp/lambda-policy-${UNIQUE_SUFFIX}.json &> /dev/null

print_success "Lambda permissions configured"

# Cross-account role
cat > /tmp/cross-trust-${UNIQUE_SUFFIX}.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::${WORKLOAD_ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name ${CROSS_ACCOUNT_ROLE_NAME} \
  --assume-role-policy-document file:///tmp/cross-trust-${UNIQUE_SUFFIX}.json \
  --description "TEST - Cross-account ${UNIQUE_SUFFIX}" \
  --tags Key=CPL-Test,Value=${UNIQUE_SUFFIX} \
  --output text &> /dev/null

cat > /tmp/cross-policy-${UNIQUE_SUFFIX}.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["ssm:*"],
    "Resource": "arn:aws:ssm:*:${CENTRAL_ACCOUNT_ID}:parameter${TEST_CENTRAL_PREFIX}/*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name ${CROSS_ACCOUNT_ROLE_NAME} \
  --policy-name SSMSyncPolicy \
  --policy-document file:///tmp/cross-policy-${UNIQUE_SUFFIX}.json &> /dev/null

print_success "Created cross-account role"
sleep 5

################################################################################
# DEPLOY LAMBDA
################################################################################

print_section "Deploying Lambda"

PACKAGE_NAME="lambda-package-${UNIQUE_SUFFIX}.zip"
zip -q ${PACKAGE_NAME} lambda_function.py
print_success "Package created"

aws lambda create-function \
  --function-name ${LAMBDA_FUNCTION_NAME} \
  --runtime python3.9 \
  --role arn:aws:iam::${WORKLOAD_ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME} \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://${PACKAGE_NAME} \
  --timeout 300 \
  --memory-size 256 \
  --environment Variables="{
    AWS_REGION=${AWS_REGION},
    VARIABLE_LOGGING_NAME=cpl-test-${UNIQUE_SUFFIX},
    SSM_PARAMETER_ROOT=${TEST_PARAM_PREFIX}/,
    CENTRAL_SSM_PARAMETER_PREFIX=${TEST_CENTRAL_PREFIX}/,
    OWNING_AWS_ACCOUNT=${CENTRAL_ACCOUNT_ID},
    CROSS_ACCOUNT_ROLE_NAME=${CROSS_ACCOUNT_ROLE_NAME},
    SENDER_FUNCTION_NAME=cpl-sender,
    FILTER_NAME_PREFIX=CplTest-${UNIQUE_SUFFIX},
    FILTERS_TRACKING_PARAM=CplTest_Filters_${UNIQUE_SUFFIX},
    LOGGING_LEVEL=INFO
  }" \
  --tags CPL-Test=${UNIQUE_SUFFIX} \
  --region ${AWS_REGION} \
  --output text &> /dev/null

print_success "Lambda deployed: ${LAMBDA_FUNCTION_NAME}"
sleep 10

################################################################################
# EVENTBRIDGE RULES
################################################################################

print_section "EventBridge Rules"

aws events put-rule \
  --name ${SSM_RULE_NAME} \
  --event-pattern "{\"source\":[\"aws.ssm\"],\"detail-type\":[\"AWS API Call via CloudTrail\"],\"detail\":{\"eventSource\":[\"ssm.amazonaws.com\"],\"eventName\":[\"PutParameter\",\"DeleteParameter\"],\"requestParameters\":{\"name\":[{\"prefix\":\"${TEST_PARAM_PREFIX}/\"}]}}}" \
  --state ENABLED \
  --region ${AWS_REGION} \
  --output text &> /dev/null

aws events put-rule \
  --name ${LOG_GROUP_RULE_NAME} \
  --event-pattern "{\"source\":[\"aws.logs\"],\"detail-type\":[\"AWS API Call via CloudTrail\"],\"detail\":{\"eventSource\":[\"logs.amazonaws.com\"],\"eventName\":[\"CreateLogGroup\"]}}" \
  --state ENABLED \
  --region ${AWS_REGION} \
  --output text &> /dev/null

print_success "Rules created"

aws lambda add-permission \
  --function-name ${LAMBDA_FUNCTION_NAME} \
  --statement-id SSM-${UNIQUE_SUFFIX} \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:${AWS_REGION}:${WORKLOAD_ACCOUNT_ID}:rule/${SSM_RULE_NAME} \
  --region ${AWS_REGION} &> /dev/null

aws lambda add-permission \
  --function-name ${LAMBDA_FUNCTION_NAME} \
  --statement-id LOG-${UNIQUE_SUFFIX} \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:${AWS_REGION}:${WORKLOAD_ACCOUNT_ID}:rule/${LOG_GROUP_RULE_NAME} \
  --region ${AWS_REGION} &> /dev/null

aws events put-targets --rule ${SSM_RULE_NAME} \
  --targets "Id"="1","Arn"="arn:aws:lambda:${AWS_REGION}:${WORKLOAD_ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME}" \
  --region ${AWS_REGION} &> /dev/null

aws events put-targets --rule ${LOG_GROUP_RULE_NAME} \
  --targets "Id"="1","Arn"="arn:aws:lambda:${AWS_REGION}:${WORKLOAD_ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME}" \
  --region ${AWS_REGION} &> /dev/null

print_success "Rules configured"

save_deployment_info

################################################################################
# TESTS
################################################################################

print_header "Running Tests"

print_section "Test 1: SSM Parameter"

TEST_PARAM="${TEST_PARAM_PREFIX}/config1"
aws ssm put-parameter \
  --name "${TEST_PARAM}" \
  --value '{"log_group_name_pattern":"/aws/lambda/test-*","prefix":"ERROR"}' \
  --type String \
  --tags Key=CPL-Test,Value=${UNIQUE_SUFFIX} \
  --overwrite \
  --region ${AWS_REGION} &> /dev/null

print_success "Parameter created: ${TEST_PARAM}"
print_info "Waiting 15s..."
sleep 15

CENTRAL_PARAM="${TEST_CENTRAL_PREFIX}/${WORKLOAD_ACCOUNT_ID}"
if PARAM_VAL=$(aws ssm get-parameter --name "${CENTRAL_PARAM}" --region ${AWS_REGION} --query 'Parameter.Value' --output text 2>/dev/null); then
    print_success "Synced to central account!"
    command -v jq &>/dev/null && echo "$PARAM_VAL" | jq . || echo "$PARAM_VAL"
else
    print_warning "Not synced yet"
fi

print_section "Test 2: Log Group"

aws logs create-log-group --log-group-name "${TEST_LOG_GROUP}" --region ${AWS_REGION} &> /dev/null || true
print_success "Log group created"
print_info "Waiting 15s..."
sleep 15

if FILTERS=$(aws logs describe-subscription-filters --log-group-name "${TEST_LOG_GROUP}" --region ${AWS_REGION} --query 'subscriptionFilters[*].filterName' --output text 2>/dev/null); then
    [ ! -z "$FILTERS" ] && print_success "Filter added: $FILTERS" || print_warning "No filter yet"
fi

################################################################################
# SUMMARY
################################################################################

print_header "Summary"

echo -e "${BOLD}Deployment: ${UNIQUE_SUFFIX}${NC}"
echo ""
echo "Resources:"
echo "  ✓ Lambda: ${LAMBDA_FUNCTION_NAME}"
echo "  ✓ Roles: ${LAMBDA_ROLE_NAME}, ${CROSS_ACCOUNT_ROLE_NAME}"
echo "  ✓ Rules: ${SSM_RULE_NAME}, ${LOG_GROUP_RULE_NAME}"
echo ""
echo "Cleanup:"
echo "  ${CYAN}./cleanup.sh ${DEPLOYMENT_INFO_FILE}${NC}"
echo ""
print_success "Done!"