# Search 证据契约

Search 后先生成 `search-evidence.json`，再运行 `scripts/search_evidence_validator.py`。

工具调用状态与证据状态分开：`transport_status=success|error`；`evidence_status=supported|provisional|conflict|empty|unsupported|blocked`。多家普通二手重复不升级supported；工具成功但目标字段为空仍为empty。只有supported可进入“已验证事实”并推动对应capability gate。

Seed可承担上市可比的合格标准金融字段，但不是公司披露；不得仅靠Seed支持私营目标公司的融资估值、收入、客户、合同或交易条件。最终外部数字和公司事实必须进入Claim ledger，派生单位经济/估值/回报需calculation与assumption记录。

比较前统一法人、产品、期间、地域、权益边界、分母、单位和reported/estimate；不可比数据不得拼区间、倍数或排名。原始轨迹优先宿主捕获，模型摘要不是raw。

每条 Claim 至少包含：

- `id`、`claim`、`critical`；
- 文档证据：`source_url`、`source_type`、`published_at`；
- 结构化数据库证据：`provider`、`dataset`、`record_id`、`field`、
  `as_of`，并提供底层公告 lineage 或标记为权威数据库；
- `supported`、`conflict`、`conflict_note`；
- 关键数字的 `period`、`currency`、`unit`；
- 规则类事实的适用辖区和年度。

关键 Claim 必须由能够直接承担该主张的公开核验来源支持。证据池不局限于财报：可包括监管注册、可购产品、政府采购、渠道、客户/医院、用户与支付方材料。不同来源只升级其直接证明的状态；二手来源只能解释机制。

Validator 未通过时：

1. 预算仍有剩余：只搜索失败 Claim；
2. 预算耗尽：删除无证据精确值，改为unknown或条件式结论；
3. 不得把Validator错误隐藏在最终回复中。

## 领域硬规则

- 融资、合作、试点、生产部署、付费合同必须使用不同状态标签。
- 未上市公司的收入、毛利、烧钱、估值、合同和条款无可承担该主张的核验证据时一律unknown。媒体融资和公司自述不能升级付款、收入确认或复购。
- 技术、商业化和收入 Claim 必须记录 `target_product`、`target_legal_entity` 与 `target_match=true`；相邻产品或关联法人只能作线索。
- 商业化状态按监管注册、可购、采购、部署、用户采用、支付、收入确认和复购分别记录，禁止跨级升级。
- 冻结点后的来源不得进入事实台账；行业平均不能替代项目单位经济。
