import logging
import json
import os
import boto3
import fnmatch

AWS_REGION = os.getenv("AWS_REGION", "eu-west-2")
VARIABLE_LOGGING_NAME = os.getenv("VARIABLE_LOGGING_NAME", "cpl")
SSM_PARAMETER_ROOT = os.getenv("SSM_PARAMETER_ROOT", f"/{VARIABLE_LOGGING_NAME}/")
FILTER_NAME = os.getenv(
    "FILTER_NAME",
    f"{VARIABLE_LOGGING_NAME.title().replace('_', '')}AutoCreatedFilter"
)
FILTERS_TRACKING_PARAM = os.getenv(
    "FILTERS_TRACKING_PARAM",
    f"{VARIABLE_LOGGING_NAME.title().replace('_', '')}_Filters"
)
SENDER_FUNCTION_NAME = os.getenv("SENDER_FUNCTION_NAME")
# Set up logger
logger = logging.getLogger("LambdaLogger")
logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
logging.basicConfig(level=logging_level)
logger.setLevel(logging_level)

# Set up global boto3 clients
cloudwatch_logs_client = boto3.client("logs", region_name=AWS_REGION)
ssm_client = boto3.client("ssm", region_name=AWS_REGION)

def get_parameters_generator():
    """Gets all parameters under the `SSM_PARAMETER_ROOT` hierarchy in Parameter Store

    Yields:
        list[dict]: The parameter objects under the `SSM_PARAMETER_ROOT` hierarchy
    """
    paginator = ssm_client.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=SSM_PARAMETER_ROOT, Recursive=True):
        yield from page["Parameters"]


def get_prefix(json_data):
    """
    Args:
        json_data (dict): A list of parameters from the parameter store

    Returns:
        prefix(str): The prefix to use for the Subscription Filter
    """
    logger.debug(json_data)
    prefix = "[]"
    if "prefix" in json_data:
        prefix = json_data["prefix"]
        logger.debug(f"Prefix Loaded: {prefix}")
        if (prefix != "") and (prefix != "[]"):
            prefix = "%^" + prefix + "*%"
    else:
        prefix = "[]"

    return prefix


def add_subscription_filter(log_group_name, prefix=None):
    """Adds a Subscription Filter to a log group pointing to a given Lambda function

    Args:
        log_group_name (str): The name of the log group to add the Subscription Filter to
        prefix (str): Subscription Filter prefix for logs
    Raises:
        Exception: Raised if the function fails to add a Subscription Filter to the log group
    """
    if prefix is None:
        logger.debug("No Prefix Parameter")
        parameters = [item for item in get_parameters_generator()]
        for parameter in parameters:
            json_data = json.loads(parameter["Value"])
            if bool(
                fnmatch.filter(
                    [log_group_name], json_data["log_group_name_pattern"]
                )
            ):
                prefix = get_prefix(json_data)
                break
        logger.info(f"Prefix Loaded From Store: {prefix}")
    else:
        logger.debug(f"Prefix Parameter Loaded: {prefix}")

    logger.info(f"Applying Prefix: {prefix}")
    account_id = (
        boto3.client("sts", region_name=AWS_REGION)
        .get_caller_identity()
        .get("Account")
    )
    try:
        cloudwatch_logs_client.put_subscription_filter(
            destinationArn=f"arn:aws:lambda:{AWS_REGION}:{account_id}:function:{SENDER_FUNCTION_NAME}",
            filterName=FILTER_NAME,
            filterPattern=prefix,
            logGroupName=log_group_name,
        )
        base_param = ssm_client.get_parameter(Name=FILTERS_TRACKING_PARAM)
        logGroupList = base_param["Parameter"]["Value"].split(",")
        logger.debug(logGroupList)

        # Ensures that multiple entries of the same log group do not appear (in case of matching to multiple groups)
        # log_group_name in logGroupList
        if any(fnmatch.fnmatch(log_group_name, x) for x in logGroupList):
            pass
        else:
            logGroupList.append(log_group_name)

        subscription_filter_param(logGroupList)

    except Exception as error:
        logger.error(f"Failed to add Subscription Filter: {error}")
        raise error


