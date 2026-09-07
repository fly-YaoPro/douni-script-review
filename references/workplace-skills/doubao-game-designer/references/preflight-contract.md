# 设计契约与出稿预检

设计契约是内部工作台：把容易在长文中漂移的范围、数字、生命周期、容量和运行证据放进一份可计算的 JSON。它只服务当前任务，正式 GDD 仍从游戏设计本身开始。

## 1. 使用边界

以下任务建立最小设计契约：

- 用户限定允许改动面、冻结项、当前配置或阶段；
- 涉及公式、概率、资源、时间、升级次数或人日；
- 涉及持续状态、重复触发、并发、胜负、存档或恢复；
- 给出明确 MVP、人数、周期、预算或生产约束；
- 承接试玩数据、多轮修订或已有实现；
- 交付研发、QA、正式配置或 HTML Demo。

早期创意讨论与方向比较使用项目基线和设计判断即可。契约只记录当前任务真实触及、且会推翻结论的风险，不为通过校验填满字段。

## 2. 初始化

在临时目录执行：

```bash
python scripts/validate_design_contract.py --init design-contract.json
```

初始化结果是一份空结构，按任务风险推进：

1. **范围校验**：建立项目基线后，把完整用户原文写入 `task.source_text`；存在允许面或冻结项时只开启 `scope_constraints`，录入权限并运行 `--freeze-scope`。
2. **方案校验**：完成诊断与最小求解后，把决定性数值问题和正式方案中的实质改动写入契约，只开启真实需要的其余 flags。
3. **成稿校验**：启用范围锁时，把完整正文路径传给 `--draft`，再由独立反审重新抽取实质改动。

首次范围校验会在契约旁生成 `design-contract.scope-lock.json`。后续校验自动比较原文、允许面与冻结项；只有用户改变授权后才重开范围校验。空数组表示本任务不触及该责任面，不为通过校验创造系统、状态或数字。

`readiness_target` 只使用 `draft`、`review`、`implementation` 或 `prototype`。在初始化文件上编辑，不从记忆重写字段名，也不把解释文字写入公式。下面的字段形状是校验器接口；替换内容，保留键名和枚举值。

| flag | 打开条件 | 对应内容 |
|---|---|---|
| `scope_constraints` | 有“只能改、保留、冻结、沿用”或阶段限制 | `authority` |
| `numbers` | 有多步公式或数值结论 | `numeric_requirements`、`parameters`、`numerical_assertions` |
| `probability` | 有随机池、权重、保底或移除 | `ledgers.probability_pools` |
| `resources` | 有收入、消费、余额或可达次数 | `ledgers.resources` |
| `capacity` | 有人日、人数、预算或截止时间 | `ledgers.capacity` |
| `lifecycle` | 有持续、累积、重复、消费、并发或恢复 | `state_machines` 与边界/恢复测试 |
| `persistence` | 有存档、跨局状态或异常退出 | `state_machines.persistence` |
| `production` | 当前改动会进入真实生产环境 | `production_risks` |
| `handoff` | 交给研发或 QA | `rules`、`tests` |
| `html` | 交付 HTML Demo | `prototype` |

## 3. 最小字段形状

契约只记录会推翻当前设计的核心风险，不镜像正文。合并同一问题与责任面的改动；普通配置项和完整内容表留在规格中。以下片段按任务实际风险选用。

### 范围、假设与规则

```json
{
  "authority": {
    "allowed_changes": [
      {
        "id": "ALLOW-RULE",
        "category": "rule",
        "description": "调整现有升级生成规则",
        "source_quote": "调整现有升级生成规则",
        "fields": ["upgrade.pool_generation"]
      }
    ],
    "forbidden_changes": [
      {
        "id": "BAN-ASSET",
        "category": "asset",
        "description": "不新增美术资源",
        "source_quote": "不新增美术资源",
        "fields": ["asset.new_content"]
      }
    ],
    "proposed_changes": [
      {
        "id": "CHG-POOL",
        "category": "rule",
        "description": "在现有升级池内重排生成与满级移除规则",
        "problem": "选择长期集中在同一数值项",
        "scope_effect": "modify",
        "responsibilities": ["program", "config", "qa"],
        "tradeoff": "",
        "authority_ids": ["ALLOW-RULE"],
        "fields": ["upgrade.pool_generation"],
        "priority": "P0"
      }
    ]
  },
  "assumptions": [
    {
      "id": "ASM-SCOPE",
      "statement": "升级作用域沿用当前全队共享规则",
      "impact": "high",
      "status": "test_value",
      "validation": "由现有配置或主策确认"
    }
  ],
  "rules": [
    {
      "id": "RULE-POOL",
      "title": "三选一生成",
      "definition": "每次从当前可用项无放回抽取三个选项，满级项先移出池。",
      "priority": "P0",
      "parameter_ids": ["PAR-OPTION-COUNT"],
      "state_machine_ids": ["SM-LEVELUP"],
      "authority_ids": ["ALLOW-RULE"],
      "fields": ["upgrade.pool_generation"]
    }
  ]
}
```

