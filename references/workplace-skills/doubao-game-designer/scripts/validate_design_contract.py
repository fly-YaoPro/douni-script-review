#!/usr/bin/env python3
"""Validate a game-design preflight contract with no third-party packages."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "6.0"
SCOPE_LOCK_VERSION = "3"
READINESS_TARGETS = {"draft", "review", "implementation", "prototype"}
FLAG_NAMES = {
    "scope_constraints",
    "numbers",
    "probability",
    "resources",
    "capacity",
    "persistence",
    "lifecycle",
    "production",
    "html",
    "handoff",
}
PARAMETER_SOURCES = {
    "user",
    "current_config",
    "external",
    "design_initial",
    "calculated",
}
ASSUMPTION_IMPACTS = {"low", "high"}
ASSUMPTION_STATUSES = {"confirmed", "test_value", "open", "blocked"}
PRIORITIES = {"P0", "P1", "non_goal"}
TEST_TYPES = {
    "normal",
    "failure",
    "boundary",
    "abuse",
    "concurrency",
    "recovery",
}
TEST_STATUSES = {"planned", "passed", "failed", "not_run"}
JOURNEY_TYPES = {"standard", "failure", "recovery", "boundary", "abuse"}
PROTOTYPE_CHECKS = {"load", "input", "main_loop", "outcome", "restart"}
ASSERTION_SCENARIOS = {"normal", "boundary", "abuse"}
NUMERIC_REQUIREMENT_SOURCES = {"user", "current_config", "external", "design_goal"}
ASSERTION_OPERATORS = {"==", "!=", "<", "<=", ">", ">=", "between"}
CHANGE_SCOPE_EFFECTS = {"reuse", "modify", "add"}
CAPACITY_TASK_KINDS = {
    "feature",
    "integration",
    "qa",
    "data",
    "content",
    "art",
    "other",
}
PRODUCTION_SURFACES = {
    "performance",
    "state_data",
    "network_concurrency",
    "content_pipeline",
    "ui_input",
    "integration_qa",
}
FIELD_PATH_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
DRAFT_HYGIENE_CHECKS = (
    (
        "draft-internal-scope-notes",
        re.compile(
            r"(?m)^#{1,6}\s*(?:可改字段|硬约束|本轮可动旋钮|改动字段清单|权限投影|校验日志)"
            r"|是否在允许范围内|^>\s*(?:版本|类型)\s*[:：]",
            re.IGNORECASE,
        ),
        "formal draft starts from the adopted project, not internal scope or audit notes",
    ),
    (
        "draft-unresolved-placeholder",
        re.compile(
            r"待确认|待核实|待补充|\bTBD\b|\bTODO\b|未知|后续再细化",
            re.IGNORECASE,
        ),
        "formal design must contain the current resolved project",
    ),
    (
        "draft-unsourced-current",
        re.compile(
            r"假设现网[^\n]{0,40}(?:占比|基值|倍率|数值)"
            r"|现网[^\n]{0,80}(?:测试初值|设计初值|假设)",
            re.IGNORECASE,
        ),
        "current-state numbers require source evidence rather than design initials",
    ),
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


def finding(severity: str, code: str, path: str, message: str) -> Finding:
    return Finding(severity, code, path, message)


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def decimal_value(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def evaluate_expression(expression: str, variables: dict[str, Decimal]) -> Decimal:
    """Evaluate a small arithmetic expression with Decimal inputs."""

    def visit(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            value = decimal_value(node.value)
            if value is None:
                raise ValueError("constants must be numeric")
            return value
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"unknown input {node.id!r}")
            return variables[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("division by zero")
                return left / right
            if isinstance(node.op, ast.Pow):
                if right != right.to_integral_value() or abs(right) > 10:
                    raise ValueError("power must use an integer exponent between -10 and 10")
                return left ** int(right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.keywords:
                raise ValueError("functions do not accept keyword arguments")
            name = node.func.id
            values = [visit(argument) for argument in node.args]
            if name == "floor" and len(values) == 1:
                return values[0].to_integral_value(rounding=ROUND_FLOOR)
            if name == "ceil" and len(values) == 1:
                return values[0].to_integral_value(rounding=ROUND_CEILING)
            if name == "abs" and len(values) == 1:
                return abs(values[0])
            if name == "min" and values:
                return min(values)
            if name == "max" and values:
                return max(values)
            if name == "clamp" and len(values) == 3:
                value, minimum, maximum = values
                if minimum > maximum:
                    raise ValueError("clamp minimum must not exceed maximum")
                return min(max(value, minimum), maximum)
            raise ValueError(f"unsupported function or arguments {name!r}")
        raise ValueError(f"unsupported expression node {type(node).__name__}")

    if not is_text(expression):
        raise ValueError("expression must be non-empty text")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"invalid expression: {error.msg}") from error
    return visit(tree)


def acceptance_error(computed: Decimal, acceptance: Any) -> str | None:
    """Return an error when a computed result does not satisfy its design condition."""
    rule = as_dict(acceptance)
    if not rule:
        return None
    operator = rule.get("operator")
    if operator not in ASSERTION_OPERATORS:
        return f"operator must be one of {sorted(ASSERTION_OPERATORS)}"
    if operator == "between":
        minimum = decimal_value(rule.get("min"))
        maximum = decimal_value(rule.get("max"))
        if minimum is None or maximum is None:
            return "between requires numeric min and max"
        if minimum > maximum:
            return "between min must not exceed max"
        return None if minimum <= computed <= maximum else f"{computed} is outside [{minimum}, {maximum}]"
    expected = decimal_value(rule.get("value"))
    if expected is None:
        return f"{operator} requires numeric value"
    passed = {
        "==": computed == expected,
        "!=": computed != expected,
        "<": computed < expected,
        "<=": computed <= expected,
        ">": computed > expected,
        ">=": computed >= expected,
    }[operator]
    return None if passed else f"{computed} does not satisfy {operator} {expected}"


def normalize_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(value.lower().split())


def normalized_scope_items(value: Any) -> list[dict[str, Any]]:
    items = []
    for raw in as_list(value):
        item = dict(as_dict(raw))
        if "fields" in item:
            item["fields"] = sorted(
                field.strip() for field in as_list(item["fields"]) if is_text(field)
            )
        items.append(item)
    return sorted(items, key=lambda item: str(item.get("id", "")))


def scope_snapshot(data: Any) -> dict[str, Any]:
    root = as_dict(data)
    authority = as_dict(root.get("authority"))
    source_text = str(as_dict(root.get("task")).get("source_text", ""))
    return {
        "scope_lock_version": SCOPE_LOCK_VERSION,
        "schema_version": SCHEMA_VERSION,
        "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "allowed_changes": normalized_scope_items(authority.get("allowed_changes")),
        "forbidden_changes": normalized_scope_items(authority.get("forbidden_changes")),
    }


def validate_scope_lock(data: Any, lock_data: Any) -> list[Finding]:
    findings: list[Finding] = []
    lock = as_dict(lock_data)
    if lock.get("scope_lock_version") != SCOPE_LOCK_VERSION:
        findings.append(
            finding(
                "BLOCK",
                "scope-lock-version",
                "$scope_lock.scope_lock_version",
                f"must equal {SCOPE_LOCK_VERSION!r}",
            )
        )
        return findings
    current = scope_snapshot(data)
    if lock.get("source_text_sha256") != current["source_text_sha256"]:
        findings.append(
            finding(
                "BLOCK",
                "source-text-lock-mismatch",
                "$.task.source_text",
                "differs from the original user request frozen before design",
            )
        )
    for key in ("allowed_changes", "forbidden_changes"):
        if current[key] != normalized_scope_items(lock.get(key)):
            findings.append(
                finding(
                    "BLOCK",
                    "scope-lock-mismatch",
                    f"$.authority.{key}",
                    "differs from the user-authorized scope frozen before solution design",
                )
            )
    return findings


def validate_scoped_input_provenance(
    data: Any, contract_path: Path, lock_path: Path
) -> list[Finding]:
    """Reject local evidence authored after the user authority was frozen."""
    findings: list[Finding] = []
    try:
        frozen_at = lock_path.stat().st_mtime
    except OSError:
        return findings
    for index, raw in enumerate(as_list(as_dict(data).get("parameters"))):
        item = as_dict(raw)
        if item.get("source") not in {"current_config", "external"}:
            continue
        source_ref = item.get("source_ref")
        if not is_text(source_ref) or not source_ref.startswith("file:"):
            continue
        source_path = Path(source_ref[5:])
        if not source_path.is_absolute():
            source_path = contract_path.parent / source_path
        try:
            authored_at = source_path.stat().st_mtime
        except OSError:
            continue
        if authored_at > frozen_at:
            findings.append(
                finding(
                    "BLOCK",
                    "scoped-input-created-after-freeze",
                    f"$.parameters[{index}].source_ref",
                    "local input evidence must predate the frozen user authority; use design_initial for authorized test values",
                )
            )
    return findings


def validate_draft(data: Any, draft_text: str) -> list[Finding]:
    """Run topic-neutral checks that can be proven from the contract and final draft."""
    findings: list[Finding] = []
    for code, term_pattern, message in DRAFT_HYGIENE_CHECKS:
        match = term_pattern.search(draft_text)
        if match is None:
            continue
        excerpt = re.sub(r"\s+", " ", draft_text[max(0, match.start() - 24):match.end() + 40])
        findings.append(
            finding(
                "BLOCK",
                code,
                "draft",
                f"{message}; found {match.group(0)!r} near {excerpt!r}",
            )
        )

    capacity_items = as_list(
        as_dict(as_dict(data).get("ledgers")).get("capacity")
    )
    available_capacity = sum(
        (decimal_value(as_dict(item).get("available")) or Decimal(0))
        for item in capacity_items
    )
    if available_capacity > 0:
        for section in re.finditer(
            r"(?m)^#{1,6}\s+[^\n]*(?:工作量|容量|排期)[^\n]*\n", draft_text
        ):
            following = draft_text[section.end():]
            next_heading = re.search(r"(?m)^#{1,6}\s+", following)
            body = following[: next_heading.start()] if next_heading else following
            total = re.search(
                r"(?im)(?:合计|总计)[^\n]{0,80}?([0-9]+(?:\.[0-9]+)?)",
                body,
            )
            if total is None:
                continue
            declared = Decimal(total.group(1))
            if declared > available_capacity:
                findings.append(
                    finding(
                        "BLOCK",
                        "draft-capacity-overrun",
                        "draft",
                        f"draft total {declared} exceeds frozen capacity {available_capacity}",
                    )
                )
                break
    return findings


def default_scope_lock_path(contract_path: Path) -> Path:
    return contract_path.with_name(f"{contract_path.stem}.scope-lock.json")


def require_text(
    obj: dict[str, Any], key: str, path: str, findings: list[Finding]
) -> None:
    if not is_text(obj.get(key)):
        findings.append(finding("BLOCK", "required-text", f"{path}.{key}", "must be non-empty text"))


def collect_ids(
    items: Iterable[Any], path: str, findings: list[Finding], global_ids: dict[str, str]
) -> set[str]:
    ids: set[str] = set()
    for index, raw in enumerate(items):
        item = as_dict(raw)
        item_path = f"{path}[{index}]"
        item_id = item.get("id")
        if not is_text(item_id):
            findings.append(finding("BLOCK", "missing-id", f"{item_path}.id", "must be non-empty text"))
            continue
        if item_id in ids:
            findings.append(finding("BLOCK", "duplicate-id", f"{item_path}.id", f"duplicate id {item_id!r}"))
        ids.add(item_id)
        previous = global_ids.get(item_id)
        if previous is not None and previous != item_path:
            findings.append(
                finding("BLOCK", "global-duplicate-id", f"{item_path}.id", f"also used at {previous}")
            )
        else:
            global_ids[item_id] = item_path
    return ids


def validate_field_paths(
    value: Any,
    path: str,
    findings: list[Finding],
    *,
    exact_one: bool = False,
) -> set[str]:
    fields = as_list(value)
    if not fields:
        findings.append(
            finding(
                "BLOCK",
                "scope-fields-empty",
                path,
                "must name at least one atomic field such as combat.damage",
            )
        )
        return set()
    if exact_one and len(fields) != 1:
        findings.append(
            finding(
                "BLOCK",
                "scope-field-cardinality",
                path,
                "must contain exactly one atomic field; split distinct fields into separate items",
            )
        )
    normalized: set[str] = set()
    for index, field_name in enumerate(fields):
        field_path = f"{path}[{index}]"
        if not is_text(field_name) or not FIELD_PATH_PATTERN.fullmatch(field_name.strip()):
            findings.append(
                finding(
                    "BLOCK",
                    "scope-field-format",
                    field_path,
                    "must be an atomic lowercase dotted path without wildcards",
                )
            )
            continue
        normalized.add(field_name.strip())
    if len(normalized) != len(fields):
        findings.append(
            finding("BLOCK", "scope-field-duplicate", path, "must not contain duplicate fields")
        )
    return normalized


def validate_authorized_fields(
    item: dict[str, Any],
    path: str,
    allowed_fields: dict[str, set[str]],
    forbidden_fields: set[str],
    findings: list[Finding],
    *,
    exact_one: bool = False,
) -> None:
    refs = as_list(item.get("authority_ids"))
    fields = validate_field_paths(
        item.get("fields"), f"{path}.fields", findings, exact_one=exact_one
    )
    authorized = set().union(*(allowed_fields.get(ref, set()) for ref in refs))
    unauthorized = sorted(fields - authorized)
    if unauthorized:
        findings.append(
            finding(
                "BLOCK",
                "unauthorized-field",
                f"{path}.fields",
                f"not present in the frozen authority: {', '.join(unauthorized)}",
            )
        )
    forbidden = sorted(fields & forbidden_fields)
    if forbidden:
        findings.append(
            finding(
                "BLOCK",
                "forbidden-field",
                f"{path}.fields",
                f"conflicts with frozen fields: {', '.join(forbidden)}",
            )
        )


def validate_contract(data: Any) -> list[Finding]:
    findings: list[Finding] = []
    root = as_dict(data)
    if not root:
        return [finding("BLOCK", "root-type", "$", "contract must be a JSON object")]

    if root.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            finding("BLOCK", "schema-version", "$.schema_version", f"must equal {SCHEMA_VERSION!r}")
        )

    task = as_dict(root.get("task"))
    require_text(task, "title", "$.task", findings)
    target = task.get("readiness_target")
    if target not in READINESS_TARGETS:
        findings.append(
            finding(
                "BLOCK",
                "readiness-target",
                "$.task.readiness_target",
                f"must be one of {sorted(READINESS_TARGETS)}",
            )
        )
        target = "draft"

    flags = as_dict(task.get("flags"))
    missing_flags = sorted(FLAG_NAMES - set(flags))
    extra_flags = sorted(set(flags) - FLAG_NAMES)
    if missing_flags:
        findings.append(
            finding("BLOCK", "missing-flags", "$.task.flags", f"missing: {', '.join(missing_flags)}")
        )
    if extra_flags:
        findings.append(
            finding("WARN", "unknown-flags", "$.task.flags", f"unknown: {', '.join(extra_flags)}")
        )
    for flag_name in FLAG_NAMES & set(flags):
        if not isinstance(flags[flag_name], bool):
            findings.append(
                finding("BLOCK", "flag-type", f"$.task.flags.{flag_name}", "must be boolean")
            )

    source_text = str(task.get("source_text", ""))
    normalized_source_text = re.sub(r"\s+", "", source_text)
    global_ids: dict[str, str] = {}

    authority = as_dict(root.get("authority"))
    allowed = as_list(authority.get("allowed_changes"))
    forbidden = as_list(authority.get("forbidden_changes"))
    proposed = as_list(authority.get("proposed_changes"))
    allowed_ids = collect_ids(allowed, "$.authority.allowed_changes", findings, global_ids)
    collect_ids(forbidden, "$.authority.forbidden_changes", findings, global_ids)
    proposed_ids = collect_ids(proposed, "$.authority.proposed_changes", findings, global_ids)

    allowed_categories: dict[str, str] = {}
    allowed_fields: dict[str, set[str]] = {}
    forbidden_fields: set[str] = set()
    for index, raw in enumerate(allowed):
        item = as_dict(raw)
        path = f"$.authority.allowed_changes[{index}]"
        require_text(item, "category", path, findings)
        require_text(item, "description", path, findings)
        require_text(item, "source_quote", path, findings)
        source_quote = item.get("source_quote")
        if not is_text(source_quote) or re.sub(r"\s+", "", source_quote) not in normalized_source_text:
            findings.append(
                finding(
                    "BLOCK",
                    "allowed-authority-evidence",
                    f"{path}.source_quote",
                    "must quote the frozen user request verbatim",
                )
            )
        if is_text(item.get("id")) and is_text(item.get("category")):
            allowed_categories[item["id"]] = item["category"]
            allowed_fields[item["id"]] = validate_field_paths(
                item.get("fields"), f"{path}.fields", findings, exact_one=True
            )
    for index, raw in enumerate(forbidden):
        item = as_dict(raw)
        path = f"$.authority.forbidden_changes[{index}]"
        require_text(item, "category", path, findings)
        require_text(item, "description", path, findings)
        require_text(item, "source_quote", path, findings)
        source_quote = item.get("source_quote")
        if not is_text(source_quote) or re.sub(r"\s+", "", source_quote) not in normalized_source_text:
            findings.append(
                finding(
                    "BLOCK",
                    "forbidden-authority-evidence",
                    f"{path}.source_quote",
                    "must quote the frozen user request verbatim",
                )
            )
        forbidden_fields.update(
            validate_field_paths(
                item.get("fields"), f"{path}.fields", findings, exact_one=True
            )
        )
    for index, raw in enumerate(proposed):
        item = as_dict(raw)
        path = f"$.authority.proposed_changes[{index}]"
        require_text(item, "category", path, findings)
        require_text(item, "description", path, findings)
        require_text(item, "problem", path, findings)
        scope_effect = item.get("scope_effect")
        if scope_effect not in CHANGE_SCOPE_EFFECTS:
            findings.append(
                finding(
                    "BLOCK",
                    "change-scope-effect",
                    f"{path}.scope_effect",
                    f"must be one of {sorted(CHANGE_SCOPE_EFFECTS)}",
                )
            )
        responsibilities = as_list(item.get("responsibilities"))
        if not all(is_text(value) for value in responsibilities):
            findings.append(
                finding(
                    "BLOCK",
                    "change-responsibilities",
                    f"{path}.responsibilities",
                    "must contain non-empty responsibility names",
                )
            )
        if scope_effect == "add":
            if not responsibilities:
                findings.append(
                    finding(
                        "BLOCK",
                        "added-responsibility-empty",
                        f"{path}.responsibilities",
                        "an added scope item must name its new responsibilities",
                    )
                )
            require_text(item, "tradeoff", path, findings)
        if item.get("priority") not in PRIORITIES:
            findings.append(
                finding("BLOCK", "change-priority", f"{path}.priority", f"must be one of {sorted(PRIORITIES)}")
            )
        refs = as_list(item.get("authority_ids"))
        if not refs:
            findings.append(
                finding("BLOCK", "unauthorized-change", f"{path}.authority_ids", "must reference an allowed change")
            )
        for ref in refs:
            if ref not in allowed_ids:
                findings.append(
                    finding("BLOCK", "unknown-authority", f"{path}.authority_ids", f"unknown allowed id {ref!r}")
                )
        validate_authorized_fields(
            item, path, allowed_fields, forbidden_fields, findings, exact_one=True
        )
        category = item.get("category")
        if refs and is_text(category):
            compatible = any(allowed_categories.get(ref) in {category, "*"} for ref in refs)
            if not compatible:
                findings.append(
                    finding(
                        "BLOCK",
                        "authority-category-mismatch",
                        path,
                        "proposed category is not covered by its allowed authority",
                    )
                )
    if flags.get("scope_constraints") and not allowed:
        findings.append(
            finding("BLOCK", "scope-authority-empty", "$.authority.allowed_changes", "required by scope flag")
        )

    assumptions = as_list(root.get("assumptions"))
    assumption_ids = collect_ids(assumptions, "$.assumptions", findings, global_ids)
    for index, raw in enumerate(assumptions):
        item = as_dict(raw)
        path = f"$.assumptions[{index}]"
        require_text(item, "statement", path, findings)
        require_text(item, "validation", path, findings)
        impact = item.get("impact")
        status = item.get("status")
        if impact not in ASSUMPTION_IMPACTS:
            findings.append(
                finding("BLOCK", "assumption-impact", f"{path}.impact", f"must be one of {sorted(ASSUMPTION_IMPACTS)}")
            )
        if status not in ASSUMPTION_STATUSES:
            findings.append(
                finding("BLOCK", "assumption-status", f"{path}.status", f"must be one of {sorted(ASSUMPTION_STATUSES)}")
            )
        if impact == "high" and status in {"open", "blocked"}:
            severity = "BLOCK" if target in {"implementation", "prototype"} else "WARN"
            findings.append(
                finding(severity, "high-impact-assumption", path, "high-impact assumption is unresolved")
            )

    parameters = as_list(root.get("parameters"))
    parameter_ids = collect_ids(parameters, "$.parameters", findings, global_ids)
    parameters_by_name: dict[str, tuple[Any, Any, str]] = {}
    parameter_values: dict[str, Decimal] = {}
    for index, raw in enumerate(parameters):
        item = as_dict(raw)
        path = f"$.parameters[{index}]"
        require_text(item, "name", path, findings)
        require_text(item, "unit", path, findings)
        parameter_source = item.get("source")
        if parameter_source not in PARAMETER_SOURCES:
            findings.append(
                finding("BLOCK", "parameter-source", f"{path}.source", f"must be one of {sorted(PARAMETER_SOURCES)}")
            )
        if parameter_source in {"current_config", "external"}:
            source_ref = item.get("source_ref")
            if not is_text(source_ref):
                findings.append(
                    finding(
                        "BLOCK",
                        "parameter-source-evidence",
                        f"{path}.source_ref",
                        f"{parameter_source} requires an actually read file: or url: reference",
                    )
                )
            elif source_ref.startswith("file:"):
                source_path = Path(source_ref[5:])
                if not source_path.is_absolute() or not source_path.is_file():
                    findings.append(
                        finding(
                            "BLOCK",
                            "parameter-source-file",
                            f"{path}.source_ref",
                            "file: must point to an existing absolute input file",
                        )
                    )
            elif not re.fullmatch(r"url:https?://\S+", source_ref):
                findings.append(
                    finding(
                        "BLOCK",
                        "parameter-source-reference",
                        f"{path}.source_ref",
                        "must use file:/absolute/input or url:https://source",
                    )
                )
        if parameter_source == "user":
            source_quote = item.get("source_quote")
            if not is_text(source_quote) or re.sub(r"\s+", "", source_quote) not in normalized_source_text:
                findings.append(
                    finding(
                        "BLOCK",
                        "parameter-user-evidence",
                        f"{path}.source_quote",
                        "must quote the frozen user request verbatim",
                    )
                )
        if flags.get("scope_constraints") and parameter_source in {"design_initial", "calculated"}:
            refs = as_list(item.get("authority_ids"))
            if not refs:
                findings.append(
                    finding(
                        "BLOCK",
                        "unauthorized-parameter",
                        f"{path}.authority_ids",
                        f"{parameter_source} parameters must reference frozen authority",
                    )
                )
            for ref in refs:
                if ref not in allowed_ids:
                    findings.append(
                        finding(
                            "BLOCK",
                            "unknown-authority",
                            f"{path}.authority_ids",
                            f"unknown allowed id {ref!r}",
                        )
                    )
            validate_authorized_fields(
                item, path, allowed_fields, forbidden_fields, findings, exact_one=True
            )
        value = decimal_value(item.get("value"))
        minimum = decimal_value(item.get("min"))
        maximum = decimal_value(item.get("max"))
        if value is None:
            findings.append(finding("BLOCK", "parameter-value", f"{path}.value", "must be numeric"))
        elif is_text(item.get("id")):
            parameter_values[item["id"]] = value
        if minimum is not None and maximum is not None and minimum > maximum:
            findings.append(finding("BLOCK", "parameter-range", path, "min must not exceed max"))
        if value is not None and minimum is not None and value < minimum:
            findings.append(finding("BLOCK", "parameter-below-min", path, "value is below min"))
        if value is not None and maximum is not None and value > maximum:
            findings.append(finding("BLOCK", "parameter-above-max", path, "value is above max"))
        name_key = normalize_name(item.get("name"))
        if name_key:
            current = (item.get("value"), item.get("unit"), path)
            previous = parameters_by_name.get(name_key)
            if previous is not None:
                severity = "BLOCK" if previous[:2] != current[:2] else "WARN"
                code = "conflicting-parameter" if severity == "BLOCK" else "duplicate-parameter"
                findings.append(
                    finding(severity, code, path, f"same parameter name also defined at {previous[2]}")
                )
            else:
                parameters_by_name[name_key] = current
    if flags.get("numbers") and not parameters:
        findings.append(finding("BLOCK", "parameters-empty", "$.parameters", "required by numbers flag"))

    numerical_assertions = as_list(root.get("numerical_assertions"))
    assertion_ids = collect_ids(
        numerical_assertions, "$.numerical_assertions", findings, global_ids
    )
    assertions_by_id = {
        item["id"]: item
        for raw in numerical_assertions
        if is_text((item := as_dict(raw)).get("id"))
    }
    assertion_scenarios: set[str] = set()
    for index, raw in enumerate(numerical_assertions):
        item = as_dict(raw)
        path = f"$.numerical_assertions[{index}]"
        require_text(item, "expression", path, findings)
        require_text(item, "unit", path, findings)
        scenario = item.get("scenario")
        if scenario not in ASSERTION_SCENARIOS:
            findings.append(
                finding(
                    "BLOCK",
                    "assertion-scenario",
                    f"{path}.scenario",
                    f"must be one of {sorted(ASSERTION_SCENARIOS)}",
                )
            )
        else:
            assertion_scenarios.add(scenario)
        declared = decimal_value(item.get("declared_value"))
        tolerance = decimal_value(item.get("tolerance"))
        if declared is None:
            findings.append(
                finding("BLOCK", "assertion-declared", f"{path}.declared_value", "must be numeric")
            )
        if tolerance is None or tolerance < 0:
            findings.append(
                finding(
                    "BLOCK",
                    "assertion-tolerance",
                    f"{path}.tolerance",
                    "must be non-negative numeric",
                )
            )
        variables: dict[str, Decimal] = {}
        inputs = as_dict(item.get("inputs"))
        if not inputs:
            findings.append(
                finding("BLOCK", "assertion-inputs-empty", f"{path}.inputs", "must not be empty")
            )
        for variable, parameter_id in inputs.items():
            if not is_text(variable) or not variable.isidentifier():
                findings.append(
                    finding(
                        "BLOCK",
                        "assertion-input-name",
                        f"{path}.inputs",
                        f"{variable!r} must be a valid identifier",
                    )
                )
                continue
            if parameter_id not in parameter_values:
                findings.append(
                    finding(
                        "BLOCK",
                        "assertion-parameter-ref",
                        f"{path}.inputs.{variable}",
                        f"unknown numeric parameter id {parameter_id!r}",
                    )
                )
                continue
            variables[variable] = parameter_values[parameter_id]
        try:
            computed = evaluate_expression(str(item.get("expression", "")), variables)
        except (ValueError, ArithmeticError) as error:
            findings.append(
                finding("BLOCK", "assertion-expression", f"{path}.expression", str(error))
            )
            continue
        if declared is not None and tolerance is not None and abs(computed - declared) > tolerance:
            findings.append(
                finding(
                    "BLOCK",
                    "assertion-mismatch",
                    path,
                    f"computed {computed}, declared {declared}, tolerance {tolerance}",
                )
            )
        acceptance = item.get("acceptance")
        if acceptance is not None and not isinstance(acceptance, dict):
            findings.append(
                finding(
                    "BLOCK",
                    "assertion-acceptance",
                    f"{path}.acceptance",
                    "must be an object",
                )
            )
            continue
        condition_error = acceptance_error(computed, acceptance)
        if condition_error is not None:
            findings.append(
                finding(
                    "BLOCK",
                    "assertion-acceptance",
                    f"{path}.acceptance",
                    condition_error,
                )
            )

    numeric_requirements = as_list(root.get("numeric_requirements"))
    numeric_requirement_ids = collect_ids(
        numeric_requirements, "$.numeric_requirements", findings, global_ids
    )
    for index, raw in enumerate(numeric_requirements):
        item = as_dict(raw)
        path = f"$.numeric_requirements[{index}]"
        require_text(item, "statement", path, findings)
        source = item.get("source")
        if source not in NUMERIC_REQUIREMENT_SOURCES:
            findings.append(
                finding(
                    "BLOCK",
                    "numeric-requirement-source",
                    f"{path}.source",
                    f"must be one of {sorted(NUMERIC_REQUIREMENT_SOURCES)}",
                )
            )
        if source == "user":
            source_quote = item.get("source_quote")
            if not is_text(source_quote) or re.sub(r"\s+", "", source_quote) not in normalized_source_text:
                findings.append(
                    finding(
                        "BLOCK",
                        "numeric-requirement-evidence",
                        f"{path}.source_quote",
                        "must quote the user request verbatim",
                    )
                )
        if source in {"current_config", "external"}:
            source_ref = item.get("source_ref")
            if not is_text(source_ref) or not (
                source_ref.startswith("file:") or re.fullmatch(r"url:https?://\S+", source_ref)
            ):
                findings.append(
                    finding(
                        "BLOCK",
                        "numeric-requirement-evidence",
                        f"{path}.source_ref",
                        "must reference an actually read file: or url:",
                    )
                )
        refs = as_list(item.get("assertion_ids"))
        if not refs:
            findings.append(
                finding(
                    "BLOCK",
                    "numeric-requirement-uncovered",
                    f"{path}.assertion_ids",
                    "must reference at least one executable assertion",
                )
            )
        for ref in refs:
            if ref not in assertion_ids:
                findings.append(
                    finding(
                        "BLOCK",
                        "numeric-requirement-assertion",
                        f"{path}.assertion_ids",
                        f"unknown numerical assertion id {ref!r}",
                    )
                )
        if refs and not any(
            as_dict(assertions_by_id.get(ref)).get("acceptance")
            for ref in refs
            if ref in assertion_ids
        ):
            findings.append(
                finding(
                    "BLOCK",
                    "numeric-requirement-decision-criterion",
                    f"{path}.assertion_ids",
                    "must reference at least one decisive assertion with an acceptance condition",
                )
            )
    if flags.get("numbers"):
        if not numerical_assertions:
            findings.append(
                finding(
                    "BLOCK",
                    "numerical-assertions-empty",
                    "$.numerical_assertions",
                    "numbers flag requires executable assertions",
                )
            )
        for required_scenario in ("normal", "boundary"):
            if required_scenario not in assertion_scenarios:
                findings.append(
                    finding(
                        "BLOCK",
                        "assertion-scenario-missing",
                        "$.numerical_assertions",
                        f"missing {required_scenario!r} assertion",
                    )
                )
        if not numeric_requirements:
            findings.append(
                finding(
                    "BLOCK",
                    "numeric-requirements-empty",
                    "$.numeric_requirements",
                    "numbers flag requires the design questions that these calculations must prove",
                )
            )

    rules = as_list(root.get("rules"))
    rule_ids = collect_ids(rules, "$.rules", findings, global_ids)
    p0_rule_ids: set[str] = set()
    rule_state_refs: list[tuple[str, str]] = []
    for index, raw in enumerate(rules):
        item = as_dict(raw)
        path = f"$.rules[{index}]"
        require_text(item, "title", path, findings)
        require_text(item, "definition", path, findings)
        priority = item.get("priority")
        if priority not in PRIORITIES:
            findings.append(
                finding("BLOCK", "rule-priority", f"{path}.priority", f"must be one of {sorted(PRIORITIES)}")
            )
        if priority == "P0" and is_text(item.get("id")):
            p0_rule_ids.add(item["id"])
        if flags.get("scope_constraints"):
            refs = as_list(item.get("authority_ids"))
            if not refs:
                findings.append(
                    finding(
                        "BLOCK",
                        "unauthorized-rule",
                        f"{path}.authority_ids",
                        "scoped rules must reference frozen authority",
                    )
                )
            for ref in refs:
                if ref not in allowed_ids:
                    findings.append(
                        finding(
                            "BLOCK",
                            "unknown-authority",
                            f"{path}.authority_ids",
                            f"unknown allowed id {ref!r}",
                        )
                    )
            validate_authorized_fields(
                item, path, allowed_fields, forbidden_fields, findings
            )
        for ref in as_list(item.get("parameter_ids")):
            if ref not in parameter_ids:
                findings.append(
                    finding("BLOCK", "unknown-parameter-ref", f"{path}.parameter_ids", f"unknown parameter id {ref!r}")
                )
        for ref in as_list(item.get("state_machine_ids")):
            rule_state_refs.append((path, ref))

    state_machines = as_list(root.get("state_machines"))
    state_machine_ids = collect_ids(state_machines, "$.state_machines", findings, global_ids)
    persistence_specs = 0
    for index, raw in enumerate(state_machines):
        item = as_dict(raw)
        path = f"$.state_machines[{index}]"
        states = as_list(item.get("states"))
        if not states:
            findings.append(finding("BLOCK", "states-empty", f"{path}.states", "must contain at least one state"))
        state_ids: set[str] = set()
        for state_index, state_raw in enumerate(states):
            state = as_dict(state_raw)
            state_path = f"{path}.states[{state_index}]"
            state_id = state.get("id")
            if not is_text(state_id):
                findings.append(finding("BLOCK", "state-id", f"{state_path}.id", "must be non-empty text"))
            elif state_id in state_ids:
                findings.append(finding("BLOCK", "duplicate-state-id", f"{state_path}.id", f"duplicate state {state_id!r}"))
            else:
                state_ids.add(state_id)
            require_text(state, "entry", state_path, findings)
            require_text(state, "exit", state_path, findings)
        if len(states) > 1 and not as_list(item.get("event_order")):
            findings.append(
                finding("BLOCK", "event-order-empty", f"{path}.event_order", "required for multi-state rules")
            )
        transitions = as_list(item.get("transitions"))
        if flags.get("lifecycle"):
            initial_state = item.get("initial_state")
            if initial_state not in state_ids:
                findings.append(
                    finding(
                        "BLOCK",
                        "initial-state",
                        f"{path}.initial_state",
                        "must reference a state in this state machine",
                    )
                )
            if not transitions:
                findings.append(
                    finding(
                        "BLOCK",
                        "transitions-empty",
                        f"{path}.transitions",
                        "lifecycle rules require explicit transitions",
                    )
                )
            transition_ids: set[str] = set()
            adjacency: dict[str, set[str]] = {state_id: set() for state_id in state_ids}
            for transition_index, transition_raw in enumerate(transitions):
                transition = as_dict(transition_raw)
                transition_path = f"{path}.transitions[{transition_index}]"
                transition_id = transition.get("id")
                if not is_text(transition_id):
                    findings.append(
                        finding(
                            "BLOCK",
                            "transition-id",
                            f"{transition_path}.id",
                            "must be non-empty text",
                        )
                    )
                elif transition_id in transition_ids:
                    findings.append(
                        finding(
                            "BLOCK",
                            "duplicate-transition-id",
                            f"{transition_path}.id",
                            f"duplicate transition {transition_id!r}",
                        )
                    )
                else:
                    transition_ids.add(transition_id)
                source_state = transition.get("from")
                target_state = transition.get("to")
                if source_state not in state_ids:
                    findings.append(
                        finding(
                            "BLOCK",
                            "transition-from",
                            f"{transition_path}.from",
                            "must reference a state in this state machine",
                        )
                    )
                if target_state not in state_ids:
                    findings.append(
                        finding(
                            "BLOCK",
                            "transition-to",
                            f"{transition_path}.to",
                            "must reference a state in this state machine",
                        )
                    )
                if source_state in state_ids and target_state in state_ids:
                    adjacency[source_state].add(target_state)
                for key in ("event", "effect", "repeat_policy", "cleanup"):
                    require_text(transition, key, transition_path, findings)
            if initial_state in state_ids:
                reachable = {initial_state}
                frontier = [initial_state]
                while frontier:
                    current_state = frontier.pop()
                    for next_state in adjacency.get(current_state, set()):
                        if next_state not in reachable:
                            reachable.add(next_state)
                            frontier.append(next_state)
                unreachable = sorted(state_ids - reachable)
                if unreachable:
                    findings.append(
                        finding(
                            "BLOCK",
                            "unreachable-state",
                            path,
                            f"states not reachable from {initial_state!r}: {', '.join(unreachable)}",
                        )
                    )
        persistence = as_dict(item.get("persistence"))
        if persistence.get("required") is True:
            persistence_specs += 1
            for key in ("write_trigger", "restore_rule", "abnormal_exit"):
                require_text(persistence, key, f"{path}.persistence", findings)
            if not all(is_text(value) for value in as_list(persistence.get("fields"))):
                findings.append(
                    finding("BLOCK", "persistence-fields", f"{path}.persistence.fields", "must contain saved field names")
                )
            elif not as_list(persistence.get("fields")):
                findings.append(
                    finding("BLOCK", "persistence-fields", f"{path}.persistence.fields", "must not be empty")
                )
    for path, ref in rule_state_refs:
        if ref not in state_machine_ids:
            findings.append(
                finding("BLOCK", "unknown-state-machine-ref", f"{path}.state_machine_ids", f"unknown state machine id {ref!r}")
            )
    if flags.get("persistence") and persistence_specs == 0:
        findings.append(
            finding("BLOCK", "persistence-spec-empty", "$.state_machines", "persistence flag requires a complete spec")
        )
    if flags.get("lifecycle") and not state_machines:
        findings.append(
            finding(
                "BLOCK",
                "lifecycle-spec-empty",
                "$.state_machines",
                "lifecycle flag requires at least one state machine",
            )
        )

    ledgers = as_dict(root.get("ledgers"))
    probability_pools = as_list(ledgers.get("probability_pools"))
    resource_ledgers = as_list(ledgers.get("resources"))
    capacity_ledgers = as_list(ledgers.get("capacity"))
    pool_ids = collect_ids(probability_pools, "$.ledgers.probability_pools", findings, global_ids)
    resource_ids = collect_ids(resource_ledgers, "$.ledgers.resources", findings, global_ids)
    capacity_ids = collect_ids(capacity_ledgers, "$.ledgers.capacity", findings, global_ids)

    for index, raw in enumerate(probability_pools):
        pool = as_dict(raw)
        path = f"$.ledgers.probability_pools[{index}]"
        expected = decimal_value(pool.get("expected_total"))
        tolerance = decimal_value(pool.get("tolerance")) or Decimal("0")
        entries = as_list(pool.get("entries"))
        if expected is None:
            findings.append(finding("BLOCK", "probability-expected", f"{path}.expected_total", "must be numeric"))
            continue
        if tolerance < 0:
            findings.append(finding("BLOCK", "probability-tolerance", f"{path}.tolerance", "must be non-negative"))
        total = Decimal("0")
        valid = True
        for entry_index, entry_raw in enumerate(entries):
            entry = as_dict(entry_raw)
            entry_path = f"{path}.entries[{entry_index}]"
            require_text(entry, "id", entry_path, findings)
            value = decimal_value(entry.get("value"))
            if value is None:
                findings.append(finding("BLOCK", "probability-value", f"{entry_path}.value", "must be numeric"))
                valid = False
            elif value < 0:
                findings.append(finding("BLOCK", "probability-negative", f"{entry_path}.value", "must be non-negative"))
            else:
                total += value
        if not entries:
            findings.append(finding("BLOCK", "probability-entries-empty", f"{path}.entries", "must not be empty"))
        elif valid and abs(total - expected) > tolerance:
            findings.append(
                finding("BLOCK", "probability-total", path, f"sum {total} does not equal expected {expected}")
            )
    if flags.get("probability") and not probability_pools:
        findings.append(
            finding("BLOCK", "probability-pools-empty", "$.ledgers.probability_pools", "required by probability flag")
        )

    for index, raw in enumerate(resource_ledgers):
        ledger = as_dict(raw)
        path = f"$.ledgers.resources[{index}]"
        starting = decimal_value(ledger.get("starting"))
        if starting is None:
            findings.append(finding("BLOCK", "resource-starting", f"{path}.starting", "must be numeric"))
            continue
        transactions = as_list(ledger.get("transactions"))
        parsed: list[tuple[int, Decimal, str]] = []
        seen_orders: set[int] = set()
        for tx_index, tx_raw in enumerate(transactions):
            tx = as_dict(tx_raw)
            tx_path = f"{path}.transactions[{tx_index}]"
            require_text(tx, "id", tx_path, findings)
            order = tx.get("order")
            amount = decimal_value(tx.get("amount"))
            if not isinstance(order, int) or isinstance(order, bool):
                findings.append(finding("BLOCK", "resource-order", f"{tx_path}.order", "must be an integer"))
                continue
            if order in seen_orders:
                findings.append(finding("BLOCK", "resource-order-duplicate", f"{tx_path}.order", "must be unique"))
            seen_orders.add(order)
            if amount is None:
                findings.append(finding("BLOCK", "resource-amount", f"{tx_path}.amount", "must be numeric"))
                continue
            parsed.append((order, amount, tx_path))
        balance = starting
        allow_negative = ledger.get("allow_negative") is True
        for _order, amount, tx_path in sorted(parsed):
            balance += amount
            if balance < 0 and not allow_negative:
                findings.append(
                    finding("BLOCK", "resource-negative", tx_path, f"balance becomes {balance}")
                )
        expected_final = decimal_value(ledger.get("expected_final"))
        if ledger.get("expected_final") is not None and expected_final is None:
            findings.append(finding("BLOCK", "resource-expected-final", f"{path}.expected_final", "must be numeric"))
        elif expected_final is not None and balance != expected_final:
            findings.append(
                finding("BLOCK", "resource-final-mismatch", path, f"computed {balance}, expected {expected_final}")
            )
    if flags.get("resources") and not resource_ledgers:
        findings.append(finding("BLOCK", "resource-ledgers-empty", "$.ledgers.resources", "required by resources flag"))

    for index, raw in enumerate(capacity_ledgers):
        ledger = as_dict(raw)
        path = f"$.ledgers.capacity[{index}]"
        available = decimal_value(ledger.get("available"))
        require_text(ledger, "unit", path, findings)
        if available is None or available < 0:
            findings.append(finding("BLOCK", "capacity-available", f"{path}.available", "must be non-negative numeric"))
            continue
        p0_total = Decimal("0")
        for task_index, task_raw in enumerate(as_list(ledger.get("tasks"))):
            task = as_dict(task_raw)
            task_path = f"{path}.tasks[{task_index}]"
            require_text(task, "id", task_path, findings)
            require_text(task, "description", task_path, findings)
            amount = decimal_value(task.get("amount"))
            if amount is None or amount < 0:
                findings.append(finding("BLOCK", "capacity-amount", f"{task_path}.amount", "must be non-negative numeric"))
                continue
            task_kind = task.get("kind")
            if task_kind not in CAPACITY_TASK_KINDS:
                findings.append(
                    finding(
                        "BLOCK",
                        "capacity-task-kind",
                        f"{task_path}.kind",
                        f"must be one of {sorted(CAPACITY_TASK_KINDS)}",
                    )
                )
            if task.get("priority") not in PRIORITIES:
                findings.append(
                    finding("BLOCK", "capacity-priority", f"{task_path}.priority", f"must be one of {sorted(PRIORITIES)}")
                )
            if task.get("priority") == "P0":
                p0_total += amount
        if p0_total > available:
            findings.append(
                finding("BLOCK", "capacity-overflow", path, f"P0 total {p0_total} exceeds available {available}")
            )
        reserve = [
            as_dict(task)
            for task in as_list(ledger.get("tasks"))
            if as_dict(task).get("priority") == "P0"
            and as_dict(task).get("kind") in {"integration", "qa"}
            and (decimal_value(as_dict(task).get("amount")) or Decimal("0")) > 0
        ]
        if not reserve:
            findings.append(
                finding(
                    "BLOCK",
                    "capacity-validation-reserve",
                    f"{path}.tasks",
                    "P0 capacity must include a positive integration or QA task",
                )
            )
    if flags.get("capacity") and not capacity_ledgers:
        findings.append(finding("BLOCK", "capacity-ledgers-empty", "$.ledgers.capacity", "required by capacity flag"))

    tests = as_list(root.get("tests"))
    test_ids = collect_ids(tests, "$.tests", findings, global_ids)
    covered_rules: set[str] = set()
    covered_test_types: set[str] = set()
    for index, raw in enumerate(tests):
        item = as_dict(raw)
        path = f"$.tests[{index}]"
        for key in ("precondition", "action", "expected"):
            require_text(item, key, path, findings)
        if item.get("type") not in TEST_TYPES:
            findings.append(
                finding("BLOCK", "test-type", f"{path}.type", f"must be one of {sorted(TEST_TYPES)}")
            )
        else:
            covered_test_types.add(item["type"])
        status = item.get("status")
        if status not in TEST_STATUSES:
            findings.append(
                finding("BLOCK", "test-status", f"{path}.status", f"must be one of {sorted(TEST_STATUSES)}")
            )
        if status == "failed":
            severity = "BLOCK" if target in {"implementation", "prototype"} else "WARN"
            findings.append(finding(severity, "failed-test", path, "test is marked failed"))
        refs = as_list(item.get("rule_ids"))
        if not refs:
            findings.append(finding("BLOCK", "test-rule-empty", f"{path}.rule_ids", "must reference at least one rule"))
        for ref in refs:
            if ref not in rule_ids:
                findings.append(
                    finding("BLOCK", "unknown-rule-ref", f"{path}.rule_ids", f"unknown rule id {ref!r}")
                )
            else:
                covered_rules.add(ref)
    if flags.get("handoff") and (not rules or not tests):
        findings.append(
            finding("BLOCK", "handoff-incomplete", "$", "handoff flag requires rules and tests")
        )
    if flags.get("lifecycle"):
        for required_type in ("boundary", "recovery"):
            if required_type not in covered_test_types:
                findings.append(
                    finding(
                        "BLOCK",
                        "lifecycle-test-missing",
                        "$.tests",
                        f"lifecycle rules require a {required_type!r} test",
                    )
                )
    uncovered = sorted(p0_rule_ids - covered_rules)
    if uncovered:
        severity = "BLOCK" if target in {"implementation", "prototype"} else "WARN"
        findings.append(
            finding(severity, "p0-test-coverage", "$.tests", f"P0 rules without tests: {', '.join(uncovered)}")
        )

    production_risks = as_list(root.get("production_risks"))
    production_risk_ids = collect_ids(
        production_risks, "$.production_risks", findings, global_ids
    )
    for index, raw in enumerate(production_risks):
        item = as_dict(raw)
        path = f"$.production_risks[{index}]"
        surface = item.get("surface")
        if surface not in PRODUCTION_SURFACES:
            findings.append(
                finding(
                    "BLOCK",
                    "production-surface",
                    f"{path}.surface",
                    f"must be one of {sorted(PRODUCTION_SURFACES)}",
                )
            )
        for key in ("trigger", "impact", "detection", "mitigation", "fallback", "owner"):
            require_text(item, key, path, findings)
    if flags.get("production") and not production_risks:
        findings.append(
            finding(
                "BLOCK",
                "production-risks-empty",
                "$.production_risks",
                "production flag requires risks from the responsibility surfaces touched",
            )
        )

    prototype = as_dict(root.get("prototype"))
    prototype_required = flags.get("html") is True or target == "prototype"
    if prototype_required:
        if prototype.get("required") is not True:
            findings.append(finding("BLOCK", "prototype-required", "$.prototype.required", "must be true"))
        require_text(prototype, "path", "$.prototype", findings)
        require_text(prototype, "ruleset_id", "$.prototype", findings)
        require_text(prototype, "config_source", "$.prototype", findings)
        checks = as_dict(prototype.get("checks"))
        for check in sorted(PROTOTYPE_CHECKS):
            if checks.get(check) != "passed":
                findings.append(
                    finding("BLOCK", "prototype-check", f"$.prototype.checks.{check}", "must equal 'passed' after a real run")
                )
        journeys = as_list(prototype.get("journeys"))
        journey_ids = collect_ids(journeys, "$.prototype.journeys", findings, global_ids)
        journey_types: set[str] = set()
        for index, raw in enumerate(journeys):
            item = as_dict(raw)
            path = f"$.prototype.journeys[{index}]"
            require_text(item, "name", path, findings)
            require_text(item, "expected", path, findings)
            require_text(item, "evidence", path, findings)
            journey_type = item.get("type")
            if journey_type not in JOURNEY_TYPES:
                findings.append(
                    finding("BLOCK", "journey-type", f"{path}.type", f"must be one of {sorted(JOURNEY_TYPES)}")
                )
            else:
                journey_types.add(journey_type)
            if not all(is_text(step) for step in as_list(item.get("steps"))) or not as_list(item.get("steps")):
                findings.append(finding("BLOCK", "journey-steps", f"{path}.steps", "must contain executable steps"))
            if item.get("status") != "passed":
                findings.append(
                    finding("BLOCK", "journey-not-passed", f"{path}.status", "must equal 'passed' after a real browser run")
                )
        if not journeys:
            findings.append(finding("BLOCK", "journeys-empty", "$.prototype.journeys", "must not be empty"))
        if "standard" not in journey_types:
            findings.append(finding("BLOCK", "standard-journey-missing", "$.prototype.journeys", "requires a standard path"))
        if not ({"failure", "recovery"} & journey_types):
            findings.append(
                finding("BLOCK", "recovery-journey-missing", "$.prototype.journeys", "requires a failure or recovery path")
            )
    else:
        journey_ids = collect_ids(as_list(prototype.get("journeys")), "$.prototype.journeys", findings, global_ids)

    all_reference_ids = (
        allowed_ids
        | proposed_ids
        | assumption_ids
        | numeric_requirement_ids
        | parameter_ids
        | assertion_ids
        | rule_ids
        | state_machine_ids
        | pool_ids
        | resource_ids
        | capacity_ids
        | test_ids
        | production_risk_ids
        | journey_ids
    )
    claims = as_list(root.get("claims"))
    collect_ids(claims, "$.claims", findings, global_ids)
    for index, raw in enumerate(claims):
        item = as_dict(raw)
        path = f"$.claims[{index}]"
        require_text(item, "text", path, findings)
        strength = item.get("strength")
        if strength not in {"fact", "calculated", "hypothesis", "test_value"}:
            findings.append(
                finding("BLOCK", "claim-strength", f"{path}.strength", "must be fact, calculated, hypothesis, or test_value")
            )
        evidence_ids = as_list(item.get("evidence_ids"))
        if strength in {"fact", "calculated"} and not evidence_ids:
            findings.append(
                finding("BLOCK", "claim-evidence-empty", f"{path}.evidence_ids", "fact/calculated claims need evidence ids")
            )
        for ref in evidence_ids:
            if ref not in all_reference_ids:
                findings.append(
                    finding("BLOCK", "unknown-evidence-ref", f"{path}.evidence_ids", f"unknown evidence id {ref!r}")
                )

    return sorted(findings, key=lambda item: (item.severity != "BLOCK", item.path, item.code))


def template_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "title": "",
            "source_text": "",
            "readiness_target": "draft",
            "flags": {name: False for name in sorted(FLAG_NAMES)},
        },
        "authority": {
            "allowed_changes": [],
            "forbidden_changes": [],
            "proposed_changes": [],
        },
        "assumptions": [],
        "rules": [],
        "parameters": [],
        "numeric_requirements": [],
        "numerical_assertions": [],
        "state_machines": [],
        "ledgers": {
            "probability_pools": [],
            "resources": [],
            "capacity": [],
        },
        "tests": [],
        "production_risks": [],
        "prototype": {
            "required": False,
            "path": "",
            "ruleset_id": "",
            "config_source": "",
            "checks": {
                "load": "not_run",
                "input": "not_run",
                "main_loop": "not_run",
                "outcome": "not_run",
                "restart": "not_run",
            },
            "journeys": [],
        },
        "claims": [],
    }


def write_template(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(template_contract(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Path to design-contract.json")
    parser.add_argument("--init", metavar="PATH", help="Create an empty design contract")
    parser.add_argument(
        "--freeze-scope",
        action="store_true",
        help="Freeze the initial user-authorized scope beside the contract",
    )
    parser.add_argument(
        "--scope-lock",
        metavar="PATH",
        help="Use an explicit scope lock path instead of <contract>.scope-lock.json",
    )
    parser.add_argument(
        "--draft",
        metavar="PATH",
        help="Audit the completed local draft against the frozen authority",
    )
    parser.add_argument("--strict", action="store_true", help="Treat WARN findings as failure")
    args = parser.parse_args(argv)

    if args.init:
        if args.path:
            parser.error("do not combine PATH with --init")
        try:
            write_template(Path(args.init))
        except FileExistsError as error:
            print(f"BLOCK [init-exists] {error}")
            return 1
        print(f"PASS initialized {args.init}")
        return 0

    if not args.path:
        parser.error("PATH is required unless --init is used")

    path = Path(args.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCK [file-not-found] {path}")
        return 1
    except json.JSONDecodeError as error:
        print(f"BLOCK [invalid-json] {path}:{error.lineno}:{error.colno} {error.msg}")
        return 1

    findings = validate_contract(data)
    flags = as_dict(as_dict(data).get("task")).get("flags")
    scope_enabled = as_dict(flags).get("scope_constraints") is True
    lock_path = Path(args.scope_lock) if args.scope_lock else default_scope_lock_path(path)

    if args.freeze_scope:
        task = as_dict(as_dict(data).get("task"))
        authority = as_dict(as_dict(data).get("authority"))
        extra_flags = [
            name
            for name, enabled in as_dict(flags).items()
            if name != "scope_constraints" and enabled is True
        ]
        if not scope_enabled:
            findings.append(
                finding(
                    "BLOCK",
                    "scope-freeze-disabled",
                    "$.task.flags.scope_constraints",
                    "must be true before freezing user authority",
                )
            )
        if not is_text(task.get("source_text")):
            findings.append(
                finding(
                    "BLOCK",
                    "scope-source-text-empty",
                    "$.task.source_text",
                    "copy the complete user request before freezing scope",
                )
            )
        if as_list(authority.get("proposed_changes")):
            findings.append(
                finding(
                    "BLOCK",
                    "scope-freeze-after-design",
                    "$.authority.proposed_changes",
                    "must be empty; freeze user authority before solution design",
                )
            )
        if extra_flags:
            findings.append(
                finding(
                    "BLOCK",
                    "scope-freeze-after-design",
                    "$.task.flags",
                    f"only scope_constraints may be enabled while freezing: {', '.join(sorted(extra_flags))}",
                )
            )
    elif scope_enabled:
        if not lock_path.exists():
            findings.append(
                finding(
                    "BLOCK",
                    "scope-lock-missing",
                    "$scope_lock",
                    f"freeze the initial user authority first: --freeze-scope {path}",
                )
            )
        else:
            try:
                lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                findings.append(
                    finding(
                        "BLOCK",
                        "scope-lock-invalid",
                        "$scope_lock",
                        f"{lock_path}:{error.lineno}:{error.colno} {error.msg}",
                    )
                )
            else:
                findings.extend(validate_scope_lock(data, lock_data))
                findings.extend(
                    validate_scoped_input_provenance(data, path, lock_path)
                )

    if args.draft:
        draft_path = Path(args.draft)
        try:
            draft_text = draft_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            findings.append(
                finding("BLOCK", "draft-file-not-found", "$draft", str(draft_path))
            )
        else:
            if scope_enabled:
                findings.extend(validate_draft(data, draft_text))

    findings = sorted(
        findings, key=lambda item: (item.severity != "BLOCK", item.path, item.code)
    )
    blocks = [item for item in findings if item.severity == "BLOCK"]
    warnings = [item for item in findings if item.severity == "WARN"]
    for item in findings:
        print(f"{item.severity} [{item.code}] {item.path}: {item.message}")
    if not findings:
        print("PASS design contract validation passed with no findings")
    else:
        print(f"SUMMARY blocks={len(blocks)} warnings={len(warnings)}")

    failed = bool(blocks or (args.strict and warnings))
    if args.freeze_scope and not failed:
        snapshot = scope_snapshot(data)
        if lock_path.exists():
            try:
                existing = json.loads(lock_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"BLOCK [scope-lock-invalid] {lock_path}")
                return 1
            if existing != snapshot:
                print(f"BLOCK [scope-lock-exists] refusing to overwrite different scope: {lock_path}")
                return 1
            print(f"PASS scope already frozen at {lock_path}")
        else:
            lock_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"PASS scope frozen at {lock_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
