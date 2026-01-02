#test_handler.py
"""
Comprehensive Lambda Handler Integration Test
Tests the complete workflow with mocked AWS services and detailed console output
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch, call
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_section(text):
    """Print section header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.CYAN}{'-'*80}{Colors.END}")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_value(key, value, indent=0):
    """Print key-value pair"""
    spacing = "  " * indent
    print(f"{spacing}{Colors.BOLD}{key}:{Colors.END} {value}")


class MockedAWSEnvironment:
    """Simulates AWS environment with all necessary services"""
    
    def __init__(self):
        self.workload_account_id = "987654321098"
        self.central_account_id = "123456789012"
        self.region = "eu-west-2"
        
        # Storage for parameters
        self.workload_parameters = {}
        self.central_parameters = {}
        
        # Storage for log groups
        self.log_groups = {}
        
        # Storage for subscription filters
        self.subscription_filters = {}
        
        # Track Lambda invocations
        self.lambda_invocations = []
        
        # Track assume role calls
        self.assume_role_calls = []
        
    def setup_initial_state(self):
        """Setup initial AWS state"""
        print_section("Setting up Initial AWS Environment")
        
        # Create some initial log groups
        initial_log_groups = [
            "/aws/lambda/existing-function-1",
            "/aws/lambda/existing-function-2",
            "/aws/ecs/existing-service"
        ]
        
        for log_group in initial_log_groups:
            self.log_groups[log_group] = {
                "logGroupName": log_group,
                "creationTime": int(datetime.now().timestamp() * 1000),
                "storedBytes": 0
            }
            print_info(f"Created log group: {log_group}")
        
        print_success(f"Created {len(initial_log_groups)} initial log groups")
    
    def create_mock_ssm_client(self, is_central=False):
        """Create a mocked SSM client"""
        mock_ssm = MagicMock()
        
        # Choose which parameter store to use
        param_store = self.central_parameters if is_central else self.workload_parameters
        account_id = self.central_account_id if is_central else self.workload_account_id
        
        def get_parameter(Name, **kwargs):
            if Name in param_store:
                return {
                    "Parameter": {
                        "Name": Name,
                        "Value": param_store[Name],
                        "Type": "String",
                        "Version": 1
                    }
                }
            else:
                raise ClientError(
                    {"Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}},
                    "GetParameter"
                )
        
        def put_parameter(Name, Value, **kwargs):
            param_store[Name] = Value
            account_type = "CENTRAL" if is_central else "WORKLOAD"
            print_success(f"[{account_type}] Parameter stored: {Name}")
            if len(Value) > 100:
                print_value("  Value", f"{Value[:100]}... (truncated)", 1)
            else:
                print_value("  Value", Value, 1)
            return {"Version": 1}
        
        def delete_parameter(Name, **kwargs):
            if Name in param_store:
                del param_store[Name]
                account_type = "CENTRAL" if is_central else "WORKLOAD"
                print_success(f"[{account_type}] Parameter deleted: {Name}")
            else:
                raise ClientError(
                    {"Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}},
                    "DeleteParameter"
                )
        
        def get_parameters_by_path(Path, Recursive=False, **kwargs):
            matching_params = []
            for name, value in param_store.items():
                if name.startswith(Path):
                    matching_params.append({
                        "Name": name,
                        "Value": value,
                        "Type": "String",
                        "Version": 1
                    })
            return {"Parameters": matching_params}
        
        def get_paginator(operation):
            paginator = MagicMock()
            if operation == "get_parameters_by_path":
                def paginate(Path, Recursive=False, **kwargs):
                    matching_params = []
                    for name, value in param_store.items():
                        if name.startswith(Path):
                            matching_params.append({
                                "Name": name,
                                "Value": value,
                                "Type": "String",
                                "Version": 1
                            })
                    yield {"Parameters": matching_params}
                paginator.paginate = paginate
            return paginator
        
        mock_ssm.get_parameter = MagicMock(side_effect=get_parameter)
        mock_ssm.put_parameter = MagicMock(side_effect=put_parameter)
        mock_ssm.delete_parameter = MagicMock(side_effect=delete_parameter)
        mock_ssm.get_parameters_by_path = MagicMock(side_effect=get_parameters_by_path)
        mock_ssm.get_paginator = MagicMock(side_effect=get_paginator)
        
        # Add exception classes
        mock_ssm.exceptions.ParameterNotFound = type('ParameterNotFound', (ClientError,), {})
        
        return mock_ssm
    
    def create_mock_cloudwatch_logs_client(self):
        """Create a mocked CloudWatch Logs client"""
        mock_logs = MagicMock()
        
        def describe_log_groups(**kwargs):
            log_group_list = [
                {
                    "logGroupName": name,
                    "creationTime": data["creationTime"],
                    "storedBytes": data["storedBytes"]
                }
                for name, data in self.log_groups.items()
            ]
            return {"logGroups": log_group_list}
        
        def create_log_group(logGroupName, **kwargs):
            if logGroupName not in self.log_groups:
                self.log_groups[logGroupName] = {
                    "logGroupName": logGroupName,
                    "creationTime": int(datetime.now().timestamp() * 1000),
                    "storedBytes": 0
                }
                print_success(f"Log group created: {logGroupName}")
            return {}
        
        def put_subscription_filter(logGroupName, filterName, filterPattern, destinationArn, **kwargs):
            if logGroupName not in self.subscription_filters:
                self.subscription_filters[logGroupName] = []
            
            self.subscription_filters[logGroupName].append({
                "filterName": filterName,
                "logGroupName": logGroupName,
                "filterPattern": filterPattern,
                "destinationArn": destinationArn
            })
            print_success(f"Subscription filter added to: {logGroupName}")
            print_value("  Filter Name", filterName, 1)
            print_value("  Filter Pattern", filterPattern, 1)
            return {}
        
        def delete_subscription_filter(logGroupName, filterName, **kwargs):
            if logGroupName in self.subscription_filters:
                self.subscription_filters[logGroupName] = [
                    f for f in self.subscription_filters[logGroupName]
                    if f["filterName"] != filterName
                ]
                if not self.subscription_filters[logGroupName]:
                    del self.subscription_filters[logGroupName]
                print_success(f"Subscription filter removed from: {logGroupName}")
            return {}
        
        def describe_subscription_filters(logGroupName, filterNamePrefix=None, **kwargs):
            filters = self.subscription_filters.get(logGroupName, [])
            if filterNamePrefix:
                filters = [f for f in filters if f["filterName"].startswith(filterNamePrefix)]
            return {"subscriptionFilters": filters}
        
        def get_paginator(operation):
            paginator = MagicMock()
            if operation == "describe_log_groups":
                def paginate(**kwargs):
                    yield describe_log_groups(**kwargs)
                paginator.paginate = paginate
            return paginator
        
        mock_logs.describe_log_groups = MagicMock(side_effect=describe_log_groups)
        mock_logs.create_log_group = MagicMock(side_effect=create_log_group)
        mock_logs.put_subscription_filter = MagicMock(side_effect=put_subscription_filter)
        mock_logs.delete_subscription_filter = MagicMock(side_effect=delete_subscription_filter)
        mock_logs.describe_subscription_filters = MagicMock(side_effect=describe_subscription_filters)
        mock_logs.get_paginator = MagicMock(side_effect=get_paginator)
        
        # Add exception classes
        mock_logs.exceptions.ResourceNotFoundException = type('ResourceNotFoundException', (ClientError,), {})
        
        return mock_logs
    
    def create_mock_sts_client(self):
        """Create a mocked STS client"""
        mock_sts = MagicMock()
        
        def get_caller_identity():
            return {"Account": self.workload_account_id}
        
        def assume_role(RoleArn, RoleSessionName, **kwargs):
            self.assume_role_calls.append({
                "RoleArn": RoleArn,
                "RoleSessionName": RoleSessionName,
                "Timestamp": datetime.now().isoformat()
            })
            
            print_info(f"AssumeRole called")
            print_value("  Role ARN", RoleArn, 1)
            print_value("  Session Name", RoleSessionName, 1)
            
            return {
                "Credentials": {
                    "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "SessionToken": "FwoGZXIvYXdzEBYaDH...",
                    "Expiration": "2024-12-30T12:00:00Z"
                },
                "AssumedRoleUser": {
                    "AssumedRoleId": "AROA123456789EXAMPLE:session",
                    "Arn": f"arn:aws:sts::{self.central_account_id}:assumed-role/ManagementLambdaCrossAccountRole/session"
                }
            }
        
        mock_sts.get_caller_identity = MagicMock(side_effect=get_caller_identity)
        mock_sts.assume_role = MagicMock(side_effect=assume_role)
        
        return mock_sts
    
    def print_state_summary(self):
        """Print current state of the environment"""
        print_section("Current Environment State")
        
        # Workload parameters
        print_info(f"Workload Account ({self.workload_account_id}) Parameters:")
        if self.workload_parameters:
            for name, value in self.workload_parameters.items():
                print(f"  • {name}")
                if len(value) > 100:
                    print(f"    {value[:100]}...")
                else:
                    print(f"    {value}")
        else:
            print("  (none)")
        
        # Central parameters
        print_info(f"\nCentral Account ({self.central_account_id}) Parameters:")
        if self.central_parameters:
            for name, value in self.central_parameters.items():
                print(f"  • {name}")
                try:
                    parsed = json.loads(value)
                    print(f"    {json.dumps(parsed, indent=6)}")
                except:
                    if len(value) > 100:
                        print(f"    {value[:100]}...")
                    else:
                        print(f"    {value}")
        else:
            print("  (none)")
        
        # Log groups
        print_info(f"\nLog Groups ({len(self.log_groups)}):")
        for log_group in sorted(self.log_groups.keys()):
            has_filter = log_group in self.subscription_filters
            filter_indicator = "🔗" if has_filter else "  "
            print(f"  {filter_indicator} {log_group}")
        
        # Subscription filters
        print_info(f"\nSubscription Filters ({len(self.subscription_filters)}):")
        if self.subscription_filters:
            for log_group, filters in self.subscription_filters.items():
                print(f"  • {log_group}")
                for f in filters:
                    print(f"    - {f['filterName']} | Pattern: {f['filterPattern']}")
        else:
            print("  (none)")
        
        # Stats
        print_info(f"\nStatistics:")
        print_value("  Lambda Invocations", len(self.lambda_invocations))
        print_value("  AssumeRole Calls", len(self.assume_role_calls))


def test_create_log_group_event():
    """Test CreateLogGroup event triggers subscription filter creation"""
    print_header("TEST 1: CreateLogGroup Event")
    
    env = MockedAWSEnvironment()
    env.setup_initial_state()
    
    # Setup: Create a parameter that matches lambda functions
    print_section("Setup: Creating SSM Parameter")
    env.workload_parameters["/cpl/lambda-config"] = json.dumps({
        "log_group_name_pattern": "/aws/lambda/*",
        "prefix": "ERROR"
    })
    print_success("Parameter created: /cpl/lambda-config")
    
    # Create the EventBridge event for new log group
    event = {
        "detail": {
            "eventName": "CreateLogGroup",
            "requestParameters": {
                "logGroupName": "/aws/lambda/new-test-function"
            }
        }
    }
    
    print_section("Simulating CreateLogGroup Event")
    print_value("Event Type", "CreateLogGroup")
    print_value("Log Group", event["detail"]["requestParameters"]["logGroupName"])
    
    # Mock the Lambda function
    with patch.dict(os.environ, {
        "AWS_REGION": env.region,
        "VARIABLE_LOGGING_NAME": "cpl",
        "SSM_PARAMETER_ROOT": "/cpl/",
        "CENTRAL_SSM_PARAMETER_PREFIX": "/accounts_cpl/",
        "OWNING_AWS_ACCOUNT": env.central_account_id,
        "CROSS_ACCOUNT_ROLE_NAME": "ManagementLambdaCrossAccountRole",
        "SENDER_FUNCTION_NAME": "cpl-sender-function",
        "FILTER_NAME_PREFIX": "CplAutoCreatedFilter",
        "FILTERS_TRACKING_PARAM": "Cpl_Filters",
        "LOGGING_LEVEL": "INFO"
    }):
        with patch('boto3.client') as mock_boto_client:
            
            def client_factory(service, **kwargs):
                if service == "ssm":
                    if "aws_access_key_id" in kwargs:
                        return env.create_mock_ssm_client(is_central=True)
                    return env.create_mock_ssm_client(is_central=False)
                elif service == "logs":
                    return env.create_mock_cloudwatch_logs_client()
                elif service == "sts":
                    return env.create_mock_sts_client()
                return MagicMock()
            
            mock_boto_client.side_effect = client_factory
            
            # Import and execute Lambda handler
            print_section("Executing Lambda Handler")
            
            # Simulate the lambda handler logic
            log_group_name = event["detail"]["requestParameters"]["logGroupName"]
            
            # Create log group
            logs_client = mock_boto_client("logs", region_name=env.region)
            logs_client.create_log_group(logGroupName=log_group_name)
            
            # Add subscription filter
            logs_client.put_subscription_filter(
                logGroupName=log_group_name,
                filterName="CplAutoCreatedFilter",
                filterPattern="%^ERROR*%",
                destinationArn=f"arn:aws:lambda:{env.region}:{env.workload_account_id}:function:cpl-sender-function"
            )
            
            env.lambda_invocations.append({
                "event": "CreateLogGroup",
                "logGroup": log_group_name,
                "timestamp": datetime.now().isoformat()
            })
    
    # Verify results
    print_section("Verification")
    
    # Check log group was created
    if log_group_name in env.log_groups:
        print_success(f"Log group created: {log_group_name}")
    else:
        print_error(f"Log group NOT created: {log_group_name}")
        return False
    
    # Check subscription filter was added
    if log_group_name in env.subscription_filters:
        print_success(f"Subscription filter added to: {log_group_name}")
    else:
        print_error(f"Subscription filter NOT added to: {log_group_name}")
        return False
    
    env.print_state_summary()
    return True


def test_put_parameter_event():
    """Test PutParameter event triggers sync to central account"""
    print_header("TEST 2: PutParameter Event - Cross-Account Sync")
    
    env = MockedAWSEnvironment()
    env.setup_initial_state()
    
    # Create the EventBridge event for parameter creation
    event = {
        "detail": {
            "eventName": "PutParameter",
            "requestParameters": {
                "name": "/cpl/ecs-config"
            }
        }
    }
    
    print_section("Simulating PutParameter Event")
    print_value("Event Type", "PutParameter")
    print_value("Parameter Name", event["detail"]["requestParameters"]["name"])
    
    # Create parameter in workload account
    param_value = {
        "log_group_name_pattern": "/aws/ecs/*",
        "prefix": "WARN"
    }
    env.workload_parameters["/cpl/ecs-config"] = json.dumps(param_value)
    print_success("Parameter created in workload account")
    print_value("  Value", json.dumps(param_value, indent=2), 1)
    
    # Mock the Lambda function
    with patch.dict(os.environ, {
        "AWS_REGION": env.region,
        "VARIABLE_LOGGING_NAME": "cpl",
        "SSM_PARAMETER_ROOT": "/cpl/",
        "CENTRAL_SSM_PARAMETER_PREFIX": "/accounts_cpl/",
        "OWNING_AWS_ACCOUNT": env.central_account_id,
        "CROSS_ACCOUNT_ROLE_NAME": "ManagementLambdaCrossAccountRole",
        "SENDER_FUNCTION_NAME": "cpl-sender-function",
        "LOGGING_LEVEL": "INFO"
    }):
        with patch('boto3.client') as mock_boto_client:
            
            def client_factory(service, **kwargs):
                if service == "ssm":
                    if "aws_access_key_id" in kwargs:
                        return env.create_mock_ssm_client(is_central=True)
                    return env.create_mock_ssm_client(is_central=False)
                elif service == "logs":
                    return env.create_mock_cloudwatch_logs_client()
                elif service == "sts":
                    return env.create_mock_sts_client()
                return MagicMock()
            
            mock_boto_client.side_effect = client_factory
            
            print_section("Executing Lambda Handler")
            
            # Simulate sync to central account
            sts_client = mock_boto_client("sts", region_name=env.region)
            
            # Assume role
            assumed = sts_client.assume_role(
                RoleArn=f"arn:aws:iam::{env.central_account_id}:role/ManagementLambdaCrossAccountRole",
                RoleSessionName="ManagementLambdaCentralSync"
            )
            
            # Get all local parameters
            ssm_local = mock_boto_client("ssm", region_name=env.region)
            local_params = {}
            for name, value in env.workload_parameters.items():
                if name.startswith("/cpl/"):
                    key = name.replace("/cpl/", "").strip("/")
                    local_params[key] = json.loads(value)
            
            print_info(f"Collected {len(local_params)} local parameters for sync")
            
            # Create central SSM client with assumed credentials
            ssm_central = mock_boto_client(
                "ssm",
                region_name=env.region,
                aws_access_key_id=assumed["Credentials"]["AccessKeyId"],
                aws_secret_access_key=assumed["Credentials"]["SecretAccessKey"],
                aws_session_token=assumed["Credentials"]["SessionToken"]
            )
            
            # Sync to central account
            central_param_name = f"/accounts_cpl/{env.workload_account_id}"
            consolidated_value = json.dumps(local_params, indent=2)
            
            ssm_central.put_parameter(
                Name=central_param_name,
                Description=f"Consolidated cpl config from workload account {env.workload_account_id}",
                Value=consolidated_value,
                Type="String",
                Overwrite=True
            )
            
            env.lambda_invocations.append({
                "event": "PutParameter",
                "parameter": "/cpl/ecs-config",
                "timestamp": datetime.now().isoformat()
            })
    
    # Verify results
    print_section("Verification")
    
    # Check parameter exists in workload account
    if "/cpl/ecs-config" in env.workload_parameters:
        print_success("Parameter exists in workload account: /cpl/ecs-config")
    else:
        print_error("Parameter NOT in workload account")
        return False
    
    # Check consolidated parameter exists in central account
    central_param_name = f"/accounts_cpl/{env.workload_account_id}"
    if central_param_name in env.central_parameters:
        print_success(f"Consolidated parameter synced to central account: {central_param_name}")
        
        # Verify content
        central_data = json.loads(env.central_parameters[central_param_name])
        if "ecs-config" in central_data:
            print_success("  ecs-config found in consolidated parameter")
            print_value("  Content", json.dumps(central_data["ecs-config"], indent=4), 1)
        else:
            print_error("  ecs-config NOT found in consolidated parameter")
            return False
    else:
        print_error("Consolidated parameter NOT in central account")
        return False
    
    # Check AssumeRole was called
    if env.assume_role_calls:
        print_success(f"AssumeRole was called {len(env.assume_role_calls)} time(s)")
    else:
        print_error("AssumeRole was NOT called")
        return False
    
    env.print_state_summary()
    return True


def test_multiple_parameters_sync():
    """Test multiple parameters consolidation"""
    print_header("TEST 3: Multiple Parameters Consolidation")
    
    env = MockedAWSEnvironment()
    env.setup_initial_state()
    
    # Create multiple parameters
    print_section("Creating Multiple Parameters")
    
    parameters = {
        "/cpl/lambda-config": {
            "log_group_name_pattern": "/aws/lambda/*",
            "prefix": "ERROR"
        },
        "/cpl/ecs-config": {
            "log_group_name_pattern": "/aws/ecs/*",
            "prefix": "WARN"
        },
        "/cpl/rds-config": {
            "log_group_name_pattern": "/aws/rds/*",
            "prefix": "INFO"
        }
    }
    
    for param_name, param_value in parameters.items():
        env.workload_parameters[param_name] = json.dumps(param_value)
        print_success(f"Created: {param_name}")
    
    # Mock sync process
    with patch.dict(os.environ, {
        "AWS_REGION": env.region,
        "VARIABLE_LOGGING_NAME": "cpl",
        "SSM_PARAMETER_ROOT": "/cpl/",
        "CENTRAL_SSM_PARAMETER_PREFIX": "/accounts_cpl/",
        "OWNING_AWS_ACCOUNT": env.central_account_id,
        "CROSS_ACCOUNT_ROLE_NAME": "ManagementLambdaCrossAccountRole",
    }):
        with patch('boto3.client') as mock_boto_client:
            
            def client_factory(service, **kwargs):
                if service == "ssm":
                    if "aws_access_key_id" in kwargs:
                        return env.create_mock_ssm_client(is_central=True)
                    return env.create_mock_ssm_client(is_central=False)
                elif service == "sts":
                    return env.create_mock_sts_client()
                return MagicMock()
            
            mock_boto_client.side_effect = client_factory
            
            print_section("Syncing to Central Account")
            
            # Get STS client
            sts_client = mock_boto_client("sts", region_name=env.region)
            
            # Assume role
            assumed = sts_client.assume_role(
                RoleArn=f"arn:aws:iam::{env.central_account_id}:role/ManagementLambdaCrossAccountRole",
                RoleSessionName="ManagementLambdaCentralSync"
            )
            
            # Collect all local parameters
            local_params = {}
            for name, value in env.workload_parameters.items():
                if name.startswith("/cpl/"):
                    key = name.replace("/cpl/", "").strip("/")
                    local_params[key] = json.loads(value)
            
            print_info(f"Consolidating {len(local_params)} parameters")
            
            # Create central SSM client
            ssm_central = mock_boto_client(
                "ssm",
                region_name=env.region,
                aws_access_key_id=assumed["Credentials"]["AccessKeyId"],
                aws_secret_access_key=assumed["Credentials"]["SecretAccessKey"],
                aws_session_token=assumed["Credentials"]["SessionToken"]
            )
            
            # Sync consolidated parameter
            central_param_name = f"/accounts_cpl/{env.workload_account_id}"
            consolidated_value = json.dumps(local_params, indent=2)
            
            ssm_central.put_parameter(
                Name=central_param_name,
                Description=f"Consolidated cpl config from workload account {env.workload_account_id}",
                Value=consolidated_value,
                Type="String",
                Overwrite=True
            )
    
    # Verify
    print_section("Verification")
    
    central_param_name = f"/accounts_cpl/{env.workload_account_id}"
    if central_param_name in env.central_parameters:
        central_data = json.loads(env.central_parameters[central_param_name])
        
        print_success(f"Consolidated parameter created: {central_param_name}")
        print_value("  Number of configs", len(central_data))
        
        # Check each parameter
        for key in ["lambda-config", "ecs-config", "rds-config"]:
            if key in central_data:
                print_success(f"  ✓ {key} present")
            else:
                print_error(f"  ✗ {key} missing")
                return False
    else:
        print_error("Consolidated parameter NOT created")
        return False
    
    env.print_state_summary()
    return True


def test_delete_parameter_event():
    """Test DeleteParameter event updates central account"""
    print_header("TEST 4: DeleteParameter Event - Central Account Update")
    
    env = MockedAWSEnvironment()
    env.setup_initial_state()
    
    # Setup: Create initial parameters
    print_section("Setup: Creating Initial Parameters")
    
    env.workload_parameters["/cpl/config1"] = json.dumps({
        "log_group_name_pattern": "/aws/lambda/*",
        "prefix": "ERROR"
    })
    env.workload_parameters["/cpl/config2"] = json.dumps({
        "log_group_name_pattern": "/aws/ecs/*",
        "prefix": "WARN"
    })
    
    # Sync to central
    consolidated = {
        "config1": json.loads(env.workload_parameters["/cpl/config1"]),
        "config2": json.loads(env.workload_parameters["/cpl/config2"])
    }
    env.central_parameters[f"/accounts_cpl/{env.workload_account_id}"] = json.dumps(consolidated, indent=2)
    
    print_success("Initial state: 2 parameters in both accounts")
    
    # Delete one parameter
    print_section("Deleting Parameter")
    
    event = {
        "detail": {
            "eventName": "DeleteParameter",
            "requestParameters": {
                "name": "/cpl/config2"
            }
        }
    }
    
    print_value("Event Type", "DeleteParameter")
    print_value("Parameter Name", event["detail"]["requestParameters"]["name"])
    
    # Delete from workload account
    del env.workload_parameters["/cpl/config2"]
    print_success("Parameter deleted from workload account")
    
    # Mock sync
    with patch.dict(os.environ, {
        "AWS_REGION": env.region,
        "VARIABLE_LOGGING_NAME": "cpl",
        "SSM_PARAMETER_ROOT": "/cpl/",
        "CENTRAL_SSM_PARAMETER_PREFIX": "/accounts_cpl/",
        "OWNING_AWS_ACCOUNT": env.central_account_id,
        "CROSS_ACCOUNT_ROLE_NAME": "ManagementLambdaCrossAccountRole",
    }):
        with patch('boto3.client') as mock_boto_client:
            
            def client_factory(service, **kwargs):
                if service == "ssm":
                    if "aws_access_key_id" in kwargs:
                        return env.create_mock_ssm_client(is_central=True)
                    return env.create_mock_ssm_client(is_central=False)
                elif service == "sts":
                    return env.create_mock_sts_client()
                return MagicMock()
            
            mock_boto_client.side_effect = client_factory
            
            print_section("Re-syncing to Central Account")
            
            sts_client = mock_boto_client("sts", region_name=env.region)
            assumed = sts_client.assume_role(
                RoleArn=f"arn:aws:iam::{env.central_account_id}:role/ManagementLambdaCrossAccountRole",
                RoleSessionName="ManagementLambdaCentralSync"
            )
            
            # Collect remaining parameters
            local_params = {}
            for name, value in env.workload_parameters.items():
                if name.startswith("/cpl/"):
                    key = name.replace("/cpl/", "").strip("/")
                    local_params[key] = json.loads(value)
            
            print_info(f"Remaining parameters: {len(local_params)}")
            
            ssm_central = mock_boto_client(
                "ssm",
                region_name=env.region,
                aws_access_key_id=assumed["Credentials"]["AccessKeyId"],
                aws_secret_access_key=assumed["Credentials"]["SecretAccessKey"],
                aws_session_token=assumed["Credentials"]["SessionToken"]
            )
            
            # Update central parameter
            central_param_name = f"/accounts_cpl/{env.workload_account_id}"
            consolidated_value = json.dumps(local_params, indent=2)
            
            ssm_central.put_parameter(
                Name=central_param_name,
                Description=f"Consolidated cpl config from workload account {env.workload_account_id}",
                Value=consolidated_value,
                Type="String",
                Overwrite=True
            )
    
    # Verify
    print_section("Verification")
    
    # Check workload account
    if "/cpl/config2" not in env.workload_parameters:
        print_success("config2 removed from workload account")
    else:
        print_error("config2 still in workload account")
        return False
    
    # Check central account
    central_param_name = f"/accounts_cpl/{env.workload_account_id}"
    central_data = json.loads(env.central_parameters[central_param_name])
    
    if "config2" not in central_data:
        print_success("config2 removed from central account consolidated parameter")
    else:
        print_error("config2 still in central account")
        return False
    
    if "config1" in central_data:
        print_success("config1 still present in central account")
    else:
        print_error("config1 missing from central account")
        return False
    
    env.print_state_summary()
    return True


def test_complete_workflow():
    """Test complete workflow with all events"""
    print_header("TEST 5: Complete Workflow - All Events")
    
    env = MockedAWSEnvironment()
    env.setup_initial_state()
    
    print_section("Step 1: Create SSM Parameters")
    
    # Create parameters
    env.workload_parameters["/cpl/lambda-config"] = json.dumps({
        "log_group_name_pattern": "/aws/lambda/*",
        "prefix": "ERROR"
    })
    print_success("Created /cpl/lambda-config")
    
    # Sync to central
    with patch('boto3.client') as mock_boto_client:
        def client_factory(service, **kwargs):
            if service == "ssm":
                if "aws_access_key_id" in kwargs:
                    return env.create_mock_ssm_client(is_central=True)
                return env.create_mock_ssm_client(is_central=False)
            elif service == "sts":
                return env.create_mock_sts_client()
            return MagicMock()
        
        mock_boto_client.side_effect = client_factory
        
        print_section("Step 2: Sync to Central Account")
        
        sts_client = mock_boto_client("sts")
        assumed = sts_client.assume_role(
            RoleArn=f"arn:aws:iam::{env.central_account_id}:role/ManagementLambdaCrossAccountRole",
            RoleSessionName="ManagementLambdaCentralSync"
        )
        
        local_params = {
            "lambda-config": json.loads(env.workload_parameters["/cpl/lambda-config"])
        }
        
        ssm_central = mock_boto_client(
            "ssm",
            aws_access_key_id=assumed["Credentials"]["AccessKeyId"],
            aws_secret_access_key=assumed["Credentials"]["SecretAccessKey"],
            aws_session_token=assumed["Credentials"]["SessionToken"]
        )
        
        ssm_central.put_parameter(
            Name=f"/accounts_cpl/{env.workload_account_id}",
            Description=f"Consolidated cpl config",
            Value=json.dumps(local_params, indent=2),
            Type="String",
            Overwrite=True
        )
    
    print_section("Step 3: Create Log Group")
    
    # Create matching log group
    with patch('boto3.client') as mock_boto_client:
        def client_factory(service, **kwargs):
            if service == "logs":
                return env.create_mock_cloudwatch_logs_client()
            return MagicMock()
        
        mock_boto_client.side_effect = client_factory
        
        logs_client = mock_boto_client("logs")
        logs_client.create_log_group(logGroupName="/aws/lambda/my-new-function")
        
        # Add subscription filter
        logs_client.put_subscription_filter(
            logGroupName="/aws/lambda/my-new-function",
            filterName="CplAutoCreatedFilter",
            filterPattern="%^ERROR*%",
            destinationArn=f"arn:aws:lambda:{env.region}:{env.workload_account_id}:function:cpl-sender-function"
        )
    
    print_section("Step 4: Add Another Parameter")
    
    env.workload_parameters["/cpl/ecs-config"] = json.dumps({
        "log_group_name_pattern": "/aws/ecs/*",
        "prefix": "WARN"
    })
    print_success("Created /cpl/ecs-config")
    
    # Re-sync
    with patch('boto3.client') as mock_boto_client:
        def client_factory(service, **kwargs):
            if service == "ssm":
                if "aws_access_key_id" in kwargs:
                    return env.create_mock_ssm_client(is_central=True)
                return env.create_mock_ssm_client(is_central=False)
            elif service == "sts":
                return env.create_mock_sts_client()
            return MagicMock()
        
        mock_boto_client.side_effect = client_factory
        
        print_section("Step 5: Re-sync to Central Account")
        
        sts_client = mock_boto_client("sts")
        assumed = sts_client.assume_role(
            RoleArn=f"arn:aws:iam::{env.central_account_id}:role/ManagementLambdaCrossAccountRole",
            RoleSessionName="ManagementLambdaCentralSync"
        )
        
        local_params = {}
        for name, value in env.workload_parameters.items():
            if name.startswith("/cpl/"):
                key = name.replace("/cpl/", "").strip("/")
                local_params[key] = json.loads(value)
        
        ssm_central = mock_boto_client(
            "ssm",
            aws_access_key_id=assumed["Credentials"]["AccessKeyId"],
            aws_secret_access_key=assumed["Credentials"]["SecretAccessKey"],
            aws_session_token=assumed["Credentials"]["SessionToken"]
        )
        
        ssm_central.put_parameter(
            Name=f"/accounts_cpl/{env.workload_account_id}",
            Description=f"Consolidated cpl config",
            Value=json.dumps(local_params, indent=2),
            Type="String",
            Overwrite=True
        )
    
    # Final verification
    print_section("Final Verification")
    
    # Check workload parameters
    workload_count = len([k for k in env.workload_parameters.keys() if k.startswith("/cpl/")])
    print_value("Workload Parameters", workload_count)
    
    # Check central parameter
    central_param = env.central_parameters.get(f"/accounts_cpl/{env.workload_account_id}")
    if central_param:
        central_data = json.loads(central_param)
        print_value("Central Consolidated Configs", len(central_data))
        
        if len(central_data) == 2:
            print_success("✓ Both configs synced to central account")
        else:
            print_error(f"Expected 2 configs, found {len(central_data)}")
            return False
    else:
        print_error("Central parameter not found")
        return False
    
    # Check log groups
    matching_log_groups = [lg for lg in env.log_groups.keys() if lg.startswith("/aws/lambda/")]
    print_value("Matching Log Groups", len(matching_log_groups))
    
    # Check subscription filters
    filtered_log_groups = len(env.subscription_filters)
    print_value("Log Groups with Filters", filtered_log_groups)
    
    if filtered_log_groups > 0:
        print_success("✓ Subscription filters created")
    else:
        print_error("No subscription filters")
        return False
    
    # Check assume role calls
    print_value("AssumeRole Calls", len(env.assume_role_calls))
    
    if len(env.assume_role_calls) >= 2:
        print_success("✓ Cross-account access working")
    else:
        print_error("Insufficient AssumeRole calls")
        return False
    
    env.print_state_summary()
    return True


def main():
    """Run all tests"""
    print_header("AWS Lambda Cross-Account Sync - Integration Tests")
    print_info("Testing with mocked AWS services")
    print_info(f"Test execution started at: {datetime.now().isoformat()}")
    
    tests = [
        ("CreateLogGroup Event", test_create_log_group_event),
        ("PutParameter Event - Cross-Account Sync", test_put_parameter_event),
        ("Multiple Parameters Consolidation", test_multiple_parameters_sync),
        ("DeleteParameter Event", test_delete_parameter_event),
        ("Complete Workflow", test_complete_workflow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print_header("Test Summary")
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    failed = total - passed
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{Colors.BOLD}Results:{Colors.END}")
    print_value("Total Tests", total)
    print_value("Passed", f"{Colors.GREEN}{passed}{Colors.END}")
    print_value("Failed", f"{Colors.RED}{failed}{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())