def add_subscription_filter_to_new_log_group(log_group_name):
    """Adds a Subscription Filter to a newly created log group

    Args:
        log_group_name (str): The name of the log group to add a Subscription Filter to
    """
    parameters = [item for item in get_parameters_generator()]
    for parameter in parameters:
        json_data = json.loads(parameter["Value"])
        prefix = get_prefix(json_data)
        if bool(
            fnmatch.filter(
                [log_group_name], json_data["log_group_name_pattern"]
            )
        ):
            logger.info(
                f"{log_group_name} matches {json_data['log_group_name_pattern']} pattern. Adding Subscription Filter"
            )
            add_subscription_filter(log_group_name, prefix)
            return


def describe_log_groups_generator():
    """Gets all CloudWatch log groups in a given AWS region

    Yields:
        list[dict]: The CloudWatch log groups
    """
    cloudwatch_logs_client = boto3.client("logs", region_name=AWS_REGION)
    paginator = cloudwatch_logs_client.get_paginator("describe_log_groups")
    for page in paginator.paginate():
        yield from page["logGroups"]


def get_matching_log_groups(parameter_name, log_groups):
    """Retrieves the "log_group_name_pattern" pattern for a parameter and finds all log groups matching the pattern

    Args:
        parameter_name (str): The name of the parameter to look up in Parameter Store
        log_groups (list[str]): The array of log groups to pattern match against

    Returns:
        list[str]: An array of matching log groups
        dict: The parameter object
    """
    response = ssm_client.get_parameter(Name=parameter_name)
    parameter_info = json.loads(response["Parameter"]["Value"])
    matched_log_groups = []
    for log_group in log_groups:
        if bool(
            fnmatch.filter(
                [log_group], parameter_info["log_group_name_pattern"]
            )
        ):
            matched_log_groups.append(log_group)
    return matched_log_groups, parameter_info


def update_subscription_filter_on_existing_log_groups(parameter_name):
    """Finds all existing log groups matching the "log_group_name_pattern" attribute of a new parameter & adds filters

    Args:
        parameter_name (str): The name of the parameter to look up in Parameter Store
    """
    all_log_groups = [
        item["logGroupName"] for item in describe_log_groups_generator()
    ]
    matched_log_groups, parameter_info = get_matching_log_groups(
        parameter_name, all_log_groups
    )

    if len(matched_log_groups) == 0:
        logger.info(
            "No log group to add Subscription Filters to. Exiting Lambda."
        )
        return

    for log_group in matched_log_groups:
        logGroupListNew = []
        logGroupToAdd = ""
        parameters = [item for item in get_parameters_generator()]
        for parameter in parameters:
            json_data = json.loads(parameter["Value"])
            if bool(
                fnmatch.filter([log_group], json_data["log_group_name_pattern"])
            ):
                logGroupToAdd = str(json_data["log_group_name_pattern"])

        try:
            base_param = ssm_client.get_parameter(Name=FILTERS_TRACKING_PARAM)
            logGroupList = base_param["Parameter"]["Value"].split(",")
            if logGroupToAdd not in logGroupList:
                logGroupList.append(logGroupToAdd)
            logGroupListNew = logGroupList
        except Exception as error:
            logGroupListNew.append(logGroupToAdd)
            logger.info(f"{error} No {FILTERS_TRACKING_PARAM} Param Yet")
        subscription_filter_param(logGroupListNew)

        logger.info(
            f"{log_group} matches {parameter_info['log_group_name_pattern']} pattern. Adding Subscription Filter"
        )
        add_subscription_filter(log_group)


