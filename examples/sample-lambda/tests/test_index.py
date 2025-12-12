import os
import json
import pytest
from unittest import mock

# import target module
from lambda_code.index import (
    normalize_param_name,
    assemble_payload,
    fetch_parameters_by_path,
    handler,
)


def test_normalize_param_name_replacement():
    old = "oldtoken"
    new = "newsolution"
    name = "/oldtoken/app/db/url"
    norm = normalize_param_name(name.strip("/"), old, new)
    assert "oldtoken" not in norm
    assert "newsolution" in norm


def test_assemble_payload():
    account_id = "111122223333"
    params = [
        {"Name": "/prefix/oldtoken/key1", "Value": "v1"},
        {"Name": "/prefix/other/key2", "Value": "v2"},
    ]

    payload = assemble_payload(
        account_id,
        params,
        "/prefix/",
        "oldtoken",
        "newsolution"
    )

    assert payload["WorkloadAccountId"] == account_id
    keys = list(payload["Parameters"].keys())
    assert any("newsolution" in k for k in keys)


def test_fetch_parameters_by_path_pagination():
    client = mock.Mock()
    client.get_parameters_by_path.side_effect = [
        {"Parameters": [{"Name": "/p/a", "Value": "1"}], "NextToken": "t1"},
        {"Parameters": [{"Name": "/p/b", "Value": "2"}]},
    ]

    params = fetch_parameters_by_path(client, "/p/")
    assert len(params) == 2
    assert any(p["Name"] == "/p/a" for p in params)
    assert any(p["Name"] == "/p/b" for p in params)


@mock.patch("lambda_code.index.boto3.client")
def test_handler_end_to_end(mock_client, monkeypatch):

    monkeypatch.setenv("SOURCE_PREFIX", "/prefix/")
    monkeypatch.setenv("OLD_TOKEN", "oldtoken")
    monkeypatch.setenv("NEW_TOKEN", "newsolution")
    monkeypatch.setenv("CENTRAL_ROLE_ARN", "arn:aws:iam::222233334444:role/CentralRole")
    monkeypatch.setenv("CENTRAL_SSM_PARAM_PREFIX", "/central-config/")

    fake_ssm = mock.Mock()
    fake_sts = mock.Mock()
    fake_central_ssm = mock.Mock()

    def client_factory(service, **kwargs):
        if service == "ssm" and "aws_access_key_id" in kwargs:
            return fake_central_ssm
        if service == "ssm":
            return fake_ssm
        if service == "sts":
            return fake_sts
        raise RuntimeError(f"Unexpected client: {service}")

    mock_client.side_effect = client_factory

    fake_sts.get_caller_identity.return_value = {"Account": "111122223333"}
    fake_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "X",
            "SecretAccessKey": "Y",
            "SessionToken": "Z",
        }
    }

    fake_ssm.get_parameters_by_path.return_value = {
        "Parameters": [
            {"Name": "/prefix/oldtoken/keyA", "Value": "123"}
        ]
    }

    result = handler({"trigger": "test"}, None)

    fake_central_ssm.put_parameter.assert_called_once()
    args, kwargs = fake_central_ssm.put_parameter.call_args

    assert kwargs["Name"].endswith("111122223333")
    assert "newsolution" in kwargs["Value"]
    assert result["status"] == "ok"
