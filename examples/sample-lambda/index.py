#!/usr/bin/env python3
"""
Management Lambda

This Lambda function synchronizes SSM parameter configuration
from workload accounts into a central audit account.

Behavior:
---------
1. Reads all SSM parameters under the workload account path defined by SOURCE_PREFIX.
2. Optionally renames parameter key segments by replacing OLD_TOKEN → NEW_TOKEN.
3. Normalizes keys and aggregates all parameters into a single JSON document.
4. Assumes a cross-account role into the central account.
5. Stores the aggregated configuration JSON document in a single SSM parameter
   within the central account under CENTRAL_SSM_PARAM_PREFIX/<AccountId>.

Environment Variables:
----------------------
SOURCE_PREFIX              (required)  - SSM path in workload account to scan.
OLD_TOKEN                 (optional)  - Text within key names to replace.
NEW_TOKEN                 (required)  - Replacement token for key renaming.
CENTRAL_ROLE_ARN          (required)  - IAM role ARN in central account to assume.
CENTRAL_SSM_PARAM_PREFIX  (optional)  - Prefix for central SSM parameter path.
REGION                    (optional)  - Override AWS region for boto3 clients.

Returns:
--------
Dict with status and central parameter name.

Notes:
------
OLD_TOKEN may be None, in which case no renaming occurs.
No parameter names or tokens are hardcoded in the Lambda.
"""

import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)


def get_env(name, required=False, default=None):
    """
    Retrieve an environment variable.

    Parameters:
    -----------
    name : str
        Name of the environment variable.
    required : bool
        If True, raises an error when the variable is missing.
    default : str | None
        Default value when not required.

    Returns:
    --------
    str
        Environment variable value.

    Raises:
    -------
    RuntimeError
        If required variable is missing.
    """
    value = os.getenv(name, default)
    if required and (value is None or value.strip() == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def fetch_parameters_by_path(ssm_client, path):
    """
    Fetch all parameters under a given SSM path using pagination.

    Parameters:
    -----------
    ssm_client : boto3.client("ssm")
        SSM client.
    path : str
        Parameter path prefix.

    Returns:
    --------
    list[dict]
        List of parameter objects from SSM.
    """
    params = []
    next_token = None

    while True:
        kwargs = {
            "Path": path,
            "Recursive": True,
            "WithDecryption": True,
            "MaxResults": 1000,
        }
        if next_token:
            kwargs["NextToken"] = next_token

        resp = ssm_client.get_parameters_by_path(**kwargs)
        params.extend(resp.get("Parameters", []))

        next_token = resp.get("NextToken")
        if not next_token:
            break

    return params


def normalize_param_name(name, old_token, new_token):
    """
    Normalize a parameter key by:
    - Removing leading/trailing slashes
    - Replacing old_token → new_token (if old_token is provided)

    Parameters:
    -----------
    name : str
        Raw parameter key.
    old_token : str | None
        Token to replace.
    new_token : str
        Replacement token.

    Returns:
    --------
    str
        Normalized parameter name.
    """
    if old_token:
        name = name.replace(old_token, new_token)

    return name.strip("/")


def assemble_payload(account_id, parameters, source_prefix, old_token, new_token):
    """
    Build a final JSON payload containing all workload account configuration.

    Parameters:
    -----------
    account_id : str
        Workload AWS Account ID.
    parameters : list[dict]
        SSM parameter records fetched from workload account.
    source_prefix : str
        Path prefix defining root of workload configuration.
    old_token : str | None
        Old name segment to replace.
    new_token : str
        New name to insert.

    Returns:
    --------
    dict
        Structured payload ready to store in central SSM.
    """
    payload = {
        "WorkloadAccountId": str(account_id),
        "SourcePrefix": source_prefix,
        "Parameters": {},
    }

    for p in parameters:
        raw = p.get("Name", "")

        # Remove prefix
        if source_prefix and raw.startswith(source_prefix):
            key_segment = raw[len(source_prefix):]
        else:
            key_segment = raw

        normalized = normalize_param_name(key_segment, old_token, new_token)
        payload["Parameters"][normalized] = p.get("Value")

    return payload


def assume_role(sts_client, role_arn):
    """
    Assume IAM role into the central account.

    Parameters:
    -----------
    sts_client : boto3.client("sts")
    role_arn : str

    Returns:
    --------
    dict
        Temporary AWS credentials.
    """
    resp = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName="management-lambda-session"
    )
    c = resp["Credentials"]
    return {
        "aws_access_key_id": c["AccessKeyId"],
        "aws_secret_access_key": c["SecretAccessKey"],
        "aws_session_token": c["SessionToken"],
    }


def handler(event, context):
    """
    AWS Lambda Handler

    Triggered whenever workload account parameters update.

    Steps:
    ------
    1. Load environment variables.
    2. Read parameters under SOURCE_PREFIX from workload account.
    3. Normalize & restructure parameters into a single JSON document.
    4. Assume a central account role.
    5. Write the final JSON document to a single SSM parameter.

    Parameters:
    -----------
    event : dict
        Lambda event payload.
    context : LambdaContext
        Lambda context runtime information.

    Returns:
    --------
    dict
        {
            "status": "ok",
            "central_parameter": "<full SSM parameter name>"
        }
    """

    LOG.info("Event: %s", json.dumps(event))

    source_prefix = get_env("SOURCE_PREFIX", required=True)
    old_token = get_env("OLD_TOKEN", required=False, default=None)
    new_token = get_env("NEW_TOKEN", required=True)
    central_role_arn = get_env("CENTRAL_ROLE_ARN", required=True)
    central_param_prefix = get_env("CENTRAL_SSM_PARAM_PREFIX", default="/central-config/")
    region = get_env("REGION", default=None)

    session_kwargs = {}
    if region:
        session_kwargs["region_name"] = region

    ssm = boto3.client("ssm", **session_kwargs)
    sts = boto3.client("sts", **session_kwargs)

    # workload account id
    acct = sts.get_caller_identity()["Account"]

    params = fetch_parameters_by_path(ssm, source_prefix)
    LOG.info("Fetched %d parameters", len(params))

    payload = assemble_payload(acct, params, source_prefix, old_token, new_token)
    payload_json = json.dumps(payload, separators=(",", ":"))

    dest_param = central_param_prefix.rstrip("/") + "/" + acct

    creds = assume_role(sts, central_role_arn)

    central_ssm = boto3.client(
        "ssm",
        aws_access_key_id=creds["aws_access_key_id"],
        aws_secret_access_key=creds["aws_secret_access_key"],
        aws_session_token=creds["aws_session_token"],
        **session_kwargs,
    )

    central_ssm.put_parameter(
        Name=dest_param,
        Value=payload_json,
        Type="String",
        Overwrite=True,
    )

    LOG.info("Updated central parameter: %s", dest_param)

    return {"status": "ok", "central_parameter": dest_param}
