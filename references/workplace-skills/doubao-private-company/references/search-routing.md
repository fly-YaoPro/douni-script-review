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
| `required` | 真实项目缺少附件但可用公开资料核验公司身份、融资、团队、产品、合作和监管背景。 |
| `optional` | BP和财务材料已提供，仅需交叉验证公开融资、客户公告或监管记录。 |
| `off` | 合成或封闭数据室任务，或只对用户材料做单位经济和跑道计算。 |
| `blocked` | 基金Mandate、项目身份或核心材料缺失；正式IC、合同条款、cap table等只能由用户提供。 |

执行前写入内部 `search-decision.json`，至少记录模式、理由、证据缺口、预算和来源顺序；该文件不向用户展示。

## 当前领域预算

- 最多调用：4 次。
- 双通道顺序：`general_search` 先冻结主体和公开事实，`seed_finance_search` 再补公开融资、机构研报、行业、上市可比与公开财务线索，关键事实最后回到一手原文核验。
- `seed_finance_search` 不可用时回退仅用 `general_search`；工具名仅限 `seed_finance_search` 与 `general_search`；参数以宿主 schema 为准，不发明。
- 来源顺序：`company_primary` → `counterparty_primary` → `investor_primary` → `regulator` → `reputable_secondary`。
- 查询阶段：
1. `entity_and_timeline`
2. `funding_primary_sources`
3. `commercialization_counterparty_check`
4. `risks_and_unknowns`

预算是上限，不是目标。证据契约满足后立即停止。

## 查询原则

1. 一次查询只解决一个证据缺口。
2. 查询词包含对象、期间、文档类型和官方域名意图。
3. 先原始文件，再解释材料；不得反向用媒体数字覆盖原始文件。
4. 搜索失败时记录缺口，不扩大到相邻对象。
5. 不得用金融库替代 BP、data room、cap table、Term Sheet、mandate 或交易条款；缺私有数据只局部降级。
6. 每次结果记录 tool、query、asof、source、period、unit、currency、reported-vs-estimate；库内结果不自动等于一手来源。

完整双通道、证据台账和回退要求见 `references/seed-finance-search-routing.md`。
