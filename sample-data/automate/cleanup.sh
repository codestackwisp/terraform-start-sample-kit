#!/bin/bash

################################################################################
# Automated Cleanup Script for CPL Test Deployment
# Deletes ALL resources created by deploy_and_test.sh
################################################################################

set -e

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
# LOAD DEPLOYMENT INFO
################################################################################

DEPLOYMENT_FILE="$1"

if [ -z "$DEPLOYMENT_FILE" ]; then
    # Try to find the most recent deployment file
    DEPLOYMENT_FILE=$(ls -t .cpl-deployment-*.json 2>/dev/null | head -1)
    
    if [ -z "$DEPLOYMENT_FILE" ]; then
        print_error "No deployment file found!"
        echo ""
        echo "Usage: $0 <deployment-info-file>"
        echo "Example: $0 .cpl-deployment-20240102-143022.json"
        echo ""
        echo "Or run from the same directory where you ran deploy_and_test.sh"
        exit 1
    fi
    
    print_warning "Using most recent deployment: ${DEPLOYMENT_FILE}"
    echo ""
    read -p "Continue with cleanup? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Cleanup cancelled"
        exit 0
    fi
fi

if [ ! -f "$DEPLOYMENT_FILE" ]; then
    print_error "Deployment file not found: ${DEPLOYMENT_FILE}"
    exit 1
fi

print_header "CPL Test Resources Cleanup"

print_info "Loading deployment info from: ${DEPLOYMENT_FILE}"

