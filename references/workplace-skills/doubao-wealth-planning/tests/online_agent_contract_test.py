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
    assert "未知项按规则3分档" in skill
    assert "不点名具体基金、保险产品、券种或机构产品" in skill
    assert "`--help`" in online and "raw_trace_unavailable" in online
    assert "online_direct_fast_path" in online
    assert "不得出现模型生成的应急月数" in online
    assert "不得给默认月份区间或中枢" in online
    assert "不得放入“保证本金”层" in online
    assert contract["max_calls_is_hard_limit"] is True
    assert contract["government_rules_require_official_general_search"] is True
    assert contract["seed_may_support_standard_public_market_fields"] is True
    assert contract["seed_may_support_tax_social_security_pension_or_regulation"] is False
    assert contract["seed_may_replace_household_inputs"] is False
    assert contract["transport_status_separate_from_evidence_status"] is True
    assert contract["trace_policy"]["model_summary_is_raw_trace"] is False
    assert contract["output_claim_policy"]["provisional_rule_claim_blocks_rule_quantification"] is True
    assert loading["runtime_profiles"]["agent_only"]["may_claim_scripts_ran"] is False
    assert all(any("online-agent-execution-contract.md" in ref for ref in refs)
               for refs in loading["mode_references"].values())
    print("PASS wealth-planning online Agent contract")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
