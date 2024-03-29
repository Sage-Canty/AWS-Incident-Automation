# aws-incident-automation

Python CLI for automated incident triage on AWS ECS. Surfaces ECS task status, ALB target health, CloudWatch error rates, and recent error logs in a single command.

Built to complement [Platform-Runbooks](https://github.com/Sage-Canty/Platform-Runbooks) — runbooks describe what to do, this automates the diagnostic steps.

---

## Commands

```bash
# Full triage for a service
python -m src.cli --env dev triage --service api

# Health check across all services
python -m src.cli --env staging health

# Recent error logs
python -m src.cli --env dev logs --service api --minutes 30

# JSON output for integration
python -m src.cli --env prod triage --service api --output json
```

---

## Example output

```
============================================================
  Triage: prod-api | 🔴 INCIDENT
============================================================

⚠️  Active Issues:
   - ECS: 0/2 tasks running
   - Error rate: 100.00%

❌ ECS: 0/2 tasks
   ↳ [1] Essential container exited — 2025-09-15T02:12:01+00:00
❌ ALB: 0/2 targets healthy
📊 CPU max: 0.0%  Memory max: 98.4%
```

---

## Development

```bash
make install
make test    # moto-mocked, no real AWS needed
make lint
```

---

## Runbook integration

| Checker | Runbook |
|---|---|
| ECS stopped task reasons | crash-loop.md |
| ALB target health | service-down.md |
| CloudWatch error rate | high-error-rate.md |

---

## Exit codes

- `0` — healthy
- `1` — incident detected

---

Makes `triage` usable as a deployment health gate — exit 1 blocks the pipeline if the service is in incident state.
