---
name: doubao-private-company
description: 评估一级市场、私募股权或创业项目的初步投资价值，基于BP、Deck、财务和访谈资料输出Screening Report、投资逻辑、红旗、情景、尽调缺口和初步建议。用于项目初筛、是否进入下一轮尽调或是否安排首次会议。不要替代完整尽调、法律意见或正式IC审批。
---

# 一级投资项目评估

## 线上最高优先级规则：输出硬模板（覆盖后文示例）

无附件自然问答只交付正文：不创建文件、不修脚本Schema、不输出内部过程。以下五条优先于本文件其余内容。约束的是"数字怎么归位、怎么标注"，不是"少写内容"；不得用减少分析深度的方式满足本节。

### 规则1 身份核验与问题长短无关

问题再短、看起来再简单，也必须先联网核验以下四类，然后才能写结论：

- 主体身份：是否仍独立存在、上市/退市/被收购/私有化/更名、交易所与证券代码；
- 规则身份：政策、法规、条款是否已由发布机关正式发布，以及生效日；
- 期间口径：报告期、单位、币种、as-of；
- 冲突：同一字段搜到两个不同值时两个都写出，不擅自择一。

复杂度路由只决定篇幅和槽位数量，不决定是否核验。未通过核验的主体或规则不得进入结论段和摘要段，只能进"待核清单"。

### 规则2 精确数字逐条带来源标记

正文出现的金额、百分比、倍数、税率、概率、期限、份额、增速、评分，其后必须紧跟一个标记：

- `[一手·发布方·文件名·日期]`：发布机关、监管、交易所、公司公告或IR原文；
- `[库·provider·as_of]`：`seed_finance_search` 返回的标准化金融字段；
- `[用户·自述]`、`[用户·账户记忆]`：用户在本次或历史对话中给出的事实，不需要外部来源；
- `[推算·公式]`：由上述任一来源经明确公式算出的派生值，括号内必须写出输入项和公式；
- `[阈值·分析设定]`：判定门槛、观察窗口、证伪触发值等由分析方自己设定的数字，例如推翻信号里的临界值和分档表的档位边界。标注时必须写明这是设定值而非观测值，并说明设定理由；不得把设定值写成市场共识或行业标准。
- `[待核·媒体]`、`[待核·研报]`、`[待核·模型记忆]`：二手转述、无检索来源或凭先验写出的值。

每个精确数字都必须落进上面某一类，不存在"没有合适标签所以不标"的情况。写不出前四种标记时，不要删掉数字，也不要改写成"较高/大幅"这类模糊表述，直接标 `[待核·…]`。段首或文末的整段来源声明不能替代逐条标记。某一段内 `[待核·…]` 数量不少于其他标记数量时，该段小结必须自称"待核结论"。

### 规则3 关键输入缺失时改写成分档表，不假设也不拒答

关键输入未知时，被禁止的是"替用户假设一个值"，不是"给出可执行内容"。把结论改写为以该未知量为自变量的分档表：

| 档位 | 触发条件（未知量取值区间） | 该档下的动作方向与优先顺序 | 该档被推翻的信号 |

分档表给方向、顺序和取舍理由，不给依赖该未知量的精确金额或比例。结尾列出"补齐哪几项后可给精确值"，最多5项，每项写清为什么需要它。

### 规则4 无一手来源的量级只能进假设卡

分析必须用到某个量级但没有一手来源时，写成独立的"假设卡"：

- 卡头写 `假设来源=先例类比|媒体口径|用户给定`，并写出该先例或口径与当前对象至少一条实质差异；
- 卡内数字按规则2标 `[待核·…]`；
- 摘要段和结论段不得复述卡内数字，只能写"见假设卡"。

不得把相邻品类、相邻政策、历史先例或同行的参数直接当作当前对象的参数；引用先例必须标为"先例参照值"。

### 规则5 开头固定为可审计摘要，不超过5行

1. 直接结论，或明确说明当前只能给条件式结论；
2. 支撑该结论的最强单条证据及其来源等级；
3. 最大的一个未知项；
4. 证据强度：`一手充分` / `部分一手` / `仅二手待核`；
5. 一条会推翻结论的信号。

摘要纪律（可执行判据）。摘要位置在最前，但**写作顺序在最后**：先把正文和全部来源标记写完，再回到开头补写摘要。这样过滤发生在分类完成之后，不需要预判。

写摘要时只做检索，不做新的判断：

