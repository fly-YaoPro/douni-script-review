# Seed Finance Search 双通道路由

## 线上工具约定（必须按此工具名调用）

宿主 Agent 只暴露以下两个搜索工具，Skill 必须按**确切工具名**自主选用，不得写成 `document_search`、`structured_data`、`general_or_document_search` 等别名：

| 工具 | 用途 | 适用场景 |
|------|------|---------|
| `seed_finance_search` | 专业金融数据库搜索 | 公开产品/市场数据、利率/收益率、指数/基金公开事实、金融机构公开材料 |
| `general_search` | 通用网页搜索 | 税法、社保、公积金、养老金资格、监管规则、政府/官方计划材料、一般公开事实与交叉验证 |

两者可组合使用。`seed_finance_search` 不可用、报错或无覆盖时，回退仅用 `general_search`，不降低一手证据要求。库内命中不等于官方来源。

## 本 Skill 路由顺序

默认顺序：`general_search`；仅在用户明确要求公开产品/市场/利率/基金等金融数据时，再按需追加 `seed_finance_search`。
税法、社保、公积金、养老金资格与监管规则必须用 `general_search` 查政府/监管/官方来源；`seed_finance_search` 不得承担规则类证据。

## 硬边界

- `seed_finance_search` 不是默认工具，优先级低。
- 规则类 Claim 不得由 `seed_finance_search` 承担或补足。
- `closed_fixture` 或 Search=`off` 时调用次数必须为 0。
- 参数以宿主 schema 为准，不得发明。