`scope_effect` 使用 `reuse`、`modify` 或 `add`；`priority` 使用 `P0`、`P1` 或 `non_goal`。`add` 必须填写被替代、删除或延期的 `tradeoff`。假设的 `impact` 使用 `high` 或 `low`，`status` 使用 `confirmed`、`test_value`、`open` 或 `blocked`。

### 参数与可执行断言

```json
{
  "numeric_requirements": [
    {
      "id": "NUMREQ-UPGRADE-COUNT",
      "statement": "一局经验能够支持多少次升级选择",
      "source": "design_goal",
      "assertion_ids": ["ASSERT-REMAIN"]
    }
  ],
  "parameters": [
    {
      "id": "PAR-EXP",
      "name": "run_experience",
      "value": 1500,
      "unit": "xp",
      "source": "user",
      "source_quote": "一局最多获得1500经验",
      "min": 0,
      "max": 2000
    },
    {
      "id": "PAR-SEVENTH",
      "name": "seventh_threshold",
      "value": 1270,
      "unit": "xp",
      "source": "user",
      "source_quote": "第7次升级阈值为1270经验",
      "min": 0,
      "max": 2000
    }
  ],
  "numerical_assertions": [
    {
      "id": "ASSERT-REMAIN",
      "scenario": "boundary",
      "expression": "experience - threshold",
      "inputs": {"experience": "PAR-EXP", "threshold": "PAR-SEVENTH"},
      "declared_value": 230,
      "unit": "xp",
      "tolerance": 0,
      "acceptance": {"operator": ">=", "value": 0}
    }
  ]
}
```

`numeric_requirements` 只记录会改变当前结论的数值问题，来源使用 `user`、`current_config`、`external` 或 `design_goal`；用户要求保留原句，配置与外部材料回指真实来源。每项引用至少一个带 `acceptance` 的决定性断言。

表达式只使用 ASCII 运算符、`floor`、`ceil`、`abs`、`min`、`max`、`clamp` 和 `inputs` 中定义的变量；`inputs` 的值只能是一个参数 ID。复合输入先建立 `calculated` 参数，或拆成多个断言。`scenario` 使用 `normal`、`boundary` 或 `abuse`。`acceptance` 可使用 `==`、`!=`、`<`、`<=`、`>`、`>=` 或 `between`，通过条件来自当前设计目标，不在脚本中预置题材结论。

### 状态、事件顺序与恢复

```json
{
  "state_machines": [
    {
      "id": "SM-LEVELUP",
      "initial_state": "BATTLE",
      "states": [
        {"id": "BATTLE", "entry": "波次开始", "exit": "升级或终局事件入队"},
        {"id": "CHOICE", "entry": "生成选项并暂停", "exit": "选择完成或终局抢占"}
      ],
      "event_order": ["damage", "death", "reward", "level_up", "outcome"],
      "transitions": [
        {
          "id": "TRIGGER-LEVELUP",
          "from": "BATTLE",
          "event": "经验跨过阈值",
          "to": "CHOICE",
          "effect": "生成一次升级选择",
          "repeat_policy": "同一经验事件 ID 只结算一次",
          "cleanup": "记录已处理事件 ID"
        },
        {
          "id": "RESOLVE-CHOICE",
          "from": "CHOICE",
          "event": "玩家完成选择或终局抢占",
          "to": "BATTLE",
          "effect": "应用一次选择；终局时取消未展示选择",
          "repeat_policy": "已消费选择不能再次提交",
          "cleanup": "关闭浮层并清空候选"
        }
      ]
    }
  ]
}
```

生命周期 flag 打开时，测试同时包含 `boundary` 与 `recovery`。

### 概率、资源与容量

