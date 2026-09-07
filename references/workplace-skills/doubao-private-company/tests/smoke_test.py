#!/usr/bin/env python3
import json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def run(*args):return subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True)
def main():
    facts=ROOT/"schemas/facts.example.json";config=json.loads((ROOT/"config/runtime.json").read_text(encoding="utf-8"))
    capabilities=ROOT/"schemas/capabilities.test.json"
    result=run(ROOT/"scripts/validate_facts.py",facts,"--capabilities-out",capabilities);assert result.returncode==0,result.stdout+result.stderr
    gates=json.loads(capabilities.read_text(encoding="utf-8"))
    assert gates["can_form_research_view"]["allowed"] is True
    assert gates["can_recommend_management_meeting"]["allowed"] is True
    assert gates["can_recommend_data_room_access"]["allowed"] is True
    assert gates["can_recommend_investment_progression"]["allowed"] is False
    assert gates["can_compute_returns"]["allowed"] is False
    assert gates["can_recommend_investment_progression"]["blocked_slots"]==["deal_quality","investment_progression"]
    tool=ROOT/config["deterministic_tool"];name=tool.name
    example_dir=ROOT/"schemas/deterministic-tool-example";example_file=ROOT/"schemas/deterministic-tool.example.json"
    if name=="company_cashflow_bridge.py":
        command=[tool,example_dir]
    elif name=="screening_engine.py":
        command=[tool,"--candidates",example_dir/"candidates.csv","--config",example_dir/"screening_config.json","--theme-evidence",example_dir/"theme_evidence.json","--dictionary",example_dir/"data_dictionary.json"]
    else:
        command=[tool,example_file,"--pretty"]
    result=run(*command);assert result.returncode==0,result.stdout+result.stderr
    tool_result=json.loads(result.stdout);assert isinstance(tool_result,dict) and tool_result
    expected={"company_cashflow_bridge.py":"bridges","screening_engine.py":"funnel","private_market_engine.py":"metrics","wealth_planning_engine.py":"runway","event_claim_engine.py":"event_capability_gate"}[name]
    assert expected in tool_result,(name,tool_result.keys())
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);data=json.loads(facts.read_text(encoding="utf-8"));data["claims"][1]["input_claims"]=["missing_claim"]
        bad=temp/"bad-facts.json";bad.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
        assert run(ROOT/"scripts/validate_facts.py",bad).returncode!=0
        duplicate_questions=json.loads(facts.read_text(encoding="utf-8"))
        duplicate_questions["payload"]["meeting"]["kill_questions"][1]["information_increment"]="identity_and_technology"
        duplicate_file=temp/"duplicate-questions.json";duplicate_file.write_text(json.dumps(duplicate_questions,ensure_ascii=False),encoding="utf-8")
        assert run(ROOT/"scripts/validate_facts.py",duplicate_file).returncode!=0
        self_reported_revenue={
            "as_of":"2026-01-01",
            "claims":[{
                "id":"fictional-revenue",
                "claim":"某虚构项目确认收入",
                "critical":True,
                "source_url":"https://example.com/company",
                "source_type":"company_primary",
                "published_at":"2025-12-01",
                "supported":True,
                "claim_category":"revenue",
                "commercialization_stage":"revenue_recognized",
                "target_product":"虚构目标产品",
                "target_legal_entity":"虚构项目公司",
                "target_match":True
            }]
        }
        revenue_ledger=temp/"self-reported-revenue.json";revenue_ledger.write_text(json.dumps(self_reported_revenue,ensure_ascii=False),encoding="utf-8")
        assert run(ROOT/"scripts/search_evidence_validator.py",revenue_ledger).returncode!=0
        verified_adoption={
            "as_of":"2026-01-01",
            "claims":[{
                "id":"fictional-hospital-use",
                "claim":"某虚构医院部署目标产品",
                "critical":True,
                "source_url":"https://example.org/hospital",
                "source_type":"hospital_primary",
                "published_at":"2025-12-01",
                "supported":True,
                "claim_category":"commercialization",
                "commercialization_stage":"deployment",
                "target_product":"虚构目标产品",
                "target_legal_entity":"虚构项目公司",
                "target_match":True
            }]
        }
        adoption_ledger=temp/"verified-adoption.json";adoption_ledger.write_text(json.dumps(verified_adoption,ensure_ascii=False),encoding="utf-8")
        assert run(ROOT/"scripts/search_evidence_validator.py",adoption_ledger).returncode==0
        evals=[{"id":"smoke-response","type":"positive","prompt":"smoke","assertions":[{"type":"must_include","value":"PASS_MARKER"}]}]
        eval_path=temp/"evals.json";eval_path.write_text(json.dumps(evals),encoding="utf-8")
        response_dir=temp/"responses";response_dir.mkdir();response=response_dir/"smoke-response.md";response.write_text("PASS_MARKER",encoding="utf-8")
        assert run(ROOT/"scripts/eval_harness.py",eval_path,"--responses-dir",response_dir).returncode==0
        response.write_text("missing marker",encoding="utf-8")
        assert run(ROOT/"scripts/eval_harness.py",eval_path,"--responses-dir",response_dir).returncode!=0
        partial_data=json.loads(facts.read_text(encoding="utf-8"))
        partial_data["payload"].pop("fund_mandate",None)
        partial_data["payload"].pop("management_materials",None)
        partial_facts=temp/"partial-facts.json";partial_facts.write_text(json.dumps(partial_data,ensure_ascii=False),encoding="utf-8")
        partial_caps=temp/"partial-capabilities.json"
        result=run(ROOT/"scripts/validate_facts.py",partial_facts,"--capabilities-out",partial_caps)
        assert result.returncode==0,result.stdout+result.stderr
        partial_gates=json.loads(partial_caps.read_text(encoding="utf-8"))
        assert partial_gates["can_form_research_view"]["allowed"] is True
        assert partial_gates["can_recommend_management_meeting"]["allowed"] is True
        assert partial_gates["can_recommend_data_room_access"]["allowed"] is True
        assert partial_gates["can_recommend_investment_progression"]["allowed"] is False
        incomplete_returns=temp/"incomplete-returns.json";incomplete_returns.write_text(json.dumps({"scenarios":[{"name":"base","probability":1,"entry_investment":10,"exit_proceeds_to_investor":20,"years":3}]}),encoding="utf-8")
        assert run(ROOT/"scripts/case_calculator.py",incomplete_returns).returncode!=0
        complete_returns=temp/"complete-returns.json";complete_returns.write_text(json.dumps({"transaction_context":{"instrument":"preferred","investor_rights":"confirmed","dilution_treatment":"included in exit proceeds","currency":"CNY"},"scenarios":[{"name":"base","probability":1,"entry_investment":10,"exit_proceeds_to_investor":20,"years":3}]}),encoding="utf-8")
        result=run(ROOT/"scripts/case_calculator.py",complete_returns)
        assert result.returncode==0,result.stdout+result.stderr
        assert json.loads(result.stdout)["capabilities"]["can_compute_returns"]["allowed"] is True
        mode=data["meta"]["mode"];sections=config["modes"][mode]["required_sections"];body=["# 测试报告"]
        for spec in sections:
            title=spec["aliases"][0];content="这是有实质内容的测试段落，说明来源、假设、机制与局限。"
            if spec.get("fact_binding"):content+=" {fact:example_fact}"
            body+=["",f"## {title}","",content]
        body+=["","本报告仅供研究参考，不构成投资建议。"]
        report=temp/"report.md";report.write_text("\n".join(body),encoding="utf-8")
        result=run(ROOT/"scripts/finalize_report.py",report,facts);assert result.returncode==0,result.stdout+result.stderr
        assert report.with_name("report-display.md").exists()
        assert report.with_name("report-manifest.json").exists()
        assert not report.with_suffix(".docx").exists()
    print("PASS private-market-project-evaluation V3");return 0
if __name__=="__main__":raise SystemExit(main())
