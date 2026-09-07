#!/usr/bin/env python3
"""Deterministic, currency-agnostic wealth-planning calculations."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


class InputError(ValueError):
    """Raised when an input cannot support deterministic calculation."""


UNKNOWN = object()


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{path} must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{path} must be a list")
    return value


def _decimal(value: Any, path: str, *, minimum: Decimal | None = None) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise InputError(f"{path} must be a finite number")
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise InputError(f"{path} must be a finite number") from exc
    if not number.is_finite():
        raise InputError(f"{path} must be a finite number")
    if minimum is not None and number < minimum:
        raise InputError(f"{path} must be at least {minimum}")
    return number


def _number(value: Decimal) -> int | float:
    integral = value.to_integral_value()
    return int(integral) if value == integral else float(value)


def _income(value: Any, path: str) -> Decimal | object:
    if value is None or value == "unknown":
        return UNKNOWN
    return _decimal(value, path, minimum=Decimal(0))


def _liquidity_ratio(value: Any, path: str) -> Decimal:
    if value is True or value == "liquid":
        return Decimal(1)
    if value is False or value == "illiquid":
        return Decimal(0)
    ratio = _decimal(value, path, minimum=Decimal(0))
    if ratio > 1:
        raise InputError(f"{path} must be between 0 and 1")
    return ratio


def _sum_amounts(value: Any, path: str) -> Decimal:
    if isinstance(value, list):
        total = Decimal(0)
        for index, item in enumerate(value):
            row = _object(item, f"{path}[{index}]")
            if "amount" not in row:
                raise InputError(f"{path}[{index}].amount is required")
            total += _decimal(
                row["amount"], f"{path}[{index}].amount", minimum=Decimal(0)
            )
        return total
    return _decimal(value, path, minimum=Decimal(0))


def _required(data: Mapping[str, Any], field: str) -> Any:
    if field not in data:
        raise InputError(f"{field} is required")
    return data[field]


def _available_assets(assets_value: Any) -> tuple[Decimal, list[dict[str, Any]]]:
    assets = _list(assets_value, "assets")
    total = Decimal(0)
    ledger: list[dict[str, Any]] = []
    for index, item in enumerate(assets):
        path = f"assets[{index}]"
        asset = _object(item, path)
        value = _decimal(_required(asset, "value"), f"{path}.value", minimum=Decimal(0))
        if "liquidity" not in asset:
            raise InputError(f"{path}.liquidity is required")
        ratio = _liquidity_ratio(asset["liquidity"], f"{path}.liquidity")
        restricted = asset.get("restricted")
        if not isinstance(restricted, bool):
            raise InputError(f"{path}.restricted must be a boolean")
        available = Decimal(0) if restricted else value * ratio
        total += available
        ledger.append(
            {
                "id": asset.get("id", asset.get("name", str(index))),
                "value": _number(value),
                "liquidity_ratio": _number(ratio),
                "restricted": restricted,
                "included": not restricted and ratio > 0,
                "available_value": _number(available),
            }
        )
    return total, ledger


def _liabilities(value: Any) -> tuple[Decimal, Decimal, list[dict[str, Any]]]:
    liabilities = _list(value, "liabilities")
    balance_total = Decimal(0)
    payment_total = Decimal(0)
    ledger: list[dict[str, Any]] = []
    for index, item in enumerate(liabilities):
        path = f"liabilities[{index}]"
        liability = _object(item, path)
        balance = _decimal(
            _required(liability, "balance"),
            f"{path}.balance",
            minimum=Decimal(0),
        )
        payment = _decimal(
            _required(liability, "monthly_payment"),
            f"{path}.monthly_payment",
            minimum=Decimal(0),
        )
        balance_total += balance
        payment_total += payment
        ledger.append(
            {
                "id": liability.get("id", liability.get("name", str(index))),
                "balance": _number(balance),
                "monthly_payment": _number(payment),
                "apr": (
                    None
                    if liability.get("apr") in {None, "unknown"}
                    else _number(
                        _decimal(
                            liability.get("apr"),
                            f"{path}.apr",
                            minimum=Decimal(0),
                        )
                    )
                ),
                "prepayment_rule": liability.get("prepayment_rule", "unknown"),
            }
        )
    return balance_total, payment_total, ledger


def _runway(
    liquid_assets: Decimal,
    one_time_needs: Decimal,
    income: Decimal | object,
    outflow: Decimal,
) -> dict[str, Any]:
    starting = max(liquid_assets - one_time_needs, Decimal(0))
    result: dict[str, Any] = {
        "formula": "max(L - N, 0) / (O - I)",
        "variables": {
            "L": "available unrestricted liquid assets",
            "N": "one-time needs",
            "O": "monthly expenses plus liability monthly payments",
            "I": "monthly income",
        },
        "domain": "I, O, L, and N are known; O > I; denominator O - I > 0",
        "starting_assets_after_one_time_needs": _number(starting),
    }
    if income is UNKNOWN:
        result.update(
            {
                "status": "formula_only_income_unknown",
                "monthly_burn": None,
                "months": None,
                "substitution": f"max({_number(liquid_assets)} - "
                f"{_number(one_time_needs)}, 0) / "
                f"({_number(outflow)} - I)",
            }
        )
    elif income >= outflow:
        result.update(
            {
                "status": "no_finite_runway_not_depleting",
                "monthly_burn": 0,
                "months": None,
                "substitution": None,
            }
        )
    else:
        burn = outflow - income
        result.update(
            {
                "status": "finite",
                "monthly_burn": _number(burn),
                "months": float(starting / burn),
                "substitution": None,
            }
        )
    return result


def _goals(value: Any) -> list[dict[str, Any]]:
    goals = _list(value, "goals")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(goals):
        path = f"goals[{index}]"
        goal = _object(item, path)
        target = _decimal(
            _required(goal, "target"), f"{path}.target", minimum=Decimal(0)
        )
        if target == 0:
            raise InputError(f"{path}.target must be greater than 0")
        funding = _decimal(
            _required(goal, "current_funding"),
            f"{path}.current_funding",
            minimum=Decimal(0),
        )
        horizon = _required(goal, "horizon_months")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
            raise InputError(f"{path}.horizon_months must be a positive integer")
        ratio = funding / target
        result.append(
            {
                "id": goal.get("id", goal.get("name", str(index))),
                "target": _number(target),
                "current_funding": _number(funding),
                "horizon_months": horizon,
                "coverage_ratio": float(ratio),
                "coverage_percent": float(ratio * 100),
                "definition": "current_funding / target",
                "interpretation": "funding coverage, not a probability of success",
            }
        )
    return result


def _household_modules(
    data: Mapping[str, Any],
    *,
    total_assets: Decimal,
    liability_balance: Decimal,
    liability_ledger: list[dict[str, Any]],
    income: Decimal | object,
    expenses: Decimal,
    liquid_assets: Decimal,
) -> dict[str, Any]:
    net_worth = {
        "assets": _number(total_assets),
        "liabilities": _number(liability_balance),
        "value": _number(total_assets - liability_balance),
        "formula": "sum(asset values) - sum(liability balances)",
        "valuation_boundary": "values are user supplied; no market value inferred",
    }

    budget_rows = data.get("budget_categories")
    budgeting: dict[str, Any]
    if isinstance(budget_rows, list):
        assigned = Decimal(0)
        rows = []
        for index, row in enumerate(budget_rows):
            item = _object(row, f"budget_categories[{index}]")
            amount = _decimal(
                _required(item, "amount"),
                f"budget_categories[{index}].amount",
                minimum=Decimal(0),
            )
            assigned += amount
            rows.append(
                {
                    "category": item.get("category", str(index)),
                    "amount": _number(amount),
                    "classification": item.get("classification", "unknown"),
                }
            )
        budgeting = {
            "status": "ready" if income is not UNKNOWN else "income_unknown",
            "assigned": _number(assigned),
            "unassigned": None if income is UNKNOWN else _number(income - assigned),
            "formula": "monthly_income - sum(user assigned categories)",
            "categories": rows,
            "rule": "no allocation ratio inferred",
        }
    else:
        budgeting = {"status": "not_requested_or_missing", "categories": []}

    essential = data.get("monthly_essential_expenses")
    target_months = data.get("emergency_months_target")
    if essential is None or essential == "unknown" or target_months is None or target_months == "unknown":
        emergency = {
            "status": "formula_only",
            "target": None,
            "formula": "monthly_essential_expenses * user supplied target months",
        }
    else:
        essential_amount = _decimal(
            essential, "monthly_essential_expenses", minimum=Decimal(0)
        )
        months = _decimal(
            target_months, "emergency_months_target", minimum=Decimal(0)
        )
        target = essential_amount * months
        emergency = {
            "status": "ready",
            "target": _number(target),
            "current_liquid_assets": _number(liquid_assets),
            "gap": _number(max(target - liquid_assets, Decimal(0))),
            "formula": "monthly_essential_expenses * user supplied target months",
        }

    all_apr_known = bool(liability_ledger) and all(
        row["apr"] is not None for row in liability_ledger
    )
    avalanche = sorted(
        liability_ledger,
        key=lambda row: (
            row["apr"] is None,
            -(row["apr"] or 0),
            row["balance"],
        ),
    )
    snowball = sorted(liability_ledger, key=lambda row: row["balance"])
    debt = {
        "status": "ready" if all_apr_known else "partial_apr_unknown",
        "avalanche_order": [row["id"] for row in avalanche] if all_apr_known else None,
        "snowball_order": [row["id"] for row in snowball],
        "comparison_boundary": "orders are patterns, not a recommendation; prepayment rules remain binding",
    }

    spending_rows = data.get("spending_periods")
    spending_review: dict[str, Any] = {"status": "not_requested_or_missing"}
    if isinstance(spending_rows, list) and spending_rows:
        category_periods: dict[str, list[Decimal]] = {}
        for index, row in enumerate(spending_rows):
            item = _object(row, f"spending_periods[{index}]")
            category = str(_required(item, "category"))
            amount = _decimal(
                _required(item, "amount"),
                f"spending_periods[{index}].amount",
                minimum=Decimal(0),
            )
            category_periods.setdefault(category, []).append(amount)
        spending_review = {
            "status": "ready",
            "categories": [
                {
                    "category": category,
                    "observations": [_number(value) for value in values],
                    "change_first_to_last": (
                        _number(values[-1] - values[0]) if len(values) >= 2 else None
                    ),
                    "explanation_state": "unknown",
                }
                for category, values in sorted(category_periods.items())
            ],
            "threshold": data.get("spending_change_threshold"),
            "threshold_source": (
                "user" if data.get("spending_change_threshold") is not None else None
            ),
        }

    subscriptions = []
    for index, row in enumerate(data.get("recurring_charges") or []):
        item = _object(row, f"recurring_charges[{index}]")
        amount = _decimal(
            _required(item, "amount"),
            f"recurring_charges[{index}].amount",
            minimum=Decimal(0),
        )
        periods = _decimal(
            _required(item, "periods_per_year"),
            f"recurring_charges[{index}].periods_per_year",
            minimum=Decimal(0),
        )
        subscriptions.append(
            {
                "id": item.get("id", str(index)),
                "annualized_cost": _number(amount * periods),
                "usage_state": item.get("usage_state", "unknown"),
                "action": "review_only",
            }
        )

    return {
        "net_worth": net_worth,
        "household_budgeting": budgeting,
        "emergency_fund": emergency,
        "debt_patterns": debt,
        "spending_review": spending_review,
        "recurring_charge_review": {
            "items": subscriptions,
            "no_auto_cancel": True,
        },
    }


def _scenario_results(
    value: Any,
    *,
    base_income: Decimal | object,
    base_expenses: Decimal,
    liability_payments: Decimal,
    base_needs: Decimal,
    base_liquid_assets: Decimal,
) -> list[dict[str, Any]]:
    scenarios = _list(value, "scenarios")
    results: list[dict[str, Any]] = []
    for index, item in enumerate(scenarios):
        path = f"scenarios[{index}]"
        scenario = _object(item, path)
        scenario_id = scenario.get("id", scenario.get("name"))
        if not isinstance(scenario_id, str) or not scenario_id:
            raise InputError(f"{path}.id or {path}.name is required")

        income = (
            _income(scenario["monthly_income"], f"{path}.monthly_income")
            if "monthly_income" in scenario
            else base_income
        )
        if "monthly_income_delta" in scenario:
            if income is UNKNOWN:
                raise InputError(
                    f"{path}.monthly_income_delta cannot be used with unknown income"
                )
            income += _decimal(scenario["monthly_income_delta"], f"{path}.monthly_income_delta")

        expenses = (
            _decimal(
                scenario["monthly_expenses"],
                f"{path}.monthly_expenses",
                minimum=Decimal(0),
            )
            if "monthly_expenses" in scenario
            else base_expenses
        )
        if "monthly_expenses_delta" in scenario:
            expenses += _decimal(
                scenario["monthly_expenses_delta"], f"{path}.monthly_expenses_delta"
            )
        if expenses < 0:
            raise InputError(f"{path} monthly expenses cannot be negative")

        needs = (
            _sum_amounts(scenario["one_time_needs"], f"{path}.one_time_needs")
            if "one_time_needs" in scenario
            else base_needs
        )
        if "one_time_needs_delta" in scenario:
            needs += _decimal(
                scenario["one_time_needs_delta"], f"{path}.one_time_needs_delta"
            )
        if needs < 0:
            raise InputError(f"{path} one-time needs cannot be negative")

        liquid_assets = base_liquid_assets
        if "liquid_assets_delta" in scenario:
            liquid_assets += _decimal(
                scenario["liquid_assets_delta"], f"{path}.liquid_assets_delta"
            )
        if liquid_assets < 0:
            raise InputError(f"{path} available liquid assets cannot be negative")

        outflow = expenses + liability_payments
        net = None if income is UNKNOWN else _number(income - outflow)
        results.append(
            {
                "id": scenario_id,
                "available_liquid_assets": _number(liquid_assets),
                "monthly_income": None if income is UNKNOWN else _number(income),
                "monthly_expenses": _number(expenses),
                "liability_monthly_payments": _number(liability_payments),
                "monthly_outflow": _number(outflow),
                "net_monthly_cash_flow": net,
                "one_time_needs": _number(needs),
                "runway": _runway(liquid_assets, needs, income, outflow),
            }
        )
    return results


def evaluate(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one input object and return a deterministic planning ledger."""
    if not isinstance(data, dict):
        raise InputError("JSON root must be an object")
    currency = _required(data, "currency")
    if not isinstance(currency, str) or not currency.strip():
        raise InputError("currency must be a non-empty string")

    liquid_assets, asset_ledger = _available_assets(_required(data, "assets"))
    total_assets = sum(
        (_decimal(row["value"], "asset_ledger.value", minimum=Decimal(0)) for row in asset_ledger),
        Decimal(0),
    )
    liability_balance, liability_payments, liability_ledger = _liabilities(
        _required(data, "liabilities")
    )
    income = _income(_required(data, "monthly_income"), "monthly_income")
    expenses = _decimal(
        _required(data, "monthly_expenses"),
        "monthly_expenses",
        minimum=Decimal(0),
    )
    needs = _sum_amounts(_required(data, "one_time_needs"), "one_time_needs")
    outflow = expenses + liability_payments
    net = None if income is UNKNOWN else _number(income - outflow)
    goal_results = _goals(_required(data, "goals"))
    scenarios = _scenario_results(
        _required(data, "scenarios"),
        base_income=income,
        base_expenses=expenses,
        liability_payments=liability_payments,
        base_needs=needs,
        base_liquid_assets=liquid_assets,
    )
    household_modules = _household_modules(
        data,
        total_assets=total_assets,
        liability_balance=liability_balance,
        liability_ledger=liability_ledger,
        income=income,
        expenses=expenses,
        liquid_assets=liquid_assets,
    )

    unknowns: list[dict[str, str]] = []
    if income is UNKNOWN:
        unknowns.append(
            {
                "field": "monthly_income",
                "impact": "net cash flow is unknown and runway remains a formula",
            }
        )
    for scenario in scenarios:
        if scenario["monthly_income"] is None:
            unknowns.append(
                {
                    "field": f"scenarios.{scenario['id']}.monthly_income",
                    "impact": "scenario net cash flow is unknown and runway remains a formula",
                }
            )

    return {
        "schema_version": "1.0",
        "currency": currency,
        "capability_gates": {
            "status": "partial" if unknowns else "ready",
            "available_liquidity": {"available": True},
            "monthly_cash_flow": {
                "available": income is not UNKNOWN,
                "reason": None if income is not UNKNOWN else "monthly_income is unknown",
            },
            "finite_runway": {
                "available": income is not UNKNOWN and outflow > income,
                "reason": (
                    "monthly_income is unknown"
                    if income is UNKNOWN
                    else "monthly cash flow is not depleting"
                    if income >= outflow
                    else None
                ),
            },
            "goal_coverage": {"available": True},
            "return_projection": {
                "available": False,
                "reason": "no return assumption was supplied or inferred",
            },
            "emergency_fund_target": {
                "available": household_modules["emergency_fund"]["status"] == "ready",
                "reason": (
                    None
                    if household_modules["emergency_fund"]["status"] == "ready"
                    else "essential expenses or user target months are missing"
                ),
            },
            "household_budgeting": {
                "available": household_modules["household_budgeting"]["status"] == "ready",
                "reason": (
                    None
                    if household_modules["household_budgeting"]["status"] == "ready"
                    else "budget categories or monthly income are missing"
                ),
            },
            "debt_avalanche": {
                "available": household_modules["debt_patterns"]["status"] == "ready",
                "reason": (
                    None
                    if household_modules["debt_patterns"]["status"] == "ready"
                    else "APR is missing for one or more liabilities"
                ),
            },
        },
        "available_liquid_assets": {
            "value": _number(liquid_assets),
            "formula": "sum(value * liquidity_ratio) for unrestricted assets",
            "asset_ledger": asset_ledger,
        },
        "liabilities": {
            "balance": _number(liability_balance),
            "monthly_payments": _number(liability_payments),
            "ledger": liability_ledger,
        },
        "monthly_cash_flow": {
            "income": None if income is UNKNOWN else _number(income),
            "expenses": _number(expenses),
            "liability_monthly_payments": _number(liability_payments),
            "outflow": _number(outflow),
            "net": net,
            "net_formula": "I - O",
        },
        "one_time_needs": _number(needs),
        "runway": _runway(liquid_assets, needs, income, outflow),
        "goal_coverage": goal_results,
        "household_modules": household_modules,
        "scenarios": scenarios,
        "unknowns": unknowns,
    }


def run_from_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    return evaluate(data)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic, currency-agnostic wealth planning."
    )
    parser.add_argument("input", type=Path, help="single input JSON file")
    parser.add_argument("-o", "--output", type=Path, help="output JSON path")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_from_file(args.input)
    except (InputError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"wealth_planning_engine: {exc}") from exc
    rendered = json.dumps(
        result,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
        allow_nan=False,
    ) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
