#!/usr/bin/env python3
"""Executable six-state transition and side-effect permission gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATES = {
    "ready",
    "degraded",
    "intake_required",
    "confirmation_required",
    "routed",
    "stopped",
}
TRANSITIONS = {
    "intake_required": {"intake_required", "degraded", "ready", "routed", "stopped"},
    "degraded": {"degraded", "ready", "confirmation_required", "routed", "stopped"},
    "ready": {"ready", "degraded", "confirmation_required", "routed", "stopped"},
    "confirmation_required": {"confirmation_required", "ready", "stopped"},
    "routed": {"routed"},
    "stopped": {"stopped"},
}
SIDE_EFFECTS = {
    "transfer",
    "repay",
    "open_account",
    "purchase",
    "external_send",
    "write_record",
}


def gate(payload):
    current = payload.get("current_state")
    requested = payload.get("requested_state")
    if current not in STATES or requested not in STATES:
        return {"allowed": False, "reason": "invalid_state"}
    if requested not in TRANSITIONS[current]:
        return {
            "allowed": False,
            "reason": "invalid_transition",
            "current_state": current,
            "requested_state": requested,
        }

    action = payload.get("action", "read")
    if action not in SIDE_EFFECTS:
        return {
            "allowed": True,
            "transition": f"{current}->{requested}",
            "permission_gate": "not_required",
        }

    checks = {
        "preview": bool(payload.get("preview")),
        "target": bool(payload.get("target")),
        "scope": bool(payload.get("scope")),
        "identity_verified": payload.get("identity_verified") is True,
        "permission_verified": payload.get("permission_verified") is True,
        "second_confirmation": payload.get("second_confirmation") is True,
        "audit_idempotency_key": bool(
            (payload.get("audit") or {}).get("idempotency_key")
        ),
        "audit_timestamp": bool((payload.get("audit") or {}).get("timestamp")),
        "result_verification_plan": bool(
            (payload.get("audit") or {}).get("result_verification_plan")
        ),
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "allowed": not missing,
        "transition": f"{current}->{requested}",
        "permission_gate": "passed" if not missing else "blocked",
        "checks": checks,
        "missing": missing,
        "execution_claim": "not_executed" if missing else "authorized_for_host_execution",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    result = gate(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
