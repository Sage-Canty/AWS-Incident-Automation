"""
src/reporters/incident.py
Combines ECS, ALB, CloudWatch into a structured triage report.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.checkers.alb import ALBChecker
from src.checkers.cloudwatch import CloudWatchChecker
from src.checkers.ecs import ECSChecker

logger = logging.getLogger(__name__)


class IncidentReporter:
    def __init__(self, env: str, region: str = "us-east-1"):
        self.env = env
        self.ecs = ECSChecker(env=env, region=region)
        self.alb = ALBChecker(env=env, region=region)
        self.cw = CloudWatchChecker(env=env, region=region)

    def triage(self, service: str, minutes: int = 15) -> dict[str, Any]:
        ecs_status  = self.ecs.check_service(service)
        alb_status  = self.alb.check_target_group(service)
        error_rate  = self.cw.get_error_rate(service=service, minutes=minutes)
        recent_errs = self.cw.get_recent_errors(service=service, minutes=minutes, limit=20)
        resources   = self.cw.get_ecs_cpu_memory(service=service, minutes=minutes)

        incidents = []
        if not ecs_status.get("healthy"):
            incidents.append(f"ECS: {ecs_status.get('running', 0)}/{ecs_status.get('desired', 0)} tasks running")
        if not alb_status.get("healthy"):
            incidents.append(f"ALB: {alb_status.get('unhealthy_count', 0)} unhealthy targets")
        if error_rate.get("above_threshold"):
            incidents.append(f"Error rate: {error_rate['error_rate'] * 100:.1f}%")

        return {
            "service": f"{self.env}-{service}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_minutes": minutes,
            "status": "incident" if incidents else "healthy",
            "incidents": incidents,
            "ecs": ecs_status,
            "alb": alb_status,
            "error_rate": error_rate,
            "resources": resources,
            "recent_errors": recent_errs[:10],
        }

    def print_report(self, report: dict[str, Any]) -> None:
        icon = "🔴 INCIDENT" if report["status"] == "incident" else "✅ HEALTHY"
        print(f"\n{'='*60}")
        print(f"  Triage: {report['service']} | {icon}")
        print(f"  Generated: {report['generated_at']}")
        print(f"{'='*60}\n")

        if report["incidents"]:
            print("⚠️  Active Issues:")
            for issue in report["incidents"]:
                print(f"   - {issue}")
            print()

        ecs = report["ecs"]
        print(f"{'✅' if ecs.get('healthy') else '❌'} ECS: {ecs.get('running','?')}/{ecs.get('desired','?')} tasks")
        if ecs.get("deployment_in_progress"):
            print("   ↳ Deployment in progress")
        for t in ecs.get("stopped_tasks", [])[:3]:
            print(f"   ↳ [{t.get('exit_code','?')}] {t.get('stopped_reason','')} — {t.get('stopped_at','')}")

        alb = report["alb"]
        print(f"{'✅' if alb.get('healthy') else '❌'} ALB: {alb.get('healthy_count','?')}/{alb.get('total_count','?')} targets")

        er = report["error_rate"]
        print(f"{'❌' if er.get('above_threshold') else '✅'} Error rate: {er.get('error_rate',0)*100:.2f}%")

        res = report["resources"]
        if res.get("cpu_max_pct") is not None:
            print(f"📊 CPU max: {res['cpu_max_pct']}%  Memory max: {res.get('memory_max_pct','?')}%")

        errors = report.get("recent_errors", [])
        if errors:
            print(f"\n📋 Recent errors ({len(errors)}):")
            for e in errors[:5]:
                print(f"   [{e['timestamp']}] {e['message'][:120]}")
        print()
