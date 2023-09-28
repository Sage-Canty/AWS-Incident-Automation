"""
src/checkers/cloudwatch.py
CloudWatch metrics and logs checker.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})


class CloudWatchChecker:
    def __init__(self, env: str, region: str = "us-east-1"):
        self.env = env
        self.region = region
        self.cw = boto3.client("cloudwatch", region_name=region, config=BOTO_CONFIG)
        self.logs = boto3.client("logs", region_name=region, config=BOTO_CONFIG)

    def get_error_rate(self, service: str, minutes: int = 15) -> dict[str, Any]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)

        def get_sum(metric_name: str) -> float:
            try:
                resp = self.cw.get_metric_statistics(
                    Namespace="AWS/ApplicationELB",
                    MetricName=metric_name,
                    Dimensions=[
                        {"Name": "LoadBalancer", "Value": f"app/{self.env}-alb/"},
                        {"Name": "TargetGroup", "Value": f"targetgroup/{self.env}-{service}-tg/"},
                    ],
                    StartTime=start, EndTime=end,
                    Period=minutes * 60, Statistics=["Sum"],
                )
                return sum(d["Sum"] for d in resp.get("Datapoints", []))
            except ClientError:
                return 0.0

        total_5xx = get_sum("HTTPCode_Target_5XX_Count")
        total_2xx = get_sum("HTTPCode_Target_2XX_Count")
        total = total_5xx + total_2xx
        error_rate = (total_5xx / total) if total > 0 else 0.0

        return {
            "service": service,
            "lookback_minutes": minutes,
            "total_requests": int(total),
            "error_5xx": int(total_5xx),
            "error_rate": round(error_rate, 4),
            "above_threshold": error_rate > 0.05,
        }

    def get_recent_errors(self, service: str, minutes: int = 15, limit: int = 50) -> list[dict]:
        log_group = f"/ecs/{self.env}/{service}"
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = end_ms - (minutes * 60 * 1000)
        try:
            resp = self.logs.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms, endTime=end_ms,
                filterPattern="ERROR", limit=limit,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return []
            logger.error("Failed to filter log events: %s", e)
            return []

        events = []
        for event in resp.get("events", []):
            ts = datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc).isoformat()
            events.append({
                "timestamp": ts,
                "stream": event.get("logStreamName", ""),
                "message": event.get("message", "").strip(),
            })
        return sorted(events, key=lambda e: e["timestamp"], reverse=True)

    def get_ecs_cpu_memory(self, service: str, minutes: int = 15) -> dict[str, Any]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)

        def get_max(metric_name: str) -> float | None:
            try:
                resp = self.cw.get_metric_statistics(
                    Namespace="ECS/ContainerInsights",
                    MetricName=metric_name,
                    Dimensions=[
                        {"Name": "ClusterName", "Value": f"{self.env}-cluster"},
                        {"Name": "ServiceName", "Value": f"{self.env}-{service}"},
                    ],
                    StartTime=start, EndTime=end,
                    Period=minutes * 60, Statistics=["Maximum"],
                )
                pts = resp.get("Datapoints", [])
                return round(max(d["Maximum"] for d in pts), 1) if pts else None
            except ClientError:
                return None

        return {
            "service": f"{self.env}-{service}",
            "lookback_minutes": minutes,
            "cpu_max_pct": get_max("CpuUtilized"),
            "memory_max_pct": get_max("MemoryUtilized"),
        }
