"""tests/test_checkers.py — Unit tests with moto-mocked AWS."""

import os
import boto3
import pytest
from moto import mock_aws

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.checkers.ecs import ECSChecker
from src.checkers.cloudwatch import CloudWatchChecker


@mock_aws
def test_ecs_service_not_found():
    boto3.client("ecs", region_name="us-east-1").create_cluster(clusterName="dev-cluster")
    result = ECSChecker(env="dev").check_service("nonexistent")
    assert result["healthy"] is False
    assert "error" in result


@mock_aws
def test_ecs_all_services_empty():
    boto3.client("ecs", region_name="us-east-1").create_cluster(clusterName="dev-cluster")
    assert ECSChecker(env="dev").check_all_services() == []


@mock_aws
def test_cloudwatch_missing_log_group():
    assert CloudWatchChecker(env="dev").get_recent_errors(service="api") == []


@mock_aws
def test_cloudwatch_error_rate_no_data():
    result = CloudWatchChecker(env="dev").get_error_rate(service="api")
    assert result["error_rate"] == 0.0
    assert result["above_threshold"] is False


@mock_aws
def test_ecs_stopped_tasks_empty():
    boto3.client("ecs", region_name="us-east-1").create_cluster(clusterName="dev-cluster")
    result = ECSChecker(env="dev").get_stopped_task_exit_codes("api")
    assert result == []


@mock_aws
def test_cloudwatch_cpu_memory_no_data():
    result = CloudWatchChecker(env="dev").get_ecs_cpu_memory("api")
    assert result["cpu_max_pct"] is None
    assert result["memory_max_pct"] is None
