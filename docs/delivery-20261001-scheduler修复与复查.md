# 交付说明 — 2026-10-01 晚：Scheduler 泄漏修复 + 数小时运行复查

对应 `CHANGELOG.md` 同日章节。git 提交 `3a655d2`。

## 问题 2 的答案：Scheduler 是谁

不是群友——是 **AstrBot 核心 Cron 调度器的合成事件昵称**（`core/cron/events.py:24`
`sender_name: str = "Scheduler"`）。所有主动/定时消息（早报、晚安、主动聊天）
在框架内部都以这个假名流转。

泄漏链路：Cron 合成事件 → companion「私聊身份锚点」把它写成
「TA 的显示名是 Scheduler」→ 模型开始叫「Scheduler博士」（9-30 22:00 首现）
→ 文本进会话历史自我强化 → 经桥接发进真实群。

**修复**：`private_identity_policy.py` 与 `user_memory.py` 两处把
`"Scheduler"` 从显示名链路隔离（第三方插件最小补丁，有备份）；
sim 会话主动消息已关闭（一天误收 9 条）。重启后 sim 实测回复正常、无 Scheduler。

## 问题 1 的答案：这几个小时的运行状况

✅ 正常：表情包生产首秀（11:53 群发「嘻嘻+假期心情喵」，群友秒互动）；
引用无错引（降级路径全部正确）；「小猫」唤醒后被动回复恢复；
进程健康（AstrBot 616MB/桥接 58MB），faulthandler 零记录。

⚠️ 已修：Scheduler 泄漏（本次）。
👀 观察：供应商 429/503 间歇（fallback 消化，无回复丢失）；
sim 会话触发的 `[UIA✗] 切换会话失败` ×10（安全红线正确拦截，
sim 主动消息关闭后消失）。

## 验证

- py_compile 两文件 OK；重启后 AstrBot :11229/:6185 pid=16180、桥接 :8766 pid=8840
- sim 实测：回复正常且不含 Scheduler；companions.json 的 Scheduler 计数停止增长
- 全部改动有备份：`*.bak_scheduler_20261001` ×3
