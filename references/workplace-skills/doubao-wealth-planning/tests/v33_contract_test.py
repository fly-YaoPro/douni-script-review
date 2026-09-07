#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_runtime_contract():
    config = json.loads((ROOT / "config/runtime.json").read_text(encoding="utf-8"))
    assert config["version"] == "V3.3-finance-integration"
    assert config["legacy_release_version"] == 11
    assert config["default_delivery_tier"] == "direct"
    assert config["state_contract"]["allowed_states"] == [
        "ready",
        "degraded",
        "intake_required",
        "confirmation_required",
        "routed",
        "stopped",
    ]
    for tier in ("direct", "brief", "full"):
        spec = config["delivery_tiers"][tier]
        assert spec["hard_max_chars"] > spec["target_chars"]
        assert spec["hard_max_output_tokens"] > spec["target_output_tokens"]
        assert "hard_gates" in spec["slots"]
    for capability in config["capabilities"].values():
        assert capability["requirements"]
        assert capability["blocked_slots"]
    required_claim_fields = config["claim_ledger"]["required_fields"]
    for field in ("as_of", "currency", "unit", "source_role"):
        assert field in required_claim_fields
    seed = config["search_runtime"]["provider_routing"]["seed_finance_search"]
    assert seed["priority"] == "low"
    assert seed["closed_fixture"] == "off"
    assert seed["search_off"] == "off"
    assert seed["unavailable_fallback"] == "general_search"
    assert seed["database_is_official"] is False
    assert (ROOT / config["jurisdiction_profiles"]["中国大陆"]).is_file()


