#!/usr/bin/env python3
"""Validate and correct directional cash-runway claims."""

import argparse
import re
from pathlib import Path


def finalize(text, cash, outflow, income_variable):
    baseline = cash / outflow
    baseline_text = f"{baseline:.2f}"
    corrections = 0
    pattern = re.compile(
        rf"(0\s*[≤<]\s*{re.escape(income_variable)}\s*<\s*{outflow:,.0f}"
        rf".{{0,180}}?)([≤<])\s*{re.escape(baseline_text)}",
        flags=re.S,
    )

    def replace(match):
        nonlocal corrections
        corrections += 1
        return match.group(1) + "≥" + baseline_text

    text = pattern.sub(replace, text)
    direct_pattern = re.compile(
        rf"(现金跑道\s*)[≤<]\s*{re.escape(baseline_text)}"
    )
    text, direct_count = direct_pattern.subn(
        rf"\1≥{baseline_text}", text
    )
    corrections += direct_count
    text = re.sub(
        r"\n?\d+\.\s*预警线设置：以“现金跑道剩余\d+(?:个月)?”[^。\n]*。?",
        "\n",
        text,
    )
    authoritative = (
        f"当 0≤{income_variable}<{outflow:,.0f} 时，跑道="
        f"{cash:,.0f}/({outflow:,.0f}-{income_variable})，"
        f"因此不短于零收入基线 {baseline_text} 个月；"
        f"当 {income_variable}≥{outflow:,.0f} 时，经常性现金流不消耗该现金池。"
    )
    if authoritative not in text:
        text = text.rstrip() + "\n\n" + authoritative + "\n"
    return text, corrections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("response")
    parser.add_argument("--cash", type=float, required=True)
    parser.add_argument("--outflow", type=float, required=True)
    parser.add_argument("--income-variable", default="I")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.response)
    text, corrections = finalize(
        path.read_text(encoding="utf-8"),
        args.cash,
        args.outflow,
        args.income_variable,
    )
    output = Path(args.output) if args.output else path
    output.write_text(text, encoding="utf-8")
    print(f"corrections={corrections}")


if __name__ == "__main__":
    main()