```json
{
  "ledgers": {
    "probability_pools": [
      {
        "id": "POOL-CATEGORY",
        "expected_total": 100,
        "tolerance": 0,
        "entries": [
          {"id": "ATTACK", "value": 50},
          {"id": "UTILITY", "value": 50}
        ]
      }
    ],
    "resources": [
      {
        "id": "RES-REFRESH",
        "starting": 2,
        "allow_negative": false,
        "transactions": [{"id": "USE-ONCE", "order": 1, "amount": -1}],
        "expected_final": 1
      }
    ],
    "capacity": [
      {
        "id": "CAP-PROGRAM",
        "available": 6,
        "unit": "person_day",
        "tasks": [
          {"id": "FEATURE", "description": "规则与配置实现", "amount": 3.5, "priority": "P0", "kind": "feature"},
          {"id": "INTEGRATION", "description": "接线与数据验证", "amount": 1, "priority": "P0", "kind": "integration"},
          {"id": "QA", "description": "回归与修复", "amount": 1.5, "priority": "P0", "kind": "qa"}
        ]
      }
    ]
  }
}
```

容量 `kind` 使用 `feature`、`integration`、`qa`、`data`、`content`、`art` 或 `other`。

### 测试、生产风险与结论

```json
{
  "tests": [
    {
      "id": "TEST-RACE",
      "type": "recovery",
      "rule_ids": ["RULE-POOL"],
      "precondition": "Boss 死亡与经验升级同帧入队",
      "action": "按事件优先级处理同一帧",
      "expected": "只出现终局界面，升级事件被消费且无残留浮层",
      "status": "planned"
    }
  ],
  "production_risks": [
    {
      "id": "RISK-INTEGRATION",
      "surface": "integration_qa",
      "trigger": "升级与终局共用浮层调度",
      "impact": "重复界面或输入焦点残留",
      "detection": "运行同帧并发回归集",
      "mitigation": "统一事件队列与界面所有权",
      "fallback": "终局抢占并取消未展示升级",
      "owner": "program and qa"
    }
  ],
  "claims": [
    {
      "id": "CLAIM-UPGRADES",
      "text": "1500 经验只能到达第 7 个阈值。",
      "strength": "calculated",
      "evidence_ids": ["ASSERT-REMAIN"]
    }
  ]
}
```

测试 `type` 使用 `normal`、`boundary`、`abuse` 或 `recovery`，`status` 使用 `planned`、`passed` 或 `failed`。生产风险 `surface` 使用 `performance`、`state_data`、`network_concurrency`、`content_pipeline`、`ui_input` 或 `integration_qa`。结论 `strength` 使用 `fact`、`calculated`、`hypothesis` 或 `test_value`。

## 4. 权限与改动

`authority.allowed_changes` 与 `forbidden_changes` 分别记录用户授权调整和明确冻结的对象。每项复制用户原句为 `source_quote`，并只写一个从当前项目名词提取的小写点路径原子 `field`；用户一句话包含多个并列对象时拆成多项。宽口径原词保留为一个字段，不据此推导其他变量、对象类型、触发状态或基础设施。字段路径不使用通配符，权限锁会冻结两组精确字段；方案、规则或设计参数与冻结字段相交时直接阻塞。

每项 `proposed_changes` 填写：

- `problem`：它解决的可观察问题；
- `scope_effect`：`reuse`、`modify` 或 `add`；
- `authority_ids`：允许面依据；
- `fields`：本项实际触及的单一字段，必须来自对应授权；
- `responsibilities`：新增或变化的程序、美术、关卡、UI、数据、QA 责任；
- `tradeoff`：`add` 时被替代、删除或延期的内容；
- `priority`：`P0`、`P1` 或 `non_goal`。

类别使用能判断边界的具体词，如 `parameter`、`rule`、`content`、`feedback`、`ui`、`state`、`entity`、`asset`。当前方案的每项实质改动都进入这里。

范围受限任务中的 `rules`，以及 `source` 为 `design_initial` 的参数，同样填写 `authority_ids` 与 `fields`。这让“伤害”与“攻速”、“攻击范围”与“溅射半径”在工具层保持为不同改动。

## 5. 规则与生命周期

`rules` 保存当前权威定义，并引用参数和状态机。复杂规则的 `state_machines` 包含：

- `initial_state`；
- 状态的进入与退出；
- 显式 `transitions`：来源状态、事件、目标状态、效果、重复策略和清理；
- 多事件的 `event_order`；
- 需要存档时的写入时机、字段、恢复和异常退出。

状态转移覆盖以下问题：

