# Seed Finance Search 双通道路由

## 线上工具约定（必须按此工具名调用）

宿主 Agent 只暴露以下两个搜索工具，Skill 必须按**确切工具名**自主选用，不得写成 `document_search`、`structured_data`、`general_or_document_search` 等别名：

| 工具 | 用途 | 适用场景 |
|------|------|---------|
| `seed_finance_search` | 专业金融数据库搜索 | 财务数据、财报原文、券商研报、一致预期、公司公告、公开行情/估值、公开融资与机构观点 |
| `general_search` | 通用网页搜索 | 监管/公司原文、新闻事件、行业与经营事实、政府规则、交易对手与客户证据、独立交叉验证 |

两者可组合使用。`seed_finance_search` 不可用、报错或无覆盖时，回退仅用 `general_search`，不降低一手证据要求。库内命中不等于一手披露，关键数字仍应尽量回到监管/公司/政府原文。

## 本 Skill 路由顺序

默认顺序：`general_search` → `seed_finance_search`。
主体、投资方、交易对手、监管、产品与客户事实先用 `general_search`；公开融资、机构研报、上市可比与公开财务线索再用 `seed_finance_search`。不得用后者替代 BP/data room。


## 边界

`seed_finance_search` 仅用于公开金融研究线索：

- 公开融资轮次、金额、估值或投资机构线索；
- 机构研报、行业规模与行业基准；
- 上市可比公司及其公开财务线索。

公司主体、投资方、交易对手、监管、临床、产品和客户事实继续使用 `general_search`，并以公司、交易对手、监管机构或其他可承担该事实的一手文件核验。库内命中不自动等于一手来源。

不得用 `seed_finance_search` 替代 BP、data room、cap table、Term Sheet、fund mandate 或任何非公开交易条款。私有数据缺失只降级依赖该数据的结论，不得整体拒答。

## 双通道工作流

1. 先用 `general_search` 冻结主体、时间线、辖区和公开事实。
2. 再用 `seed_finance_search` 补公开融资、机构观点、行业和上市可比线索。
3. 对决定性事实和关键数字回到可承担该主张的一手原文核验；聚合库只保留为线索或二手证据。
4. 对机构估算与公司披露分别标记 `estimate` 与 `reported`，不得混写。
5. 同步证据台账，标记支持、反对、冲突和缺口；达到证据契约、结果重复或预算上限即停止。

事件式快速取数与原文核验分属两条通道：金融库负责发现和对比，官方/通用搜索负责确认身份、发布日期、报告期及原始披露。这一分工沿用 earnings-analysis 的“结果/预期数据 + 原始披露”双通道，以及 market-hotspot 的证据台账与来源核验门禁。

## 工具调用与回退

- 工具 schema 未知时，先读取宿主暴露的实际 schema，再按该 schema 调用；不得发明工具名、字段或参数。
- `seed_finance_search` 不可用、无权限、报错或无有效结果时，回退仅用 `general_search` 流程。
- `closed_fixture`、Search=`off` 或用户禁止联网时，不调用任一搜索工具。
- 回退不改变来源门禁，也不得把搜索摘要包装为 BP、data room 或交易文件。

## 查询与证据台账

每次结果至少记录：

- `tool`
- `query`
- `asof`
- `source`
- `period`
- `unit`
- `currency`
- `reported-vs-estimate`

同时记录 claim、来源类型、支持/反对/冲突/缺口状态及下一核验入口。字段缺失时写 `unknown`，不得猜测补齐。精确融资、财务或估值数字若无法回到可承担该主张的来源，只能作为待核验线索。