def test_search_decision_policy():
    router = ROOT / "scripts/search_router.py"
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        cases = [
            (
                {
                    "skill": "wealth-planning",
                    "prompt": "仅基于这些家庭数据计算净资产和预算",
                    "context": {"object_frozen": True, "jurisdiction_frozen": True},
                },
                "off",
            ),
            (
                {
                    "skill": "wealth-planning",
                    "prompt": "按中国大陆当前养老金官方规则做规划",
                    "context": {"object_frozen": True, "jurisdiction_frozen": True},
                },
                "required",
            ),
            (
                {
                    "skill": "wealth-planning",
                    "prompt": "按某地区当前税务规则精确计算",
                    "context": {"object_frozen": False, "jurisdiction_frozen": False},
                },
                "blocked",
            ),
            (
                {
                    "skill": "wealth-planning",
                    "prompt": "我不知道债务APR和最低还款，但请给我精确还债顺序",
                    "context": {"object_frozen": True, "jurisdiction_frozen": True},
                },
                "blocked",
            ),
            (
                {
                    "skill": "wealth-planning",
                    "prompt": "请查询最新指数和基金公开事实",
                    "context": {"object_frozen": True, "jurisdiction_frozen": True},
                },
                "required",
            ),
            (
                {
                    "skill": "wealth-planning",
                    "prompt": "closed fixture：请查询最新指数和基金公开事实",
                    "context": {
                        "object_frozen": True,
                        "jurisdiction_frozen": True,
                        "closed_fixture": True,
                    },
                },
                "off",
            ),
        ]
        for index, (payload, expected) in enumerate(cases):
            path = temp / f"search-{index}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run(router, path)
            assert result.returncode == 0, result.stdout + result.stderr
            output = json.loads(result.stdout)
            assert output["mode"] == expected
            if expected == "required":
                assert output["query_stages"][0] == "jurisdiction_and_tax_year"
            if "不知道债务" in payload["prompt"]:
                assert output["signals"]["needs_private_data"] is True
            if "指数和基金" in payload["prompt"] and expected == "required":
                assert output["provider_route"] == "seed_finance_search"
                assert output["seed_finance_search"]["eligible"] is True
            if payload["prompt"].startswith("closed fixture"):
                assert output["provider_route"] == "none"
                assert output["max_calls"] == 0

        rule_path = temp / "rule.json"
        rule_path.write_text(
            json.dumps(
                {
                    "skill": "wealth-planning",
                    "prompt": "请查询中国大陆养老金资格和监管规则",
                    "context": {
                        "object_frozen": True,
                        "jurisdiction_frozen": True,
                        "seed_finance_requested": True,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        rule_output = json.loads(run(router, rule_path).stdout)
        assert rule_output["provider_route"] == "general_search"
        assert rule_output["seed_finance_search"]["eligible"] is False


def test_complexity_defaults_to_direct():
    router = ROOT / "scripts/complexity_router.py"
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "complexity.json"
        path.write_text(
            json.dumps(
                {
                    "skill": "wealth-planning",
                    "prompt": "我的应急金缺口怎么算？",
                    "requested_artifacts": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = run(router, path)
        assert result.returncode == 0, result.stdout + result.stderr
        output = json.loads(result.stdout)
        assert output["tier"] == "direct"
        assert "hard_gates" in output["slots"]
        assert output["hard_max_output_tokens"] == 1200


def test_seed_evidence_role_and_lineage():
    validator = ROOT / "scripts/search_evidence_validator.py"
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "seed-evidence.json"
        claim = {
            "id": "seed-market-1",
            "claim": "示例公开市场数据",
            "claim_kind": "numeric",
            "critical": False,
            "source_type": "structured_financial_database",
            "source_role": "database_aggregator",
            "provider": "host-seed-provider",
            "dataset": "public-market-data",
            "record_id": "record-1",
            "field": "yield",
            "value": 2.5,
            "as_of": "2026-07-24",
            "period": "2026-07-24",
            "currency": "CNY",
            "unit": "percent",
            "underlying_source_url": "https://example.com/primary",
            "supported": True,
            "conflict": False,
        }
        path.write_text(
            json.dumps({"as_of": "2026-07-24", "claims": [claim]}),
            encoding="utf-8",
        )
        assert run(validator, path).returncode == 0
        claim["source_role"] = "government"
        path.write_text(
            json.dumps({"as_of": "2026-07-24", "claims": [claim]}),
            encoding="utf-8",
        )
        result = run(validator, path)
        assert result.returncode == 1
        assert "source_role=database_aggregator" in result.stdout


def test_claim_artifact_and_finalizer_gates():
    validator = ROOT / "scripts/validate_deliverable.py"
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        response = temp / "response.md"
        response.write_text("直接结论：现金流可计算。\n\n局限：税务规则未纳入。", encoding="utf-8")
        artifact = temp / "facts.json"
        artifact.write_text('{"claims":[]}', encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        claim = {
            "claim_id": "c1",
            "claim": "现金流可计算",
            "claim_type": "calculation",
            "critical": True,
            "object_id": "household-1",
            "as_of": "2026-07-24",
            "period": "2026-07",
            "currency": "CNY",
            "unit": "CNY",
            "source_ids": ["user-budget"],
            "source_role": "user_fact",
            "source_tier": "primary",
            "confidence": "high",
            "conflict_state": "none",
        }
        contract = {
            "min_chars": 10,
            "required_any": [["结论"], ["局限"]],
            "claim_ledger": [claim],
            "claim_required_fields": list(claim),
            "artifact_paths": ["facts.json"],
            "artifact_hashes": {"facts.json": digest},
            "full_counts": {"claims": 1, "unknowns": 0},
            "compact_counts": {"claims": 1, "unknowns": 0},
            "source_ids_before": ["user-budget"],
            "source_ids_after": ["user-budget"],
            "finalizer_run_count": 1,
        }
        contract_path = temp / "contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        result = run(validator, response, contract_path)
        assert result.returncode == 0, result.stdout + result.stderr

        contract["source_ids_after"].append("invented-source")
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        result = run(validator, response, contract_path)
        assert result.returncode == 1
        assert "added source_ids" in result.stdout


def test_six_state_and_permission_gate():
    gate = ROOT / "scripts/wealth_runtime_gate.py"
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)

        def execute(payload):
            path = temp / "gate.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = run(gate, path)
            return result.returncode, json.loads(result.stdout)

        for current, requested in [
            ("intake_required", "degraded"),
            ("degraded", "confirmation_required"),
            ("ready", "confirmation_required"),
            ("confirmation_required", "ready"),
            ("routed", "routed"),
            ("stopped", "stopped"),
        ]:
            code, output = execute(
                {
                    "current_state": current,
                    "requested_state": requested,
                    "action": "read",
                }
            )
            assert code == 0 and output["allowed"] is True
        code, output = execute(
            {
                "current_state": "stopped",
                "requested_state": "ready",
                "action": "read",
            }
        )
        assert code == 1 and output["reason"] == "invalid_transition"

        base = {
            "current_state": "confirmation_required",
            "requested_state": "ready",
            "action": "transfer",
            "target": "account-tokenized",
            "scope": "CNY 1000",
        }
        code, output = execute(base)
        assert code == 1
        assert "preview" in output["missing"]
        assert "identity_verified" in output["missing"]
        assert "second_confirmation" in output["missing"]
        assert "audit_idempotency_key" in output["missing"]

        approved = {
            **base,
            "preview": "transfer preview",
            "identity_verified": True,
            "permission_verified": True,
            "second_confirmation": True,
            "audit": {
                "idempotency_key": "household-1:transfer-1",
                "timestamp": "2026-07-24T11:00:00+08:00",
                "result_verification_plan": "verify host receipt and balance delta",
            },
        }
        code, output = execute(approved)
        assert code == 0
        assert output["permission_gate"] == "passed"
        assert output["execution_claim"] == "authorized_for_host_execution"


def main():
    test_runtime_contract()
    test_search_decision_policy()
    test_complexity_defaults_to_direct()
    test_seed_evidence_role_and_lineage()
    test_claim_artifact_and_finalizer_gates()
    test_six_state_and_permission_gate()
    print("PASS wealth-planning V3.3 contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
