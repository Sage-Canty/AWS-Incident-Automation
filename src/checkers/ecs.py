"""
src/checkers/ecs.py
ECS service health checker. Returns running/desired counts,
stopped task reasons, and active deployment status.
"""

import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})


class ECSChecker:
    def __init__(self, env: str, region: str = "us-east-1"):
        self.env = env
        self.region = region
        self.cluster = f"{env}-cluster"
        self.ecs = boto3.client("ecs", region_name=region, config=BOTO_CONFIG)

    def check_service(self, service_name: str) -> dict[str, Any]:
        full_name = f"{self.env}-{service_name}"
        try:
            resp = self.ecs.describe_services(cluster=self.cluster, services=[full_name])
        except ClientError as e:
            logger.error("Failed to describe ECS service %s: %s", full_name, e)
            return {"name": full_name, "error": str(e), "healthy": False}

        if not resp["services"]:
            return {"name": full_name, "error": "service not found", "healthy": False}

        svc = resp["services"][0]
        running = svc["runningCount"]
        desired = svc["desiredCount"]
        deployments = svc.get("deployments", [])
        active_deploy = next(
            (d for d in deployments if d["status"] == "PRIMARY" and d["rolloutState"] == "IN_PROGRESS"),
            None,
        )
        stopped_tasks = self._get_stopped_task_reasons(full_name)

        return {
            "name": full_name,
            "running": running,
            "desired": desired,
            "healthy": running == desired and desired > 0,
            "deployment_in_progress": active_deploy is not None,
            "stopped_tasks": stopped_tasks,
        }

    def check_all_services(self) -> list[dict[str, Any]]:
        try:
            paginator = self.ecs.get_paginator("list_services")
            arns = []
            for page in paginator.paginate(cluster=self.cluster):
                arns.extend(page["serviceArns"])
        except ClientError as e:
            logger.error("Failed to list ECS services: %s", e)
            return []

        results = []
        for i in range(0, len(arns), 10):
            batch = arns[i:i + 10]
            try:
                resp = self.ecs.describe_services(cluster=self.cluster, services=batch)
                for svc in resp["services"]:
                    running = svc["runningCount"]
                    desired = svc["desiredCount"]
                    results.append({
                        "name": svc["serviceName"],
                        "running": running,
                        "desired": desired,
                        "healthy": running == desired and desired > 0,
                    })
            except ClientError as e:
                logger.error("describe_services batch failed: %s", e)
        return results

    def _get_stopped_task_reasons(self, full_name: str, limit: int = 5) -> list[dict]:
        try:
            resp = self.ecs.list_tasks(
                cluster=self.cluster, serviceName=full_name, desiredStatus="STOPPED"
            )
            arns = resp.get("taskArns", [])[:limit]
            if not arns:
                return []
            tasks = self.ecs.describe_tasks(cluster=self.cluster, tasks=arns)
            results = []
            for task in tasks.get("tasks", []):
                container = task.get("containers", [{}])[0]
                stopped_at = task.get("stoppedAt")
                results.append({
                    "task_arn": task["taskArn"].split("/")[-1],
                    "stopped_reason": task.get("stoppedReason", "unknown"),
                    "exit_code": container.get("exitCode"),
                    "stopped_at": stopped_at.isoformat() if stopped_at else None,
                })
            return results
        except ClientError as e:
            logger.warning("Could not fetch stopped tasks: %s", e)
            return []

    def get_stopped_task_exit_codes(self, service_name: str, limit: int = 5) -> list[dict]:
        return self._get_stopped_task_reasons(f"{self.env}-{service_name}", limit=limit)
