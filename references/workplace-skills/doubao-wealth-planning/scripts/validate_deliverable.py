#!/usr/bin/env python3
"""Validate final response completeness before user delivery."""

import argparse
import hashlib
import json
import re
from pathlib import Path


URL_RE = re.compile(r"https?://[^\s)\]>）】；，。]+")
INTERNAL_MARKERS = (
    "DETERMINISTIC TOOL OUTPUT",
    "VERIFIED COMPACT EVIDENCE",
    "evidence-validation.json",
    "_call",
)


def validate(text, contract, base_dir=None):
    failures = []
    warnings = []
    length = len(text)
    if length < contract.get("min_chars", 0):
        failures.append(f"response too short: {length}")
    if contract.get("target_chars") and length > contract["target_chars"]:
        warnings.append(
            f"response exceeds soft target: {length} > {contract['target_chars']}"
        )
    if contract.get("max_chars") and length > contract["max_chars"]:
        failures.append(f"response exceeds hard length limit: {length}")
    if contract.get("response_status") == "incomplete":
        failures.append("API response status is incomplete")
    if contract.get("finish_reason") in {"length", "max_tokens"}:
        failures.append(
            f"response stopped by token limit: {contract['finish_reason']}"
        )
    lowered = text.lower()
    missing = []
    for section in contract.get("required_any", []):
        aliases = section if isinstance(section, list) else [section]
        if not any(alias.lower() in lowered for alias in aliases):
            missing.append(" / ".join(aliases))
    if missing:
        failures.append("missing required sections: " + "; ".join(missing))
    urls = URL_RE.findall(text)
    if len(set(urls)) < contract.get("min_urls", 0):
        failures.append(
            f"insufficient source URLs: {len(set(urls))} < {contract['min_urls']}"
        )
    for marker in INTERNAL_MARKERS:
        if marker.lower() in lowered:
            failures.append(f"internal marker leaked: {marker}")
    for pattern in contract.get("forbidden_patterns", []):
        if re.search(pattern, text, flags=re.I):
            failures.append(f"forbidden pattern: {pattern}")
    for phrase in contract.get("required_phrases", []):
        if phrase.lower() not in lowered:
            failures.append(f"missing required phrase: {phrase}")
    if text.rstrip().endswith(("：", ":", "、", "-", "|")):
        failures.append("response appears truncated")
    if text.count("```") % 2:
        failures.append("unclosed code fence")
    last_lines = [
        line.strip() for line in text.rstrip().splitlines() if line.strip()
    ]
    if last_lines and re.match(r"^#{1,6}\s+", last_lines[-1]):
        failures.append("response ends with an empty heading")
    if contract.get("answer_first_any"):
        prefix = text[: contract.get("answer_first_chars", 250)].lower()
        aliases = contract["answer_first_any"]
        if not any(alias.lower() in prefix for alias in aliases):
            failures.append("direct answer missing from opening")
    if contract.get("claim_ledger") is not None:
        required_claim_fields = set(contract.get("claim_required_fields", []))
        for index, claim in enumerate(contract["claim_ledger"]):
            missing_fields = sorted(required_claim_fields - set(claim))
            if missing_fields:
                failures.append(
                    f"claim_ledger[{index}] missing fields: {missing_fields}"
                )
            if claim.get("claim_type") == "unknown" and not claim.get("unknown_resolution"):
                failures.append(
                    f"claim_ledger[{index}] unknown lacks unknown_resolution"
                )
    base_dir = Path(base_dir) if base_dir else None
    for artifact in contract.get("artifact_paths", []):
        path = (base_dir / artifact).resolve() if base_dir else Path(artifact).resolve()
        if not path.is_file():
            failures.append(f"artifact missing: {artifact}")
            continue
        expected_hash = contract.get("artifact_hashes", {}).get(artifact)
        if expected_hash:
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                failures.append(f"artifact hash mismatch: {artifact}")
    full_counts = contract.get("full_counts")
    compact_counts = contract.get("compact_counts")
    if isinstance(full_counts, dict) and isinstance(compact_counts, dict):
        for key, value in compact_counts.items():
            if full_counts.get(key) != value:
                failures.append(f"full/compact count mismatch: {key}")
    before = set(contract.get("source_ids_before", []))
    after = set(contract.get("source_ids_after", []))
    if before or after:
        added = sorted(after - before)
        if added:
            failures.append(f"source-locked finalizer added source_ids: {added}")
    if contract.get("finalizer_run_count", 0) > 1:
        failures.append("source-locked finalizer ran more than once")
    return {
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "stats": {
            "chars": length,
            "urls": len(set(urls)),
            "required_sections": len(contract.get("required_any", [])),
            "missing_sections": len(missing),
        },
        "repair_instructions": [
            "Use only facts and URLs already present in the evidence package.",
            "Do not add assumptions, thresholds, probabilities or new facts.",
            *failures,
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("response")
    parser.add_argument("contract")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = Path(args.response).read_text(encoding="utf-8")
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    result = validate(text, contract, Path(args.response).resolve().parent)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
