#!/usr/bin/env python3
"""Generic fictional contract tests for Seed Finance Search routing."""

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from search_router import plan  # noqa: E402


LEDGER_FIELDS = [
    "tool",
    "query",
    "asof",
    "source",
    "period",
    "unit",
    "currency",
    "reported-vs-estimate",
]


def main():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.search(r"^---\n(.*?)\n---", skill, re.S).group(1)
    assert "name: doubao-private-company" in frontmatter

    profile = json.loads((ROOT / "config/loading-profile.json").read_text())
    runtime = json.loads((ROOT / "config/runtime.json").read_text())
    contract = runtime["seed_finance_search"]

    assert profile["search"]["tool_order"] == [
        "general_search",
        "seed_finance_search",
    ]
    assert contract["schema_policy"] == "use_host_actual_schema_do_not_invent_parameters"
    assert contract["fallback"] == "general_search"
    assert contract["library_result_is_primary"] is False
    assert contract["private_data_gap_policy"] == (
        "local_degradation_no_blanket_refusal"
    )
    assert contract["ledger_fields"] == LEDGER_FIELDS
    routed = plan(
        {
            "skill": "private-market-project-evaluation",
            "object_frozen": True,
            "needs_current_public_facts": True,
        }
    )
    assert routed["tool_order"] == ["general_search", "seed_finance_search"]
    assert routed["seed_finance_policy"]["fallback"] == "general_search"

    fictional_case = {
        "company": "虚构星港机器人",
        "seed_finance_allowed": ["public_funding", "listed_comparables"],
        "general_document_required": ["company", "customer", "regulator", "product"],
        "private_only": ["bp", "data_room", "cap_table", "term_sheet", "mandate"],
    }
    assert set(fictional_case["seed_finance_allowed"]) <= set(
        contract["allowed_scope"]
    )
    assert set(fictional_case["private_only"]) <= set(
        contract["forbidden_substitutions"]
    )
    assert "客户事实继续走 `general_search`" in skill
    assert "缺私有数据时只局部降级" in skill

    reference = (
        ROOT / "references/seed-finance-search-routing.md"
    ).read_text(encoding="utf-8")
    for field in LEDGER_FIELDS:
        assert f"`{field}`" in reference
    assert "不得发明工具名、字段或参数" in reference
    print("PASS private-market Seed Finance Search fictional contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