- 写第2行之前，先在正文里检索一遍是否存在带 `[一手·…]` 或 `[库·…]` 标记的句子。**这一步是前置判断，不是事后补救**：检索不到就直接写兜底行，不许降格用 `[待核·…]` 顶替最强证据。
- 检索到时，从中**原样摘抄一句**，连同标记一起复制。不得现写、不得改写数字、不得把两句合并成一句。
- **摘要每一行只能来自一次摘抄，摘抄完即结束该行**：复制完那一句就换行，不得在同一行后面继续拼接其他来源、补充推论或无标记的比较值。
- 摘要其余各行如需引用数字，同样只能从正文中已标 `[一手·…]`、`[库·…]`、`[用户·…]` 的句子里摘抄。
- `[推算·…]` 只有在正文中已写出算式、且算式输入全部属于上述三类时，才可连同算式一起摘抄。
- `[待核·…]` 的数字一律不进摘要。正文里有、摘要里没有，是正常且正确的结果。
- **第5行"推翻信号"是摘抄规则的唯一例外**：证伪触发值按定义是在写摘要时设定的，正文里没有原句可抄。因此这一行允许现写数字，但必须标 `[阈值·分析设定]` 并写明设定理由，不得因为抄不到就不标。
- 前置检索为空时，第2行固定写"当前无一手或库级证据支撑，结论为条件式"，并且整个摘要不出现任何数字。这是正确结果，不是降级，也不要为了让摘要"看起来有料"而破例。

交付前自检两项：一是摘要里的每个数字都必须能在正文中找到带相同标记的原句，找不到就说明是现写的，删掉或换成正文里的合格句子；二是摘要每一行只对应正文里的一句原句，出现两个来源拼接就拆行或删掉后半段。

### 本Skill补充（同等优先级）

- 目标公司的融资额、估值、收入、ARR、客户数、份额和产品性能一律按规则2逐条标注；仅来自媒体或转述的一律标 `[待核·媒体]`。
- 倍数、估值区间、回报、折价只能出现在假设卡内，卡头写清每个输入的来源等级；任一输入为 `[待核·…]` 时，结果自称"口径演算，不作估值结论"。
- 材料层级分档交付：先写"仅凭公开信息能判断什么"，再写"进数据室后能判断什么"，最后写"见到条款后能判断什么"。
- 初会问题只问口径、验证方式和材料清单，不预设百分比、月数、天数或倍数阈值。

## 任务定义

对一级市场项目做Screening级别判断，连接基金mandate、商业质量、单位经济、团队、交易、红旗和下一轮尽调。

- 输入：公司名、BP、Deck、财务资料等
- 输出：Screening Report、初步投资建议
- 定位：L2 业务任务执行器，不扮演专家人格。

## 适用与不适用

### 适用

- 用户提供 BP、Deck、CIM、Teaser、财务或项目描述，希望判断是否值得继续看。
- 基金或投资团队需要按投资标准做项目初筛。
- 需要形成进入尽调、条件进入或暂缓/放弃的初步建议。

### 不适用

- 正式 IC Memo、LBO 模型或完整商业/财务/法务尽调，应进入后续专项 Skill。
- 上市公司二级市场分析，使用 company-analysis。
- 个人财富规划，使用 wealth-planning。

不适用时只返回正确相邻任务和下一步输入，然后停止。

## 成功定义与交付物

| 模式 | 成功 | 降级 | 停止 |
|---|---|---|---|
| 快速初筛 | 分别判断研究观点、信息收集型初会、数据室信息获取和投资推进能力；可答部分先答。 | 私有材料不足时保留公开研究、条件式初会及适用的数据室信息获取建议，只暂停受影响槽位。 | 请求实际是上市公司研究或正式IC审批。 |
| 完整 Screening | 商业、市场、单位经济、团队、交易、情景、红旗、尽调问题与条件建议一致。 | 缺条款时can_compute_returns=false，只给公式和数据需求。 | 材料身份不明或命中基金Hard Pass。 |
| 聚焦核查 | 围绕单位经济、团队、估值条款或指定红旗给出证据、反方和验证请求。 | 管理层数据只作management claim。 | 用户要求完整LBO、正式IC Memo或专项尽调。 |

标准交付物：`screening-report.md`、`management-claims.json`、`red-flags.json`、`diligence-requests.md`。

## 专业能力地图与深度边界

