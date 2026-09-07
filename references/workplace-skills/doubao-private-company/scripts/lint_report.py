#!/usr/bin/env python3
"""Shared V3 mode-aware report linter. Stdlib only."""

import argparse
import json
import re
from pathlib import Path


COMMON_BANNED = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"待补充",
    r"保证收益",
    r"稳赚(?:不赔)?",
    r"必然?(?:上涨|下跌)",
    r"强烈推荐(?:买入|卖出)",
    r"建议(?:立即|马上)?(?:买入|卖出|加仓|减仓)",
    r"目标价\s*[:：]?\s*[￥$¥]?\d",
    r"仓位\s*[:：]?\s*\d+(?:\.\d+)?%",
    r"(?:补证|材料)(?:全部)?(?:完成|齐备)后方可安排(?:管理层)?(?:初会|会议)",
    r"没有完整材料.{0,16}(?:无法|不能)评估(?:该|此)?项目",
    r"(?:满足|达到|收到|提供).{0,12}(?:\d+|[一二三四五六七八九十]+)\s*(?:项|条|类).{0,16}(?:安排|推进|进入|开放)",
]
INVALID_GAP_REFUSAL = re.compile(
    r"(?:缺少|没有|未提供).{0,24}(?:Term\s*Sheet|交易条款|审计财报|合同|cohort|私有财务|mandate)"
    r".{0,40}(?:无法|不能|不再|暂不)(?:评估|分析|回答|安排(?:管理层)?(?:初会|会议))",
    re.I,
)
DATA_ROOM_CONFLATION = re.compile(
    r"(?:进入|开放)数据室.{0,24}(?:等于|意味着|视为|即为).{0,12}(?:投资推进|立项|通过)",
    re.I,
)
ADJACENT_PRODUCT_PROOF = re.compile(
    r"(?:相邻|同类|关联方).{0,12}(?:产品|技术).{0,24}(?:证明|证实|说明).{0,16}(?:目标|该).{0,12}(?:技术|产品).{0,12}(?:商业化|收入)",
    re.I,
)
MEETING_SECTION = re.compile(r"(?:初会问题|首次管理层会议问题|kill\s*questions)", re.I)
MEETING_INCREMENT_LABELS = {
    "主体/技术": re.compile(r"主体\s*/\s*技术|主体与技术"),
    "收入回款": re.compile(r"收入(?:与|/)?回款|回款"),
    "临床增量": re.compile(r"临床增量"),
    "单位经济": re.compile(r"单位经济"),
    "交易": re.compile(r"交易"),
}
SENSITIVE = [
    r"\b\d{17}[\dXx]\b",
    r"\b\d{16,19}\b",
    r"\b1[3-9]\d{9}\b",
]
FACT_RE = re.compile(r"\{fact:([A-Za-z0-9_.-]+)\}")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sections(text):
    found = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = re.sub(r"^\[[^\]]+\]\s*", "", match.group(1)).strip()
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {name: "\n".join(body).strip() for name, body in found.items()}


def find_section(parsed, aliases):
    for alias in aliases:
        if alias in parsed:
            return alias, parsed[alias]
    return None, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("facts")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent.parent / "config" / "runtime.json"),
    )
    args = parser.parse_args()
    try:
        text = Path(args.report).read_text(encoding="utf-8")
        facts = load(args.facts)
        config = load(args.config)
    except Exception as error:
        print(f"ERROR: cannot load input: {error}")
        return 2

    errors = []
    warnings = []
    mode = facts.get("meta", {}).get("mode")
    mode_config = config.get("modes", {}).get(mode)
    if not mode_config:
        errors.append(f"unsupported or missing mode: {mode}")
        mode_config = {}
    parsed = sections(text)
    for spec in mode_config.get("required_sections", []):
        name, body = find_section(parsed, spec["aliases"])
        if not name:
            errors.append(f"missing section: {spec['aliases'][0]}")
            continue
        if len(re.sub(r"\s+", "", body)) < spec.get("min_chars", 20):
            errors.append(f"section too thin: {name}")
        if spec.get("fact_binding") and not FACT_RE.search(body):
            errors.append(f"section has no fact binding: {name}")

    patterns = COMMON_BANNED + config.get("banned_patterns", [])
    for pattern in patterns:
        if re.search(pattern, text, re.I):
            errors.append(f"banned pattern: {pattern}")
    if INVALID_GAP_REFUSAL.search(text):
        errors.append("invalid blanket refusal caused by a slot-scoped data gap")
    if DATA_ROOM_CONFLATION.search(text):
        errors.append("data-room access conflated with investment progression")
    if ADJACENT_PRODUCT_PROOF.search(text):
        errors.append("adjacent product used to prove target commercialization")
    if MEETING_SECTION.search(text):
        missing = [
            label
            for label, pattern in MEETING_INCREMENT_LABELS.items()
            if not pattern.search(text)
        ]
        if missing:
            errors.append(
                "first-meeting questions miss information increments: "
                + ",".join(missing)
            )
    if config.get("privacy_scan"):
        for pattern in SENSITIVE:
            if re.search(pattern, text):
                errors.append(f"sensitive data pattern: {pattern}")

    refs = set(FACT_RE.findall(text))
    known = {
        claim.get("claim_id")
        for claim in facts.get("claims", [])
        if isinstance(claim, dict) and claim.get("claim_id")
    }
    for ref in sorted(refs - known):
        errors.append(f"unknown fact binding: {ref}")
    if not refs:
        errors.append("report has no fact bindings")
    if "来源" not in text and "Sources" not in text:
        errors.append("source disclosure missing")
    if (
        "局限" not in text
        and "限制" not in text
        and "Limitations" not in text
    ):
        errors.append("limitations disclosure missing")
    if "不构成" not in text and "does not constitute" not in text.lower():
        errors.append("financial disclaimer missing")

    for item in warnings:
        print("WARNING:", item)
    for item in errors:
        print("ERROR:", item)
    print(
        f"SUMMARY errors={len(errors)} warnings={len(warnings)} "
        f"mode={mode} fact_bindings={len(refs)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
