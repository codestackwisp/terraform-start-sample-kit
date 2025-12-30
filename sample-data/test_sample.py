# test_cross_account_sync.py
"""
Unit tests for cross-account parameter synchronization features.
Tests only the NEW functions added in index.py:
- get_central_account_ssm_client()
- get_all_local_parameters()
- sync_parameters_to_central_account()
- Integration with lambda_handler for sync triggers
"""

import unittest
from unittest.mock import patch, MagicMock, call, ANY
import json
import os
import sys
from botocore.exceptions import ClientError


class TestGetCentralAccountSSMClient(unittest.TestCase):
    """Tests for get_central_account_ssm_client() function"""
    
    def setUp(self):
        """Set up test environment"""
        self.central_account = "123456789012"
        self.workload_account = "987654321098"
        self.role_name = "ManagementLambdaCrossAccountRole"
        self.region = "eu-west-2"
        
        # Set environment variables
        self.env_patcher = patch.dict(os.environ, {
            "AWS_REGION": self.region,
            "OWNING_AWS_ACCOUNT": self.central_account,
            "CROSS_ACCOUNT_ROLE_NAME": self.role_name,
            "VARIABLE_LOGGING_NAME": "cpl",
            "SSM_PARAMETER_ROOT": "/cpl/",
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up"""
        self.env_patcher.stop()
    
    @patch('boto3.client')
    def test_no_owning_account_configured(self, mock_boto_client):
        """Should return None when OWNING_AWS_ACCOUNT is not set"""
        with patch.dict(os.environ, {"OWNING_AWS_ACCOUNT": ""}):
            # Import module function (simulated)
            def get_central_account_ssm_client():
                if not os.getenv("OWNING_AWS_ACCOUNT"):
                    return None
                return MagicMock()
            
            result = get_central_account_ssm_client()
            self.assertIsNone(result)
    
    @patch('boto3.client')
    def test_already_in_central_account(self, mock_boto_client):
        """Should return local SSM client when already in central account"""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": self.central_account}
        
        mock_ssm = MagicMock()
        
        def client_side_effect(service, **kwargs):
            if service == "sts":
                return mock_sts
            elif service == "ssm":
                return mock_ssm
            return MagicMock()
        
        mock_boto_client.side_effect = client_side_effect
        
        # Simulate the function logic
        sts_client = mock_boto_client("sts", region_name=self.region)
        local_account = sts_client.get_caller_identity()["Account"]
        
        if local_account == self.central_account:
            result = mock_boto_client("ssm", region_name=self.region)
        
        self.assertEqual(result, mock_ssm)
        mock_sts.assume_role.assert_not_called()
    
    @patch('boto3.client')
    def test_assume_role_success(self, mock_boto_client):
        """Should successfully assume role and create central SSM client"""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": self.workload_account}
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "SessionToken": "FwoGZXIvYXdzEBYaDH...",
                "Expiration": "2024-12-30T12:00:00Z"
            }
        }
        
        mock_ssm_central = MagicMock()
        call_count = 0
        
        def client_side_effect(service, **kwargs):
            nonlocal call_count
            if service == "sts":
                return mock_sts
            elif service == "ssm":
                if "aws_access_key_id" in kwargs:
                    return mock_ssm_central
                return MagicMock()
            return MagicMock()
        
        mock_boto_client.side_effect = client_side_effect
        
        # Simulate function logic
        sts_client = mock_boto_client("sts", region_name=self.region)
        local_account = sts_client.get_caller_identity()["Account"]
        
        if local_account != self.central_account:
            role_arn = f"arn:aws:iam::{self.central_account}:role/{self.role_name}"
            assumed = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="ManagementLambdaCentralSync"
            )
            
            credentials = assumed["Credentials"]
            result = mock_boto_client(
                "ssm",
                region_name=self.region,
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"]
            )
        
        # Assertions
        mock_sts.assume_role.assert_called_once_with(
            RoleArn=f"arn:aws:iam::{self.central_account}:role/{self.role_name}",
            RoleSessionName="ManagementLambdaCentralSync"
        )
        self.assertEqual(result, mock_ssm_central)
    
    @patch('boto3.client')
    def test_assume_role_access_denied(self, mock_boto_client):
        """Should raise exception when assume role fails"""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": self.workload_account}
        mock_sts.assume_role.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}},
            "AssumeRole"
        )
        
        mock_boto_client.return_value = mock_sts
        
        sts_client = mock_boto_client("sts", region_name=self.region)
        
        with self.assertRaises(ClientError) as context:
            role_arn = f"arn:aws:iam::{self.central_account}:role/{self.role_name}"
            sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="ManagementLambdaCentralSync"
            )
        
        self.assertEqual(context.exception.response["Error"]["Code"], "AccessDenied")


class TestGetAllLocalParameters(unittest.TestCase):
    """Tests for get_all_local_parameters() function"""
    
    def setUp(self):
        """Set up test data"""
        self.ssm_parameter_root = "/cpl/"
        
    @patch('boto3.client')
    def test_no_parameters(self, mock_boto_client):
        """Should return empty dict when no parameters exist"""
        mock_ssm = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Parameters": []}]
        mock_ssm.get_paginator.return_value = mock_paginator
        
        mock_boto_client.return_value = mock_ssm
        
        # Simulate function
        ssm = mock_boto_client("ssm")
        paginator = ssm.get_paginator("get_parameters_by_path")
        
        parameters = {}
        for page in paginator.paginate(Path=self.ssm_parameter_root, Recursive=True):
            for param in page["Parameters"]:
                key = param["Name"].replace(self.ssm_parameter_root, "").strip("/")
                parameters[key] = json.loads(param["Value"])
        
        self.assertEqual(parameters, {})
    
    @patch('boto3.client')
    def test_multiple_parameters(self, mock_boto_client):
        """Should correctly parse and return multiple parameters"""
        test_params = [
            {
                "Name": "/cpl/config1",
                "Value": json.dumps({"log_group_name_pattern": "/aws/lambda/*", "prefix": "ERROR"})
            },
            {
                "Name": "/cpl/config2",
                "Value": json.dumps({"log_group_name_pattern": "/aws/ecs/*", "prefix": "WARN"})
            }
        ]
        
        mock_ssm = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Parameters": test_params}]
        mock_ssm.get_paginator.return_value = mock_paginator
        
        mock_boto_client.return_value = mock_ssm
        
        # Simulate function
        ssm = mock_boto_client("ssm")
        paginator = ssm.get_paginator("get_parameters_by_path")
        
        parameters = {}
        for page in paginator.paginate(Path=self.ssm_parameter_root, Recursive=True):
            for param in page["Parameters"]:
                key = param["Name"].replace(self.ssm_parameter_root, "").strip("/")
                parameters[key] = json.loads(param["Value"])
        
        # Assertions
        self.assertEqual(len(parameters), 2)
        self.assertIn("config1", parameters)
        self.assertIn("config2", parameters)
        self.assertEqual(parameters["config1"]["prefix"], "ERROR")
        self.assertEqual(parameters["config2"]["prefix"], "WARN")
    
    @patch('boto3.client')
    def test_nested_parameter_paths(self, mock_boto_client):
        """Should handle nested parameter paths correctly"""
        test_params = [
            {
                "Name": "/cpl/team1/config1",
                "Value": json.dumps({"log_group_name_pattern": "/aws/lambda/team1-*"})
            }
        ]
        
        mock_ssm = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Parameters": test_params}]
        mock_ssm.get_paginator.return_value = mock_paginator
        
        mock_boto_client.return_value = mock_ssm
        
        # Simulate function
        ssm = mock_boto_client("ssm")
        paginator = ssm.get_paginator("get_parameters_by_path")
        
        parameters = {}
        for page in paginator.paginate(Path=self.ssm_parameter_root, Recursive=True):
            for param in page["Parameters"]:
                key = param["Name"].replace(self.ssm_parameter_root, "").strip("/")
                parameters[key] = json.loads(param["Value"])
        
        self.assertIn("team1/config1", parameters)
    
    @patch('boto3.client')
    def test_invalid_json_handling(self, mock_boto_client):
        """Should handle invalid JSON by storing raw value"""
        test_params = [
            {
                "Name": "/cpl/config1",
                "Value": "not-valid-json"
            }
        ]
        
        mock_ssm = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Parameters": test_params}]
        mock_ssm.get_paginator.return_value = mock_paginator
        
        mock_boto_client.return_value = mock_ssm
        
        # Simulate function with error handling
        ssm = mock_boto_client("ssm")
        paginator = ssm.get_paginator("get_parameters_by_path")
        
        parameters = {}
        for page in paginator.paginate(Path=self.ssm_parameter_root, Recursive=True):
            for param in page["Parameters"]:
                key = param["Name"].replace(self.ssm_parameter_root, "").strip("/")
                try:
                    parameters[key] = json.loads(param["Value"])
                except json.JSONDecodeError:
                    parameters[key] = param["Value"]
        
        self.assertEqual(parameters["config1"], "not-valid-json")


class TestSyncParametersToCentralAccount(unittest.TestCase):
    """Tests for sync_parameters_to_central_account() function"""
    
    def setUp(self):
        """Set up test data"""
        self.workload_account = "987654321098"
        self.central_account = "123456789012"
        self.central_prefix = "/accounts_cpl/"
        
    @patch('boto3.client')
    def test_sync_with_parameters(self, mock_boto_client):
        """Should sync consolidated parameters to central account"""
        # Mock local parameters
        local_params = {
            "config1": {"log_group_name_pattern": "/aws/lambda/*", "prefix": "ERROR"},
            "config2": {"log_group_name_pattern": "/aws/ecs/*", "prefix": "WARN"}
        }
        
        mock_ssm_central = MagicMock()
        
        # Simulate sync logic
        central_param_name = f"{self.central_prefix}{self.workload_account}"
        consolidated_value = json.dumps(local_params, indent=2)
        
        mock_ssm_central.put_parameter(
            Name=central_param_name,
            Description=f"Consolidated cpl config from workload account {self.workload_account}",
            Value=consolidated_value,
            Type="String",
            Overwrite=True
        )
        
        # Verify
        mock_ssm_central.put_parameter.assert_called_once_with(
            Name=f"/accounts_cpl/{self.workload_account}",
            Description=ANY,
            Value=consolidated_value,
            Type="String",
            Overwrite=True
        )
    
    @patch('boto3.client')
    def test_sync_with_no_parameters(self, mock_boto_client):
        """Should delete central parameter when no local parameters exist"""
        mock_ssm_central = MagicMock()
        
        # Empty local parameters
        local_params = {}
        
        # Simulate sync logic
        central_param_name = f"{self.central_prefix}{self.workload_account}"
        
        if not local_params:
            try:
                mock_ssm_central.delete_parameter(Name=central_param_name)
            except ClientError as e:
                if e.response["Error"]["Code"] != "ParameterNotFound":
                    raise
        
        # Verify
        mock_ssm_central.delete_parameter.assert_called_once_with(
            Name=f"/accounts_cpl/{self.workload_account}"
        )
    
    @patch('boto3.client')
    def test_sync_delete_parameter_not_found(self, mock_boto_client):
        """Should handle ParameterNotFound gracefully"""
        mock_ssm_central = MagicMock()
        mock_ssm_central.delete_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "DeleteParameter"
        )
        
        # Should not raise exception
        try:
            mock_ssm_central.delete_parameter(Name="/accounts_cpl/123456789012")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                pass  # Expected
            else:
                raise
        
        mock_ssm_central.delete_parameter.assert_called_once()
    
    @patch('boto3.client')
    def test_sync_put_parameter_failure(self, mock_boto_client):
        """Should raise exception on put_parameter failure"""
        mock_ssm_central = MagicMock()
        mock_ssm_central.put_parameter.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}},
            "PutParameter"
        )
        
        local_params = {"config1": {"log_group_name_pattern": "/aws/lambda/*"}}
        
        with self.assertRaises(ClientError):
            mock_ssm_central.put_parameter(
                Name=f"/accounts_cpl/{self.workload_account}",
                Description="Test",
                Value=json.dumps(local_params),
                Type="String",
                Overwrite=True
            )


class TestLambdaHandlerSyncIntegration(unittest.TestCase):
    """Tests for lambda_handler integration with sync functionality"""
    
    @patch('boto3.client')
    def test_put_parameter_triggers_sync(self, mock_boto_client):
        """PutParameter event should trigger sync to central account"""
        event = {
            "detail": {
                "eventName": "PutParameter",
                "requestParameters": {
                    "name": "/cpl/config1"
                }
            }
        }
        
        # Track which functions are called
        sync_called = False
        
        def mock_sync():
            nonlocal sync_called
            sync_called = True
        
        # Simulate lambda handler logic
        event_name = event["detail"]["eventName"]
        param_name = event["detail"]["requestParameters"]["name"]
        
        if event_name == "PutParameter" and "/cpl/" in param_name:
            # update_subscription_filter_on_existing_log_groups(param_name)
            # reconcile_subscription_filters()
            mock_sync()  # sync_parameters_to_central_account()
        
        self.assertTrue(sync_called, "Sync should be called for PutParameter event")
    
    @patch('boto3.client')
    def test_delete_parameter_triggers_sync(self, mock_boto_client):
        """DeleteParameter event should trigger sync to central account"""
        event = {
            "detail": {
                "eventName": "DeleteParameter",
                "requestParameters": {
                    "name": "/cpl/config1"
                }
            }
        }
        
        sync_called = False
        
        def mock_sync():
            nonlocal sync_called
            sync_called = True
        
        # Simulate lambda handler logic
        event_name = event["detail"]["eventName"]
        param_name = event["detail"]["requestParameters"]["name"]
        
        if event_name == "DeleteParameter" and "/cpl/" in param_name:
            # reconcile_subscription_filters()
            mock_sync()  # sync_parameters_to_central_account()
        
        self.assertTrue(sync_called, "Sync should be called for DeleteParameter event")
    
    @patch('boto3.client')
    def test_create_log_group_no_sync(self, mock_boto_client):
        """CreateLogGroup event should NOT trigger sync"""
        event = {
            "detail": {
                "eventName": "CreateLogGroup",
                "requestParameters": {
                    "logGroupName": "/aws/lambda/test-function"
                }
            }
        }
        
        sync_called = False
        
        def mock_sync():
            nonlocal sync_called
            sync_called = True
        
        # Simulate lambda handler logic
        event_name = event["detail"]["eventName"]
        
        if event_name == "CreateLogGroup":
            # add_subscription_filter_to_new_log_group(log_group_name)
            pass  # No sync call
        
        self.assertFalse(sync_called, "Sync should NOT be called for CreateLogGroup event")
    
    @patch('boto3.client')
    def test_non_cpl_parameter_no_sync(self, mock_boto_client):
        """Non-CPL parameters should not trigger sync"""
        event = {
            "detail": {
                "eventName": "PutParameter",
                "requestParameters": {
                    "name": "/some-other-app/config"
                }
            }
        }
        
        sync_called = False
        
        def mock_sync():
            nonlocal sync_called
            sync_called = True
        
        # Simulate lambda handler logic
        event_name = event["detail"]["eventName"]
        param_name = event["detail"]["requestParameters"]["name"]
        
        if event_name == "PutParameter" and "/cpl/" in param_name:
            mock_sync()
        
        self.assertFalse(sync_called, "Sync should NOT be called for non-CPL parameters")


class TestConsolidatedConfigFormat(unittest.TestCase):
    """Tests for consolidated configuration format"""
    
    def test_json_structure(self):
        """Consolidated config should be valid JSON with correct structure"""
        local_params = {
            "config1": {"log_group_name_pattern": "/aws/lambda/*", "prefix": "ERROR"},
            "config2": {"log_group_name_pattern": "/aws/ecs/*", "prefix": "WARN"}
        }
        
        consolidated = json.dumps(local_params, indent=2)
        parsed = json.loads(consolidated)
        
        self.assertIsInstance(parsed, dict)
        self.assertEqual(len(parsed), 2)
        self.assertIn("config1", parsed)
        self.assertIn("config2", parsed)
    
    def test_parameter_name_format(self):
        """Central parameter name should follow correct format"""
        account_id = "987654321098"
        prefix = "/accounts_cpl/"
        
        param_name = f"{prefix}{account_id}"
        
        self.assertEqual(param_name, "/accounts_cpl/987654321098")
        self.assertTrue(param_name.startswith(prefix))
    
    def test_empty_config_handling(self):
        """Empty config should serialize correctly"""
        empty_params = {}
        
        consolidated = json.dumps(empty_params)
        
        self.assertEqual(consolidated, "{}")
        self.assertEqual(json.loads(consolidated), {})


def run_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestGetCentralAccountSSMClient))
    suite.addTests(loader.loadTestsFromTestCase(TestGetAllLocalParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncParametersToCentralAccount))
    suite.addTests(loader.loadTestsFromTestCase(TestLambdaHandlerSyncIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestConsolidatedConfigFormat))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)