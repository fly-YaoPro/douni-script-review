#!/usr/bin/env python3
"""Deterministic Search routing and budget planner for financial Skills."""

import argparse
import json
from pathlib import Path


PROFILES = {
    "company-analysis": {
        "max_calls": 3,
        "tool_order": ["seed_finance_search", "general_search"],
        "source_order": ["regulator_filing", "company_ir", "official_transcript", "reputable_secondary"],
        "query_stages": ["identity_period_and_filing", "latest_results_and_cashflow", "specific_risks_and_conflicts"],
    },
    "investment-opportunity-screening": {
        "max_calls": 5,
        "tool_order": ["seed_finance_search", "general_search"],
        "source_order": ["regulator_filing", "company_ir", "exchange_market_data", "reputable_secondary"],
        "query_stages": ["universe_definition", "candidate_primary_evidence", "financial_hard_filters", "theme_false_positives", "market_data_as_of"],
    },
    "private-market-project-evaluation": {
        "max_calls": 4,
        "tool_order": ["general_search", "seed_finance_search"],
        "source_order": ["company_primary", "counterparty_primary", "investor_primary", "regulator", "reputable_secondary"],
        "query_stages": ["entity_and_timeline", "funding_primary_sources", "commercialization_counterparty_check", "risks_and_unknowns"],
    },
    "wealth-planning": {
        "max_calls": 4,
        "tool_order": ["general_search", "seed_finance_search"],
        "source_order": ["government_rule", "regulator", "official_program", "professional_secondary"],
        "query_stages": ["jurisdiction_and_tax_year", "official_limits", "official_benefit_rules", "professional_boundaries"],
    },
    "event-impact-analysis": {
        "max_calls": 4,
        "tool_order": ["general_search", "seed_finance_search"],
        "source_order": ["law_or_regulation", "issuing_authority", "implementing_authority", "industry_primary", "reputable_secondary"],
        "query_stages": ["original_event_and_status", "consolidated_rules", "implementation_details", "affected_entities_and_conflicts"],
    },
}

CURRENT_RE = r"最新|当前|截至|近期|今日|现在|本周|本月|本季度|本年度|202[4-9]"
RULE_RE = r"政策|法规|监管|个税|所得税|税率|税务规则|税收|社保|公积金|养老金资格|养老待遇|关税|限制|合规|官方规则"
SEED_ELIGIBLE_RE = (
    r"公开产品|市场数据|利率|收益率|指数|基金.{0,8}(事实|数据|公告|材料)|"
    r"金融机构.{0,8}(公开|公告|材料|数据)"
)
EXPLICIT_DATA_REQUEST_RE = r"查|查询|搜索|检索|获取|提供|列出|核对|验证|截至|最新"
METHOD_ONLY_RE = r"模板|方法论|框架示例|如何分析|怎么分析|计算公式|空白表格"
USER_SOURCE_ONLY_RE = r"仅使用.{0,12}(附件|材料|数据)|只基于.{0,12}(附件|材料|数据)|封闭材料|closed.fixture"
AMBIGUOUS_RE = r"某.{0,4}(公司|项目|政策|事件|监管)|一家企业|一个标的|随便选|你帮我选"
WEALTH_PRIVATE_GAP_RE = (
    r"(?:没(?:有|提供)|未(?:提供|给出)|缺少|不知道|不清楚|待补|无法提供).{0,16}"
    r"(?:收入|支出|余额|资产|负债|APR|利率|最低还款|目标金额|目标期限|流水|保单|账户)"
    r"|(?:收入|支出|余额|资产|负债|APR|最低还款|目标金额|目标期限).{0,16}"
    r"(?:未知|缺失|没有|未提供|不清楚)"
)


def matches(pattern, text):
    import re

    return bool(re.search(pattern, text, flags=re.I))


