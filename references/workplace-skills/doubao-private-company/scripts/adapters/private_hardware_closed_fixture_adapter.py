#!/usr/bin/env python3
"""Calculate batch unit economics and cash runway from private-market fixtures.

The implementation intentionally derives every result from the supplied records.
Unknown warranty assumptions and undated collections remain symbolic.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FILES = {
    "orders": "orders.csv",
    "invoices": "invoices_and_receipts.csv",
    "bom_versions": "bom_versions.csv",
    "batch_bom_evidence": "batch_bom_evidence.csv",
    "manufacturing_overhead": "manufacturing_overhead.csv",
    "cash_position": "cash_position.json",
    "cash_budget": "cash_budget.csv",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _decimal(value: Any, field: str) -> Decimal:
    if value is None or str(value).strip() == "":
        raise ValueError(f"missing numeric field: {field}")
    try:
        return Decimal(str(value).strip())
    except Exception as exc:
        raise ValueError(f"invalid numeric field {field}: {value!r}") from exc


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value).strip())


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _month(value: str) -> str:
    return date.fromisoformat(value).strftime("%Y-%m")


def _variable_suffix(batch_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]+", "", batch_id)
    if not suffix:
        raise ValueError(f"batch_id cannot form a variable name: {batch_id!r}")
    return suffix


def load_inputs(input_dir: str | Path) -> dict[str, Any]:
    """Load the seven required fixture inputs from *input_dir*."""
    root = Path(input_dir)
    paths = {name: root / filename for name, filename in REQUIRED_FILES.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing required input files: " + ", ".join(missing))
    return {
        name: (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix == ".json"
            else _read_csv(path)
        )
        for name, path in paths.items()
    }


def _select_bom_evidence(
    evidence_rows: Iterable[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    by_batch: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        by_batch[row["batch_id"]].append(row)

    selected: dict[str, dict[str, Any]] = {}
    for batch_id, rows in by_batch.items():
        strongest = max(_decimal(row["evidence_strength"], "evidence_strength") for row in rows)
        winners = [
            row
            for row in rows
            if _decimal(row["evidence_strength"], "evidence_strength") == strongest
        ]
        winning_versions = {row["bom_version"] for row in winners}
        if len(winning_versions) != 1:
            raise ValueError(
                f"ambiguous strongest BOM evidence for {batch_id}: "
                f"{sorted(winning_versions)}"
            )
        winner = max(
            winners,
            key=lambda row: (row.get("evidence_date", ""), row.get("evidence_id", "")),
        )
        selected[batch_id] = {
            "winner": winner,
            "conflicts": [
                row for row in rows if row["bom_version"] != winner["bom_version"]
            ],
        }
    return selected


def calculate_unit_economics(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate contribution before warranty and preserve missing warranty variables."""
    orders = [
        row
        for row in inputs["orders"]
        if row.get("revenue_type") == "batch_hardware"
        and row.get("record_status", "signed") == "signed"
    ]
    bom_by_version = {row["bom_version"]: row for row in inputs["bom_versions"]}
    overhead_by_batch = {
        row["batch_id"]: row for row in inputs["manufacturing_overhead"]
    }
    evidence_by_batch = _select_bom_evidence(inputs["batch_bom_evidence"])

    result: dict[str, Any] = {}
    for order in orders:
        batch_id = order["batch_id"]
        if batch_id not in overhead_by_batch:
            raise ValueError(f"missing manufacturing overhead for batch {batch_id}")
        if batch_id not in evidence_by_batch:
            raise ValueError(f"missing BOM evidence for batch {batch_id}")

        overhead = overhead_by_batch[batch_id]
        evidence = evidence_by_batch[batch_id]
        selected_version = evidence["winner"]["bom_version"]
        planned_version = order.get("planned_bom_version", "")
        if selected_version not in bom_by_version:
            raise ValueError(f"unknown selected BOM version: {selected_version}")
        if planned_version not in bom_by_version:
            raise ValueError(f"unknown planned BOM version: {planned_version}")

        selected_bom = bom_by_version[selected_version]
        planned_bom = bom_by_version[planned_version]
        if selected_bom.get("approval_status") != "approved":
            raise ValueError(f"selected BOM is not approved: {selected_version}")
        if selected_bom.get("sku") != order.get("sku"):
            raise ValueError(
                f"selected BOM {selected_version} does not match order SKU {order.get('sku')}"
            )

        quantity = _decimal(order["quantity"], "quantity")
        if quantity <= 0:
            raise ValueError(f"quantity must be positive for batch {batch_id}")
        allocation_units = _decimal(
            overhead["units_in_allocation_base"], "units_in_allocation_base"
        )
        if allocation_units <= 0:
            raise ValueError(f"allocation units must be positive for batch {batch_id}")

        unit_price = _decimal(order["unit_price_cny"], "unit_price_cny")
        assembly = _decimal(
            overhead["contract_assembly_per_unit_cny"],
            "contract_assembly_per_unit_cny",
        )
        planned_material = _decimal(
            planned_bom["total_material_cost_per_unit_cny"],
            "total_material_cost_per_unit_cny",
        )
        material = _decimal(
            selected_bom["total_material_cost_per_unit_cny"],
            "total_material_cost_per_unit_cny",
        )
        logistics = _decimal(
            overhead["logistics_per_unit_cny"], "logistics_per_unit_cny"
        )
        installation = _decimal(
            overhead["installation_per_unit_cny"], "installation_per_unit_cny"
        )
        rebate_rate = _decimal(
            overhead.get("channel_rebate_rate", order.get("channel_rebate_rate")),
            "channel_rebate_rate",
        )
        after_sales = _decimal(
            overhead["after_sales_cost_incurred_per_unit_cny"],
            "after_sales_cost_incurred_per_unit_cny",
        )
        fixed_pool = _decimal(
            overhead["fixed_manufacturing_overhead_pool_cny"],
            "fixed_manufacturing_overhead_pool_cny",
        )
        allocated_fixed = fixed_pool / allocation_units
        rebate = unit_price * rebate_rate

        management_gp = unit_price - planned_material - assembly
        known_contribution = (
            unit_price
            - material
            - assembly
            - logistics
            - installation
            - rebate
            - after_sales
            - allocated_fixed
        )
        known_batch_contribution = known_contribution * quantity
        warranty_rate = _optional_decimal(overhead.get("warranty_claim_rate"))
        warranty_cost = _optional_decimal(
            overhead.get("warranty_cash_cost_per_claim_cny")
        )
        suffix = _variable_suffix(batch_id)

        bridge = [
            {
                "item": (
                    f"replace_planned_{planned_version}_with_actual_{selected_version}"
                    if planned_version != selected_version
                    else "BOM_mapping_adjustment"
                ),
                "impact_on_contribution_cny": _json_number(
                    planned_material - material
                ),
            },
            {"item": "logistics", "impact_on_contribution_cny": _json_number(-logistics)},
            {
                "item": "installation",
                "impact_on_contribution_cny": _json_number(-installation),
            },
            {
                "item": "channel_rebate",
                "impact_on_contribution_cny": _json_number(-rebate),
            },
            {
                "item": "incurred_after_sales",
                "impact_on_contribution_cny": _json_number(-after_sales),
            },
            {
                "item": "allocated_fixed_manufacturing_overhead",
                "impact_on_contribution_cny": _json_number(-allocated_fixed),
            },
        ]

        row: dict[str, Any] = {
            "selected_bom": selected_version,
            "selected_material_cost_per_unit_cny": _json_number(material),
            "winning_evidence": evidence["winner"]["evidence_id"],
            "conflicting_evidence_ids": [
                item["evidence_id"] for item in evidence["conflicts"]
            ],
            "quantity": _json_number(quantity),
            "unit_price_cny": _json_number(unit_price),
            "management_gross_profit_per_unit_cny": _json_number(management_gp),
            "management_gross_margin": float(management_gp / unit_price),
            "management_to_adjusted_bridge_per_unit_cny": bridge,
            "known_cost_contribution_before_warranty_per_unit_cny": _json_number(
                known_contribution
            ),
            "known_cost_contribution_before_warranty_batch_cny": _json_number(
                known_batch_contribution
            ),
            "delivery_status": order.get("delivery_status"),
        }

        if warranty_rate is None or warranty_cost is None:
            rate_value: int | float | str = (
                f"w_{suffix}" if warranty_rate is None else _json_number(warranty_rate)
            )
            cost_value: int | float | str = (
                f"c_{suffix}" if warranty_cost is None else _json_number(warranty_cost)
            )
            warranty_term = f"{rate_value}*{cost_value}"
            row.update(
                {
                    "warranty_rate": rate_value,
                    "cost_per_claim": cost_value,
                    "adjusted_unit_contribution_formula": (
                        f"{_json_number(known_contribution)} - {warranty_term}"
                    ),
                    "adjusted_batch_contribution_formula": (
                        f"{_json_number(known_batch_contribution)} - "
                        f"{_json_number(quantity)}*{warranty_term}"
                    ),
                    "positive_contribution_condition": (
                        f"{warranty_term} < {_json_number(known_contribution)}"
                    ),
                }
            )
        else:
            warranty_per_unit = warranty_rate * warranty_cost
            row.update(
                {
                    "warranty_rate": _json_number(warranty_rate),
                    "cost_per_claim": _json_number(warranty_cost),
                    "adjusted_unit_contribution_cny": _json_number(
                        known_contribution - warranty_per_unit
                    ),
                    "adjusted_batch_contribution_cny": _json_number(
                        (known_contribution - warranty_per_unit) * quantity
                    ),
                }
            )
        result[batch_id] = row
    return result


