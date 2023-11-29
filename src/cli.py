#!/usr/bin/env python3
"""
aws-incident-automation — CLI for automated ECS incident triage.

Usage:
    python -m src.cli --env dev triage --service api
    python -m src.cli --env staging health
    python -m src.cli --env dev logs --service api --minutes 30
    python -m src.cli --env prod triage --service api --output json
"""

import argparse
import json
import sys

from src.checkers.ecs import ECSChecker
from src.checkers.alb import ALBChecker
from src.checkers.cloudwatch import CloudWatchChecker
from src.reporters.incident import IncidentReporter


def cmd_triage(args):
    reporter = IncidentReporter(env=args.env, region=args.region)
    report = reporter.triage(service=args.service, minutes=args.minutes)
    if args.output == "json":
        print(json.dumps(report, indent=2, default=str))
    else:
        reporter.print_report(report)
    if report.get("status") == "incident":
        sys.exit(1)


def cmd_health(args):
    ecs = ECSChecker(env=args.env, region=args.region)
    alb = ALBChecker(env=args.env, region=args.region)
    result = {
        "env": args.env,
        "ecs": ecs.check_all_services(),
        "alb": alb.check_target_group if hasattr(alb, 'check_all_target_groups') else [],
    }
    if args.output == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n=== Health: {args.env} ===\n")
        for svc in result["ecs"]:
            icon = "✅" if svc["healthy"] else "❌"
            print(f"  {icon} {svc['name']}: {svc['running']}/{svc['desired']} tasks")


def cmd_logs(args):
    cw = CloudWatchChecker(env=args.env, region=args.region)
    logs = cw.get_recent_errors(service=args.service, minutes=args.minutes, limit=args.limit)
    if args.output == "json":
        print(json.dumps(logs, indent=2, default=str))
    else:
        for entry in logs:
            print(f"[{entry['timestamp']}] {entry['message']}")


def main():
    parser = argparse.ArgumentParser(description="AWS incident triage automation")
    parser.add_argument("--env",    default="dev", choices=["dev", "staging", "prod"])
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", default="text", choices=["text", "json"])
    subparsers = parser.add_subparsers(dest="command", required=True)

    triage = subparsers.add_parser("triage")
    triage.add_argument("--service", required=True)
    triage.add_argument("--minutes", type=int, default=15)
    triage.set_defaults(func=cmd_triage)

    health = subparsers.add_parser("health")
    health.set_defaults(func=cmd_health)

    logs = subparsers.add_parser("logs")
    logs.add_argument("--service", required=True)
    logs.add_argument("--minutes", type=int, default=15)
    logs.add_argument("--limit",   type=int, default=50)
    logs.set_defaults(func=cmd_logs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
