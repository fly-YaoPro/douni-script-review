#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    skill = (ROOT / "SKILL.md").read_text()
    online = (ROOT / "references/online-agent-execution-contract.md").read_text()
    runtime = json.loads((ROOT / "config/runtime.json").read_text())
    loading = json.loads((ROOT / "config/loading-profile.json").read_text())
    contract = runtime["search_contract"]
    for term in ("full_runtime", "hybrid_runtime", "agent_only"):
        assert term in skill
    assert "线上最高优先级规则" in skill
    assert "仅来自媒体或转述的一律标 `[待核·媒体]`" in skill
    assert "口径演算，不作估值结论" in skill
    assert "`--help`" in online and "raw_trace_unavailable" in online
    assert "online_direct_fast_path" in online
    assert "从用户正文删除" in online
    assert "不是模型自行设定的数字门槛" in online
    assert "Seed空结果不产生额外General额度" in online
    assert contract["max_calls_is_hard_limit"] is True
    assert contract["authoritative_financial_database_may_support_listed_comparable_standard_fields"] is True
    assert contract["seed_may_support_private_target_revenue_customer_contract_or_terms"] is False
    assert contract["transport_status_separate_from_evidence_status"] is True
    assert contract["trace_policy"]["model_summary_is_raw_trace"] is False
    assert contract["output_claim_policy"]["all_critical_provisional_blocks_investment_progression"] is True
    assert set(("bp", "data_room", "cap_table", "term_sheet")) <= set(contract["forbidden_substitutions"])
    assert loading["runtime_profiles"]["agent_only"]["may_claim_scripts_ran"] is False
    assert all(any("online-agent-execution-contract.md" in ref for ref in refs)
               for refs in loading["mode_references"].values())
    print("PASS private-market online Agent contract")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
