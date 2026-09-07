#!/usr/bin/env python3
"""Build a structured household wealth-runway update from five local files.

The parser intentionally relies on the fixture field names and Markdown section
format, while every monetary result is calculated from the supplied inputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
LABEL = re.compile(r"^\s*-\s*([^：:]+)[：:]\s*(.+?)\s*$", re.MULTILINE)
ORDERED_ITEM = re.compile(r"^\s*(\d+)[.、]\s*(.+?)\s*$", re.MULTILINE)


class InputError(ValueError):
    """Raised when an input cannot support a reproducible calculation."""


def _read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _decimal(value: str) -> Decimal:
    match = NUMBER.search(value)
    if not match:
        raise InputError(f"未找到数值：{value!r}")
    return Decimal(match.group().replace(",", ""))


def _json_number(value: Decimal) -> int | float:
    integral = value.to_integral_value()
    return int(integral) if value == integral else float(value)


def _labels(markdown: str) -> dict[str, str]:
    return {key.strip(): value.strip() for key, value in LABEL.findall(markdown)}


def _section(markdown: str, heading: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise InputError(f"缺少 Markdown 章节：{heading}")
    return match.group(1).strip()


def _table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def _first_row(rows: Iterable[list[str]], needle: str) -> list[str]:
    for row in rows:
        if needle in row[0]:
            return row
    raise InputError(f"表格缺少字段：{needle}")


def _month_from_iso(value: str) -> date:
    match = re.search(r"(\d{4})-(\d{2})", value)
    if not match:
        raise InputError(f"缺少 YYYY-MM 日期：{value!r}")
    return date(int(match.group(1)), int(match.group(2)), 1)


def _add_months(month: date, count: int) -> date:
    index = month.year * 12 + month.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


@dataclass(frozen=True)
class CashRecord:
    record_type: str
    item: str
    period: str
    amount: Decimal
    status: str
    notes: str


def _cash_records(path: str | Path) -> list[CashRecord]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "record_type",
            "item",
            "as_of_or_period",
            "amount_aud",
            "status",
            "notes",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required.difference(reader.fieldnames or []))
            raise InputError(f"现金流 CSV 缺少字段：{', '.join(missing)}")
        return [
            CashRecord(
                record_type=row["record_type"].strip(),
                item=row["item"].strip(),
                period=row["as_of_or_period"].strip(),
                amount=Decimal(row["amount_aud"].replace(",", "").strip()),
                status=row["status"].strip(),
                notes=row["notes"].strip(),
            )
            for row in reader
        ]


def _record(records: Iterable[CashRecord], item: str) -> CashRecord:
    for record in records:
        if record.item == item:
            return record
    raise InputError(f"现金流 CSV 缺少 item：{item}")


def _old_plan_values(markdown: str) -> dict[str, Any]:
    baseline = _table_rows(_section(markdown, "2025 基线"))
    balances = _table_rows(_section(markdown, "2026-07-17 原预测余额"))
    labels = _labels(_section(markdown, "计划口径"))
    risk = _section(markdown, "风险记录")
    return {
        "morgan_income": _decimal(_first_row(baseline, "Morgan 税后工资")[1]),
        "alex_income": _decimal(_first_row(baseline, "Alex 税后工资")[1]),
        "mortgage_payment": _decimal(_first_row(baseline, "房贷最低月供")[1]),
        "cash_forecast": _decimal(_first_row(balances, "现金合计")[1]),
        "investment_portfolio": _decimal(_first_row(balances, "投资组合合计")[1]),
        "jurisdiction": labels.get("常住地与适用州"),
        "tax_residency": labels.get("税务居民"),
        "currency": labels.get("基础币种"),
        "risk_preference": next(
            (
                line.removeprefix("- 风险偏好（willingness）：").strip()
                for line in risk.splitlines()
                if line.startswith("- 风险偏好（willingness）：")
            ),
            None,
        ),
        "recovery_tests": [
            text.rstrip("；。") for _, text in ORDERED_ITEM.findall(
                _section(markdown, "旧计划的家庭自定恢复测试")
            )
        ],
    }


def _goal_data(markdown: str, records: list[CashRecord]) -> dict[str, Any]:
    deferral = [
        text.rstrip("；。")
        for _, text in ORDERED_ITEM.findall(_section(markdown, "家庭指定的延期顺序"))
    ]
    recovery_section = _section(markdown, "恢复顺序与条件")
    recovery = [
        text.rstrip("；。")
        for _, text in ORDERED_ITEM.findall(recovery_section)
    ]
    contribution_by_keyword = {
        "装修": "renovation_contribution_monthly",
        "额外还款": "extra_mortgage_repayment_monthly",
        "长期投资": "general_investment_contribution_monthly",
        "教育": "education_contribution_monthly",
    }
    deferral_rows = []
    for order, action in enumerate(deferral, start=1):
        if "不属于可延期" in action:
            continue
        amount = next(
            (
                _record(records, item).amount
                for keyword, item in contribution_by_keyword.items()
                if keyword in action
            ),
            None,
        )
        row: dict[str, Any] = {"order": order, "action": action}
        if amount is not None:
            row["monthly_cash_released_aud"] = _json_number(amount)
        deferral_rows.append(row)

    non_deferrable = []
    if deferral and "不属于可延期" in deferral[-1]:
        subject = deferral[-1].split("不属于可延期", 1)[0].rstrip("，, ")
        non_deferrable = [part.strip() for part in re.split(r"[、和]", subject) if part.strip()]
    return {
        "deferral": deferral_rows,
        "non_deferrable": non_deferrable,
        "recovery": recovery,
        "test_method": next(
            (
                line.strip()
                for line in recovery_section.splitlines()
                if line.strip().startswith("每恢复一项")
            ),
            "",
        ),
        "prohibited_defaults": next(
            (
                line.strip()
                for line in recovery_section.splitlines()
                if "没有设定" in line or "没有授权" in line
            ),
            "",
        ),
    }


def _exclusions(
    records: list[CashRecord], termination: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = {
        "renovation_contribution_monthly": "Renovation contribution",
        "education_contribution_monthly": "Education contribution",
        "general_investment_contribution_monthly": "General investment contribution",
        "extra_mortgage_repayment_monthly": "Extra mortgage repayment",
        "optional_consumption_monthly": "Optional consumption",
    }
    for record in records:
        if record.status == "planned_not_committed":
            rows.append(
                {
                    "item": names.get(record.item, record.item),
                    "monthly_aud": _json_number(record.amount),
                    "reason": record.notes,
                }
            )

    pending_categories = [
        ("Severance and other termination payments", ("遣散费", "终止款项")),
        ("Government or other benefits", ("福利",)),
        ("Future re-employment income", ("再就业",)),
    ]
    for name, markers in pending_categories:
        if any(marker in termination for marker in markers):
            rows.insert(
                0,
                {
                    "item": name,
                    "reason": "Unconfirmed amount or receipt date; excluded from Base",
                },
            )
    rows.append(
        {
            "item": "Investment income, market recovery or asset sale proceeds",
            "reason": "No confirmed recurring cash flow is supplied",
        }
    )
    rows.append(
        {
            "item": "Home equity and investment account balances",
            "reason": "Balances are not liquid Base cash without a separate sale decision",
        }
    )
    return rows


def build_report(
    old_plan_path: str | Path,
    cashflow_path: str | Path,
    mortgage_notice_path: str | Path,
    termination_notice_path: str | Path,
    goals_register_path: str | Path,
    *,
    months: int = 12,
) -> dict[str, Any]:
    """Parse the five inputs and return a JSON-serializable runway report."""
    if months <= 0:
        raise InputError("months 必须为正整数")

    old_path = Path(old_plan_path)
    cash_path = Path(cashflow_path)
    mortgage_path = Path(mortgage_notice_path)
    termination_path = Path(termination_notice_path)
    goals_path = Path(goals_register_path)
    old_text = _read(old_path)
    mortgage_text = _read(mortgage_path)
    termination_text = _read(termination_path)
    goals_text = _read(goals_path)
    old = _old_plan_values(old_text)
    records = _cash_records(cash_path)
    mortgage = _labels(mortgage_text)
    goals = _goal_data(goals_text, records)

    current_income_records = [
        record
        for record in records
        if record.record_type == "income"
        and record.status == "confirmed"
        and "monthly" in record.item
    ]
    income = sum((record.amount for record in current_income_records), Decimal(0))
    living = _record(records, "necessary_living_ex_mortgage_monthly").amount
    mortgage_payment = _decimal(mortgage["生效后的最低月供"])
    effective_month = _month_from_iso(mortgage["生效日期"])
    gross_cash = _record(records, "gross_liquid_cash").amount
    card_due = _record(records, "credit_card_statement_due").amount
    starting_cash = gross_cash - card_due
    supplied_net = _record(records, "net_liquid_cash_for_runway").amount
    if supplied_net != starting_cash:
        raise InputError(
            "净流动现金不勾稽：gross_liquid_cash - credit_card_statement_due "
            "!= net_liquid_cash_for_runway"
        )

    outflow = living + mortgage_payment
    net_monthly = income - outflow
    schedule = []
    opening = starting_cash
    for offset in range(months):
        month = _add_months(effective_month, offset)
        closing = opening + net_monthly
        schedule.append(
            {
                "month": month.strftime("%Y-%m"),
                "opening_cash_aud": _json_number(opening),
                "income_aud": _json_number(income),
                "outflow_aud": _json_number(outflow),
                "net_cash_flow_aud": _json_number(net_monthly),
                "closing_cash_aud": _json_number(closing),
            }
        )
        opening = closing

    burn = -net_monthly
    runway_months = starting_cash / burn if burn > 0 else None
    latest_investment = _record(records, "total_investment_portfolio").amount
    bridge_records = [record for record in records if record.record_type == "bridge"]
    bridge_components = [
        record for record in bridge_records if record.status != "derived"
    ]
    bridge_total = sum((record.amount for record in bridge_components), Decimal(0))
    if bridge_total != gross_cash:
        raise InputError("现金桥接记录之和与最新 gross_liquid_cash 不一致")

    sources = "; ".join(
        [
            old_path.name,
            cash_path.name,
            mortgage_path.name,
            termination_path.name,
            goals_path.name,
        ]
    )
    changes = [
        {
            "item": "Household earned income",
            "old": f"{_json_number(old['morgan_income'] + old['alex_income'])} AUD per month",
            "new": f"{_json_number(income)} AUD per month confirmed",
            "classification": "invalidated",
            "source": f"{old_path.name}; {cash_path.name}; {termination_path.name}",
        },
        {
            "item": "Mortgage minimum payment",
            "old": f"{_json_number(old['mortgage_payment'])} AUD per month",
            "new": (
                f"{_json_number(mortgage_payment)} AUD per month from "
                f"{mortgage['生效日期']}"
            ),
            "classification": "invalidated",
            "source": mortgage_path.name,
        },
        {
            "item": "Liquid cash",
            "old": f"{_json_number(old['cash_forecast'])} AUD forecast",
            "new": (
                f"{_json_number(gross_cash)} AUD gross; "
                f"{_json_number(starting_cash)} AUD net after card due"
            ),
            "classification": "conflict_latest_wins",
            "bridge": [
                {
                    "item": record.item,
                    "amount_aud": _json_number(record.amount),
                    "status": record.status,
                }
                for record in bridge_records
            ],
            "source": cash_path.name,
        },
        {
            "item": "Investment portfolio",
            "old": f"{_json_number(old['investment_portfolio'])} AUD",
            "new": f"{_json_number(latest_investment)} AUD",
            "classification": "invalidated_for_current_value",
            "source": f"{old_path.name}; {cash_path.name}",
        },
        {
            "item": "Risk preference",
            "old": old["risk_preference"],
            "new": "Unchanged; no supplied input reports a preference change",
            "classification": "unchanged",
            "source": old_path.name,
        },
        {
            "item": "Severance and termination payments",
            "old": "Not applicable in prior plan",
            "new": "Amount and receipt date unconfirmed",
            "classification": "pending_and_excluded_from_base",
            "source": termination_path.name,
        },
        {
            "item": "Jurisdiction, tax residency and currency",
            "old": {
                "jurisdiction": old["jurisdiction"],
                "tax_residency": old["tax_residency"],
                "currency": old["currency"],
            },
            "new": "Unchanged",
            "classification": "unchanged",
            "source": old_path.name,
        },
    ]

    return {
        "schema_version": "1.0",
        "source_files": sources.split("; "),
        "assumption_change_log": changes,
        "base_scenario": {
            "included_items": [
                {
                    "item": record.item,
                    "monthly_aud": _json_number(record.amount),
                }
                for record in current_income_records
            ]
            + [
                {
                    "item": "necessary_living_ex_mortgage_monthly",
                    "monthly_aud": -_json_number(living),
                },
                {
                    "item": "minimum_mortgage_payment",
                    "monthly_aud": -_json_number(mortgage_payment),
                    "effective_date": mortgage["生效日期"],
                },
            ],
            "excluded_items": _exclusions(records, termination_text),
            "starting_cash_calculation": {
                "gross_liquid_cash_aud": _json_number(gross_cash),
                "less_credit_card_statement_due_aud": _json_number(card_due),
                "net_liquid_cash_aud": _json_number(starting_cash),
            },
            "monthly_calculation": {
                "confirmed_income_aud": _json_number(income),
                "necessary_living_aud": _json_number(living),
                "minimum_mortgage_aud": _json_number(mortgage_payment),
                "total_base_outflow_aud": _json_number(outflow),
                "net_monthly_cash_flow_aud": _json_number(net_monthly),
            },
            "twelve_month_runway": schedule,
            "twelve_month_totals": {
                "income_aud": _json_number(income * months),
                "outflow_aud": _json_number(outflow * months),
                "net_cash_flow_aud": _json_number(net_monthly * months),
                "ending_cash_aud": _json_number(opening),
            },
            "total_cash_runway": {
                "starting_cash_aud": _json_number(starting_cash),
                "monthly_burn_aud": _json_number(burn) if burn > 0 else 0,
                "months": round(float(runway_months), 4)
                if runway_months is not None
                else None,
                "status": "finite" if runway_months is not None else "not_depleting",
            },
        },
        "goal_deferral_order": goals["deferral"],
        "non_deferrable_items": goals["non_deferrable"],
        "recovery_conditions": {
            "all_required_before_testing_any_goal": old["recovery_tests"],
            "restore_one_at_a_time_in_order": goals["recovery"],
            "test_method": goals["test_method"],
            "prohibited_default_conditions": goals["prohibited_defaults"],
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate structured household cash-runway JSON."
    )
    parser.add_argument("old_plan", type=Path)
    parser.add_argument("cashflow", type=Path)
    parser.add_argument("mortgage_notice", type=Path)
    parser.add_argument("termination_notice", type=Path)
    parser.add_argument("goals_register", type=Path)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("-o", "--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_report(
            args.old_plan,
            args.cashflow,
            args.mortgage_notice,
            args.termination_notice,
            args.goals_register,
            months=args.months,
        )
    except (InputError, OSError, csv.Error) as exc:
        raise SystemExit(f"wealth_runway: {exc}") from exc
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
