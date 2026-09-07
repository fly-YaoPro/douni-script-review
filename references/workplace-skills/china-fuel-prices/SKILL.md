---
name: china-fuel-prices
description: Use when the user invokes $china-fuel-prices or asks for workflows supported by the China Fuel Prices MCP.
---

# China Fuel Prices

## Overview

Use this skill for requests that should be answered through the China Fuel Prices MCP. The verified scope is limited to the operations listed in the K-column tool catalog supplied for this version.

## Core Rules

- Use the bound `china-fuel-prices` MCP only when its live callable tools are available in the current runtime.
- Select the narrowest live callable operation that directly answers the request and follow its current callable interface.
- Do not invent provider facts, identifiers, statuses, dates, records, or capabilities from memory.
- Keep secrets, private content, and authorization material out of prompts, logs, and final answers.
- Do not use shell commands, direct HTTP calls, or hand-written JSON-RPC to recreate, probe, or simulate the MCP server.
- Treat provider output as evidence and label calculations or interpretation separately.
- Require explicit confirmation before any external write, send, purchase, order, deletion, publication, merge, or permission change.

## Tools

- `查询行情`: Queries fuel-price adjustment ranges and the latest and next update dates.
- `查询油价`: Queries the latest fuel prices for a specified province.
- Select the narrowest live callable tool that directly answers the request. Follow the live callable interface for current inputs, outputs, and errors.

## Workflow

1. Identify the relevant entity or resource, identifier, scope, date or time range, filters, and requested output.
2. Classify the request as lookup, retrieval, search, analysis, creation, update, export, deletion, sending, purchase, permission change, or another provider operation before routing.
3. Resolve ambiguous identifiers with a live lookup when available; never guess a code, ID, path, record, or account.
4. Pass only supported arguments and preserve provider pagination, status, units, timestamps, and returned identifiers.
5. Chain operations only when a returned identifier, status, or structured result is required by the next operation.
6. Inspect the outer MCP error and provider status before reading result fields. Do not treat an empty or partial response as success without reporting its scope.

## Query Guidance

- Ask only for missing inputs required to choose or safely execute the operation.
- Preserve the user's requested scope and normalize names, dates, identifiers, or formats only when the mapping is unambiguous; state any normalization.
- Keep unrelated entities, time windows, accounts, and writes separate.
- State filters, result limits, sort order, output format, and data time when available.
- Add only provider-specific required context and confirmation boundaries supported by the K-column catalog.

## Failure Handling

- If no live China Fuel Prices callable tool is present, stop MCP execution and report that the connector is unavailable in the current runtime.
- For authorization, quota, timeout, invalid-argument, permission, provider, or missing-tool errors, report the failed operation without exposing secrets.
- Retry at most once only after a safe correction such as narrowing scope, supplying a known identifier, reducing result limits, or removing an unsupported optional field.
- For empty or partial results, report the exact query scope and provider status; do not fill missing fields from memory or another source.
- If the user specifically requests this connector, do not silently substitute another provider. State the connector failure first and offer a clearly labeled fallback only if the user wants it.

## Result Contract

- Separate returned provider facts from model interpretation and derived calculations.
- Preserve identifiers, URLs, paths, dates, timestamps, units, filters, page scope, totals, status, and provider caveats when returned.
- Do not describe one page, sample, or preview as complete unless the provider confirms completeness.
- Repeat only the highest-risk provider-specific caveat when it materially affects the result.
