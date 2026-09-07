#!/usr/bin/env python3
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "scripts" / "wealth_planning_engine.py"
EXAMPLE = ROOT / "schemas" / "deterministic-tool.example.json"


def run(payload):
    import tempfile

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ENGINE), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return json.loads(proc.stdout)


def main():
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["liabilities"][0].update({"apr": 0.045, "prepayment_rule": "allowed"})
    payload["budget_categories"] = [
        {"category": "essential", "amount": 10000, "classification": "essential"},
        {"category": "goals", "amount": 5000, "classification": "goal"},
    ]
    payload["monthly_essential_expenses"] = 10000
    payload["emergency_months_target"] = 4
    payload["spending_periods"] = [
        {"period": "2026-01", "category": "food", "amount": 2000},
        {"period": "2026-02", "category": "food", "amount": 2300},
    ]
    payload["recurring_charges"] = [
        {"id": "software", "amount": 20, "periods_per_year": 12}
    ]
    first = run(payload)
    modules = first["household_modules"]
    assert modules["net_worth"]["value"] == 1580000
    assert modules["household_budgeting"]["unassigned"] == 9000
    assert modules["emergency_fund"]["target"] == 40000
    assert modules["debt_patterns"]["avalanche_order"] == ["mortgage"]
    assert modules["recurring_charge_review"]["items"][0]["usage_state"] == "unknown"

    changed = copy.deepcopy(payload)
    changed["monthly_income"] = 30000
    changed["emergency_months_target"] = 6
    changed["liabilities"][0]["apr"] = "unknown"
    second = run(changed)
    changed_modules = second["household_modules"]
    assert changed_modules["household_budgeting"]["unassigned"] == 15000
    assert changed_modules["emergency_fund"]["target"] == 60000
    assert changed_modules["debt_patterns"]["avalanche_order"] is None
    assert second["capability_gates"]["debt_avalanche"]["available"] is False
    print("PASS household modules perturbation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
