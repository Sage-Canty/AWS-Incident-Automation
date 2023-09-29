"""
src/checkers/alb.py
ALB target group health checker.
"""

import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})


class ALBChecker:
    def __init__(self, env: str, region: str = "us-east-1"):
        self.env = env
        self.region = region
        self.elbv2 = boto3.client("elbv2", region_name=region, config=BOTO_CONFIG)

    def check_target_group(self, service_name: str) -> dict[str, Any]:
        tg_name = f"{self.env}-{service_name}-tg"
        try:
            resp = self.elbv2.describe_target_groups(Names=[tg_name])
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "TargetGroupNotFound":
                return {"name": tg_name, "error": "target group not found", "healthy": False}
            return {"name": tg_name, "error": str(e), "healthy": False}

        tg_arn = resp["TargetGroups"][0]["TargetGroupArn"]
        health_resp = self.elbv2.describe_target_health(TargetGroupArn=tg_arn)
        targets = health_resp["TargetHealthDescriptions"]
        healthy = [t for t in targets if t["TargetHealth"]["State"] == "healthy"]
        unhealthy = [t for t in targets if t["TargetHealth"]["State"] != "healthy"]

        return {
            "name": tg_name,
            "total_count": len(targets),
            "healthy_count": len(healthy),
            "unhealthy_count": len(unhealthy),
            "healthy": len(unhealthy) == 0 and len(targets) > 0,
            "unhealthy_targets": [
                {
                    "id": t["Target"]["Id"],
                    "state": t["TargetHealth"]["State"],
                    "reason": t["TargetHealth"].get("Reason", ""),
                    "description": t["TargetHealth"].get("Description", ""),
                }
                for t in unhealthy
            ],
        }
