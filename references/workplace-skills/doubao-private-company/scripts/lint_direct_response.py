#!/usr/bin/env python3
"""Lint user-facing direct responses before delivery. Stdlib only."""

import argparse
import re
from pathlib import Path


INTERNAL_MARKERS = [
    re.compile(r"\{fact:[^}]+\}"),
    re.compile(r"\b(?:facts\.json|analysis-plan|source-plan)\b", re.I),
]
TRADE_PATTERNS = [
    re.compile(r"建议(?:立即|马上)?(?:买入|卖出|加仓|减仓)"),
    re.compile(r"目标价\s*[:：]?\s*[￥$¥]?\d"),
    re.compile(r"仓位\s*[:：]?\s*\d+(?:\.\d+)?%"),
    re.compile(r"(?:保证收益|稳赚(?:不赔)?|必然?(?:上涨|下跌))"),
]
INVALID_BLANKET_REFUSALS = [
    re.compile(
        r"(?:缺少|没有|未提供).{0,24}(?:Term\s*Sheet|交易条款|审计财报|合同|cohort|私有财务|mandate)"
        r".{0,40}(?:无法|不能|不再|暂不)(?:评估|分析|回答|安排(?:管理层)?(?:初会|会议))",
        re.I,
    ),
    re.compile(r"(?:补证|材料)(?:全部)?(?:完成|齐备)后方可安排(?:管理层)?(?:初会|会议)"),
    re.compile(r"没有完整材料.{0,16}(?:无法|不能)评估(?:该|此)?项目"),
]
MECHANICAL_GATE = re.compile(
    r"(?:满足|达到|收到|提供).{0,12}(?:\d+|[一二三四五六七八九十]+)\s*(?:项|条|类).{0,16}(?:安排|推进|进入|开放)",
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
CRITICAL_NUMBER = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:%|个百分点|亿元|万元|万美元|倍|美元|人民币|港元)|"
    r"(?:PE|PB|PS|EV/EBITDA|IRR|MOIC)\s*[:：]?\s*\d)",
    re.I,
)
URL = re.compile(r"https?://\S+")
LOW_QUALITY = re.compile(
    r"(?:xueqiu\.com|caifuhao\.eastmoney\.com|book118\.com|renrendoc\.com|"
    r"wenku\.baidu\.com|docin\.com|fanwen|csdn\.net|cofool\.com)",
    re.I,
)


def paragraphs(text):
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("response")
    parser.add_argument("--route-only", action="store_true")
    parser.add_argument("--prompt", default="")
    args = parser.parse_args()
    text = Path(args.response).read_text(encoding="utf-8")
    errors = []
    warnings = []
    prompt_numbers = {
        match.group(0).replace(" ", "") for match in CRITICAL_NUMBER.finditer(args.prompt)
    }

    for pattern in INTERNAL_MARKERS:
        if pattern.search(text):
            errors.append(f"internal marker exposed: {pattern.pattern}")
    for pattern in TRADE_PATTERNS:
        if pattern.search(text):
            errors.append(f"unsafe action language: {pattern.pattern}")
    for pattern in INVALID_BLANKET_REFUSALS:
        if pattern.search(text):
            errors.append(f"invalid blanket refusal: {pattern.pattern}")
    if MECHANICAL_GATE.search(text):
        errors.append("mechanical count threshold used as a decision gate")
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
    parts = paragraphs(text)
    for index, paragraph in enumerate(parts, 1):
        nearby = "\n".join(parts[max(0, index - 2) : min(len(parts), index + 1)])
        paragraph_numbers = {
            match.group(0).replace(" ", "")
            for match in CRITICAL_NUMBER.finditer(paragraph)
        }
        user_supplied = bool(paragraph_numbers & prompt_numbers)
        if CRITICAL_NUMBER.search(paragraph) and not URL.search(nearby) and not user_supplied:
            errors.append(f"paragraph {index}: critical number has no inline URL")
        if CRITICAL_NUMBER.search(paragraph) and LOW_QUALITY.search(paragraph):
            warnings.append(f"paragraph {index}: critical number uses low-quality source")
    if args.route_only:
        if len(text) > 800:
            errors.append("route-only response exceeds 800 characters")
        if re.search(r"##\s+(?:财务|估值|候选|情景|投资观点)", text):
            errors.append("route-only response continued into domain analysis")
    if "不构成" not in text and not args.route_only:
        warnings.append("financial disclaimer missing")

    for warning in warnings:
        print("WARNING:", warning)
    for error in errors:
        print("ERROR:", error)
    print(f"SUMMARY errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