负责：mandate_fit、business_quality、unit_economics、team_and_governance、deal_quality、conditional_recommendation。

不负责：正式IC批准、完整LBO模型、完整三表或独立DCF、法律税务尽调、Term Sheet谈判。

更深能力路由：`lbo-analysis`、`ic-memo`、`cap-table-modeling`、`commercial-due-diligence`、`legal-tax-due-diligence`。

## 模式路由

用户无需指定模式。先执行交付复杂度路由，再选择领域分析模式；复杂度改变输出长度和槽位，不改变事实、计算和安全门禁。

## 首轮决策

1. **错误路由**：说明正确任务并停止；默认不 Search。
2. **拆分结论槽位**：mandate fit、商业/技术质量、估值方法、交易可行性、回报可计算性、下一动作分别判定。
3. **缺局部输入**：先回答可答部分；初会最多给 5 个问题，分别覆盖主体/技术、收入回款、临床增量、单位经济和交易，只暂停受影响槽位。
4. **输入足够**：冻结对象、as-of、辖区、模式和交付物后执行。

Search 只能补证，不能代替用户附件、候选池、基线、家庭数据、mandate 或交易条款。对象冻结前不得搜索同名对象并据此替用户选择。

## 交付复杂度路由

先运行 `scripts/complexity_router.py`。`direct` 用于一个自然问题，先回答再补最多两个问题；`brief` 用于聚焦多步骤分析；`full` 仅在用户明确要求完整报告或多工件时启用。搜索复杂度不得自动放大正文。详见 `references/complexity-routing.md`。

`direct` 不是免核验档：篇幅可以只有几行，但规则1的身份、规则状态和期间口径核验必须照做，凭模型记忆写出的主体状态或数字一律标 `[待核·模型记忆]`。

## 线上运行档案

按本任务脚本执行证据选择`full_runtime|hybrid_runtime|agent_only`；`--help`、导入或文件存在不算执行。未执行门禁使用`references/online-agent-execution-contract.md`内联检查，不得伪称脚本已运行。

### 豆包办公任务快速路径

无附件、自然语言的`direct|brief`请求默认`online_direct_fast_path`：仅读取最少Reference，直接形成公开研究/初会级回答，不创建facts/report/finalize工件，不尝试修复脚本Schema。只有用户提供BP、财务包、条款或明确要求结构化工件时才进入完整脚本工作流。

快速路径只压缩产物和篇幅，不减少规则1的核验：身份、规则状态、期间口径类查询即使问题很短也必须实际执行；无法核验时按规则2标 `[待核·模型记忆]` 并降级该段结论。

本节不重复顶部硬模板的禁令；数字归位、来源标记、分档表和假设卡一律按顶部五条执行。

## Search 决策与证据门禁

用户不需要声明是否联网。先冻结对象、期间、辖区、材料充分性和交付物，再运行 `scripts/search_router.py`，生成内部 `search-decision.json`。

- `off`：不Search；`blocked`：澄清或降级；`required/optional`：按预算和来源顺序执行。
- 当前事实、公开规则或候选发现是必要输入且材料不足时，必须主动Search。
- 封闭材料、纯计算或方法模板任务不Search；缺口只能由用户提供时不得用Search替代。
- 线上仅使用两个搜索工具：`seed_finance_search`（专业金融数据）与 `general_search`（通用网页搜索）。
- required最多4次、optional最多2次，均为硬上限；至少保留一次失败Claim修复预算。
- `seed_finance_search` 仅用于公开融资、机构研报、行业、上市可比和公开财务线索；公司、投资方、交易对手、监管、临床、产品和客户事实继续走 `general_search` 并回到可承担主张的一手原文核验。
- 不得用 `seed_finance_search` 替代 BP、data room、cap table、Term Sheet、mandate 或交易条款；缺私有数据时只局部降级，不得整体拒答。
- 按宿主 schema 传参；工具名仅限 `seed_finance_search` 与 `general_search`，不发明参数或其他工具名；`seed_finance_search` 不可用时回退仅用 `general_search`。每次结果记录 tool、query、asof、source、period、unit、currency、reported-vs-estimate；库内结果不自动等于一手来源。
- 上市可比或公开标准金融字段满足provider、对象/代码、期间/as_of、field、单位/币种、reported/estimate且无冲突时，可标`supported + authoritative_financial_database`；私营目标公司的融资估值、收入、客户、合同和交易条件不能仅靠Seed升级。
- 分离`transport_status`与`evidence_status`；使用`supported|provisional|conflict|empty|unsupported|blocked`。只有supported可推动对应capability gate。
- Search只生成紧凑证据台账，不把完整搜索结果直接注入分析。
- 分析前运行 `scripts/search_evidence_validator.py`；失败Claim继续定向补证或降为unknown。
- 最终外部数字和公司事实必须在Claim ledger；单位经济、估值和回报派生值需calculation/assumption记录。宿主原始轨迹优先，模型摘要不得冒充raw。
- 关键数字不得由二手来源承担：二手值仍可写出，但必须按规则2标 `[待核·…]`，且不得进入摘要段和结论段。详见 `references/seed-finance-search-routing.md`、`references/search-routing.md` 与 `references/search-evidence-contract.md`。

