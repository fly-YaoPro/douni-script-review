# Search 路由与预算

## 决策

- `off`：Closed-fixture、错误路由、用户禁止Search。
- `required`：当前公开事实、规则、市场数据或公开候选池是完成任务的必要输入。
- `optional`：用户材料已足够，仅需补证。
- `blocked`：对象未冻结，或缺口只能由用户提供的私有材料补齐。

先运行 `scripts/search_router.py`。`blocked` 时先澄清，不得用同名对象或行业平均替代。

用户无需主动说明是否联网。根据任务对象、材料充分性、时效性和规则依赖自主判断：

| 模式 | 当前领域判断标准 |
|---|---|
| `required` | 需要适用年度和辖区的税务、社保、公积金、养老金、失业保障、存款保险或监管规则。 |
| `optional` | 用户已提供官方规则或通知，仅需核对有效期和适用范围。 |
| `off` | 只基于用户数字计算预算、现金跑道和目标缺口，不涉及外部政策或产品事实。 |
| `blocked` | 国家/地区、税务居民或地方缴存地未确认，却要求给出辖区规则和精确待遇。 |

执行前写入内部 `search-decision.json`，至少记录模式、理由、证据缺口、预算和来源顺序；该文件不向用户展示。

## 工具路由

按以下优先级选择；Seed 仅是低优先级兼容路径：

1. 税法、社保、公积金、养老金资格、监管规则：只用 `general_search`（查询政府/监管/官方来源），并以政府、监管或官方计划材料闭合证据。
2. 用户明确要求公开产品/市场数据、利率/收益率、指数/基金公开事实或金融机构公开材料：可按需使用 `seed_finance_search`。
3. 其他公开事实：使用 general search；不得为了调用 Seed 扩大问题范围。

`seed_finance_search` 的硬边界：

- Closed fixture、用户禁搜或 Search=`off`：不调用。
- 仅在对象、期间、币种和结论槽位已冻结后调用。
- 调用前检查宿主 schema，只使用明示字段；工具名仅限 `seed_finance_search` 与 `general_search`，不发明参数。
- 工具不可用、未暴露、超时或失败：记录 `seed_unavailable`，回退 `general_search`（查询政府/监管/官方来源）；P2 也失败则将 Claim 降为 unknown。
- 结果属于数据库/聚合检索证据，不自动升级为官方来源；关键数字必须追溯到底层官方、交易所、基金管理人或金融机构一手材料。
- 不用它推荐、排序或销售具体产品，不用它填补家庭收入、支出、资产、负债、目标、风险偏好或风险承载能力，也不替代持牌意见。

## 当前领域预算

- 最多调用：4 次。
- 默认工具顺序：`general_search`（查询政府/监管/官方来源） → 一手材料核验。
- 仅命中上述显式适用范围时：`general_search`（查询政府/监管/官方来源） → `seed_finance_search`（按需）→ 一手材料核验。
- 来源顺序：`government_rule` → `regulator` → `official_program` → `professional_secondary`。
- 查询阶段：
1. `jurisdiction_and_tax_year`
2. `official_limits`
3. `official_benefit_rules`
4. `professional_boundaries`

预算是上限，不是目标。证据契约满足后立即停止。

## 查询原则

1. 一次查询只解决一个证据缺口。
2. 查询词包含对象、期间、文档类型和官方域名意图。
3. 先原始文件，再解释材料；不得反向用媒体数字覆盖原始文件。
4. 搜索失败时记录缺口，不扩大到相邻对象。
5. Claim ledger 必须记录 `as_of`、`currency`、`unit`、`source_role` 和底层来源；数据库结果不得标成 government/official。