`谁创建 → 何时生效 → 同事件能否再次结算 → 何时消费/退出 → 结束留下什么 → 打断与恢复`

校验器检查转移引用、从初始状态的可达性，以及边界和恢复测试。语义评审继续检查同一事件跨帧、递归触发、A-B-A 绕过、死亡和切场景。

## 6. 数字与账本

### 参数

每个参数具有唯一 ID、名称、当前值、单位、来源、上下限。来源使用：

- `user`
- `current_config`
- `external`
- `design_initial`
- `calculated`

用户正文直接给出的数字使用 `user`，并在 `source_quote` 逐字引用冻结原文。`current_config` 与 `external` 只用于已经实际读取的输入，并填写 `source_ref`：本地材料写 `file:/绝对路径`，链接材料写 `url:https://...`。没有来源的项目内数值使用 `design_initial`，计算结果使用 `calculated`；启用范围锁时，两者都映射到权限字段。同名参数只有一个当前定义。

### 可执行断言

`numeric_requirements` 先把这轮计算必须证明的内容写成可证伪命题，并引用对应断言。用户原文中的数值硬约束使用 `user` 与逐字 `source_quote`；当前配置或外部来源使用真实 `source_ref`；本轮策划需要验证的回报、收敛、节奏或容量关系使用 `design_goal`。

`numerical_assertions` 填写：

- `expression`：实际公式；
- `inputs`：表达式变量到参数 ID 的映射；
- `declared_value`、单位与容差；
- `scenario`：`normal`、`boundary` 或 `abuse`。
- `acceptance`：决定性断言填写当前项目的通过条件。

校验器重新计算表达式、检查通过条件，并阻止没有决定性断言的数值问题。数字任务至少有正常和边界断言；滥用场景只在递归、叠加、刷取或支配策略存在时加入。脚本证明计算与条件，独立语义评审继续判断公式是否选对、条件是否对应真实设计目标。

### 账本

- 概率池使用同一单位，并复算总和。
- 资源按发生顺序记录起始量、每笔收入/支出与期末量。
- 容量按同一单位逐项相加。任务 `kind` 使用 `feature`、`integration`、`qa`、`data`、`content`、`art` 或 `other`；P0 中为集成或 QA 留出正工作量。

复杂模拟仍由代码、表格或专业计算工具完成，再把权威输入与关键断言回填契约。

## 7. 生产风险

`production_risks` 只记录当前改动触及的责任面：

- `performance`
- `state_data`
- `network_concurrency`
- `content_pipeline`
- `ui_input`
- `integration_qa`

每项写触发条件、影响、发现方式、缓解、降级/回滚和负责人角色。风险描述需要能改变实现、范围或验收；通用项目风险留在项目管理材料。

## 8. 测试与原型

每条测试填写前置、动作、预期、规则 ID、类型和状态。`planned` 表示规格，`passed` 与 `failed` 只来自真实执行。

生命周期任务包含边界与恢复测试；研发交接覆盖每条 P0 规则。

HTML Demo 还填写：

- `ruleset_id` 与共享配置源；
- 加载、输入、主循环、结果和重开检查；
- 标准、失败/恢复和目标高风险玩家路径；
- 运行方式、视口、观察结果、截图或日志。

浏览器真实执行后才能标记 `passed`。

## 9. 运行与判定

```bash
python scripts/validate_design_contract.py --freeze-scope design-contract.json
python scripts/validate_design_contract.py design-contract.json
# 启用范围锁并完成本地正文后；支持 Markdown、XML 或纯文本
python scripts/validate_design_contract.py design-contract.json --draft <local-draft>
```

需要把警告也视为失败时：

```bash
python scripts/validate_design_contract.py --strict design-contract.json
```

- `BLOCK`：当前范围、计算、生命周期、容量、生产责任或运行路径存在阻塞。
- `WARN`：当前等级可继续评审，但需要处理或降级。
- `PASS`：机器能够判断的引用、总和、可达性和覆盖通过。

`--draft` 对正式稿追加主题中性的文本与容量检查，并重新校验契约中已经登记的权限和改动。正文里未登记的新对象、状态或责任由独立反审重新抽取并与范围锁对账；脚本不替代这层语义判断。

脚本通过后读取 [adversarial-review.md](adversarial-review.md)，从原始需求重新检查玩家问题、机制自然度、事实口径、生产可信度和多轮承接。机械结果与语义评审共同决定就绪等级。