## 工作目录与中间产物

任务写入 `work/<task-id>/`：`intake.json`、`facts.json`、`capabilities.json`、`report.md`、`report-display.md`、`finalize-manifest.json`。

## 分层 capability gate

- `can_form_research_view`：对象已冻结，公开信息或通用机制足以支持方向性分析；不要求交易条款。
- `can_recommend_management_meeting`：对象真实、无已确认 mandate Hard Pass，且存在依赖管理层回答的高信息价值 kill questions；不要求会前取得审计财报、合同、cohort 或 Term Sheet。
- `can_recommend_data_room_access`：初会后，积极公开证据已形成可交叉验证链条，且存在能改变判断的定向数据请求时，可建议条件进入数据室。该 gate 只授予信息获取，不代表立项或投资推进。
- `can_recommend_investment_progression`：mandate、额度、工具、权益、估值口径、关键商业数据和退出框架达到相应阶段要求。

某个 gate 为 false 只阻断其对应槽位。无条款时，交易质量与回报保持 unknown，但商业、技术、估值方法和初会信息价值仍继续。动作词固定为：`公开研究`、`初会`、`进入数据室`、`条款评估`、`IC`；本 Skill 不批准 IC。详见 `references/capability-gates.md`。

## 七阶段工作流

1. 路由和输入冻结；先运行 `scripts/intake_preflight.py`，失败则补齐输入后停止。
2. 按模式读取必要 Reference。
3. 建立 Facts 与来源台账。
4. 计算 capability gates。
5. 执行领域计算与竞争性解释。
6. 按输出预算写作。
7. Validate → Lint → Finalize；失败不得交付。

## 输入契约

基础输入：

- 项目或公司名称与业务描述
- 评估目标
- as-of 与辖区

mandate、投资阶段和交易条款按结论槽位补齐；它们缺失不得阻断公开研究。对象或主体无法冻结时，只暂停依赖该对象的结论。

机器结构：`schemas/intake.schema.json`、`config/runtime.json`。

## 文件导航

- 成功契约：`references/success-contract.md`
- 模式加载：`config/loading-profile.json`
- 来源：`references/source-policy.md`
- Seed Finance Search：`references/seed-finance-search-routing.md`
- 线上 Agent：`references/online-agent-execution-contract.md`
- Search路由：`references/search-routing.md`
- Search证据：`references/search-evidence-contract.md`
- Facts：`references/facts-schema.md`
- 专业方法：`references/playbook-index.md`
- 能力门禁：`references/capability-gates.md`
- 复杂度：`references/complexity-routing.md`
- 输出：`references/output-structure.md`
- 质量：`references/quality-gates.md`

## 确定性工具

`intake_preflight.py`、`search_router.py`、`search_evidence_validator.py`、`validate_deliverable.py`、`validate_facts.py`、`compact_tool_output.py`、`private_market_engine.py`、`case_calculator.py`、`lint_report.py`、`lint_direct_response.py`、`privacy_scrub.py`、`finalize_report.py`。

脚本在本任务实际执行失败时修输入，不手算替代；未调用时按hybrid/agent_only内联校验。

## 确定性分析

仅在具备订单、BOM、成本或现金预算等结构化输入时运行单位经济工具；公开预筛与SaaS缺数据任务不得套硬件Fixture。 工具结果优先于模型自由计算；详见 `references/deterministic-tool-contract.md`。

## Ark 上下文预算

完整工具 JSON 写入工作目录，不直接注入模型。先运行 `scripts/compact_tool_output.py`，仅注入核心结果、异常、unknown 和 Hard Gate。结构化输入由工具读取；模型只读取必要叙事材料。输出预算 3,500 tokens（软目标）。

