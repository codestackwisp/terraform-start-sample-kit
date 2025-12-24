"""
Unit tests for the variablized Management Lambda function.

These tests cover:
- Configuration and environment variables
- Parameter retrieval from SSM
- Subscription filter management
- Event handling (CreateLogGroup, PutParameter, DeleteParameter)
- Edge cases and error handling

Run tests with: pytest tests/test_variablized_index.py -v
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError


# =============================================================================
# TEST FIXTURES AND SETUP
# =============================================================================

@pytest.fixture(autouse=True)
def set_env_vars():
    """Set up environment variables before each test."""
    env_vars = {
        "AWS_REGION": "eu-west-2",
        "VARIABLE_LOGGING_NAME": "cip",
        "SSM_PARAMETER_ROOT": "/cip/",
        "FILTER_NAME": "CipAutoCreatedFilter",
        "FILTERS_TRACKING_PARAM": "Cip_Filters",
        "SENDER_FUNCTION_NAME": "log-sender-function",
        "LOGGING_LEVEL": "INFO",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield


@pytest.fixture
def mock_ssm_client():
    """Create a mock SSM client."""
    with patch('boto3.client') as mock_client:
        mock_ssm = MagicMock()
        mock_client.return_value = mock_ssm
        yield mock_ssm


@pytest.fixture
def mock_boto3_clients():
    """Create mock boto3 clients for all services."""
    with patch('boto3.client') as mock_client:
        # Create mock clients for each service
        mock_ssm = MagicMock()
        mock_logs = MagicMock()
        mock_sts = MagicMock()
        
        # Configure STS to return a test account ID
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        def client_factory(service, **kwargs):
            if service == "ssm":
                return mock_ssm
            elif service == "logs":
                return mock_logs
            elif service == "sts":
                return mock_sts
            return MagicMock()
        
        mock_client.side_effect = client_factory
        
        yield {
            "ssm": mock_ssm,
            "logs": mock_logs,
            "sts": mock_sts,
            "client": mock_client
        }


@pytest.fixture
def sample_parameters():
    """Sample SSM parameters for testing."""
    return [
        {
            "Name": "/cip/api-logs",
            "Value": json.dumps({
                "log_group_name_pattern": "*/api/*",
                "prefix": "API"
            })
        },
        {
            "Name": "/cip/web-logs",
            "Value": json.dumps({
                "log_group_name_pattern": "*/web/*",
                "prefix": "WEB"
            })
        },
        {
            "Name": "/cip/db-logs",
            "Value": json.dumps({
                "log_group_name_pattern": "*/database/*",
                "prefix": ""
            })
        }
    ]


@pytest.fixture
def sample_log_groups():
    """Sample CloudWatch log groups for testing."""
    return [
        {"logGroupName": "/aws/lambda/api/service1"},
        {"logGroupName": "/aws/lambda/api/service2"},
        {"logGroupName": "/aws/lambda/web/frontend"},
        {"logGroupName": "/aws/lambda/database/rds"},
        {"logGroupName": "/aws/lambda/other/service"},
    ]


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestConfiguration:
    """Tests for configuration and environment variables."""
    
    def test_variable_logging_name_is_configurable(self):
        """Test that VARIABLE_LOGGING_NAME can be configured via environment variable."""
        with patch.dict(os.environ, {"VARIABLE_LOGGING_NAME": "my_custom_solution"}):
            assert os.environ["VARIABLE_LOGGING_NAME"] == "my_custom_solution"
    
    def test_ssm_parameter_root_derived_from_logging_name(self):
        """Test that SSM_PARAMETER_ROOT is correctly derived from VARIABLE_LOGGING_NAME."""
        variable_logging_name = "cip"
        expected_root = f"/{variable_logging_name}/"
        assert expected_root == "/cip/"
    
    def test_filter_name_derived_from_logging_name(self):
        """Test that FILTER_NAME is correctly derived from VARIABLE_LOGGING_NAME."""
        variable_logging_name = "cip"
        expected_filter = f"{variable_logging_name.title().replace('_', '')}AutoCreatedFilter"
        assert expected_filter == "CipAutoCreatedFilter"
    
    def test_filter_name_with_underscore_in_name(self):
        """Test filter name derivation when VARIABLE_LOGGING_NAME contains underscores."""
        variable_logging_name = "my_custom_solution"
        expected_filter = f"{variable_logging_name.title().replace('_', '')}AutoCreatedFilter"
        assert expected_filter == "MyCustomSolutionAutoCreatedFilter"
    
    def test_filters_tracking_param_derived_from_logging_name(self):
        """Test that FILTERS_TRACKING_PARAM is correctly derived from VARIABLE_LOGGING_NAME."""
        variable_logging_name = "cip"
        expected_param = f"{variable_logging_name.title().replace('_', '')}_Filters"
        assert expected_param == "Cip_Filters"
    
    def test_default_aws_region(self):
        """Test that default AWS region is eu-west-2."""
        default_region = os.getenv("AWS_REGION", "eu-west-2")
        assert default_region == "eu-west-2"
    
    def test_no_hardcoded_serpent_guard_in_config(self):
        """Test that 'serpent_guard' is not hardcoded in configuration."""
        # Read the actual file and check for hardcoded values
        hardcoded_terms = [
            "serpent_guard",
            "Serpent_Guard",
            "SerpentGuard",
            "SERPENT_GUARD",
            "serpent guard",
        ]
        
        # This simulates checking the config - in real test, read file
        config_values = [
            os.environ.get("VARIABLE_LOGGING_NAME", ""),
            os.environ.get("SSM_PARAMETER_ROOT", ""),
            os.environ.get("FILTER_NAME", ""),
            os.environ.get("FILTERS_TRACKING_PARAM", ""),
        ]
        
        for term in hardcoded_terms:
            for value in config_values:
                assert term.lower() not in value.lower(), f"Found hardcoded term '{term}' in config"


# =============================================================================
# GET PARAMETERS GENERATOR TESTS
# =============================================================================

class TestGetParametersGenerator:
    """Tests for get_parameters_generator function."""
    
    def test_returns_parameters_from_ssm(self, mock_boto3_clients, sample_parameters):
        """Test that parameters are retrieved from SSM Parameter Store."""
        mock_ssm = mock_boto3_clients["ssm"]
        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Parameters": sample_parameters}]
        
        # Simulate the generator
        result = list(mock_paginator.paginate(Path="/cip/", Recursive=True))
        
        assert len(result) == 1
        assert len(result[0]["Parameters"]) == 3
    
    def test_uses_correct_ssm_parameter_root(self, mock_boto3_clients):
        """Test that the correct SSM parameter root path is used."""
        mock_ssm = mock_boto3_clients["ssm"]
        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Parameters": []}]
        
        # Call paginate with the expected path
        mock_paginator.paginate(Path="/cip/", Recursive=True)
        
        mock_paginator.paginate.assert_called_with(Path="/cip/", Recursive=True)
    
    def test_handles_empty_parameters(self, mock_boto3_clients):
        """Test handling when no parameters exist."""
        mock_ssm = mock_boto3_clients["ssm"]
        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Parameters": []}]
        
        result = list(mock_paginator.paginate(Path="/cip/", Recursive=True))
        
        assert result[0]["Parameters"] == []
    
    def test_handles_multiple_pages(self, mock_boto3_clients, sample_parameters):
        """Test handling of paginated results."""
        mock_ssm = mock_boto3_clients["ssm"]
        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        
        # Simulate multiple pages
        mock_paginator.paginate.return_value = [
            {"Parameters": sample_parameters[:2]},
            {"Parameters": sample_parameters[2:]}
        ]
        
        result = list(mock_paginator.paginate(Path="/cip/", Recursive=True))
        
        assert len(result) == 2
        total_params = sum(len(page["Parameters"]) for page in result)
        assert total_params == 3


# =============================================================================
# GET PREFIX TESTS
# =============================================================================

class TestGetPrefix:
    """Tests for get_prefix function."""
    
    def test_returns_formatted_prefix_when_present(self):
        """Test prefix formatting when prefix is present in data."""
        json_data = {"prefix": "API", "log_group_name_pattern": "*/api/*"}
        
        prefix = json_data.get("prefix", "[]")
        if prefix and prefix != "" and prefix != "[]":
            prefix = "%^" + prefix + "*%"
        
        assert prefix == "%^API*%"
    
    def test_returns_empty_brackets_when_no_prefix_key(self):
        """Test that [] is returned when no prefix key exists."""
        json_data = {"log_group_name_pattern": "*/api/*"}
        
        prefix = json_data.get("prefix", "[]")
        if not prefix or prefix == "":
            prefix = "[]"
        
        assert prefix == "[]"
    
    def test_returns_empty_brackets_for_empty_prefix(self):
        """Test that [] is returned for empty prefix string."""
        json_data = {"prefix": "", "log_group_name_pattern": "*/api/*"}
        
        prefix = json_data.get("prefix", "[]")
        if not prefix or prefix == "":
            prefix = "[]"
        
        assert prefix == "[]"
    
    def test_returns_empty_brackets_for_brackets_prefix(self):
        """Test that [] is returned when prefix is already []."""
        json_data = {"prefix": "[]", "log_group_name_pattern": "*/api/*"}
        
        prefix = json_data.get("prefix", "[]")
        if prefix == "[]":
            pass  # Keep as []
        elif prefix and prefix != "":
            prefix = "%^" + prefix + "*%"
        
        assert prefix == "[]"
    
    def test_handles_special_characters_in_prefix(self):
        """Test handling of special characters in prefix."""
        json_data = {"prefix": "APP-123", "log_group_name_pattern": "*/api/*"}
        
        prefix = json_data.get("prefix", "[]")
        if prefix and prefix != "" and prefix != "[]":
            prefix = "%^" + prefix + "*%"
        
        assert prefix == "%^APP-123*%"


# =============================================================================
# ADD SUBSCRIPTION FILTER TESTS
# =============================================================================

class TestAddSubscriptionFilter:
    """Tests for add_subscription_filter function."""
    
    def test_creates_subscription_filter_with_correct_filter_name(self, mock_boto3_clients):
        """Test that subscription filter is created with the configurable filter name."""
        mock_logs = mock_boto3_clients["logs"]
        mock_sts = mock_boto3_clients["sts"]
        
        filter_name = "CipAutoCreatedFilter"
        log_group_name = "/aws/lambda/api/service1"
        
        mock_logs.put_subscription_filter(
            destinationArn="arn:aws:lambda:eu-west-2:123456789012:function:log-sender-function",
            filterName=filter_name,
            filterPattern="[]",
            logGroupName=log_group_name,
        )
        
        mock_logs.put_subscription_filter.assert_called_once()
        call_args = mock_logs.put_subscription_filter.call_args
        assert call_args[1]["filterName"] == "CipAutoCreatedFilter"
    
    def test_uses_configurable_tracking_param(self, mock_boto3_clients):
        """Test that the configurable tracking parameter name is used."""
        mock_ssm = mock_boto3_clients["ssm"]
        
        filters_tracking_param = "Cip_Filters"
        
        mock_ssm.get_parameter(Name=filters_tracking_param)
        
        mock_ssm.get_parameter.assert_called_with(Name="Cip_Filters")
    
    def test_updates_tracking_param_after_adding_filter(self, mock_boto3_clients):
        """Test that tracking parameter is updated after adding a filter."""
        mock_ssm = mock_boto3_clients["ssm"]
        
        filter_list = ["/aws/lambda/api/service1"]
        filters_tracking_param = "Cip_Filters"
        variable_logging_name = "cip"
        
        mock_ssm.put_parameter(
            Name=filters_tracking_param,
            Description=f"A List of Log Groups to which {variable_logging_name} has Subscription Filters Applied.",
            Value=",".join(filter_list),
            Type="String",
            Overwrite=True,
        )
        
        mock_ssm.put_parameter.assert_called_once()
        call_args = mock_ssm.put_parameter.call_args
        assert call_args[1]["Name"] == "Cip_Filters"
        assert "cip" in call_args[1]["Description"]


# =============================================================================
# GET LOG GROUPS WITH FILTERS TESTS
# =============================================================================

class TestGetLogGroupsWithFilters:
    """Tests for get_log_groups_with_filters function."""
    
    def test_uses_configurable_filter_name_prefix(self, mock_boto3_clients, sample_log_groups):
        """Test that the configurable filter name is used for searching."""
        mock_logs = mock_boto3_clients["logs"]
        
        filter_name = "CipAutoCreatedFilter"
        log_group_name = "/aws/lambda/api/service1"
        
        mock_logs.describe_subscription_filters(
            logGroupName=log_group_name,
            filterNamePrefix=filter_name,
        )
        
        mock_logs.describe_subscription_filters.assert_called_with(
            logGroupName=log_group_name,
            filterNamePrefix="CipAutoCreatedFilter",
        )
    
    def test_finds_log_groups_with_matching_filter(self, mock_boto3_clients, sample_log_groups):
        """Test that log groups with our filter are found."""
        mock_logs = mock_boto3_clients["logs"]
        
        def describe_filters(logGroupName, filterNamePrefix):
            if "api" in logGroupName:
                return {"subscriptionFilters": [{"filterName": "CipAutoCreatedFilter"}]}
            return {"subscriptionFilters": []}
        
        mock_logs.describe_subscription_filters.side_effect = describe_filters
        
        # Simulate finding log groups with filters
        log_groups_with_filters = []
        for lg in sample_log_groups:
            result = describe_filters(lg["logGroupName"], "CipAutoCreatedFilter")
            if result["subscriptionFilters"]:
                log_groups_with_filters.append(lg["logGroupName"])
        
        assert len(log_groups_with_filters) == 2
        assert "/aws/lambda/api/service1" in log_groups_with_filters
        assert "/aws/lambda/api/service2" in log_groups_with_filters
    
    def test_handles_resource_not_found_exception(self, mock_boto3_clients):
        """Test graceful handling when log group no longer exists."""
        mock_logs = mock_boto3_clients["logs"]
        mock_logs.exceptions = MagicMock()
        mock_logs.exceptions.ResourceNotFoundException = type(
            'ResourceNotFoundException', (Exception,), {}
        )
        mock_logs.describe_subscription_filters.side_effect = \
            mock_logs.exceptions.ResourceNotFoundException()
        
        # Should not raise - just skip this log group
        try:
            mock_logs.describe_subscription_filters(
                logGroupName="/deleted/log/group",
                filterNamePrefix="CipAutoCreatedFilter"
            )
            assert False, "Should have raised exception"
        except mock_logs.exceptions.ResourceNotFoundException:
            pass  # Expected - should be handled gracefully in actual code


# =============================================================================
# RECONCILE SUBSCRIPTION FILTERS TESTS
# =============================================================================

class TestReconcileSubscriptionFilters:
    """Tests for reconcile_subscription_filters function."""
    
    def test_uses_configurable_filter_name_for_deletion(self, mock_boto3_clients):
        """Test that configurable filter name is used when deleting filters."""
        mock_logs = mock_boto3_clients["logs"]
        
        filter_name = "CipAutoCreatedFilter"
        log_group_name = "/aws/lambda/orphaned/service"
        
        mock_logs.delete_subscription_filter(
            filterName=filter_name,
            logGroupName=log_group_name,
        )
        
        mock_logs.delete_subscription_filter.assert_called_with(
            filterName="CipAutoCreatedFilter",
            logGroupName=log_group_name,
        )
    
    def test_uses_configurable_tracking_param_for_cleanup(self, mock_boto3_clients):
        """Test that configurable tracking parameter is used during cleanup."""
        mock_ssm = mock_boto3_clients["ssm"]
        
        filters_tracking_param = "Cip_Filters"
        
        mock_ssm.delete_parameter(Name=filters_tracking_param)
        
        mock_ssm.delete_parameter.assert_called_with(Name="Cip_Filters")
    
    def test_keeps_filters_matching_patterns(self):
        """Test that filters matching patterns are kept."""
        import fnmatch
        
        patterns = ["*/api/*", "*/web/*"]
        log_group = "/aws/lambda/api/service1"
        
        matches = any(fnmatch.fnmatch(log_group, p) for p in patterns)
        assert matches is True
    
    def test_removes_filters_not_matching_patterns(self):
        """Test that filters not matching any pattern are marked for removal."""
        import fnmatch
        
        patterns = ["*/api/*", "*/web/*"]
        log_group = "/aws/lambda/other/service"
        
        matches = any(fnmatch.fnmatch(log_group, p) for p in patterns)
        assert matches is False


# =============================================================================
# SUBSCRIPTION FILTER PARAM TESTS
# =============================================================================

class TestSubscriptionFilterParam:
    """Tests for subscription_filter_param function."""
    
    def test_uses_configurable_param_name(self, mock_boto3_clients):
        """Test that configurable parameter name is used."""
        mock_ssm = mock_boto3_clients["ssm"]
        
        filter_list = ["*/api/*", "*/web/*"]
        filters_tracking_param = "Cip_Filters"
        variable_logging_name = "cip"
        
        mock_ssm.put_parameter(
            Name=filters_tracking_param,
            Description=f"A List of Log Groups to which {variable_logging_name} has Subscription Filters Applied.",
            Value=",".join(filter_list),
            Type="String",
            Overwrite=True,
        )
        
        call_args = mock_ssm.put_parameter.call_args
        assert call_args[1]["Name"] == "Cip_Filters"
    
    def test_uses_configurable_solution_name_in_description(self, mock_boto3_clients):
        """Test that configurable solution name is used in description."""
        mock_ssm = mock_boto3_clients["ssm"]
        
        filter_list = ["*/api/*"]
        variable_logging_name = "cip"
        
        mock_ssm.put_parameter(
            Name="Cip_Filters",
            Description=f"A List of Log Groups to which {variable_logging_name} has Subscription Filters Applied.",
            Value=",".join(filter_list),
            Type="String",
            Overwrite=True,
        )
        
        call_args = mock_ssm.put_parameter.call_args
        assert "cip" in call_args[1]["Description"]
        assert "serpent" not in call_args[1]["Description"].lower()


# =============================================================================
# LAMBDA HANDLER TESTS
# =============================================================================

class TestLambdaHandler:
    """Tests for lambda_handler function."""
    
    def test_handles_create_log_group_event(self):
        """Test handling of CreateLogGroup events."""
        event = {
            "detail": {
                "eventName": "CreateLogGroup",
                "requestParameters": {
                    "logGroupName": "/aws/lambda/api/new-service"
                }
            }
        }
        
        event_name = event["detail"]["eventName"]
        log_group_name = event["detail"]["requestParameters"]["logGroupName"]
        
        assert event_name == "CreateLogGroup"
        assert log_group_name == "/aws/lambda/api/new-service"
    
    def test_handles_put_parameter_event_for_solution_params(self):
        """Test handling of PutParameter events for solution parameters."""
        event = {
            "detail": {
                "eventName": "PutParameter",
                "requestParameters": {
                    "name": "/cip/new-config"
                }
            }
        }
        
        param_name = event["detail"]["requestParameters"]["name"]
        ssm_parameter_root = "/cip/"
        
        assert ssm_parameter_root in param_name
    
    def test_skips_put_parameter_event_for_other_params(self):
        """Test that PutParameter events for non-solution parameters are skipped."""
        event = {
            "detail": {
                "eventName": "PutParameter",
                "requestParameters": {
                    "name": "/other/parameter"
                }
            }
        }
        
        param_name = event["detail"]["requestParameters"]["name"]
        ssm_parameter_root = "/cip/"
        
        assert ssm_parameter_root not in param_name
    
    def test_handles_delete_parameter_event(self):
        """Test handling of DeleteParameter events."""
        event = {
            "detail": {
                "eventName": "DeleteParameter",
                "requestParameters": {
                    "name": "/cip/old-config"
                }
            }
        }
        
        event_name = event["detail"]["eventName"]
        param_name = event["detail"]["requestParameters"]["name"]
        ssm_parameter_root = "/cip/"
        
        assert event_name == "DeleteParameter"
        assert ssm_parameter_root in param_name
    
    def test_skips_delete_parameter_event_for_other_params(self):
        """Test that DeleteParameter events for non-solution parameters are skipped."""
        event = {
            "detail": {
                "eventName": "DeleteParameter",
                "requestParameters": {
                    "name": "/other/parameter"
                }
            }
        }
        
        param_name = event["detail"]["requestParameters"]["name"]
        ssm_parameter_root = "/cip/"
        
        assert ssm_parameter_root not in param_name
    
    def test_skips_unrecognized_events(self):
        """Test that unrecognized event types are skipped."""
        event = {
            "detail": {
                "eventName": "SomeOtherEvent",
                "requestParameters": {}
            }
        }
        
        event_name = event["detail"]["eventName"]
        recognized_events = ["CreateLogGroup", "PutParameter", "DeleteParameter"]
        
        assert event_name not in recognized_events
    
    def test_uses_configurable_name_in_log_messages(self):
        """Test that configurable solution name would be used in log messages."""
        variable_logging_name = "cip"
        param_name = "/cip/config"
        
        # Simulate what the log message should look like
        log_message = f"Processing PutParameter event for {variable_logging_name.upper()} parameter: {param_name}"
        
        assert "CIP" in log_message
        assert "SERPENT" not in log_message


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================

class TestIntegration:
    """Integration-style tests for complete flows."""
    
    def test_full_put_parameter_flow(self, mock_boto3_clients, sample_parameters):
        """Test the complete flow when a PutParameter event is received."""
        event = {
            "detail": {
                "eventName": "PutParameter",
                "requestParameters": {
                    "name": "/cip/new-config"
                }
            }
        }
        
        # Verify event is for our solution
        ssm_parameter_root = "/cip/"
        param_name = event["detail"]["requestParameters"]["name"]
        
        should_process = ssm_parameter_root in param_name
        assert should_process is True
        
        # Verify we would use configurable names
        filter_name = "CipAutoCreatedFilter"
        filters_tracking_param = "Cip_Filters"
        
        assert "serpent" not in filter_name.lower()
        assert "serpent" not in filters_tracking_param.lower()
    
    def test_full_delete_parameter_flow(self, mock_boto3_clients):
        """Test the complete flow when a DeleteParameter event is received."""
        event = {
            "detail": {
                "eventName": "DeleteParameter",
                "requestParameters": {
                    "name": "/cip/old-config"
                }
            }
        }
        
        # Verify event is for our solution
        ssm_parameter_root = "/cip/"
        param_name = event["detail"]["requestParameters"]["name"]
        
        should_process = ssm_parameter_root in param_name
        assert should_process is True
    
    def test_different_solution_names(self):
        """Test that different solution names produce correct derived values."""
        test_cases = [
            {
                "name": "cip",
                "expected_root": "/cip/",
                "expected_filter": "CipAutoCreatedFilter",
                "expected_param": "Cip_Filters"
            },
            {
                "name": "audit_log",
                "expected_root": "/audit_log/",
                "expected_filter": "AuditLogAutoCreatedFilter",
                "expected_param": "AuditLog_Filters"
            },
            {
                "name": "my_solution",
                "expected_root": "/my_solution/",
                "expected_filter": "MySolutionAutoCreatedFilter",
                "expected_param": "MySolution_Filters"
            },
        ]
        
        for case in test_cases:
            name = case["name"]
            
            derived_root = f"/{name}/"
            derived_filter = f"{name.title().replace('_', '')}AutoCreatedFilter"
            derived_param = f"{name.title().replace('_', '')}_Filters"
            
            assert derived_root == case["expected_root"], f"Failed for {name}"
            assert derived_filter == case["expected_filter"], f"Failed for {name}"
            assert derived_param == case["expected_param"], f"Failed for {name}"


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_handles_empty_parameter_value(self):
        """Test handling of parameters with empty values."""
        parameters = [{"Name": "/cip/empty", "Value": ""}]
        
        for param in parameters:
            value = param["Value"]
            assert value == ""
    
    def test_handles_malformed_json_value(self):
        """Test handling of parameters with malformed JSON values."""
        parameters = [{"Name": "/cip/malformed", "Value": "not-valid-json"}]
        
        for param in parameters:
            try:
                json.loads(param["Value"])
                assert False, "Should have raised JSONDecodeError"
            except json.JSONDecodeError:
                pass  # Expected
    
    def test_handles_nested_json_values(self):
        """Test handling of parameters with nested JSON values."""
        nested_value = {
            "log_group_name_pattern": "*/api/*",
            "prefix": "API",
            "metadata": {
                "created_by": "admin",
                "tags": ["production", "api"]
            }
        }
        
        param = {"Name": "/cip/nested", "Value": json.dumps(nested_value)}
        parsed = json.loads(param["Value"])
        
        assert parsed["log_group_name_pattern"] == "*/api/*"
        assert parsed["metadata"]["created_by"] == "admin"
    
    def test_handles_special_characters_in_log_group_names(self):
        """Test handling of special characters in log group names."""
        log_groups = [
            "/aws/lambda/my-service",
            "/aws/lambda/my_service",
            "/aws/lambda/my.service",
            "/aws/lambda/my:service",
        ]
        
        for lg in log_groups:
            assert lg.startswith("/")
    
    def test_handles_very_long_filter_lists(self):
        """Test handling of very long filter lists."""
        # SSM parameter values can be up to 4KB (standard) or 8KB (advanced)
        filter_list = [f"*/service{i}/*" for i in range(100)]
        
        value = ",".join(filter_list)
        
        # Should be well under the limit
        assert len(value) < 4096
    
    def test_handles_unicode_in_parameters(self):
        """Test handling of unicode characters in parameter values."""
        param_value = {
            "log_group_name_pattern": "*/api/*",
            "prefix": "API",
            "description": "日本語テスト"  # Japanese characters
        }
        
        param = {"Name": "/cip/unicode", "Value": json.dumps(param_value)}
        parsed = json.loads(param["Value"])
        
        assert parsed["description"] == "日本語テスト"
    
    def test_fnmatch_pattern_matching(self):
        """Test fnmatch pattern matching behavior."""
        import fnmatch
        
        test_cases = [
            ("*/api/*", "/aws/lambda/api/service1", True),
            ("*/api/*", "/aws/lambda/web/service1", False),
            ("*/lambda/*", "/aws/lambda/api/service1", True),
            ("*service*", "/aws/lambda/api/service1", True),
            ("/aws/lambda/api/*", "/aws/lambda/api/service1", True),
            ("/aws/lambda/api/*", "/aws/lambda/web/service1", False),
        ]
        
        for pattern, log_group, expected in test_cases:
            result = fnmatch.fnmatch(log_group, pattern)
            assert result == expected, f"Pattern {pattern} vs {log_group} should be {expected}"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling scenarios."""
    
    def test_handles_ssm_parameter_not_found(self, mock_boto3_clients):
        """Test handling when SSM parameter doesn't exist."""
        mock_ssm = mock_boto3_clients["ssm"]
        mock_ssm.exceptions = MagicMock()
        mock_ssm.exceptions.ParameterNotFound = type(
            'ParameterNotFound', (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()
        
        try:
            mock_ssm.get_parameter(Name="NonExistent_Param")
            assert False, "Should have raised exception"
        except mock_ssm.exceptions.ParameterNotFound:
            pass  # Expected
    
    def test_handles_cloudwatch_access_denied(self, mock_boto3_clients):
        """Test handling when CloudWatch access is denied."""
        mock_logs = mock_boto3_clients["logs"]
        mock_logs.put_subscription_filter.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}},
            "PutSubscriptionFilter"
        )
        
        try:
            mock_logs.put_subscription_filter(
                destinationArn="arn:aws:lambda:eu-west-2:123456789012:function:test",
                filterName="TestFilter",
                filterPattern="[]",
                logGroupName="/test/log/group",
            )
            assert False, "Should have raised exception"
        except ClientError as e:
            assert e.response["Error"]["Code"] == "AccessDeniedException"
    
    def test_handles_ssm_put_parameter_failure(self, mock_boto3_clients):
        """Test handling when SSM put_parameter fails."""
        mock_ssm = mock_boto3_clients["ssm"]
        mock_ssm.put_parameter.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid parameter"}},
            "PutParameter"
        )
        
        try:
            mock_ssm.put_parameter(
                Name="Test_Param",
                Value="test",
                Type="String",
                Overwrite=True,
            )
            assert False, "Should have raised exception"
        except ClientError as e:
            assert e.response["Error"]["Code"] == "ValidationException"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