def get_log_groups_with_filters():
    """Find all log groups that currently have our subscription filter.

    This function queries the actual CloudWatch Logs state to find which log groups
    have our auto-created filter, providing a source-of-truth approach
    that is resilient to drift and manual changes.

    Returns:
        list[str]: List of log group names that have our subscription filter
    """
    log_groups_with_filters = []
    logger.info(
        f"Scanning all log groups to find those with {VARIABLE_LOGGING_NAME} filters..."
    )

    for log_group in describe_log_groups_generator():
        log_group_name = log_group["logGroupName"]
        try:
            filters = cloudwatch_logs_client.describe_subscription_filters(
                logGroupName=log_group_name,
                filterNamePrefix=FILTER_NAME,
            )

            if filters["subscriptionFilters"]:
                log_groups_with_filters.append(log_group_name)
                logger.debug(f"Found filter on: {log_group_name}")
        except cloudwatch_logs_client.exceptions.ResourceNotFoundException:
            # Log group was deleted between describe_log_groups and describe_subscription_filters
            logger.debug(f"Log group no longer exists: {log_group_name}")
        except Exception as error:
            logger.warning(
                f"Could not check filters for {log_group_name}: {error}"
            )

    logger.info(
        f"Found {len(log_groups_with_filters)} log groups with {VARIABLE_LOGGING_NAME} filters"
    )
    return log_groups_with_filters


def reconcile_subscription_filters():
    """Reconcile subscription filters to match current SSM parameter patterns.

    This function uses a source-of-truth approach by:
    1. Getting all current patterns that SHOULD have filters (from SSM parameters)
    2. Finding all log groups that ACTUALLY have our subscription filter (from CloudWatch)
    3. Removing filters from log groups that don't match any current pattern

    This approach is self-healing and resilient to manual changes or state drift.
    Called after parameter create/update/delete to ensure consistency.
    """
    logger.info("Starting subscription filter cleanup process...")

    # Step 1: Get all current patterns that SHOULD have filters
    current_patterns = []
    try:
        parameters = [item for item in get_parameters_generator()]
        for parameter in parameters:
            json_data = json.loads(parameter["Value"])
            pattern = json_data["log_group_name_pattern"]
            current_patterns.append(pattern)
            logger.debug(f"Active pattern: {pattern}")
    except Exception as error:
        logger.error(f"Failed to retrieve SSM parameters: {error}")
        raise error

    logger.info(
        f"Found {len(current_patterns)} active pattern(s) in SSM parameters"
    )

    # Step 2: Find ALL log groups that ACTUALLY have our subscription filter
    log_groups_with_filters = get_log_groups_with_filters()

    if not log_groups_with_filters:
        logger.info(
            f"No log groups found with {VARIABLE_LOGGING_NAME} filters. Nothing to clean up."
        )
        # Clean up the SSM parameter if it exists
        try:
            ssm_client.delete_parameter(Name=FILTERS_TRACKING_PARAM)
            logger.info(f"Deleted {FILTERS_TRACKING_PARAM} SSM parameter")
        except ssm_client.exceptions.ParameterNotFound:
            logger.debug(f"{FILTERS_TRACKING_PARAM} parameter does not exist")
        return

    # Step 3: Determine which filters should be removed
    filters_to_remove = []
    filters_to_keep = []

    for log_group_name in log_groups_with_filters:
        matches_any_pattern = False
        matched_pattern = None

        for pattern in current_patterns:
            if fnmatch.fnmatch(log_group_name, pattern):
                matches_any_pattern = True
                matched_pattern = pattern
                break

        if matches_any_pattern:
            filters_to_keep.append(log_group_name)
            logger.debug(
                f"Keeping filter on {log_group_name} (matches {matched_pattern})"
            )
        else:
            filters_to_remove.append(log_group_name)
            logger.info(
                f"Will remove filter from {log_group_name} (no matching pattern)"
            )

    logger.info(
        f"Filters to keep: {len(filters_to_keep)}, Filters to remove: {len(filters_to_remove)}"
    )

    # Step 4: Remove orphaned filters
    removed_count = 0
    failed_count = 0

    for log_group_name in filters_to_remove:
        try:
            cloudwatch_logs_client.delete_subscription_filter(
                filterName=FILTER_NAME,
                logGroupName=log_group_name,
            )
            removed_count += 1
            logger.info(f"Successfully removed filter from {log_group_name}")
        except cloudwatch_logs_client.exceptions.ResourceNotFoundException:
            # Filter or log group no longer exists - this is fine
            logger.info(f"Filter or log group already gone: {log_group_name}")
            removed_count += 1
        except Exception as error:
            failed_count += 1
            logger.error(
                f"Failed to remove filter from {log_group_name}: {error}"
            )
            # Continue processing - don't let one failure stop cleanup

    logger.info(
        f"Cleanup complete: {removed_count} filters removed, {failed_count} failures"
    )

    # Step 5: Update SSM parameter to reflect current patterns (for reference/auditing)
    if current_patterns:
        subscription_filter_param(current_patterns)
        logger.info(
            f"Updated {FILTERS_TRACKING_PARAM} SSM parameter with current patterns"
        )
    else:
        try:
            ssm_client.delete_parameter(Name=FILTERS_TRACKING_PARAM)
            logger.info(
                f"Deleted {FILTERS_TRACKING_PARAM} SSM parameter (no active patterns)"
            )
        except ssm_client.exceptions.ParameterNotFound:
            logger.debug(f"{FILTERS_TRACKING_PARAM} parameter does not exist")