def infer_signals(skill, prompt, context=None):
    """Infer routing signals when the user did not mention Search."""
    context = context or {}
    text = prompt or ""
    attachments_present = bool(context.get("attachments_present"))
    attachments_sufficient = bool(context.get("attachments_sufficient"))
    closed_fixture = bool(context.get("closed_fixture"))
    source_only = matches(USER_SOURCE_ONLY_RE, text)
    method_only = matches(METHOD_ONLY_RE, text)
    ambiguous = matches(AMBIGUOUS_RE, text)
    current = matches(CURRENT_RE, text)
    rules = matches(RULE_RE, text)
    seed_finance_requested = bool(context.get("seed_finance_requested")) or matches(
        r"seed_finance_search", text
    ) or (
        matches(SEED_ELIGIBLE_RE, text)
        and matches(EXPLICIT_DATA_REQUEST_RE, text)
    )
    needs_broad_universe = skill == "investment-opportunity-screening" and matches(
        r"筛选|候选池|选股|扫描|全市场|Top\s*\d+|排名|"
        r"哪些|有没有|有啥|找几家|挑几家|推荐几家",
        text,
    )

    object_frozen = context.get("object_frozen")
    if object_frozen is None:
        object_frozen = not ambiguous
    jurisdiction_frozen = context.get("jurisdiction_frozen")
    if jurisdiction_frozen is None:
        jurisdiction_frozen = bool(
            matches(
                r"中国大陆|中国香港|香港|美国|新加坡|欧盟|上海|北京|深圳|加州|纽约|人民币|美元|港元",
                text,
            )
        )

    needs_current_public_facts = current
    needs_public_rules = rules
    needs_private_data = False

    if skill == "company-analysis":
        needs_current_public_facts = (
            not method_only
            and not attachments_sufficient
            and matches(
                r"公司|股票|上市|财务|年报|季报|估值|现金流|"
                r"利润|经营|烧钱",
                text,
            )
        ) or current
    elif skill == "investment-opportunity-screening":
        needs_current_public_facts = (
            needs_broad_universe and not attachments_sufficient
        ) or current
    elif skill == "private-market-project-evaluation":
        needs_current_public_facts = (
            not attachments_sufficient
            and matches(r"公司|项目|融资|商业化|团队|客户|市场", text)
        )
        needs_private_data = matches(
            r"正式IC|完整尽调|交易条款|cap table|客户合同|数据室|精确IRR",
            text,
        )
    elif skill == "wealth-planning":
        needs_current_public_facts = seed_finance_requested
        needs_public_rules = rules
        needs_private_data = matches(WEALTH_PRIVATE_GAP_RE, text)
        if not jurisdiction_frozen and rules:
            object_frozen = False
    elif skill == "event-impact-analysis":
        needs_current_public_facts = (
            not attachments_sufficient
            and matches(r"事件|政策|监管|并购|制裁|关税|调查|限制|影响", text)
        ) or current

    if method_only:
        needs_current_public_facts = False
        needs_public_rules = False
    if source_only or closed_fixture:
        closed_fixture = True

    return {
        "skill": skill,
        "prompt": text,
        "as_of": context.get("as_of"),
        "route_status": context.get("route_status", "correct"),
        "object_frozen": bool(object_frozen),
        "jurisdiction_frozen": bool(jurisdiction_frozen),
        "attachments_present": attachments_present,
        "attachments_sufficient": attachments_sufficient,
        "closed_fixture": closed_fixture,
        "user_forbids_search": bool(context.get("user_forbids_search")),
        "needs_current_public_facts": bool(needs_current_public_facts),
        "needs_public_rules": bool(needs_public_rules),
        "needs_broad_universe": bool(needs_broad_universe),
        "needs_private_data": bool(needs_private_data),
        "seed_finance_requested": bool(seed_finance_requested),
        "inference": {
            "current_language": current,
            "rule_language": rules,
            "method_only": method_only,
            "source_only": source_only,
            "ambiguous_object": ambiguous,
            "seed_finance_eligible_language": matches(SEED_ELIGIBLE_RE, text),
        },
    }


