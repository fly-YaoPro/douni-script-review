# 财富规划 facts.json

## 顶层结构

```json
{
  "meta": {
    "case_type": "wealth-planning",
    "as_of": "YYYY-MM-DD",
    "market_or_jurisdiction": "",
    "mode": ""
  },
  "claims": [],
  "assumptions": [],
  "data_gaps": [],
  "payload": {
    "household": null, "cash_flow": null, "assets": null, "liabilities": null, "goals": null, "assumptions": null
  }
}
```

## Claim

```json
{
  "claim_id": "unique-id",
  "statement": "读者可理解的事实或判断",
  "claim_type": "fact|estimate|inference|assumption|management_claim",
  "as_of": "YYYY-MM-DD",
  "period": "YYYY / YYYY-Qx / as-of date",
  "value": null,
  "unit": "",
  "currency": "",
  "source": "材料名称",
  "source_date": "YYYY-MM-DD",
  "source_role": "government|regulator|official_program|financial_institution_primary|database_aggregator|professional_secondary|user_fact|derived",
  "url": "",
  "confidence": "high|medium|low",
  "calculation": "",
  "input_claims": []
}
```

## 硬规则

- claim_id 唯一且只含字母、数字、点、下划线和短横线。
- fact 和 management_claim 必须有来源与日期；无公开 URL 可留空，但来源名不可空。
- estimate/inference/assumption 必须使用限制语。
- value 存在时必须填写 unit；涉及金额时填写 currency。
- 每条 Claim 均记录 as_of、currency、unit 和 source_role；不适用的币种或单位显式写 `N/A`。
- Seed/数据库结果使用 `database_aggregator`，不得直接标记为官方来源。
- calculation 存在时必须列 input_claims。
- data_gaps 写明缺什么、影响哪个结论、如何补齐。

完整机器示例见 `schemas/facts.example.json`，交付前运行 `validate_facts.py`。