# Parse deployment info
if ! command -v jq &> /dev/null; then
    print_warning "jq not installed - using basic parsing"
    AWS_REGION=$(grep -o '"region": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    LAMBDA_FUNCTION=$(grep -o '"lambda_function": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    LAMBDA_ROLE=$(grep -o '"lambda_role": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    CROSS_ACCOUNT_ROLE=$(grep -o '"cross_account_role": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    SSM_RULE=$(grep -o '"ssm_rule": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    LOG_GROUP_RULE=$(grep -o '"log_group_rule": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    TEST_PARAM_PREFIX=$(grep -o '"test_param_prefix": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    TEST_CENTRAL_PREFIX=$(grep -o '"test_central_prefix": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    TEST_LOG_GROUP=$(grep -o '"test_log_group": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
    DEPLOYMENT_PACKAGE=$(grep -o '"deployment_package": "[^"]*' ${DEPLOYMENT_FILE} | cut -d'"' -f4)
else
    AWS_REGION=$(jq -r '.region' ${DEPLOYMENT_FILE})
    LAMBDA_FUNCTION=$(jq -r '.resources.lambda_function' ${DEPLOYMENT_FILE})
    LAMBDA_ROLE=$(jq -r '.resources.lambda_role' ${DEPLOYMENT_FILE})
    CROSS_ACCOUNT_ROLE=$(jq -r '.resources.cross_account_role' ${DEPLOYMENT_FILE})
    SSM_RULE=$(jq -r '.resources.ssm_rule' ${DEPLOYMENT_FILE})
    LOG_GROUP_RULE=$(jq -r '.resources.log_group_rule' ${DEPLOYMENT_FILE})
    TEST_PARAM_PREFIX=$(jq -r '.resources.test_param_prefix' ${DEPLOYMENT_FILE})
    TEST_CENTRAL_PREFIX=$(jq -r '.resources.test_central_prefix' ${DEPLOYMENT_FILE})
    TEST_LOG_GROUP=$(jq -r '.resources.test_log_group' ${DEPLOYMENT_FILE})
    DEPLOYMENT_PACKAGE=$(jq -r '.resources.deployment_package' ${DEPLOYMENT_FILE})
fi

print_success "Deployment info loaded"

echo ""
echo -e "${BOLD}Resources to be deleted:${NC}"
echo "  • Lambda Function: ${LAMBDA_FUNCTION}"
echo "  • Lambda Role: ${LAMBDA_ROLE}"
echo "  • Cross-Account Role: ${CROSS_ACCOUNT_ROLE}"
echo "  • SSM Rule: ${SSM_RULE}"
echo "  • Log Group Rule: ${LOG_GROUP_RULE}"
echo "  • Parameters: ${TEST_PARAM_PREFIX}/*"
echo "  • Central Parameters: ${TEST_CENTRAL_PREFIX}/*"
echo "  • Test Log Group: ${TEST_LOG_GROUP}"
echo "  • Package: ${DEPLOYMENT_PACKAGE}"
echo ""

read -p "Are you sure you want to delete ALL these resources? (yes/no): " final_confirm
if [ "$final_confirm" != "yes" ]; then
    print_info "Cleanup cancelled"
    exit 0
fi

WORKLOAD_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

################################################################################
# DELETE EVENTBRIDGE RULES
################################################################################

print_section "Deleting EventBridge Rules"

# Remove targets first
aws events remove-targets \
  --rule ${SSM_RULE} \
  --ids 1 \
  --region ${AWS_REGION} &> /dev/null || print_warning "SSM rule targets already removed"

aws events remove-targets \
  --rule ${LOG_GROUP_RULE} \
  --ids 1 \
  --region ${AWS_REGION} &> /dev/null || print_warning "Log group rule targets already removed"

print_success "Removed EventBridge targets"

# Delete rules
aws events delete-rule \
  --name ${SSM_RULE} \
  --region ${AWS_REGION} &> /dev/null || print_warning "SSM rule already deleted"

aws events delete-rule \
  --name ${LOG_GROUP_RULE} \
  --region ${AWS_REGION} &> /dev/null || print_warning "Log group rule already deleted"

print_success "Deleted EventBridge rules"

################################################################################
# DELETE LAMBDA FUNCTION
################################################################################

print_section "Deleting Lambda Function"

aws lambda delete-function \
  --function-name ${LAMBDA_FUNCTION} \
  --region ${AWS_REGION} &> /dev/null || print_warning "Lambda function already deleted"

print_success "Deleted Lambda function: ${LAMBDA_FUNCTION}"

################################################################################
# DELETE IAM ROLES
################################################################################

print_section "Deleting IAM Roles"

# Delete Lambda role
print_info "Deleting Lambda role policies..."

aws iam delete-role-policy \
  --role-name ${LAMBDA_ROLE} \
  --policy-name CplTestPolicy &> /dev/null || true

aws iam detach-role-policy \
  --role-name ${LAMBDA_ROLE} \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole &> /dev/null || true

aws iam delete-role \
  --role-name ${LAMBDA_ROLE} &> /dev/null || print_warning "Lambda role already deleted"

print_success "Deleted Lambda role: ${LAMBDA_ROLE}"

# Delete cross-account role
print_info "Deleting cross-account role..."

aws iam delete-role-policy \
  --role-name ${CROSS_ACCOUNT_ROLE} \
  --policy-name SSMSyncPolicy &> /dev/null || true

aws iam delete-role \
  --role-name ${CROSS_ACCOUNT_ROLE} &> /dev/null || print_warning "Cross-account role already deleted"

print_success "Deleted cross-account role: ${CROSS_ACCOUNT_ROLE}"

################################################################################
# DELETE SSM PARAMETERS
################################################################################

print_section "Deleting SSM Parameters"

# Delete workload parameters
print_info "Deleting workload parameters: ${TEST_PARAM_PREFIX}/*"

PARAM_NAMES=$(aws ssm get-parameters-by-path \
  --path "${TEST_PARAM_PREFIX}" \
  --recursive \
  --region ${AWS_REGION} \
  --query 'Parameters[*].Name' \
  --output text 2>/dev/null || echo "")

if [ ! -z "$PARAM_NAMES" ]; then
    for param in $PARAM_NAMES; do
        aws ssm delete-parameter --name "$param" --region ${AWS_REGION} &> /dev/null
        print_success "  Deleted: $param"
    done
else
    print_info "  No workload parameters found"
fi

# Delete central parameters
print_info "Deleting central parameters: ${TEST_CENTRAL_PREFIX}/*"

CENTRAL_PARAMS=$(aws ssm get-parameters-by-path \
  --path "${TEST_CENTRAL_PREFIX}" \
  --recursive \
  --region ${AWS_REGION} \
  --query 'Parameters[*].Name' \
  --output text 2>/dev/null || echo "")

if [ ! -z "$CENTRAL_PARAMS" ]; then
    for param in $CENTRAL_PARAMS; do
        aws ssm delete-parameter --name "$param" --region ${AWS_REGION} &> /dev/null
        print_success "  Deleted: $param"
    done
else
    print_info "  No central parameters found"
fi

# Delete tracking parameter
TRACKING_PARAM=$(echo ${TEST_PARAM_PREFIX} | sed 's/\/cpl-test-/CplTest_Filters_/')
aws ssm delete-parameter \
  --name "${TRACKING_PARAM}" \
  --region ${AWS_REGION} &> /dev/null || print_info "  Tracking parameter already deleted"

print_success "Deleted SSM parameters"

################################################################################
# DELETE LOG GROUPS
################################################################################

print_section "Deleting Log Groups"

# Delete test log group
aws logs delete-log-group \
  --log-group-name "${TEST_LOG_GROUP}" \
  --region ${AWS_REGION} &> /dev/null || print_warning "Test log group already deleted"

print_success "Deleted test log group: ${TEST_LOG_GROUP}"

# Delete Lambda log group
LAMBDA_LOG_GROUP="/aws/lambda/${LAMBDA_FUNCTION}"
aws logs delete-log-group \
  --log-group-name "${LAMBDA_LOG_GROUP}" \
  --region ${AWS_REGION} &> /dev/null || print_warning "Lambda log group already deleted"

print_success "Deleted Lambda log group: ${LAMBDA_LOG_GROUP}"

################################################################################
# DELETE LOCAL FILES
################################################################################

print_section "Deleting Local Files"

if [ -f "${DEPLOYMENT_PACKAGE}" ]; then
    rm -f "${DEPLOYMENT_PACKAGE}"
    print_success "Deleted deployment package: ${DEPLOYMENT_PACKAGE}"
else
    print_info "Deployment package already deleted"
fi

# Delete temporary files
rm -f /tmp/lambda-trust-*.json 2>/dev/null || true
rm -f /tmp/lambda-policy-*.json 2>/dev/null || true
rm -f /tmp/cross-trust-*.json 2>/dev/null || true
rm -f /tmp/cross-policy-*.json 2>/dev/null || true

print_success "Deleted temporary files"

################################################################################
# DELETE DEPLOYMENT INFO FILE
################################################################################

print_section "Removing Deployment Info"

rm -f "${DEPLOYMENT_FILE}"
print_success "Deleted deployment info: ${DEPLOYMENT_FILE}"

################################################################################
# SUMMARY
################################################################################

print_header "Cleanup Complete"

echo -e "${GREEN}${BOLD}All test resources have been deleted!${NC}"
echo ""
echo "Deleted resources:"
echo "  ✓ Lambda function and log group"
echo "  ✓ IAM roles (Lambda + Cross-account)"
echo "  ✓ EventBridge rules"
echo "  ✓ SSM parameters (workload + central)"
echo "  ✓ Test log groups"
echo "  ✓ Local deployment files"
echo ""
echo -e "${BOLD}Your AWS account is now clean!${NC}"
echo "No test resources remain."
echo ""
print_success "Cleanup complete!"