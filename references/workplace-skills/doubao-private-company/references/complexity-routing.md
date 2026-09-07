# 交付复杂度路由

- `direct`：软目标 1400 中文字符；必需槽位：stage_gate、meeting_decision、key_reasons、questions
- `brief`：软目标 2800 中文字符；必需槽位：stage_and_mandate、commercialization、economics_unknowns、red_flags、questions、decision
- `full`：软目标 6000 中文字符；必需槽位：identity、mandate、commercialization、market、unit_economics、team、terms、red_flags、diligence、decision

字符数仅用于写作压缩，不是交付失败条件。只有 provider 的 incomplete、finish_reason=length/max_tokens 或结构截断触发安全上限失败。用户问题越短不代表可以省略直接结论；证据搜索复杂度不自动扩大最终输出。
