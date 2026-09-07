# 交付复杂度路由

- `direct`：软目标 1200 中文字符；必需槽位：direct_answer、formula_or_priority、immediate_actions、missing_inputs
- `brief`：软目标 2600 中文字符；必需槽位：baseline、priority、scenario、actions、professional_boundary
- `full`：软目标 6000 中文字符；必需槽位：household_snapshot、goals、cashflow、risk_capacity、scenarios、allocation_boundary、actions、assumptions

字符数仅用于写作压缩，不是交付失败条件。只有 provider 的 incomplete、finish_reason=length/max_tokens 或结构截断触发安全上限失败。用户问题越短不代表可以省略直接结论；证据搜索复杂度不自动扩大最终输出。