## 公共硬约束

- 事实、管理层陈述、推断、假设和缺口分开。
- 关键数字带期间、单位、币种及可承担该主张的公开核验来源。
- capability=false 时不输出对应强结论。
- 不保证收益、不执行交易、不利用内幕信息。
- 不泄漏内部 fact 标记、路径和计划。
- 缺数据时不用默认阈值、概率、期限和区间；确需给量级时按规则3改写为分档表，或按规则4放入假设卡并标注来源等级。

## 领域硬规则

- 项目材料未提供时，不得用搜索到的同名或同类项目代替用户项目。
- mandate 缺失只阻断 mandate fit；交易输入缺失只阻断交易推进、交易质量或回报槽位，不得扩张为整体拒答。
- 信息收集型初会按预期信息价值和 kill questions 判断，不以会前取得审计财报、合同、cohort 或 Term Sheet 为条件。
- 公开商业化证据按监管注册、可购产品、政府采购、渠道、客户/医院、用户和支付方交叉验证；媒体融资与公司自述只能作为线索，不能升级付款或收入确认。
- 信息收集型初会的升级/降级答案只描述需要验证的事实方向；没有基金政策、历史分布、同行基准或用户要求时，不得自行生成收入占比、回款天数、良率、毛利率、估值溢价或时间表阈值。
- 技术/产品判断前先做 taxonomy：冻结传感模态、刺激或解码、医疗或消费、硬件或软件、目标产品及法人业务边界；相邻产品不得证明目标技术商业化。
- 初会问题逐题标记信息增量、重要性、升级条件和降级条件；五类信息增量不得重复或遗漏。
- 数据室是初会后的条件式信息获取层，不等于投资推进、条款评估或 IC。
- 估值先冻结对象与权益边界，再冻结指标口径；缺输入时给变量关系式，不给默认倍数、概率、期限或机械计数阈值。
- required总预算4次包含Seed与General的成功、空结果、错误和回退；不得把Seed空结果视为预算外，再额外发起第5次调用。
- SaaS、消费、机器人等指标阈值必须按阶段和业务模式校准，不得写成通用红线。
- 回购、对赌和管理层承诺不得表述为保底收益；无交易条款时 `can_compute_returns=false`。
- 技术路线按性能演示、独立验证、可制造/可部署、系统集成、客户采用、付费续约、单位经济、规模化资本需求逐层判断，不得跨级推断。
- 产业价值必须与目标公司可通过合同、IP、数据和议价权捕获的价值分开。


## 输出契约

第一节固定为规则5的可审计摘要（≤5行），其后才是默认章节；摘要段只引用带 `[一手·…]` 或 `[库·…]` 标记的数字。

默认先输出研究、初会、数据室信息获取、投资推进和回报能力状态，再按需展开项目、mandate、商业/技术、估值方法、交易与回报、kill questions、下一动作。初会问题最多 5 个，覆盖五类不同信息增量；每个问题必须说明升级与降级条件。

证据不足时按 `references/degraded-artifacts.md` 压缩；不得为填满模板制造内容。

## 质量门禁

管理层陈述与外部证据分开。；所有关键数字注明来源、期间和口径。；建议必须附升级/降级条件。；完整 Screening 至少列出三项可能推翻投资逻辑的红旗，直接回答则优先最多五个 kill questions。；不得把初筛包装成完整尽调或正式IC批准。；不得因局部缺口整体拒答。

直接回复运行 `lint_direct_response.py`；研究工件运行 `finalize_report.py`。

## 渐进式上下文


| 模式 | 只加载这些 References | 输出预算 |
|---|---|---:|
| 快速初筛 | `references/mandate-structure.md`、`references/red-flags.md` | 1200 tokens（软目标） |
| 完整 Screening | `references/mandate-screen.md`、`references/unit-economics.md` | 3200 tokens（软目标） |
| 聚焦核查 | `references/unit-economics.md`、`references/forecast-bridge-protocol.md` | 1800 tokens（软目标） |
不得预加载整个 References 目录。原始工具结果落盘，只向模型注入摘要和证据索引。

## 评测

短 Evals 测路由；复杂 Case 和 Rubric 位于仓库 `evaluation/`，不加载给被测模型。

## 免责声明

仅用于研究与决策辅助，不构成证券买卖、收益保证或持牌投资、法律、税务、保险、会计及审计意见。