def plan(payload):
    if "prompt" in payload and not any(
        key in payload
        for key in [
            "needs_current_public_facts",
            "needs_public_rules",
            "needs_broad_universe",
            "needs_private_data",
        ]
    ):
        payload = infer_signals(
            payload["skill"], payload["prompt"], payload.get("context")
        )
    skill = payload["skill"]
    profile = PROFILES[skill]
    if payload.get("closed_fixture") or payload.get("user_forbids_search"):
        mode, reason = "off", "closed fixture or user explicitly disabled Search"
    elif payload.get("route_status") == "wrong_task":
        mode, reason = "off", "route-only response"
    elif payload.get("inference", {}).get("method_only"):
        mode, reason = "off", "method, template or pure calculation task"
    elif not payload.get("object_frozen", False):
        mode, reason = "blocked", "object or jurisdiction is not frozen"
    elif payload.get("needs_private_data") and not (
        payload.get("needs_current_public_facts")
        or payload.get("needs_public_rules")
    ):
        mode, reason = "blocked", "missing information can only come from the user"
    elif (
        payload.get("attachments_present")
        and payload.get("attachments_sufficient")
        and (
            payload.get("needs_current_public_facts")
            or payload.get("needs_public_rules")
            or payload.get("needs_broad_universe")
        )
    ):
        mode, reason = "optional", "attachments are sufficient; Search may only corroborate"
    elif payload.get("needs_current_public_facts") or payload.get(
        "needs_public_rules"
    ) or payload.get("needs_broad_universe"):
        mode, reason = "required", "current public evidence is necessary"
    elif skill == "wealth-planning" and not payload.get(
        "needs_public_rules"
    ):
        mode, reason = "off", "household arithmetic does not require external rules"
    else:
        mode, reason = "optional", "Search can supplement but must not replace missing private inputs"

    max_calls = profile["max_calls"] if mode in {"required", "optional"} else 0
    if mode == "optional":
        max_calls = min(2, max_calls)
    seed_eligible = (
        skill == "wealth-planning"
        and bool(payload.get("seed_finance_requested"))
        and not payload.get("needs_public_rules")
        and mode in {"required", "optional"}
    )
    if mode in {"off", "blocked"}:
        provider_route = "none"
    elif payload.get("needs_public_rules"):
        provider_route = "general_search"
    elif seed_eligible:
        provider_route = "seed_finance_search"
    else:
        provider_route = "general_search"
    return {
        "mode": mode,
        "reason": reason,
        "skill": skill,
        "as_of": payload.get("as_of"),
        "max_calls": max_calls,
        "max_calls_is_hard_limit": True,
        "repair_calls_reserved_min": 1 if max_calls else 0,
        "source_order": profile["source_order"],
        "tool_order": profile["tool_order"],
        "provider_route": provider_route,
        "seed_finance_search": {
            "priority": "low",
            "eligible": seed_eligible,
            "inspect_host_schema": True,
            "unsupported_parameter_policy": "do_not_invent",
            "unavailable_fallback": "general_search",
            "database_is_official": False,
        },
        "query_stages": profile["query_stages"][:max_calls],
        "requirements": [
            "script availability is not task execution; help/import does not count",
            "transport status and evidence status are separate",
            "Seed standard market fields may be supported but never establish government rules",
            "secondary repetition does not upgrade a rule claim to supported",
            "all external numbers and household inputs must exist in their ledgers",
            "host-captured raw trace is preferred; model summary is not raw",
            "never issue a tool call after max_calls is exhausted",
            "freeze object, period, jurisdiction and deliverable before Search",
            "critical facts require primary or official evidence",
            "secondary sources may explain but cannot carry critical numbers",
            "unknown remains unknown when primary evidence is unavailable",
            "stop when the evidence contract is met; do not fill the call budget",
        ],
        "signals": {
            key: payload.get(key)
            for key in [
                "object_frozen",
                "jurisdiction_frozen",
                "attachments_present",
                "attachments_sufficient",
                "needs_current_public_facts",
                "needs_public_rules",
                "needs_broad_universe",
                "needs_private_data",
                "seed_finance_requested",
            ]
        },
        "inference": payload.get("inference", {}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = plan(payload)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
