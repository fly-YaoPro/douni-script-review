#!/usr/bin/env python3
"""Deterministic private-market project metrics from JSON inputs.

The engine performs arithmetic only. It contains no industry benchmarks or
implicit red-flag thresholds; red flags are emitted solely from input rules.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


ARCHETYPES = {"saas", "hardware", "consumer", "services"}
OPERATORS = {
    "eq": lambda actual, expected: actual == expected,
    "ne": lambda actual, expected: actual != expected,
    "gt": lambda actual, expected: actual > expected,
    "gte": lambda actual, expected: actual >= expected,
    "lt": lambda actual, expected: actual < expected,
    "lte": lambda actual, expected: actual <= expected,
    "in": lambda actual, expected: actual in expected,
    "not_in": lambda actual, expected: actual not in expected,
}
MISSING = object()


class PrivateMarketEngineError(ValueError):
    """Raised when an input cannot be evaluated safely."""


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PrivateMarketEngineError(f"{field} must be a number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PrivateMarketEngineError(f"{field} must be finite")
    return parsed


def _number(
    data: Mapping[str, Any],
    path: str,
    *,
    non_negative: bool = True,
) -> float | None:
    value = _get(data, path)
    if value is MISSING or value is None:
        return None
    parsed = _finite_number(value, path)
    if non_negative and parsed < 0:
        raise PrivateMarketEngineError(f"{path} must be non-negative")
    return parsed


def _get(data: Mapping[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return MISSING
        current = current[part]
    return current


def _set(target: dict[str, Any], path: str, value: Any) -> None:
    current = target
    parts = path.split(".")
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise PrivateMarketEngineError(
                f"scenario override conflicts with non-object field: {path}"
            )
        current = child
    current[parts[-1]] = value


def _json_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _ratio(numerator: float | None, denominator: float | None) -> int | float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _json_number(numerator / denominator)


def _validate_root(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise PrivateMarketEngineError("JSON root must be an object")
    archetype = data.get("archetype")
    if archetype not in ARCHETYPES:
        raise PrivateMarketEngineError(
            "archetype must be one of: consumer, hardware, saas, services"
        )
    for section in (
        "valuation",
        "financing",
        "cash",
        "financials",
        "archetype_metrics",
    ):
        value = data.get(section)
        if value is not None and not isinstance(value, dict):
            raise PrivateMarketEngineError(f"{section} must be an object")
    scenarios = data.get("scenarios", [])
    if not isinstance(scenarios, list):
        raise PrivateMarketEngineError("scenarios must be a list")
    rules = data.get("red_flag_rules", [])
    if not isinstance(rules, list):
        raise PrivateMarketEngineError("red_flag_rules must be a list")
    return data


def _add_metric(
    metrics: dict[str, Any],
    unknowns: list[dict[str, Any]],
    name: str,
    value: Any,
    required_fields: Sequence[str],
    reason: str = "missing_required_fields",
) -> None:
    metrics[name] = value
    if value is None:
        unknowns.append(
            {
                "metric": name,
                "reason": reason,
                "required_fields": list(required_fields),
            }
        )


def _common_metrics(
    data: Mapping[str, Any],
    metrics: dict[str, Any],
    unknowns: list[dict[str, Any]],
) -> None:
    pre_money = _number(data, "valuation.pre_money")
    post_money = _number(data, "valuation.post_money")
    round_size = _number(data, "financing.round_size")
    ticket_size = _number(data, "financing.ticket_size")

    if pre_money is None and post_money is not None and round_size is not None:
        pre_money = post_money - round_size
        if pre_money < 0:
            raise PrivateMarketEngineError(
                "valuation.post_money cannot be less than financing.round_size"
            )
    if post_money is None and pre_money is not None and round_size is not None:
        post_money = pre_money + round_size

    _add_metric(
        metrics,
        unknowns,
        "pre_money",
        None if pre_money is None else _json_number(pre_money),
        ["valuation.pre_money or valuation.post_money + financing.round_size"],
    )
    _add_metric(
        metrics,
        unknowns,
        "post_money",
        None if post_money is None else _json_number(post_money),
        ["valuation.post_money or valuation.pre_money + financing.round_size"],
    )
    _add_metric(
        metrics,
        unknowns,
        "ticket_ownership",
        _ratio(ticket_size, post_money),
        ["financing.ticket_size", "post_money"],
    )

    current_cash = _number(data, "cash.current_cash")
    monthly_net_burn = _number(data, "cash.monthly_net_burn")
    post_financing_cash = (
        None
        if current_cash is None or round_size is None
        else current_cash + round_size
    )
    _add_metric(
        metrics,
        unknowns,
        "cash_runway_months",
        _ratio(current_cash, monthly_net_burn),
        ["cash.current_cash", "cash.monthly_net_burn"],
    )
    _add_metric(
        metrics,
        unknowns,
        "post_financing_cash",
        None
        if post_financing_cash is None
        else _json_number(post_financing_cash),
        ["cash.current_cash", "financing.round_size"],
    )
    _add_metric(
        metrics,
        unknowns,
        "post_financing_runway_months",
        _ratio(post_financing_cash, monthly_net_burn),
        [
            "cash.current_cash",
            "financing.round_size",
            "cash.monthly_net_burn",
        ],
    )

    revenue = _number(data, "financials.revenue")
    arr = _number(data, "financials.arr")
    for basis_name, basis_value in (("pre_money", pre_money), ("post_money", post_money)):
        _add_metric(
            metrics,
            unknowns,
            f"{basis_name}_revenue_multiple",
            _ratio(basis_value, revenue),
            [basis_name, "financials.revenue"],
        )
        _add_metric(
            metrics,
            unknowns,
            f"{basis_name}_arr_multiple",
            _ratio(basis_value, arr),
            [basis_name, "financials.arr"],
        )


def _saas_metrics(
    data: Mapping[str, Any],
    metrics: dict[str, Any],
    unknowns: list[dict[str, Any]],
) -> None:
    prefix = "archetype_metrics.saas"
    start = _number(data, f"{prefix}.starting_arr")
    expansion = _number(data, f"{prefix}.expansion_arr")
    contraction = _number(data, f"{prefix}.contraction_arr")
    churn = _number(data, f"{prefix}.churned_arr")
    nrr = (
        None
        if None in (start, expansion, contraction, churn) or start == 0
        else (start + expansion - contraction - churn) / start
    )
    grr = (
        None
        if None in (start, contraction, churn) or start == 0
        else (start - contraction - churn) / start
    )
    _add_metric(
        metrics,
        unknowns,
        "nrr",
        None if nrr is None else _json_number(nrr),
        [
            f"{prefix}.starting_arr",
            f"{prefix}.expansion_arr",
            f"{prefix}.contraction_arr",
            f"{prefix}.churned_arr",
        ],
    )
    _add_metric(
        metrics,
        unknowns,
        "grr",
        None if grr is None else _json_number(grr),
        [
            f"{prefix}.starting_arr",
            f"{prefix}.contraction_arr",
            f"{prefix}.churned_arr",
        ],
    )

    cac = _number(data, f"{prefix}.cac")
    new_customer_arr = _number(data, f"{prefix}.new_customer_arr")
    gross_margin = _number(data, f"{prefix}.gross_margin")
    payback = (
        None
        if None in (cac, new_customer_arr, gross_margin)
        or new_customer_arr == 0
        or gross_margin == 0
        else cac / (new_customer_arr * gross_margin / 12)
    )
    _add_metric(
        metrics,
        unknowns,
        "cac_payback_months",
        None if payback is None else _json_number(payback),
        [
            f"{prefix}.cac",
            f"{prefix}.new_customer_arr",
            f"{prefix}.gross_margin",
        ],
    )

    net_burn = _number(data, "financials.net_burn")
    net_new_arr = _number(data, "financials.net_new_arr", non_negative=False)
    burn_multiple = (
        None
        if net_burn is None or net_new_arr is None or net_new_arr <= 0
        else net_burn / net_new_arr
    )
    reason = (
        "net_new_arr_must_be_positive"
        if net_new_arr is not None and net_new_arr <= 0
        else "missing_required_fields"
    )
    _add_metric(
        metrics,
        unknowns,
        "burn_multiple",
        None if burn_multiple is None else _json_number(burn_multiple),
        ["financials.net_burn", "financials.net_new_arr (> 0)"],
        reason,
    )


def _hardware_metrics(
    data: Mapping[str, Any],
    metrics: dict[str, Any],
    unknowns: list[dict[str, Any]],
) -> None:
    prefix = "archetype_metrics.hardware"
    units = _number(data, f"{prefix}.units")
    asp = _number(data, f"{prefix}.asp")
    bom = _number(data, f"{prefix}.bom_cost_per_unit")
    warranty_rate = _number(data, f"{prefix}.warranty_rate")
    warranty_cost = _number(data, f"{prefix}.warranty_cost_per_claim")
    _add_metric(metrics, unknowns, "units", units, [f"{prefix}.units"])
    _add_metric(metrics, unknowns, "asp", asp, [f"{prefix}.asp"])
    _add_metric(
        metrics,
        unknowns,
        "implied_revenue",
        None if units is None or asp is None else _json_number(units * asp),
        [f"{prefix}.units", f"{prefix}.asp"],
    )
    _add_metric(metrics, unknowns, "bom_cost_per_unit", bom, [f"{prefix}.bom_cost_per_unit"])
    _add_metric(
        metrics,
        unknowns,
        "warranty_cost_per_unit",
        None
        if warranty_rate is None or warranty_cost is None
        else _json_number(warranty_rate * warranty_cost),
        [f"{prefix}.warranty_rate", f"{prefix}.warranty_cost_per_claim"],
    )


def _consumer_metrics(
    data: Mapping[str, Any],
    metrics: dict[str, Any],
    unknowns: list[dict[str, Any]],
) -> None:
    prefix = "archetype_metrics.consumer"
    for field in ("revenue", "gross_margin", "inventory"):
        value = _number(data, f"{prefix}.{field}")
        _add_metric(metrics, unknowns, field, value, [f"{prefix}.{field}"])
    revenue = _number(data, f"{prefix}.revenue")
    inventory = _number(data, f"{prefix}.inventory")
    _add_metric(
        metrics,
        unknowns,
        "inventory_to_revenue",
        _ratio(inventory, revenue),
        [f"{prefix}.inventory", f"{prefix}.revenue"],
    )


def _services_metrics(
    data: Mapping[str, Any],
    metrics: dict[str, Any],
    unknowns: list[dict[str, Any]],
) -> None:
    path = "archetype_metrics.services.utilization"
    utilization = _number(data, path)
    _add_metric(metrics, unknowns, "utilization", utilization, [path])


def _evaluate_red_flags(
    rules: Sequence[Any],
    data: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    context = {"input": data, "metrics": metrics}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise PrivateMarketEngineError(f"red_flag_rules[{index}] must be an object")
        field = rule.get("field")
        operator = rule.get("operator")
        if not isinstance(field, str) or operator not in OPERATORS:
            raise PrivateMarketEngineError(
                f"red_flag_rules[{index}] requires a field and supported operator"
            )
        expected = rule.get("value")
        actual = _get(context, field)
        matched = False
        if actual is not MISSING and actual is not None:
            try:
                matched = bool(OPERATORS[operator](actual, expected))
            except (TypeError, ValueError) as exc:
                raise PrivateMarketEngineError(
                    f"red_flag_rules[{index}] cannot compare field {field}"
                ) from exc
        if matched:
            flags.append(
                {
                    "rule_id": rule.get("id", f"rule_{index + 1}"),
                    "field": field,
                    "operator": operator,
                    "actual": actual,
                    "threshold": expected,
                    "message": rule.get("message"),
                }
            )
    return flags


def _calculate(data: Mapping[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    unknowns: list[dict[str, Any]] = []
    _common_metrics(data, metrics, unknowns)
    calculators = {
        "saas": _saas_metrics,
        "hardware": _hardware_metrics,
        "consumer": _consumer_metrics,
        "services": _services_metrics,
    }
    calculators[data["archetype"]](data, metrics, unknowns)
    return {
        "metrics": metrics,
        "unknowns": unknowns,
        "red_flags": _evaluate_red_flags(
            data.get("red_flag_rules", []), data, metrics
        ),
    }


def run(data: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate the base case and any explicit input scenarios."""
    validated = _validate_root(dict(data))
    base = _calculate(validated)
    scenario_results: list[dict[str, Any]] = []
    for index, scenario in enumerate(validated.get("scenarios", [])):
        if not isinstance(scenario, dict):
            raise PrivateMarketEngineError(f"scenarios[{index}] must be an object")
        name = scenario.get("name")
        overrides = scenario.get("overrides")
        if not isinstance(name, str) or not name:
            raise PrivateMarketEngineError(f"scenarios[{index}].name must be non-empty")
        if not isinstance(overrides, dict):
            raise PrivateMarketEngineError(
                f"scenarios[{index}].overrides must be an object"
            )
        scenario_input = deepcopy(validated)
        scenario_input["scenarios"] = []
        for path, value in overrides.items():
            if not isinstance(path, str) or not path:
                raise PrivateMarketEngineError(
                    f"scenarios[{index}] override keys must be dotted field paths"
                )
            _set(scenario_input, path, value)
        result = _calculate(scenario_input)
        scenario_results.append({"name": name, **result})

    return {
        "schema_version": "1.0",
        "archetype": validated["archetype"],
        "capabilities": {
            "common": [
                "pre_post_money",
                "ticket_ownership",
                "cash_runway",
                "revenue_arr_multiples",
                "input_defined_red_flags",
                "scenarios",
            ],
            "archetype": {
                "saas": ["nrr", "grr", "cac_payback", "burn_multiple"],
                "hardware": ["units", "asp", "bom", "warranty"],
                "consumer": ["revenue", "gross_margin", "inventory"],
                "services": ["utilization"],
            }[validated["archetype"]],
        },
        **base,
        "scenarios": scenario_results,
    }


def _load_input(path: str | None) -> dict[str, Any]:
    if path:
        with Path(path).open(encoding="utf-8") as handle:
            value = json.load(handle)
    else:
        value = json.load(sys.stdin)
    return _validate_root(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        help="input JSON path; reads JSON from stdin when omitted",
    )
    parser.add_argument("--output", help="output JSON path; defaults to stdout")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print output JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run(_load_input(args.input))
    rendered = json.dumps(
        result,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
