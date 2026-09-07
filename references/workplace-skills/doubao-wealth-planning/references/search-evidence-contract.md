# Search 证据契约

Search 后先生成 `search-evidence.json`，再运行 `scripts/search_evidence_validator.py`。

工具调用状态与证据状态分开：`transport_status=success|error`；`evidence_status=supported|provisional|conflict|empty|unsupported|blocked`。多家普通二手重复不升级supported；工具成功但目标字段为空仍为empty。

Seed公开利率/收益率、指数/基金标准字段具备provider、产品/指数标识、field、as_of、unit/currency、reported/estimate且无冲突时，可由`authoritative_financial_database`承担，但不是政府或发行人原文。税法、社保、公积金、养老金资格和监管规则必须由适用辖区官方来源承担。

最终外部数字必须进入Claim ledger，家庭输入进入user-fact ledger，派生值需calculation与assumption记录。比较前统一期限、风险、流动性、税前税后、币种和as_of。原始轨迹优先宿主捕获，模型摘要不是raw。

每条 Claim 至少包含：

- `id`、`claim`、`critical`、`as_of`、`currency`、`unit`、`source_role`；
- 文档证据：`source_url`、`source_type`、`published_at`；
- 结构化数据库证据：`provider`、`dataset`、`record_id`、`field`、
  `as_of`，并提供底层公告 lineage 或标记为权威数据库；
- `supported`、`conflict`、`conflict_note`；
- 关键数字的 `period`、`currency`、`unit`；
- 规则类事实的适用辖区和年度。

`source_role` 用于区分 `government`、`regulator`、`official_program`、`financial_institution_primary`、`authoritative_financial_database`、`database_aggregator`、`professional_secondary`、`user_fact` 与 `derived`。合格Seed标准市场字段可标`authoritative_financial_database`；新闻/摘要或口径不完整记录仍标`database_aggregator`。二者都不得伪装成政府或发行人原文。

关键 Claim 必须由监管披露、公司/交易对手一手材料、政府规则或发布机关材料承担。二手来源只能解释机制。

Validator 未通过时：

1. 预算仍有剩余：只搜索失败 Claim；
2. 预算耗尽：删除无证据精确值，改为unknown或条件式结论；
3. 不得把Validator错误隐藏在最终回复中。

## 领域硬规则

- 用户提供的家庭数字标记为user_fact，不要求外部引用，也不得被Search覆盖。
- 税务、账户、福利和保障规则只接受适用年度的政府或监管来源。
- 税率、失业金、遣散费、再就业月份和市场回报未知时必须变量化，不得填情景默认值。
- Seed/数据库结果不等于官方来源；不得承载关键规则。满足字段契约的标准市场数字可直接支持，其他关键数字缺少底层lineage时保持provisional。