def _cash_path(
    opening_cash: Decimal,
    budget_rows: list[dict[str, str]],
    dated_receipts: dict[str, Decimal],
    first_month_extra_receipts: Decimal = Decimal(0),
) -> dict[str, Any]:
    cash = opening_cash
    monthly: list[dict[str, Any]] = []
    first_negative_month: str | None = None
    first_negative_number: int | None = None
    for index, row in enumerate(budget_rows, start=1):
        month = row["month"]
        receipts = dated_receipts.get(month, Decimal(0))
        if index == 1:
            receipts += first_month_extra_receipts
        cash += receipts - _decimal(row["total_cash_outflow_cny"], "total_cash_outflow_cny")
        monthly.append({"month": month, "ending_cash_cny": _json_number(cash)})
        if cash < 0:
            first_negative_month = month
            first_negative_number = index
            break
    funded = (
        first_negative_number - 1
        if first_negative_number is not None
        else len(budget_rows)
    )
    return {
        "monthly_ending_cash_cny": monthly,
        "fully_funded_month_ends": funded,
        "first_negative_projected_month_number": first_negative_number,
        "first_negative_month": first_negative_month,
    }


def calculate_cash_runway(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate dated-receipts-only and mechanical earliest-collection paths."""
    accounts = inputs["cash_position"].get("accounts")
    if not isinstance(accounts, list):
        raise ValueError("cash_position.json must contain an accounts list")
    gross_cash = sum(
        (_decimal(row["balance_cny"], "balance_cny") for row in accounts),
        Decimal(0),
    )
    opening_cash = sum(
        (
            _decimal(row["balance_cny"], "balance_cny")
            for row in accounts
            if _truthy(row.get("include_in_available_cash"))
        ),
        Decimal(0),
    )
    restricted_cash = gross_cash - opening_cash

    budget_rows = [
        row for row in inputs["cash_budget"] if _truthy(row.get("board_approved"))
    ]
    budget_rows.sort(key=lambda row: row["month"])
    if not budget_rows:
        raise ValueError("cash budget has no board-approved months")
    forecast_months = {row["month"] for row in budget_rows}

    dated_receipts: dict[str, Decimal] = defaultdict(Decimal)
    dated_receipt_rows: list[dict[str, Any]] = []
    undated_rows: list[dict[str, Any]] = []
    undated_total = Decimal(0)
    for invoice in inputs["invoices"]:
        open_amount = _decimal(invoice["open_receivable_cny"], "open_receivable_cny")
        if open_amount <= 0:
            continue
        collection_date = invoice.get("contractual_collection_date", "").strip()
        date_status = invoice.get("date_status", "").strip().lower()
        if collection_date and date_status == "known":
            collection_month = _month(collection_date)
            if collection_month in forecast_months:
                dated_receipts[collection_month] += open_amount
                dated_receipt_rows.append(
                    {
                        "invoice_id": invoice["invoice_id"],
                        "month": collection_month,
                        "amount_cny": _json_number(open_amount),
                    }
                )
        else:
            suffix = _variable_suffix(invoice["invoice_id"])
            undated_total += open_amount
            undated_rows.append(
                {
                    "invoice_id": invoice["invoice_id"],
                    "amount_cny": _json_number(open_amount),
                    "collection_date_variable": f"t_{suffix}",
                    "collection_fraction_variable": f"alpha_{suffix}",
                }
            )

    known_path = _cash_path(opening_cash, budget_rows, dated_receipts)
    upper_path = _cash_path(
        opening_cash, budget_rows, dated_receipts, first_month_extra_receipts=undated_total
    )
    known_path["description"] = (
        "Undated receivables are excluded from every month; this is not a bad-debt assumption."
    )
    upper_path["description"] = (
        "All undated receivables are collected in full in the first forecast month; "
        "this is a mechanical upper bound, not a forecast."
    )
    upper_path["undated_receipts_for_bound_cny"] = _json_number(undated_total)

    return {
        "gross_bank_balance_cny": _json_number(gross_cash),
        "restricted_cash_excluded_cny": _json_number(restricted_cash),
        "opening_available_cash_cny": _json_number(opening_cash),
        "dated_future_receipts": dated_receipt_rows,
        "undated_receivables": undated_rows,
        "known_dated_receipts_only": known_path,
        "mechanical_earliest_collection_upper_bound": upper_path,
    }


def run(input_dir: str | Path) -> dict[str, Any]:
    """Load a fixture directory and return deterministic calculation output."""
    inputs = load_inputs(input_dir)
    return {
        "unit_economics": calculate_unit_economics(inputs),
        "cash_runway": calculate_cash_runway(inputs),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_dir",
        help="directory containing orders.csv, invoices_and_receipts.csv, and other inputs",
    )
    parser.add_argument("--output", help="optional output JSON path")
    args = parser.parse_args(argv)
    payload = json.dumps(run(args.input_dir), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