def subscription_filter_param(filterList):
    """Updates the SSM parameter tracking which log groups have subscription filters.

    Args:
        filterList (list): List of log group patterns/names with filters
    """
    logger.info(f"Filter List: {filterList}")
    logGroupStr = ",".join(filterList)
    ssm_client.put_parameter(
        Name=FILTERS_TRACKING_PARAM,
        Description=f"A List of Log Groups to which {VARIABLE_LOGGING_NAME} has Subscription Filters Applied.",
        Value=logGroupStr,
        Type="String",
        Overwrite=True,
    )


def lambda_handler(event, context):
    """Main Lambda handler for processing EventBridge events.

    Processes CreateLogGroup, PutParameter, and DeleteParameter events to manage
    CloudWatch Logs subscription filters.
    """
    logger.info("Lambda invoked by EventBridge")
    logger.debug(f"Event payload:\n{json.dumps(event, indent=4)}")

    event_name = event["detail"]["eventName"]

    if event_name == "CreateLogGroup":
        log_group_name = event["detail"]["requestParameters"]["logGroupName"]
        logger.info(f"Processing CreateLogGroup event for: {log_group_name}")
        add_subscription_filter_to_new_log_group(log_group_name)
        logger.info(
            f"Completed processing CreateLogGroup event for: {log_group_name}"
        )

    elif event_name == "PutParameter":
        param_name = event["detail"]["requestParameters"]["name"]
        if SSM_PARAMETER_ROOT in param_name:
            logger.info(
                f"Processing PutParameter event for {VARIABLE_LOGGING_NAME.upper()} parameter: {param_name}"
            )
            update_subscription_filter_on_existing_log_groups(param_name)
            logger.info(
                "Reconciling all filters to remove orphaned subscriptions..."
            )
            reconcile_subscription_filters()
            logger.info(
                f"Completed processing PutParameter event for: {param_name}"
            )
        else:
            logger.info(
                f"Skipping PutParameter event - not a {VARIABLE_LOGGING_NAME.upper()} parameter: {param_name}"
            )

    elif event_name == "DeleteParameter":
        param_name = event["detail"]["requestParameters"]["name"]
        if SSM_PARAMETER_ROOT in param_name:
            logger.info(
                f"Processing DeleteParameter event for {VARIABLE_LOGGING_NAME.upper()} parameter: {param_name}"
            )
            reconcile_subscription_filters()
            logger.info(
                f"Completed processing DeleteParameter event for: {param_name}"
            )
        else:
            logger.info(
                f"Skipping DeleteParameter event - not a {VARIABLE_LOGGING_NAME.upper()} parameter: {param_name}"
            )

    else:
        logger.info(
            f"Skipping event - not a recognized event type: {event_name}"
        )
