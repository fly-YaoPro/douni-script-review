#!/usr/bin/env python3
"""Regression tests for validate_design_contract.py."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from validate_design_contract import (  # noqa: E402
    main,
    validate_contract,
    validate_draft,
    validate_scoped_input_provenance,
)


def valid_contract() -> dict:
    return {
        "schema_version": "6.0",
        "task": {
            "title": "Generic contract validation",
            "source_text": "Use primary value 60 and numeric input 10. Adjust one existing rule. Do not add new units.",
            "readiness_target": "implementation",
            "flags": {
                "scope_constraints": True,
                "numbers": True,
                "probability": True,
                "resources": True,
                "capacity": True,
                "persistence": True,
                "lifecycle": True,
                "production": True,
                "html": False,
                "handoff": True,
            },
        },
        "authority": {
            "allowed_changes": [
                {
                    "id": "ALLOW-RULE",
                    "category": "rule",
                    "description": "Adjust one existing rule",
                    "source_quote": "Adjust one existing rule",
                    "fields": ["system.primary_rule"],
                }
            ],
            "forbidden_changes": [
                {
                    "id": "BAN-UNIT",
                    "category": "entity",
                    "description": "No new units",
                    "source_quote": "Do not add new units",
                    "fields": ["system.unit_roster"],
                }
            ],
            "proposed_changes": [
                {
                    "id": "CHG-PRIMARY",
                    "category": "rule",
                    "description": "Update the authorized rule",
                    "problem": "The current rule can resolve more than once",
                    "scope_effect": "modify",
                    "responsibilities": [],
                    "tradeoff": "",
                    "authority_ids": ["ALLOW-RULE"],
                    "fields": ["system.primary_rule"],
                    "priority": "P0",
                }
            ],
        },
        "assumptions": [
            {
                "id": "ASM-REWARD",
                "statement": "Source data uses the supplied baseline",
                "impact": "high",
                "status": "confirmed",
                "validation": "Compare against current config",
            }
        ],
        "rules": [
            {
                "id": "RULE-PRIMARY",
                "title": "Parameter application",
                "definition": "The configured value applies once when its preconditions hold.",
                "priority": "P0",
                "parameter_ids": ["PAR-PRIMARY-VALUE"],
                "state_machine_ids": ["SM-PRIMARY"],
                "authority_ids": ["ALLOW-RULE"],
                "fields": ["system.primary_rule"],
            }
        ],
        "parameters": [
            {
                "id": "PAR-PRIMARY-VALUE",
                "name": "primary_value",
                "value": 60,
                "unit": "unit",
                "source": "user",
                "source_quote": "primary value 60",
                "min": 0,
                "max": 100,
            },
            {
                "id": "PAR-NUMERIC-INPUT",
                "name": "numeric_input",
                "value": 10,
                "unit": "unit",
                "source": "user",
                "source_quote": "numeric input 10",
                "min": 0,
                "max": 100,
            }
        ],
        "numeric_requirements": [
            {
                "id": "NUMREQ-PRIMARY",
                "statement": "Verify the supplied numeric input in standard and boundary cases.",
                "source": "user",
                "source_quote": "numeric input 10",
                "assertion_ids": ["ASSERT-NORMAL", "ASSERT-BOUNDARY"],
            }
        ],
        "numerical_assertions": [
            {
                "id": "ASSERT-NORMAL",
                "scenario": "normal",
                "expression": "value",
                "inputs": {"value": "PAR-NUMERIC-INPUT"},
                "declared_value": 10,
                "unit": "unit",
                "tolerance": 0,
                "acceptance": {"operator": "==", "value": 10},
            },
            {
                "id": "ASSERT-BOUNDARY",
                "scenario": "boundary",
                "expression": "value - value",
                "inputs": {"value": "PAR-NUMERIC-INPUT"},
                "declared_value": 0,
                "unit": "unit",
                "tolerance": 0,
                "acceptance": {"operator": "between", "min": 0, "max": 0},
            },
        ],
        "state_machines": [
            {
                "id": "SM-PRIMARY",
                "states": [
                    {"id": "INITIAL", "entry": "Process starts", "exit": "Activation occurs"},
                    {"id": "ACTIVE", "entry": "Activation occurs", "exit": "Outcome resolves"},
                ],
                "event_order": ["outcome", "reward", "state_change"],
                "initial_state": "INITIAL",
                "transitions": [
                    {
                        "id": "TRANSITION-ACTIVATE",
                        "from": "INITIAL",
                        "event": "Activation occurs",
                        "to": "ACTIVE",
                        "effect": "Apply the configured value once",
                        "repeat_policy": "Ignore the same event identity",
                        "cleanup": "Clear the event identity after resolution",
                    },
                    {
                        "id": "TRANSITION-RESOLVE",
                        "from": "ACTIVE",
                        "event": "Outcome resolves",
                        "to": "INITIAL",
                        "effect": "Return to the initial state",
                        "repeat_policy": "A new event may start a new cycle",
                        "cleanup": "Clear transient state",
                    },
                ],
                "persistence": {
                    "required": True,
                    "write_trigger": "Persistence trigger",
                    "fields": ["state_value", "resource_value"],
                    "restore_rule": "Restore saved fields and reset transient state",
                    "abnormal_exit": "Use the latest completed snapshot",
                },
            }
        ],
        "ledgers": {
            "probability_pools": [
                {
                    "id": "POOL-PRIMARY",
                    "expected_total": 100,
                    "tolerance": 0,
                    "entries": [
                        {"id": "ENTRY-A", "value": 80},
                        {"id": "ENTRY-B", "value": 20},
                    ],
                }
            ],
            "resources": [
                {
                    "id": "RES-PRIMARY",
                    "starting": 120,
                    "allow_negative": False,
                    "transactions": [
                        {"id": "ACTION-A", "order": 1, "amount": -50},
                        {"id": "ACTION-B", "order": 2, "amount": -60},
                    ],
                    "expected_final": 10,
                }
            ],
            "capacity": [
                {
                    "id": "CAP-PROGRAM",
                    "available": 6,
                    "unit": "person_day",
                    "tasks": [
                        {
                            "id": "TASK-RULE",
                            "description": "Implement rule and tests",
                            "amount": 4,
                            "priority": "P0",
                            "kind": "feature",
                        },
                        {
                            "id": "TASK-QA",
                            "description": "Integration and regression verification",
                            "amount": 1,
                            "priority": "P0",
                            "kind": "qa",
                        }
                    ],
                }
            ],
        },
        "tests": [
            {
                "id": "TEST-PRIMARY",
                "type": "normal",
                "rule_ids": ["RULE-PRIMARY"],
                "precondition": "The configured preconditions hold",
                "action": "Apply the configured action",
                "expected": "The value changes exactly once",
                "status": "planned",
            },
            {
                "id": "TEST-BOUNDARY",
                "type": "boundary",
                "rule_ids": ["RULE-PRIMARY"],
                "precondition": "The event has already resolved once",
                "action": "Process the same event identity again",
                "expected": "The value does not change again",
                "status": "planned",
            },
            {
                "id": "TEST-RECOVERY",
                "type": "recovery",
                "rule_ids": ["RULE-PRIMARY"],
                "precondition": "The active state is interrupted",
                "action": "Restore the persisted snapshot",
                "expected": "Transient state is cleared and saved values are restored",
                "status": "planned",
            },
        ],
        "production_risks": [
            {
                "id": "RISK-INTEGRATION",
                "surface": "integration_qa",
                "trigger": "The rule and persistence layer are integrated late",
                "impact": "Regression time is compressed",
                "detection": "Run the integration suite before the feature freeze",
                "mitigation": "Reserve one QA day in the capacity ledger",
                "fallback": "Ship the previous rule behind the existing switch",
                "owner": "engineering and QA",
            }
        ],
        "prototype": {
            "required": False,
            "path": "",
            "ruleset_id": "",
            "config_source": "",
            "checks": {},
            "journeys": [],
        },
        "claims": [
            {
                "id": "CLAIM-BALANCE",
                "text": "The standard path produces the declared result.",
                "strength": "calculated",
                "evidence_ids": ["RES-PRIMARY"],
            }
        ],
    }


def codes(contract: dict) -> set[str]:
    return {item.code for item in validate_contract(contract)}


class ContractValidationTests(unittest.TestCase):
    def test_valid_implementation_contract(self) -> None:
        self.assertEqual([], validate_contract(valid_contract()))

    def test_probability_resource_capacity_and_scope_failures(self) -> None:
        contract = valid_contract()
        contract["authority"]["proposed_changes"][0]["authority_ids"] = []
        contract["ledgers"]["probability_pools"][0]["entries"][1]["value"] = 35
        contract["ledgers"]["resources"][0]["transactions"][1]["amount"] = -90
        contract["ledgers"]["resources"][0]["expected_final"] = -20
        contract["ledgers"]["capacity"][0]["tasks"][0]["amount"] = 8
        result = codes(contract)
        self.assertTrue(
            {"unauthorized-change", "probability-total", "resource-negative", "capacity-overflow"}
            <= result
        )

    def test_conflicting_parameter_and_missing_test_coverage(self) -> None:
        contract = valid_contract()
        duplicate = copy.deepcopy(contract["parameters"][0])
        duplicate["id"] = "PAR-PRIMARY-VALUE-ALT"
        duplicate["value"] = 70
        duplicate["unit"] = "unit_per_second"
        contract["parameters"].append(duplicate)
        contract["tests"] = []
        result = codes(contract)
        self.assertIn("conflicting-parameter", result)
        self.assertIn("p0-test-coverage", result)
        self.assertIn("handoff-incomplete", result)

    def test_persistence_requires_real_write_and_restore_fields(self) -> None:
        contract = valid_contract()
        persistence = contract["state_machines"][0]["persistence"]
        persistence["write_trigger"] = ""
        persistence["fields"] = []
        result = codes(contract)
        self.assertIn("required-text", result)
        self.assertIn("persistence-fields", result)

    def test_prototype_requires_real_browser_journeys(self) -> None:
        contract = valid_contract()
        contract["task"]["readiness_target"] = "prototype"
        contract["task"]["flags"]["html"] = True
        contract["prototype"] = {
            "required": True,
            "path": "demo.html",
            "ruleset_id": "RULESET-EXAMPLE",
            "config_source": "window.GAME_CONFIG",
            "checks": {
                "load": "passed",
                "input": "passed",
                "main_loop": "passed",
                "outcome": "not_run",
                "restart": "not_run",
            },
            "journeys": [
                {
                    "id": "JOURNEY-STANDARD",
                    "name": "Standard route",
                    "type": "standard",
                    "steps": ["Open demo", "Complete one cycle"],
                    "expected": "Outcome screen appears",
                    "status": "not_run",
                    "evidence": "Not run",
                }
            ],
        }
        result = codes(contract)
        self.assertIn("prototype-check", result)
        self.assertIn("journey-not-passed", result)
        self.assertIn("recovery-journey-missing", result)

    def test_high_impact_unknown_and_unsupported_claim_block_handoff(self) -> None:
        contract = valid_contract()
        contract["assumptions"][0]["status"] = "open"
        contract["claims"][0]["evidence_ids"] = []
        result = codes(contract)
        self.assertIn("high-impact-assumption", result)
        self.assertIn("claim-evidence-empty", result)

    def test_failed_execution_test_blocks_implementation(self) -> None:
        contract = valid_contract()
        contract["tests"][0]["status"] = "failed"
        self.assertIn("failed-test", codes(contract))

    def test_numerical_assertion_recomputes_declared_result(self) -> None:
        contract = valid_contract()
        contract["numerical_assertions"][0]["declared_value"] = 110
        self.assertIn("assertion-mismatch", codes(contract))

    def test_numerical_assertion_checks_design_acceptance(self) -> None:
        contract = valid_contract()
        contract["numerical_assertions"][0]["acceptance"] = {
            "operator": ">",
            "value": 10,
        }
        self.assertIn("assertion-acceptance", codes(contract))

        contract = valid_contract()
        contract["numerical_assertions"][0]["acceptance"] = "positive"
        self.assertIn("assertion-acceptance", codes(contract))

    def test_numerical_assertion_supports_rounding_and_clamp(self) -> None:
        contract = valid_contract()
        assertion = contract["numerical_assertions"][0]
        assertion["expression"] = "floor(value * 0.75) + ceil(value * 0.11) + clamp(value, 0, 8)"
        assertion["declared_value"] = 17
        assertion["acceptance"] = {"operator": "==", "value": 17}
        self.assertEqual([], validate_contract(contract))

    def test_numbers_require_design_question_coverage(self) -> None:
        contract = valid_contract()
        contract["numeric_requirements"] = []
        self.assertIn("numeric-requirements-empty", codes(contract))

        contract = valid_contract()
        contract["numeric_requirements"][0]["assertion_ids"] = []
        self.assertIn("numeric-requirement-uncovered", codes(contract))

    def test_numeric_requirement_needs_decisive_acceptance(self) -> None:
        contract = valid_contract()
        for assertion in contract["numerical_assertions"]:
            assertion.pop("acceptance", None)
        self.assertIn(
            "numeric-requirement-decision-criterion",
            codes(contract),
        )

    def test_user_numeric_requirement_needs_real_quote(self) -> None:
        contract = valid_contract()
        contract["numeric_requirements"][0]["source_quote"] = "invented combat target"
        self.assertIn("numeric-requirement-evidence", codes(contract))

    def test_numbers_require_normal_and_boundary_assertions(self) -> None:
        contract = valid_contract()
        contract["numerical_assertions"] = [
            contract["numerical_assertions"][0]
        ]
        self.assertIn("assertion-scenario-missing", codes(contract))

    def test_lifecycle_requires_transitions_and_recovery_coverage(self) -> None:
        contract = valid_contract()
        contract["state_machines"][0]["transitions"] = []
        contract["tests"] = [
            test for test in contract["tests"] if test["type"] != "recovery"
        ]
        result = codes(contract)
        self.assertIn("transitions-empty", result)
        self.assertIn("lifecycle-test-missing", result)

    def test_capacity_requires_integration_or_qa_reserve(self) -> None:
        contract = valid_contract()
        contract["ledgers"]["capacity"][0]["tasks"] = [
            contract["ledgers"]["capacity"][0]["tasks"][0]
        ]
        self.assertIn("capacity-validation-reserve", codes(contract))

    def test_production_flag_requires_concrete_risk(self) -> None:
        contract = valid_contract()
        contract["production_risks"] = []
        self.assertIn("production-risks-empty", codes(contract))

    def test_added_scope_requires_responsibility_and_tradeoff(self) -> None:
        contract = valid_contract()
        change = contract["authority"]["proposed_changes"][0]
        change["scope_effect"] = "add"
        change["responsibilities"] = []
        change["tradeoff"] = ""
        result = codes(contract)
        self.assertIn("added-responsibility-empty", result)
        self.assertIn("required-text", result)

    def test_scope_lock_blocks_self_authorized_expansion(self) -> None:
        contract = valid_contract()
        contract["authority"]["proposed_changes"] = []
        for name in contract["task"]["flags"]:
            contract["task"]["flags"][name] = name == "scope_constraints"

        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "design-contract.json"
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(
                0,
                main(["--freeze-scope", str(contract_path)]),
            )

            contract["authority"]["allowed_changes"].append(
                {
                    "id": "ALLOW-SELF-ADDED",
                    "category": "rule",
                    "description": "Authority added after solution design",
                    "source_quote": "authority added",
                    "fields": ["system.self_added_rule"],
                }
            )
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(1, main([str(contract_path)]))

    def test_scope_cannot_be_frozen_after_solution_design(self) -> None:
        contract = valid_contract()
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "design-contract.json"
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(
                1,
                main(["--freeze-scope", str(contract_path)]),
            )

    def test_changed_field_must_exist_in_frozen_authority(self) -> None:
        contract = valid_contract()
        contract["authority"]["proposed_changes"][0]["fields"] = [
            "system.attack_speed"
        ]
        self.assertIn("unauthorized-field", codes(contract))

    def test_design_initial_parameter_must_map_to_authorized_field(self) -> None:
        contract = valid_contract()
        contract["parameters"][0]["source"] = "design_initial"
        contract["parameters"][0]["authority_ids"] = ["ALLOW-RULE"]
        contract["parameters"][0]["fields"] = ["system.attack_speed"]
        self.assertIn("unauthorized-field", codes(contract))

    def test_current_config_parameter_needs_real_input_reference(self) -> None:
        contract = valid_contract()
        contract["parameters"][0]["source"] = "current_config"
        self.assertIn("parameter-source-evidence", codes(contract))

    def test_user_parameter_must_quote_frozen_request(self) -> None:
        contract = valid_contract()
        contract["parameters"][0]["source_quote"] = "invented attack speed 1.2"
        self.assertIn("parameter-user-evidence", codes(contract))

    def test_allowed_authority_is_one_quoted_atomic_field(self) -> None:
        contract = valid_contract()
        contract["authority"]["allowed_changes"][0]["fields"] = [
            "system.primary_rule",
            "system.attack_speed",
        ]
        self.assertIn("scope-field-cardinality", codes(contract))

    def test_authority_must_quote_frozen_request(self) -> None:
        contract = valid_contract()
        contract["authority"]["allowed_changes"][0]["source_quote"] = (
            "Invented allowed scope"
        )
        contract["authority"]["forbidden_changes"][0]["source_quote"] = (
            "Invented forbidden scope"
        )
        result = codes(contract)
        self.assertIn("allowed-authority-evidence", result)
        self.assertIn("forbidden-authority-evidence", result)

    def test_forbidden_authority_is_one_atomic_field(self) -> None:
        contract = valid_contract()
        contract["authority"]["forbidden_changes"][0]["fields"] = [
            "system.unit_roster",
            "system.enemy_roster",
        ]
        self.assertIn("scope-field-cardinality", codes(contract))

    def test_frozen_field_blocks_proposed_change_and_rule(self) -> None:
        contract = valid_contract()
        contract["authority"]["forbidden_changes"][0]["fields"] = [
            "system.primary_rule"
        ]
        contract["parameters"][0]["source"] = "design_initial"
        contract["parameters"][0]["authority_ids"] = ["ALLOW-RULE"]
        contract["parameters"][0]["fields"] = ["system.primary_rule"]
        findings = validate_contract(contract)
        blocked_paths = {
            finding.path
            for finding in findings
            if finding.code == "forbidden-field"
        }
        self.assertTrue(
            {
                "$.authority.proposed_changes[0].fields",
                "$.parameters[0].fields",
                "$.rules[0].fields",
            }
            <= blocked_paths
        )

    def test_authority_fields_are_domain_neutral(self) -> None:
        for field in (
            "card.draw_cost",
            "vehicle.acceleration",
            "dialogue.choice_weight",
            "level.checkpoint_interval",
        ):
            with self.subTest(field=field):
                contract = valid_contract()
                contract["authority"]["allowed_changes"][0]["fields"] = [field]
                contract["authority"]["proposed_changes"][0]["fields"] = [field]
                contract["rules"][0]["fields"] = [field]
                self.assertEqual([], validate_contract(contract))

    def test_draft_hygiene_is_topic_neutral(self) -> None:
        contract = valid_contract()
        draft = (
            "卡牌抽取费用调整为 2 点，赛车加速度保持当前配置，"
            "对话权重与关卡检查点沿用已确认规则。"
        )
        self.assertEqual([], validate_draft(contract, draft))

    def test_completed_draft_rejects_internal_scope_notes(self) -> None:
        contract = valid_contract()
        draft = "## 权限投影\n\n| 字段 | 是否在允许范围内 |\n|---|---|"
        self.assertIn(
            "draft-internal-scope-notes",
            {item.code for item in validate_draft(contract, draft)},
        )

    def test_completed_draft_cannot_exceed_capacity(self) -> None:
        contract = valid_contract()
        draft = "## 工作量评估\n\n| 项目 | 人日 |\n|---|---:|\n| 合计 | 7.5 |"
        self.assertIn(
            "draft-capacity-overrun",
            {item.code for item in validate_draft(contract, draft)},
        )

    def test_completed_draft_rejects_unresolved_placeholders(self) -> None:
        contract = valid_contract()
        self.assertIn(
            "draft-unresolved-placeholder",
            {item.code for item in validate_draft(contract, "恢复规则待确认。")},
        )

    def test_completed_draft_rejects_current_number_as_design_initial(self) -> None:
        contract = valid_contract()
        self.assertIn(
            "draft-unsourced-current",
            {
                item.code
                for item in validate_draft(
                    contract, "现网转化率为 18%（设计初值）。"
                )
            },
        )

    def test_scoped_task_cannot_author_its_own_external_evidence(self) -> None:
        contract = valid_contract()
        contract["parameters"][0]["source"] = "external"
        contract["parameters"][0].pop("source_quote", None)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract_path = root / "design-contract.json"
            lock_path = root / "design-contract.scope-lock.json"
            lock_path.write_text("{}", encoding="utf-8")
            evidence_path = root / "test-values.md"
            evidence_path.write_text("invented test values", encoding="utf-8")
            contract["parameters"][0]["source_ref"] = f"file:{evidence_path}"
            self.assertIn(
                "scoped-input-created-after-freeze",
                {
                    item.code
                    for item in validate_scoped_input_provenance(
                        contract, contract_path, lock_path
                    )
                },
            )


if __name__ == "__main__":
    unittest.main()
